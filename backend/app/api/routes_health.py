from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.models import Job
from app.schemas import HealthResponse
from app.services.heartbeat import count_online_workers
from app.services.metrics_store import runtime_metrics
from app.services.resource_manager import ResourceManager


router = APIRouter(tags=["health"])
resource_manager = ResourceManager()


def _queue_counts(db: Session) -> dict[str, int]:
    queued = int(db.scalar(select(func.count(Job.id)).where(Job.status == "queued")) or 0)
    processing = int(db.scalar(select(func.count(Job.id)).where(Job.status == "processing")) or 0)
    retry_wait = int(db.scalar(select(func.count(Job.id)).where(Job.status == "retry_wait")) or 0)
    dead_letter = int(db.scalar(select(func.count(Job.id)).where(Job.status == "dead_letter")) or 0)
    return {
        "queued": queued,
        "processing": processing,
        "retry_wait": retry_wait,
        "dead_letter": dead_letter,
    }


@router.get("/health/live")
def health_live() -> dict:
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    ok = True
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        ok = False
        checks["db"] = f"error: {exc}"

    return {
        "status": "ready" if ok else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    snap = resource_manager.snapshot()
    perf = runtime_metrics.snapshot(cost_currency=settings.estimated_cost_currency)

    details = {
        "environment": settings.environment,
        "queue": _queue_counts(db),
        "workers_online": count_online_workers(db),
        "resources": {
            "cpu_percent": snap.cpu_percent,
            "ram_percent": snap.ram_percent,
            "gpu_available": snap.gpu_available,
            "gpu_memory_used_percent": snap.gpu_memory_used_percent,
            "recommended_workers": snap.recommended_workers,
        },
        "performance": {
            "audio_minutes_processed_total": perf["audio_minutes_processed_total"],
            "audio_minutes_per_hour": perf["throughput_audio_minutes_per_hour"],
            "realtime_factor": perf["realtime_factor"],
            "estimated_cost_total": perf["estimated_cost_total"],
            "estimated_cost_currency": perf["estimated_cost_currency"],
        },
    }

    return HealthResponse(
        status="ok",
        app=settings.app_name,
        model=settings.primary_model_id,
        timestamp=datetime.now(timezone.utc),
        details=details,
    )
