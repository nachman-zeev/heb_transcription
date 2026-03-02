from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, JobChannel, User
from app.services.media import probe_audio


settings = get_settings()


def create_job_for_file(db: Session, user: User, file_path: Path, priority: int = 100) -> Job:
    probe = probe_audio(file_path)
    job = Job(
        tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        source_file_path=str(file_path.resolve()),
        source_filename=file_path.name,
        source_extension=probe.extension,
        source_duration_sec=probe.duration_sec,
        source_channel_count=probe.channel_count,
        status="queued",
        priority=priority,
        retry_count=0,
        max_retries=settings.job_default_max_retries,
    )
    db.add(job)
    db.flush()

    for channel_idx in range(probe.channel_count):
        db.add(
            JobChannel(
                job_id=job.id,
                channel_index=channel_idx,
                status="queued",
            )
        )

    db.commit()
    db.refresh(job)
    return job
