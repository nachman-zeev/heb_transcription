from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def backup_sqlite(db_path: Path, out_dir: Path) -> tuple[Path, Path]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = out_dir / f"app_{stamp}.sqlite"

    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_db": str(db_path.resolve()),
        "backup_file": str(backup_path.resolve()),
        "size_bytes": backup_path.stat().st_size,
        "sha256": _sha256_file(backup_path),
    }
    meta_path = backup_path.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return backup_path, meta_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup SQLite database (Stage 5)")
    parser.add_argument("--db-path", type=str, default="backend/data/app.db", help="Path to source sqlite db")
    parser.add_argument("--out-dir", type=str, default="data/backups", help="Output backup directory")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    out_dir = Path(args.out_dir)

    backup_file, meta_file = backup_sqlite(db_path, out_dir)
    print(f"backup_file={backup_file}")
    print(f"metadata_file={meta_file}")


if __name__ == "__main__":
    main()
