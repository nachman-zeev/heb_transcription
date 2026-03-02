from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from backup_sqlite import backup_sqlite
from restore_sqlite import restore_sqlite


def _cleanup_retention(backup_dir: Path, keep_last: int) -> int:
    files = sorted(backup_dir.glob("app_*.sqlite"))
    if keep_last < 1:
        keep_last = 1
    to_remove = files[:-keep_last]
    removed = 0
    for f in to_remove:
        meta = f.with_suffix(".json")
        try:
            f.unlink(missing_ok=True)
            removed += 1
        except Exception:
            pass
        try:
            meta.unlink(missing_ok=True)
        except Exception:
            pass
    return removed


def _integrity_check(db_path: Path) -> tuple[bool, str]:
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        if not row:
            return False, "empty_integrity_result"
        msg = str(row[0])
        return msg.lower() == "ok", msg
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _restore_drill(backup_file: Path, drill_dir: Path) -> tuple[bool, str]:
    drill_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    drill_db = drill_dir / f"restore_drill_{stamp}.db"

    restore_sqlite(backup_file, drill_db, force=True)
    ok, msg = _integrity_check(drill_db)
    try:
        drill_db.unlink(missing_ok=True)
    except Exception:
        pass
    return ok, msg


def _log(event: str, **kwargs) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **kwargs,
    }
    print(payload)


def run_scheduler(
    db_path: Path,
    backup_dir: Path,
    interval_seconds: int,
    keep_last: int,
    restore_drill_every: int,
    restore_drill_dir: Path,
    max_runs: int,
) -> None:
    cycle = 0
    _log("scheduler_started", db_path=str(db_path), backup_dir=str(backup_dir), interval_seconds=interval_seconds)

    while True:
        cycle += 1
        backup_file, meta_file = backup_sqlite(db_path=db_path, out_dir=backup_dir)
        removed = _cleanup_retention(backup_dir=backup_dir, keep_last=keep_last)
        _log(
            "backup_completed",
            cycle=cycle,
            backup_file=str(backup_file),
            metadata_file=str(meta_file),
            removed_old_backups=removed,
        )

        if restore_drill_every > 0 and cycle % restore_drill_every == 0:
            ok, msg = _restore_drill(backup_file=backup_file, drill_dir=restore_drill_dir)
            _log("restore_drill_completed", cycle=cycle, ok=ok, result=msg)
            if not ok:
                raise RuntimeError(f"restore_drill_failed:{msg}")

        if max_runs > 0 and cycle >= max_runs:
            _log("scheduler_max_runs_reached", max_runs=max_runs)
            break

        time.sleep(max(1, interval_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheduled backup + restore drill runner (Stage 7)")
    parser.add_argument("--db-path", type=str, default="backend/data/app.db")
    parser.add_argument("--backup-dir", type=str, default="data/backups")
    parser.add_argument("--interval-minutes", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=0, help="Override interval in seconds (for testing)")
    parser.add_argument("--keep-last", type=int, default=48)
    parser.add_argument("--restore-drill-every", type=int, default=24, help="Run restore drill every N backups (0 disables)")
    parser.add_argument("--restore-drill-dir", type=str, default="data/restore_drills")
    parser.add_argument("--max-runs", type=int, default=0, help="0 means infinite")
    args = parser.parse_args()

    interval_seconds = args.interval_seconds if args.interval_seconds > 0 else max(1, args.interval_minutes) * 60

    run_scheduler(
        db_path=Path(args.db_path),
        backup_dir=Path(args.backup_dir),
        interval_seconds=max(1, interval_seconds),
        keep_last=max(1, args.keep_last),
        restore_drill_every=max(0, args.restore_drill_every),
        restore_drill_dir=Path(args.restore_drill_dir),
        max_runs=max(0, args.max_runs),
    )


if __name__ == "__main__":
    main()
