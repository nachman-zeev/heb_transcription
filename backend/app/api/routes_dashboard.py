from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Job, Tenant, User
from app.schemas import ActivityPoint, ActivityResponse, UsageResponse


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _to_day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _to_day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


@router.get("/usage", response_model=UsageResponse)
def usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UsageResponse:
    tenant = db.get(Tenant, user.tenant_id)
    quota = float((tenant.package_minutes_quota if tenant else 0.0) or 0.0)

    used_sec = db.scalar(
        select(func.coalesce(func.sum(Job.source_duration_sec), 0.0)).where(
            Job.tenant_id == user.tenant_id,
            Job.status == "completed",
        )
    )
    used_minutes = round(float(used_sec or 0.0) / 60.0, 3)
    remaining = max(0.0, quota - used_minutes)
    utilization = round((used_minutes / quota) * 100.0, 2) if quota > 0 else 0.0

    completed_jobs = int(
        db.scalar(select(func.count(Job.id)).where(Job.tenant_id == user.tenant_id, Job.status == "completed"))
        or 0
    )

    return UsageResponse(
        tenant_id=user.tenant_id,
        quota_minutes=round(quota, 3),
        used_minutes=used_minutes,
        remaining_minutes=round(remaining, 3),
        utilization_percent=utilization,
        completed_jobs=completed_jobs,
    )


@router.get("/activity", response_model=ActivityResponse)
def activity(
    period: str = Query(default="week", pattern="^(week|month)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ActivityResponse:
    days = 7 if period == "week" else 30
    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=days - 1)

    rows = db.execute(
        select(
            func.date(Job.queued_at).label("d"),
            func.count(Job.id).label("jobs_total"),
            func.sum(case((Job.status == "completed", 1), else_=0)).label("jobs_completed"),
            func.coalesce(func.sum(Job.source_duration_sec), 0.0).label("sec_total"),
        )
        .where(
            Job.tenant_id == user.tenant_id,
            Job.queued_at >= _to_day_start(start_day),
            Job.queued_at <= _to_day_end(today),
        )
        .group_by(func.date(Job.queued_at))
        .order_by(func.date(Job.queued_at).asc())
    ).all()

    by_day = {
        date.fromisoformat(str(r.d)): {
            "jobs_total": int(r.jobs_total or 0),
            "jobs_completed": int(r.jobs_completed or 0),
            "minutes_total": round(float(r.sec_total or 0.0) / 60.0, 3),
        }
        for r in rows
    }

    points: list[ActivityPoint] = []
    for i in range(days):
        d = start_day + timedelta(days=i)
        stats = by_day.get(d, {"jobs_total": 0, "jobs_completed": 0, "minutes_total": 0.0})
        points.append(
            ActivityPoint(
                day=d,
                jobs_total=stats["jobs_total"],
                jobs_completed=stats["jobs_completed"],
                minutes_total=stats["minutes_total"],
            )
        )

    return ActivityResponse(period=period, points=points)
