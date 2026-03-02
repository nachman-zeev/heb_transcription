from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job


RUNNING_STATUS = "processing"
QUEUED_CANDIDATE_STATUSES = ("queued", "retry_wait")


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind and bind.dialect and bind.dialect.name == "postgresql")


def release_stale_locks(db: Session, lock_timeout_seconds: int = 900) -> int:
    threshold = datetime.now(timezone.utc).timestamp() - lock_timeout_seconds
    threshold_dt = datetime.fromtimestamp(threshold, tz=timezone.utc)

    result = db.execute(
        update(Job)
        .where(
            Job.locked_by_worker.is_not(None),
            Job.locked_at.is_not(None),
            Job.locked_at < threshold_dt,
        )
        .values(
            locked_by_worker=None,
            locked_at=None,
            status=case((Job.status == "processing", "retry_wait"), else_=Job.status),
        )
    )

    changed = int(result.rowcount or 0)
    if changed:
        db.commit()
    return changed


def _pick_fair_candidate(db: Session) -> Job | None:
    now = datetime.now(timezone.utc)

    running_counts = dict(
        db.execute(
            select(Job.tenant_id, func.count(Job.id))
            .where(Job.status == RUNNING_STATUS)
            .group_by(Job.tenant_id)
        ).all()
    )

    queued_jobs = list(
        db.scalars(
            select(Job)
            .where(
                Job.status.in_(QUEUED_CANDIDATE_STATUSES),
                Job.locked_by_worker.is_(None),
            )
            .where(
                (Job.next_attempt_at.is_(None)) | (Job.next_attempt_at <= now)
            )
            .order_by(Job.priority.asc(), Job.queued_at.asc())
        )
    )
    if not queued_jobs:
        return None

    def score(job: Job) -> tuple[int, datetime]:
        return (int(running_counts.get(job.tenant_id, 0)), job.queued_at)

    queued_jobs.sort(key=score)
    return queued_jobs[0]


def _acquire_next_job_postgres(db: Session, worker_id: str) -> Job | None:
    now = datetime.now(timezone.utc)

    candidate = db.execute(
        text(
            """
            WITH running AS (
                SELECT tenant_id, COUNT(id) AS running_count
                FROM jobs
                WHERE status = :running_status
                GROUP BY tenant_id
            ),
            candidate AS (
                SELECT j.id
                FROM jobs j
                LEFT JOIN running r ON r.tenant_id = j.tenant_id
                WHERE j.locked_by_worker IS NULL
                  AND j.status IN (:queued_status, :retry_status)
                  AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= :now_ts)
                ORDER BY COALESCE(r.running_count, 0) ASC, j.priority ASC, j.queued_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE jobs j
            SET locked_by_worker = :worker_id,
                locked_at = :now_ts,
                last_heartbeat_at = :now_ts,
                status = 'processing',
                started_at = COALESCE(j.started_at, :now_ts)
            FROM candidate c
            WHERE j.id = c.id
              AND j.locked_by_worker IS NULL
            RETURNING j.id
            """
        ),
        {
            "running_status": RUNNING_STATUS,
            "queued_status": "queued",
            "retry_status": "retry_wait",
            "now_ts": now,
            "worker_id": worker_id,
        },
    ).first()

    if not candidate:
        db.rollback()
        return None

    db.commit()
    return db.get(Job, candidate[0])


def acquire_next_job(db: Session, worker_id: str) -> Job | None:
    settings = get_settings()

    if _is_postgres(db) and settings.enable_postgres_skip_locked:
        return _acquire_next_job_postgres(db, worker_id)

    candidate = _pick_fair_candidate(db)
    if not candidate:
        return None

    now = datetime.now(timezone.utc)

    result = db.execute(
        update(Job)
        .where(
            Job.id == candidate.id,
            Job.locked_by_worker.is_(None),
            Job.status.in_(QUEUED_CANDIDATE_STATUSES),
        )
        .values(
            locked_by_worker=worker_id,
            locked_at=now,
            last_heartbeat_at=now,
            status="processing",
            started_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return None

    db.commit()
    return db.get(Job, candidate.id)


def touch_job_heartbeat(db: Session, job_id: str, worker_id: str) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(Job)
        .where(Job.id == job_id, Job.locked_by_worker == worker_id)
        .values(last_heartbeat_at=now, locked_at=now)
    )
    db.commit()
