from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass

from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import db_session, init_db
from app.models import Job
from app.services.logging_utils import log_event
from app.services.resource_manager import ResourceManager


@dataclass
class ManagedWorker:
    worker_id: str
    proc: subprocess.Popen


def _queue_depth() -> int:
    with db_session() as db:
        queued = int(
            db.scalar(select(func.count(Job.id)).where(Job.status.in_(("queued", "retry_wait")))) or 0
        )
    return queued


def _spawn_worker(worker_id: str, node_id: str) -> ManagedWorker:
    cmd = [sys.executable, "worker.py", "--worker-id", worker_id, "--node-id", node_id]
    proc = subprocess.Popen(cmd)
    log_event("manager_spawn_worker", node_id=node_id, worker_id=worker_id, pid=proc.pid)
    return ManagedWorker(worker_id=worker_id, proc=proc)


def _stop_worker(w: ManagedWorker, node_id: str, graceful_timeout: float = 10.0) -> None:
    if w.proc.poll() is not None:
        return

    log_event("manager_stop_worker", node_id=node_id, worker_id=w.worker_id, pid=w.proc.pid)
    w.proc.terminate()
    deadline = time.time() + graceful_timeout
    while time.time() < deadline:
        if w.proc.poll() is not None:
            return
        time.sleep(0.2)

    w.proc.kill()


def _cleanup_dead_workers(workers: list[ManagedWorker], node_id: str) -> list[ManagedWorker]:
    alive: list[ManagedWorker] = []
    for w in workers:
        code = w.proc.poll()
        if code is None:
            alive.append(w)
            continue
        log_event("manager_worker_exit", node_id=node_id, worker_id=w.worker_id, pid=w.proc.pid, return_code=code)
    return alive


def _compute_desired_workers(queue_depth: int, recommended_workers: int, settings) -> int:
    target_queue = max(1, int(settings.autoscale_target_queue_per_worker))
    desired_by_queue = int(math.ceil(queue_depth / float(target_queue))) if queue_depth > 0 else 0

    hard_cap = max(1, int(settings.autoscale_max_workers_per_node))
    cap = max(1, min(int(recommended_workers), hard_cap))

    return max(0, min(desired_by_queue, cap))


def run_manager(min_workers: int = 0, max_ticks: int = 0, node_id: str | None = None) -> None:
    settings = get_settings()
    init_db()

    node_id = (node_id or settings.node_id or "node-local").strip()
    resource_manager = ResourceManager()
    workers: list[ManagedWorker] = []
    tick = 0

    last_scale_up_at = 0.0
    last_scale_down_at = 0.0

    log_event("manager_started", node_id=node_id, min_workers=min_workers)
    try:
        while True:
            tick += 1
            workers = _cleanup_dead_workers(workers, node_id=node_id)

            snap = resource_manager.snapshot()
            queue_depth = _queue_depth()

            desired = _compute_desired_workers(queue_depth, snap.recommended_workers, settings)
            desired = max(min_workers, desired)

            now_ts = time.time()
            current = len(workers)

            if desired > current and now_ts - last_scale_up_at < max(0, int(settings.autoscale_scale_up_cooldown_seconds)):
                desired = current
            if desired < current and now_ts - last_scale_down_at < max(0, int(settings.autoscale_scale_down_cooldown_seconds)):
                desired = current

            while len(workers) < desired:
                wid = f"{node_id}-wm-{os.getpid()}-{len(workers)+1}-{int(time.time())}"
                workers.append(_spawn_worker(wid, node_id=node_id))
                last_scale_up_at = time.time()

            while len(workers) > desired:
                w = workers.pop()
                _stop_worker(w, node_id=node_id)
                last_scale_down_at = time.time()

            if tick % 3 == 0:
                target_queue = max(1, int(settings.autoscale_target_queue_per_worker))
                queue_per_worker = (queue_depth / max(1, len(workers))) if workers else float(queue_depth)
                log_event(
                    "manager_tick",
                    node_id=node_id,
                    queue_depth=queue_depth,
                    workers_running=len(workers),
                    workers_desired=desired,
                    target_queue_per_worker=target_queue,
                    queue_per_worker=round(queue_per_worker, 3),
                    cpu_percent=round(snap.cpu_percent, 2),
                    ram_percent=round(snap.ram_percent, 2),
                    gpu_available=snap.gpu_available,
                    gpu_memory_used_percent=round(snap.gpu_memory_used_percent, 2),
                )

            if max_ticks > 0 and tick >= max_ticks:
                log_event("manager_max_ticks_reached", node_id=node_id, max_ticks=max_ticks)
                break

            time.sleep(settings.worker_poll_seconds)

    except KeyboardInterrupt:
        log_event("manager_stopping", node_id=node_id, reason="keyboard_interrupt")
    finally:
        for w in workers:
            _stop_worker(w, node_id=node_id)
        log_event("manager_stopped", node_id=node_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamic worker manager (Stage 9)")
    parser.add_argument("--min-workers", type=int, default=0, help="Keep at least this many workers alive")
    parser.add_argument("--max-ticks", type=int, default=0, help="Stop manager after N ticks (0 = infinite)")
    parser.add_argument("--node-id", type=str, default="", help="Node id for multi-node worker fleets")
    args = parser.parse_args()

    run_manager(min_workers=max(0, args.min_workers), max_ticks=max(0, args.max_ticks), node_id=args.node_id or None)


if __name__ == "__main__":
    main()
