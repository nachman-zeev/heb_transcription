from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text


REQUIRED_ENV = [
    "APP_ENV",
    "PRIMARY_MODEL_ID",
]


def _check_env() -> list[str]:
    issues: list[str] = []
    for key in REQUIRED_ENV:
        if not os.getenv(key):
            issues.append(f"missing_env:{key}")

    if not os.getenv("DB_URL") and not os.getenv("DB_URL_FILE"):
        issues.append("missing_env:DB_URL_or_DB_URL_FILE")

    return issues


def _check_secret_files() -> list[str]:
    issues: list[str] = []
    for key in ("DB_URL_FILE", "TOKEN_HASH_PEPPER_FILE"):
        value = os.getenv(key, "").strip()
        if not value:
            continue
        p = Path(value)
        if not p.exists() or not p.is_file():
            issues.append(f"secret_file_missing:{key}:{p}")
            continue
        if not p.read_text(encoding="utf-8").strip():
            issues.append(f"secret_file_empty:{key}:{p}")
    return issues


def _check_binaries() -> list[str]:
    issues: list[str] = []
    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            issues.append(f"missing_binary:{binary}")
    return issues


def _resolve_db_url() -> str:
    file_var = os.getenv("DB_URL_FILE", "").strip()
    if file_var:
        p = Path(file_var)
        if p.exists() and p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            if v:
                return v
    return os.getenv("DB_URL", "sqlite:///./backend/data/app.db")


def _check_db(db_url: str) -> list[str]:
    issues: list[str] = []
    prefix = "sqlite:///"

    if db_url.startswith(prefix):
        db_path = Path(db_url[len(prefix) :])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT 1")
            conn.close()
        except Exception as exc:  # noqa: BLE001
            issues.append(f"db_unavailable:{exc}")
        return issues

    if db_url.startswith("postgresql"):
        try:
            engine = create_engine(db_url, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"db_unavailable:{exc}")
        return issues

    issues.append("db_url_unsupported_scheme")
    return issues


def _check_paths(recordings_path: Path) -> list[str]:
    issues: list[str] = []
    if not recordings_path.exists():
        issues.append(f"missing_path:{recordings_path}")
    elif not recordings_path.is_dir():
        issues.append(f"not_a_directory:{recordings_path}")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 8 preflight checks")
    parser.add_argument("--recordings-path", type=str, default="Recordings Examples")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings")
    args = parser.parse_args()

    issues: list[str] = []
    issues.extend(_check_env())
    issues.extend(_check_secret_files())
    issues.extend(_check_binaries())

    db_url = _resolve_db_url()
    issues.extend(_check_db(db_url))
    issues.extend(_check_paths(Path(args.recordings_path)))

    if not issues:
        print("preflight=ok")
        return

    print("preflight=issues")
    for item in issues:
        print(item)

    if args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
