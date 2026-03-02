from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine_kwargs = {"future": True, "pool_pre_ping": True}
if settings.db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = max(1, int(settings.database_pool_size))
    engine_kwargs["max_overflow"] = max(0, int(settings.database_max_overflow))
    engine_kwargs["pool_recycle"] = 1800

engine = create_engine(settings.db_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def _sqlite_has_column(conn, table_name: str, column_name: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(r[1] == column_name for r in rows)


def _apply_sqlite_migrations() -> None:
    if not settings.db_url.startswith("sqlite"):
        return

    migration_columns = {
        "tenants": [
            ("package_minutes_quota", "FLOAT DEFAULT 10000.0"),
        ],
        "jobs": [
            ("retry_count", "INTEGER DEFAULT 0"),
            ("max_retries", "INTEGER DEFAULT 2"),
            ("next_attempt_at", "DATETIME"),
            ("locked_by_worker", "VARCHAR(64)"),
            ("locked_at", "DATETIME"),
            ("last_heartbeat_at", "DATETIME"),
        ],
        "job_channels": [
            ("transcript_normalized_text", "TEXT"),
            ("diarization_json", "TEXT"),
            ("alignment_status", "VARCHAR(32) DEFAULT 'unknown'"),
            ("diarization_status", "VARCHAR(32) DEFAULT 'unknown'"),
        ],
        "transcript_words": [
            ("normalized_text", "VARCHAR(256)"),
            ("speaker_label", "VARCHAR(64)"),
            ("speaker_confidence", "FLOAT DEFAULT 0.0"),
        ],
    }

    with engine.begin() as conn:
        for table_name, columns in migration_columns.items():
            table_exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
                {"name": table_name},
            ).first()
            if not table_exists:
                continue

            for column_name, column_def in columns:
                if _sqlite_has_column(conn, table_name, column_name):
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_sqlite_migrations()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
