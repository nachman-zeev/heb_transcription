from __future__ import annotations

import argparse
import json
import os
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.database import db_session, init_db
from app.models import Job, JobChannel, TranscriptWord
from app.services.alignment import align_words_robust
from app.services.diarization import diarize_words
from app.services.heartbeat import upsert_worker_heartbeat
from app.services.hebrew_text import normalize_hebrew_text
from app.services.logging_utils import log_event
from app.services.metrics_store import runtime_metrics
from app.services.queueing import acquire_next_job, release_stale_locks, touch_job_heartbeat
from app.services.transcription_engine import IvritWhisperEngine


def _reset_job_channels_for_retry(db, job_id: str) -> None:
    channels = list(db.scalars(select(JobChannel).where(JobChannel.job_id == job_id)))
    channel_ids = [c.id for c in channels]

    for ch in channels:
        ch.status = "queued"
        ch.started_at = None
        ch.completed_at = None
        ch.error_message = None
        ch.transcript_text = None
        ch.transcript_normalized_text = None
        ch.transcript_json = None
        ch.diarization_json = None
        ch.alignment_status = "unknown"
        ch.diarization_status = "unknown"
        db.add(ch)

    if channel_ids:
        db.execute(delete(TranscriptWord).where(TranscriptWord.job_channel_id.in_(channel_ids)))


def _mark_job_success(db, job: Job) -> None:
    job.status = "completed"
    job.error_message = None
    job.completed_at = datetime.now(timezone.utc)
    job.locked_by_worker = None
    job.locked_at = None
    job.last_heartbeat_at = datetime.now(timezone.utc)
    db.add(job)


def _mark_job_failure_with_retry(db, job: Job, error_message: str, settings) -> str:
    now = datetime.now(timezone.utc)
    next_retry_count = int(job.retry_count or 0) + 1

    if next_retry_count <= int(job.max_retries or settings.job_default_max_retries):
        backoff_sec = int(settings.job_retry_backoff_seconds) * (2 ** max(0, next_retry_count - 1))
        job.status = "retry_wait"
        job.retry_count = next_retry_count
        job.next_attempt_at = now + timedelta(seconds=backoff_sec)
        job.error_message = error_message
        job.locked_by_worker = None
        job.locked_at = None
        job.last_heartbeat_at = now
        db.add(job)
        runtime_metrics.retries_scheduled += 1
        return "retry_wait"

    job.status = "dead_letter"
    job.retry_count = next_retry_count
    job.error_message = error_message
    job.completed_at = now
    job.next_attempt_at = None
    job.locked_by_worker = None
    job.locked_at = None
    job.last_heartbeat_at = now
    db.add(job)
    runtime_metrics.jobs_dead_letter += 1
    return "dead_letter"


def process_job(engine: IvritWhisperEngine, job_id: str, worker_id: str) -> None:
    with db_session() as db:
        job = db.get(Job, job_id)
        if not job:
            raise RuntimeError(f"Job not found: {job_id}")
        input_path = Path(job.source_file_path)
        if not input_path.exists():
            raise RuntimeError(f"Input file missing: {input_path}")

        _reset_job_channels_for_retry(db, job.id)
        job.status = "processing"
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        job.last_heartbeat_at = datetime.now(timezone.utc)
        db.add(job)

    with db_session() as db:
        channels = list(
            db.scalars(
                select(JobChannel)
                .where(JobChannel.job_id == job_id)
                .order_by(JobChannel.channel_index.asc())
            )
        )
        source_channel_count = 1
        job = db.get(Job, job_id)
        if job:
            source_channel_count = int(job.source_channel_count or 1)

    for channel in channels:
        with db_session() as db:
            touch_job_heartbeat(db, job_id, worker_id)
            upsert_worker_heartbeat(db, worker_id=worker_id, status="processing", active_job_id=job_id)
            db_channel = db.get(JobChannel, channel.id)
            db_channel.status = "processing"
            db_channel.started_at = datetime.now(timezone.utc)
            db.add(db_channel)

        try:
            output = engine.transcribe_channel(Path(job.source_file_path), channel.channel_index)
        except Exception as exc:
            with db_session() as db:
                db_channel = db.get(JobChannel, channel.id)
                if db_channel:
                    db_channel.status = "failed"
                    db_channel.error_message = str(exc)
                    db_channel.completed_at = datetime.now(timezone.utc)
                    db.add(db_channel)
            raise

        duration = output.audio_duration_sec if output.audio_duration_sec > 0 else float(job.source_duration_sec)
        aligned_words, alignment_status = align_words_robust(output.text, output.words, duration_sec=duration)
        diarized = diarize_words(
            aligned_words,
            total_channels=source_channel_count,
            channel_index=int(channel.channel_index),
        )
        normalized_text = normalize_hebrew_text(output.text)

        with db_session() as db:
            touch_job_heartbeat(db, job_id, worker_id)
            db_channel = db.get(JobChannel, channel.id)
            db_channel.status = "completed"
            db_channel.transcript_text = output.text
            db_channel.transcript_normalized_text = normalized_text
            db_channel.transcript_json = json.dumps(output.payload, ensure_ascii=False)
            db_channel.diarization_json = json.dumps(diarized.payload, ensure_ascii=False)
            db_channel.alignment_status = alignment_status
            db_channel.diarization_status = diarized.status
            db_channel.completed_at = datetime.now(timezone.utc)
            db.add(db_channel)

            db.execute(delete(TranscriptWord).where(TranscriptWord.job_channel_id == db_channel.id))
            for word in diarized.words:
                db.add(
                    TranscriptWord(
                        job_channel_id=db_channel.id,
                        seq=int(word.get("seq", 0)),
                        text=str(word.get("text", "")).strip(),
                        normalized_text=str(word.get("normalized_text", "")).strip() or None,
                        speaker_label=str(word.get("speaker_label", "")).strip() or None,
                        speaker_confidence=float(word.get("speaker_confidence", 0.0)) if word.get("speaker_confidence") is not None else None,
                        start_sec=float(word.get("start_sec", 0.0)),
                        end_sec=float(word.get("end_sec", 0.0)),
                    )
                )

    with db_session() as db:
        job = db.get(Job, job_id)
        failed_channels = db.scalar(
            select(JobChannel.id)
            .where(JobChannel.job_id == job_id, JobChannel.status == "failed")
            .limit(1)
        )
        if failed_channels:
            raise RuntimeError("At least one channel failed")

        _mark_job_success(db, job)


