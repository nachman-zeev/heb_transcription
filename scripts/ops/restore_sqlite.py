from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def restore_sqlite(backup_path: Path, target_db_path: Path, force: bool) -> Path:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    target_db_path.parent.mkdir(parents=True, exist_ok=True)

    if target_db_path.exists() and not force:
        raise FileExistsError(
            f"Target exists: {target_db_path}. Use --force to overwrite."
        )

    if target_db_path.exists() and force:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pre_restore = target_db_path.with_suffix(f".pre_restore_{stamp}.db")
        shutil.copy2(target_db_path, pre_restore)

    shutil.copy2(backup_path, target_db_path)

    conn = sqlite3.connect(str(target_db_path))
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()

    return target_db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore SQLite database from backup (Stage 5)")
    parser.add_argument("--backup-path", type=str, required=True, help="Backup sqlite file path")
    parser.add_argument("--target-db-path", type=str, default="backend/data/app.db", help="Target sqlite db path")
    parser.add_argument("--force", action="store_true", help="Overwrite target if exists")
    args = parser.parse_args()

    restored = restore_sqlite(Path(args.backup_path), Path(args.target_db_path), bool(args.force))
    print(f"restored={restored}")


if __name__ == "__main__":
    main()
