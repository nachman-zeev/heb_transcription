from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone

import psutil
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import WorkerHeartbeat


def _online_threshold_seconds() -> int:
    settings = get_settings()
    return max(5, int(settings.worker_online_grace_seconds))


def _online_threshold_time() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=_online_threshold_seconds())


def count_online_workers(db: Session) -> int:
    threshold = _online_threshold_time()
    return int(
        db.scalar(
            select(func.count(WorkerHeartbeat.worker_id)).where(WorkerHeartbeat.updated_at >= threshold)
        )
        or 0
    )


def list_online_workers(db: Session) -> list[WorkerHeartbeat]:
    threshold = _online_threshold_time()
    return list(
        db.scalars(
            select(WorkerHeartbeat)
            .where(WorkerHeartbeat.updated_at >= threshold)
            .order_by(WorkerHeartbeat.updated_at.desc())
        )
    )


def upsert_worker_heartbeat(
    db: Session,
    worker_id: str,
    status: str,
    active_job_id: str | None = None,
) -> None:
    cpu = float(psutil.cpu_percent(interval=0.0))
    ram = float(psutil.virtual_memory().percent)

    hb = db.scalar(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id))
    if hb is None:
        hb = WorkerHeartbeat(
            worker_id=worker_id,
            pid=os.getpid(),
            host=socket.gethostname(),
        )

    hb.pid = os.getpid()
    hb.host = socket.gethostname()
    hb.status = status
    hb.active_job_id = active_job_id
    hb.cpu_percent = cpu
    hb.ram_percent = ram
    hb.updated_at = datetime.now(timezone.utc)

    db.add(hb)
    db.commit()
