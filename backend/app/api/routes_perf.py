from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.models import Job
from app.services.heartbeat import count_online_workers
from app.services.metrics_store import runtime_metrics


router = APIRouter(prefix="/perf", tags=["perf"])


@router.get("/summary")
def perf_summary(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()

    queued = int(db.scalar(select(func.count(Job.id)).where(Job.status == "queued")) or 0)
    processing = int(db.scalar(select(func.count(Job.id)).where(Job.status == "processing")) or 0)
    retry_wait = int(db.scalar(select(func.count(Job.id)).where(Job.status == "retry_wait")) or 0)

    metrics = runtime_metrics.snapshot(cost_currency=settings.estimated_cost_currency)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": settings.primary_model_id,
        "queue": {
            "queued": queued,
            "processing": processing,
            "retry_wait": retry_wait,
        },
        "workers_online": count_online_workers(db),
        "throughput": {
            "jobs_completed_total": metrics["jobs_completed_total"],
            "audio_minutes_processed_total": metrics["audio_minutes_processed_total"],
            "audio_minutes_per_hour": metrics["throughput_audio_minutes_per_hour"],
            "realtime_factor": metrics["realtime_factor"],
        },
        "cost": {
            "estimated_cost_total": metrics["estimated_cost_total"],
            "estimated_cost_per_audio_minute": settings.estimated_cost_per_audio_minute,
            "currency": settings.estimated_cost_currency,
        },
    }
