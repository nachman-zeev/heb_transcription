from __future__ import annotations

import mimetypes
import re
from datetime import date, datetime, time, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_current_user_from_token_query
from app.core.config import get_settings
from app.database import get_db
from app.models import Job, JobChannel, User
from app.schemas import (
    IngestFolderRequest,
    IngestFolderResponse,
    JobChannelResponse,
    JobChannelWord,
    JobCreateRequest,
    JobListResponse,
    JobResponse,
)
from app.services.exports import render_docx, render_srt, render_txt
from app.services.job_service import create_job_for_file
from app.services.media import discover_audio_files
from app.services.timestamp_repair import repair_job_timestamps_if_needed


router = APIRouter(prefix="/jobs", tags=["jobs"])
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _to_day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _to_day_end(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=timezone.utc)


def _channel_to_schema(channel: JobChannel) -> JobChannelResponse:
    words = [
        JobChannelWord(
            seq=w.seq,
            text=w.text,
            normalized_text=w.normalized_text,
            speaker_label=w.speaker_label,
            speaker_confidence=w.speaker_confidence,
            start_sec=w.start_sec,
            end_sec=w.end_sec,
        )
        for w in sorted(channel.words, key=lambda x: x.seq)
    ]
    return JobChannelResponse(
        id=channel.id,
        channel_index=channel.channel_index,
        status=channel.status,
        transcript_text=channel.transcript_text,
        transcript_normalized_text=channel.transcript_normalized_text,
        alignment_status=channel.alignment_status,
        diarization_status=channel.diarization_status,
        words=words,
    )


def _job_to_schema(job: Job, include_channels: bool = True) -> JobResponse:
    channels: list[JobChannelResponse] = []
    if include_channels:
        channels = [_channel_to_schema(c) for c in sorted(job.channels, key=lambda x: x.channel_index)]

    word_count = sum(len(c.words) for c in job.channels)
    transcription_duration_sec = None
    if job.started_at and job.completed_at:
        transcription_duration_sec = max(0.0, (job.completed_at - job.started_at).total_seconds())

    return JobResponse(
        id=job.id,
        status=job.status,
        source_file_path=job.source_file_path,
        source_filename=job.source_filename,
        source_extension=job.source_extension,
        source_duration_sec=job.source_duration_sec,
        source_channel_count=job.source_channel_count,
        transcription_duration_sec=transcription_duration_sec,
        word_count=word_count,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        next_attempt_at=job.next_attempt_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        channels=channels,
    )


def _get_job_for_tenant(db: Session, job_id: str, tenant_id: int) -> Job:
    job = db.scalar(
        select(Job)
        .where(Job.id == job_id, Job.tenant_id == tenant_id)
        .options(selectinload(Job.channels).selectinload(JobChannel.words))
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _safe_upload_filename(name: str) -> str:
    base = Path(name or "upload.wav").name
    if not base:
        base = "upload.wav"
    return SAFE_FILENAME_RE.sub("_", base)


@router.post("", response_model=JobResponse)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobResponse:
    path = Path(payload.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=400, detail="File not found")

    if path.suffix.lower() not in {".wav", ".mp3"}:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    job = create_job_for_file(db, user, path, priority=payload.priority)
    job = _get_job_for_tenant(db, job.id, user.tenant_id)
    return _job_to_schema(job)


@router.post("/upload", response_model=JobResponse)
def create_job_upload(
    file: UploadFile = File(...),
    priority: int = Form(default=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobResponse:
    filename = _safe_upload_filename(file.filename or "upload.wav")
    suffix = Path(filename).suffix.lower()
    allowed = {e.lower() for e in get_settings().allowed_extensions}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    uploads_root = Path(get_settings().uploads_dir).resolve()
    tenant_dir = uploads_root / f"tenant_{user.tenant_id}"
    tenant_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_path = tenant_dir / f"{stamp}_{filename}"

    with out_path.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    file.file.close()

    job = create_job_for_file(db, user, out_path, priority=priority)
    job = _get_job_for_tenant(db, job.id, user.tenant_id)
    return _job_to_schema(job)


@router.post("/ingest-folder", response_model=IngestFolderResponse)
def ingest_folder(
    payload: IngestFolderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IngestFolderResponse:
    folder = Path(payload.folder_path)
    extensions = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in payload.extensions}

    files = discover_audio_files(folder, recursive=payload.recursive, extensions=extensions)
    job_ids: list[str] = []

    for path in files:
        job = create_job_for_file(db, user, path)
        job_ids.append(job.id)

    return IngestFolderResponse(
        folder_path=str(folder),
        files_discovered=len(files),
        jobs_created=len(job_ids),
        job_ids=job_ids,
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobListResponse:
    query = (
        select(Job)
        .where(Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.channels).selectinload(JobChannel.words))
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(Job.status == status)
    if date_from:
        query = query.where(Job.queued_at >= _to_day_start(date_from))
    if date_to:
        query = query.where(Job.queued_at <= _to_day_end(date_to))

    items = list(db.scalars(query))
    return JobListResponse(items=[_job_to_schema(j) for j in items])


@router.get("/{job_id}/audio")
def get_job_audio(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_tenant(db, job_id, user.tenant_id)
    audio_path = Path(job.source_file_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    media_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    return FileResponse(path=audio_path, media_type=media_type, filename=audio_path.name)


@router.get("/{job_id}/audio-public")
def get_job_audio_public(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_from_token_query),
):
    job = _get_job_for_tenant(db, job_id, user.tenant_id)
    audio_path = Path(job.source_file_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    media_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    return FileResponse(path=audio_path, media_type=media_type, filename=audio_path.name)


@router.get("/{job_id}/export")
def export_job(
    job_id: str,
    format: str = Query(..., pattern="^(txt|srt|docx)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_tenant(db, job_id, user.tenant_id)

    if format == "txt":
        payload = render_txt(job)
        media_type = "text/plain; charset=utf-8"
        filename = f"{Path(job.source_filename).stem}.txt"
    elif format == "srt":
        payload = render_srt(job)
        media_type = "application/x-subrip"
        filename = f"{Path(job.source_filename).stem}.srt"
    else:
        payload = render_docx(job)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{Path(job.source_filename).stem}.docx"

    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=payload, media_type=media_type, headers=headers)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobResponse:
    job = _get_job_for_tenant(db, job_id, user.tenant_id)
    if repair_job_timestamps_if_needed(db, job):
        db.flush()
        job = _get_job_for_tenant(db, job_id, user.tenant_id)
    return _job_to_schema(job)