def run_worker(once: bool, max_jobs: int, worker_id: str | None = None, node_id: str | None = None) -> None:
    settings = get_settings()
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = settings.hf_disable_symlinks_warning

    init_db()
    engine = IvritWhisperEngine(settings.primary_model_id)

    node_id = (node_id or settings.node_id or socket.gethostname() or "node").strip()
    if not worker_id:
        worker_id = f"{node_id}-{socket.gethostname()}-{os.getpid()}"

    log_event("worker_started", worker_id=worker_id, node_id=node_id, model=settings.primary_model_id)
    processed = 0
    last_heartbeat = 0.0

    while True:
        now_ts = time.time()
        if now_ts - last_heartbeat >= settings.worker_heartbeat_seconds:
            with db_session() as db:
                upsert_worker_heartbeat(db, worker_id=worker_id, status="idle", active_job_id=None)
            last_heartbeat = now_ts

        with db_session() as db:
            release_stale_locks(db)
            next_job = acquire_next_job(db, worker_id=worker_id)

        if not next_job:
            if once:
                log_event("worker_no_jobs", worker_id=worker_id, node_id=node_id)
                break
            time.sleep(settings.worker_idle_sleep_seconds)
            continue

        started_perf = time.perf_counter()
        log_event("job_processing_started", worker_id=worker_id, node_id=node_id, job_id=next_job.id, source=next_job.source_filename)
        try:
            with db_session() as db:
                upsert_worker_heartbeat(db, worker_id=worker_id, status="processing", active_job_id=next_job.id)

            process_job(engine, next_job.id, worker_id)

            processing_seconds = max(0.0, time.perf_counter() - started_perf)
            runtime_metrics.record_job_success(
                audio_seconds=float(next_job.source_duration_sec or 0.0),
                processing_seconds=processing_seconds,
                cost_per_audio_minute=float(settings.estimated_cost_per_audio_minute),
            )
            log_event(
                "job_completed",
                worker_id=worker_id,
                node_id=node_id,
                job_id=next_job.id,
                audio_seconds=float(next_job.source_duration_sec or 0.0),
                processing_seconds=round(processing_seconds, 3),
            )

        except Exception as exc:
            runtime_metrics.jobs_failed += 1
            error_message = str(exc)
            with db_session() as db:
                job = db.get(Job, next_job.id)
                final_status = _mark_job_failure_with_retry(db, job, error_message, settings)
                upsert_worker_heartbeat(db, worker_id=worker_id, status="idle", active_job_id=None)

            log_event(
                "job_failed",
                worker_id=worker_id,
                node_id=node_id,
                job_id=next_job.id,
                final_status=final_status,
                error=error_message,
            )

        processed += 1
        if once:
            break
        if max_jobs > 0 and processed >= max_jobs:
            log_event("worker_reached_max_jobs", worker_id=worker_id, node_id=node_id, max_jobs=max_jobs)
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage-9 transcription worker")
    parser.add_argument("--once", action="store_true", help="Process one queued job and exit")
    parser.add_argument("--max-jobs", type=int, default=0, help="Stop after N jobs (0 = unlimited)")
    parser.add_argument("--worker-id", type=str, default="", help="Explicit worker id")
    parser.add_argument("--node-id", type=str, default="", help="Node id for multi-node worker fleets")
    args = parser.parse_args()

    run_worker(once=args.once, max_jobs=args.max_jobs, worker_id=args.worker_id or None, node_id=args.node_id or None)


if __name__ == "__main__":
    main()
