from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil


ACTIVE_STATUSES = ("queued", "processing", "retry_wait")


def read_pid_file(path: Path) -> int | None:
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="ascii").strip()
        if not raw:
            return None
        return int(raw)
    except Exception:
        return None


def is_pid_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except Exception:
        return False


def remove_file_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def kill_pid_tree(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass


def kill_python_by_pattern(pattern: str) -> None:
    pat = (pattern or "").strip()
    if not pat:
        return

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = str(proc.info.get("name") or "").lower()
            if "python" not in name:
                continue
            cmd = " ".join(proc.info.get("cmdline") or [])
            if pat in cmd:
                kill_pid_tree(int(proc.pid))
        except Exception:
            continue


def has_active_jobs(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(
            "select count(*) from jobs where status in ('queued','processing','retry_wait')"
        )
        count = int(cur.fetchone()[0] or 0)
        con.close()
        return count > 0
    except Exception:
        # If DB is temporarily locked/unavailable, avoid false auto-shutdown.
        return True


def terminate_services(
    api_pid_file: Path,
    worker_pid_file: Path,
    api_pattern: str,
    worker_pattern: str,
) -> None:
    for pid_file in (api_pid_file, worker_pid_file):
        pid = read_pid_file(pid_file)
        if pid is not None:
            kill_pid_tree(pid)
        remove_file_quiet(pid_file)

    kill_python_by_pattern(api_pattern)
    kill_python_by_pattern(worker_pattern)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-shutdown local services when idle")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--api-pid-file", required=True)
    parser.add_argument("--worker-pid-file", required=True)
    parser.add_argument("--watchdog-pid-file", required=True)
    parser.add_argument("--idle-minutes", type=float, default=10.0)
    parser.add_argument("--check-seconds", type=float, default=15.0)
    parser.add_argument("--api-pattern", default="uvicorn app.main:app --host 127.0.0.1 --port 8090")
    parser.add_argument("--worker-pattern", default="worker.py --node-id local-cpu-node")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    api_pid_file = Path(args.api_pid_file).resolve()
    worker_pid_file = Path(args.worker_pid_file).resolve()
    watchdog_pid_file = Path(args.watchdog_pid_file).resolve()

    idle_seconds = max(60.0, float(args.idle_minutes) * 60.0)
    check_seconds = max(2.0, float(args.check_seconds))
    last_active_ts = time.monotonic()

    while True:
        api_running = is_pid_running(read_pid_file(api_pid_file))
        worker_running = is_pid_running(read_pid_file(worker_pid_file))

        if not api_running and not worker_running:
            remove_file_quiet(watchdog_pid_file)
            return 0

        if has_active_jobs(db_path):
            last_active_ts = time.monotonic()
        else:
            if (time.monotonic() - last_active_ts) >= idle_seconds:
                terminate_services(
                    api_pid_file=api_pid_file,
                    worker_pid_file=worker_pid_file,
                    api_pattern=args.api_pattern,
                    worker_pattern=args.worker_pattern,
                )
                remove_file_quiet(watchdog_pid_file)
                return 0

        time.sleep(check_seconds)


if __name__ == "__main__":
    sys.exit(main())
