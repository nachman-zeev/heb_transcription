from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    package_minutes_quota: Mapped[float] = mapped_column(Float, default=10000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    users: Mapped[list[User]] = relationship("User", back_populates="tenant")
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_salt: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")
    tokens: Mapped[list[ApiToken]] = relationship("ApiToken", back_populates="user")

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship("User", back_populates="tokens")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    source_file_path: Mapped[str] = mapped_column(Text)
    source_filename: Mapped[str] = mapped_column(String(512), index=True)
    source_extension: Mapped[str] = mapped_column(String(16))
    source_duration_sec: Mapped[float] = mapped_column(Float)
    source_channel_count: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    locked_by_worker: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="jobs")
    channels: Mapped[list[JobChannel]] = relationship("JobChannel", back_populates="job", cascade="all, delete-orphan")


class JobChannel(Base):
    __tablename__ = "job_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    channel_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    diarization_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    alignment_status: Mapped[str] = mapped_column(String(32), default="unknown")
    diarization_status: Mapped[str] = mapped_column(String(32), default="unknown")

    job: Mapped[Job] = relationship("Job", back_populates="channels")
    words: Mapped[list[TranscriptWord]] = relationship(
        "TranscriptWord",
        back_populates="channel",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("job_id", "channel_index", name="uq_job_channel_idx"),)


class TranscriptWord(Base):
    __tablename__ = "transcript_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_channel_id: Mapped[int] = mapped_column(ForeignKey("job_channels.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(256))
    normalized_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    speaker_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    speaker_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)

    channel: Mapped[JobChannel] = relationship("JobChannel", back_populates="words")

    __table_args__ = (UniqueConstraint("job_channel_id", "seq", name="uq_channel_word_seq"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pid: Mapped[int] = mapped_column(Integer)
    host: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="idle")
    active_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    ram_percent: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
