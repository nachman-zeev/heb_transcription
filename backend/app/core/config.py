from __future__ import annotations

import os
import socket
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


def _read_secret_file(path: str) -> str | None:
    p = Path(path)
    try:
        if not p.exists() or not p.is_file():
            return None
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


def _env_str_or_file(name: str, default: str) -> str:
    file_val = _env_str(f"{name}_FILE", "").strip()
    if file_val:
        loaded = _read_secret_file(file_val)
        if loaded:
            return loaded
    return _env_str(name, default)


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    parts = tuple(x.strip() for x in raw.split(",") if x.strip())
    return parts or default


class Settings(BaseModel):
    app_name: str = "Hebrew Transcription API"
    environment: str = "dev"
    db_url: str = "sqlite:///./data/app.db"

    database_pool_size: int = 10
    database_max_overflow: int = 20

    token_ttl_hours: int = 12
    token_hash_pepper: str = ""
    primary_model_id: str = "ivrit-ai/whisper-large-v3"
    hf_disable_symlinks_warning: str = "1"

    node_id: str = "node-local"

    worker_poll_seconds: float = 2.0
    worker_idle_sleep_seconds: float = 1.0
    worker_heartbeat_seconds: float = 5.0
    worker_online_grace_seconds: int = 15

    max_parallel_workers_cpu: int = 1
    max_parallel_workers_gpu: int = 2
    cpu_soft_limit_percent: float = 80.0
    ram_soft_limit_percent: float = 80.0

    autoscale_target_queue_per_worker: int = 2
    autoscale_scale_up_cooldown_seconds: int = 10
    autoscale_scale_down_cooldown_seconds: int = 20
    autoscale_max_workers_per_node: int = 8

    asr_chunk_length_sec: float = 30.0
    asr_batch_size_cpu: int = 1
    asr_batch_size_gpu: int = 8
    asr_warmup_enabled: bool = False

    job_default_max_retries: int = 2
    job_retry_backoff_seconds: int = 30

    enable_postgres_skip_locked: bool = True

    estimated_cost_per_audio_minute: float = 0.0
    estimated_cost_currency: str = "USD"

    allowed_extensions: tuple[str, ...] = Field(default=(".wav", ".mp3"))
    uploads_dir: str = "./data/uploads"

    cors_allowed_origins: tuple[str, ...] = Field(default=("http://localhost:8080", "http://127.0.0.1:8080"))
    security_headers_enabled: bool = True
    enforce_https: bool = False

    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 180
    rate_limit_auth_max_requests: int = 20

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if self.db_url.startswith(prefix):
            return Path(self.db_url[len(prefix) :]).resolve()
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=_env_str("APP_NAME", "Hebrew Transcription API"),
        environment=_env_str("APP_ENV", "dev"),
        db_url=_env_str_or_file("DB_URL", "sqlite:///./data/app.db"),
        database_pool_size=_env_int("DB_POOL_SIZE", 10),
        database_max_overflow=_env_int("DB_MAX_OVERFLOW", 20),
        token_ttl_hours=_env_int("TOKEN_TTL_HOURS", 12),
        token_hash_pepper=_env_str_or_file("TOKEN_HASH_PEPPER", ""),
        primary_model_id=_env_str("PRIMARY_MODEL_ID", "ivrit-ai/whisper-large-v3"),
        hf_disable_symlinks_warning=_env_str("HF_HUB_DISABLE_SYMLINKS_WARNING", "1"),
        node_id=_env_str("NODE_ID", socket.gethostname() or "node-local"),
        worker_poll_seconds=_env_float("WORKER_POLL_SECONDS", 2.0),
        worker_idle_sleep_seconds=_env_float("WORKER_IDLE_SLEEP_SECONDS", 1.0),
        worker_heartbeat_seconds=_env_float("WORKER_HEARTBEAT_SECONDS", 5.0),
        worker_online_grace_seconds=_env_int("WORKER_ONLINE_GRACE_SECONDS", 15),
        max_parallel_workers_cpu=_env_int("MAX_PARALLEL_WORKERS_CPU", 1),
        max_parallel_workers_gpu=_env_int("MAX_PARALLEL_WORKERS_GPU", 2),
        cpu_soft_limit_percent=_env_float("CPU_SOFT_LIMIT_PERCENT", 80.0),
        ram_soft_limit_percent=_env_float("RAM_SOFT_LIMIT_PERCENT", 80.0),
        autoscale_target_queue_per_worker=_env_int("AUTOSCALE_TARGET_QUEUE_PER_WORKER", 2),
        autoscale_scale_up_cooldown_seconds=_env_int("AUTOSCALE_SCALE_UP_COOLDOWN_SECONDS", 10),
        autoscale_scale_down_cooldown_seconds=_env_int("AUTOSCALE_SCALE_DOWN_COOLDOWN_SECONDS", 20),
        autoscale_max_workers_per_node=_env_int("AUTOSCALE_MAX_WORKERS_PER_NODE", 8),
        asr_chunk_length_sec=_env_float("ASR_CHUNK_LENGTH_SEC", 30.0),
        asr_batch_size_cpu=_env_int("ASR_BATCH_SIZE_CPU", 1),
        asr_batch_size_gpu=_env_int("ASR_BATCH_SIZE_GPU", 8),
        asr_warmup_enabled=_env_bool("ASR_WARMUP_ENABLED", False),
        job_default_max_retries=_env_int("JOB_DEFAULT_MAX_RETRIES", 2),
        job_retry_backoff_seconds=_env_int("JOB_RETRY_BACKOFF_SECONDS", 30),
        enable_postgres_skip_locked=_env_bool("ENABLE_POSTGRES_SKIP_LOCKED", True),
        estimated_cost_per_audio_minute=_env_float("ESTIMATED_COST_PER_AUDIO_MINUTE", 0.0),
        estimated_cost_currency=_env_str("ESTIMATED_COST_CURRENCY", "USD"),
        allowed_extensions=_env_csv("ALLOWED_EXTENSIONS", (".wav", ".mp3")),
        uploads_dir=_env_str("UPLOADS_DIR", "./data/uploads"),
        cors_allowed_origins=_env_csv("CORS_ALLOWED_ORIGINS", ("http://localhost:8080", "http://127.0.0.1:8080")),
        security_headers_enabled=_env_bool("SECURITY_HEADERS_ENABLED", True),
        enforce_https=_env_bool("ENFORCE_HTTPS", False),
        rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", True),
        rate_limit_window_seconds=_env_int("RATE_LIMIT_WINDOW_SECONDS", 60),
        rate_limit_max_requests=_env_int("RATE_LIMIT_MAX_REQUESTS", 180),
        rate_limit_auth_max_requests=_env_int("RATE_LIMIT_AUTH_MAX_REQUESTS", 20),
    )
