from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Job, User
from app.services.heartbeat import list_online_workers


router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/stats")
def queue_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    tenant_id = user.tenant_id
    queued = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "queued")) or 0
    processing = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "processing")) or 0
    retry_wait = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "retry_wait")) or 0
    completed = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "completed")) or 0
    failed = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "failed")) or 0
    dead_letter = db.scalar(select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status == "dead_letter")) or 0

    return {
        "tenant_id": tenant_id,
        "queued": int(queued),
        "processing": int(processing),
        "retry_wait": int(retry_wait),
        "completed": int(completed),
        "failed": int(failed),
        "dead_letter": int(dead_letter),
    }


@router.get("/workers")
def workers(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = list_online_workers(db)
    return {
        "items": [
            {
                "worker_id": r.worker_id,
                "pid": r.pid,
                "host": r.host,
                "status": r.status,
                "active_job_id": r.active_job_id,
                "cpu_percent": r.cpu_percent,
                "ram_percent": r.ram_percent,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    }
