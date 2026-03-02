from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class BootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=128)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    tenant_name: str
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    tenant_id: int
    user_id: int


class MeResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    user_id: int
    email: str


class IngestFolderRequest(BaseModel):
    folder_path: str
    recursive: bool = True
    extensions: list[str] = Field(default_factory=lambda: [".wav", ".mp3"])


class JobCreateRequest(BaseModel):
    file_path: str
    priority: int = 100


class JobChannelWord(BaseModel):
    seq: int
    text: str
    normalized_text: str | None = None
    speaker_label: str | None = None
    speaker_confidence: float | None = None
    start_sec: float
    end_sec: float


class JobChannelResponse(BaseModel):
    id: int
    channel_index: int
    status: str
    transcript_text: str | None
    transcript_normalized_text: str | None = None
    alignment_status: str | None = None
    diarization_status: str | None = None
    words: list[JobChannelWord] = Field(default_factory=list)


class JobResponse(BaseModel):
    id: str
    status: str
    source_file_path: str
    source_filename: str
    source_extension: str
    source_duration_sec: float
    source_channel_count: int
    transcription_duration_sec: float | None = None
    word_count: int = 0
    retry_count: int = 0
    max_retries: int = 0
    next_attempt_at: datetime | None = None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    channels: list[JobChannelResponse] = Field(default_factory=list)


class JobListResponse(BaseModel):
    items: list[JobResponse]


class IngestFolderResponse(BaseModel):
    folder_path: str
    files_discovered: int
    jobs_created: int
    job_ids: list[str]


class GenericMessage(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    app: str
    model: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class UsageResponse(BaseModel):
    tenant_id: int
    quota_minutes: float
    used_minutes: float
    remaining_minutes: float
    utilization_percent: float
    completed_jobs: int


class ActivityPoint(BaseModel):
    day: date
    jobs_total: int
    jobs_completed: int
    minutes_total: float


class ActivityResponse(BaseModel):
    period: str
    points: list[ActivityPoint]
