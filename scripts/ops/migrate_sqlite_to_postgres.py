from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select, text


DEFAULT_TABLE_ORDER = [
    "tenants",
    "users",
    "api_tokens",
    "jobs",
    "job_channels",
    "transcript_words",
    "worker_heartbeats",
]


def _resolve_target_url(postgres_url: str, postgres_url_file: str) -> str:
    if postgres_url_file:
        p = Path(postgres_url_file)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"postgres_url_file not found: {p}")
        val = p.read_text(encoding="utf-8").strip()
        if not val:
            raise ValueError("postgres_url_file is empty")
        return val
    if not postgres_url.strip():
        raise ValueError("postgres_url is required")
    return postgres_url.strip()


def migrate(sqlite_url: str, target_url: str, truncate_target: bool) -> None:
    src_engine = create_engine(sqlite_url, future=True)
    dst_engine = create_engine(target_url, future=True)

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    present_tables = [name for name in DEFAULT_TABLE_ORDER if name in src_meta.tables]
    if not present_tables:
        raise RuntimeError("No known source tables found in sqlite database")

    schema_meta = MetaData()
    for name in present_tables:
        src_meta.tables[name].to_metadata(schema_meta)

    schema_meta.create_all(bind=dst_engine)

    dst_meta = MetaData()
    dst_meta.reflect(bind=dst_engine)

    with src_engine.connect() as src, dst_engine.begin() as dst:
        if truncate_target:
            if dst_engine.dialect.name == "postgresql":
                quoted = ", ".join(f'"{t}"' for t in reversed(present_tables))
                dst.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
            else:
                for t in reversed(present_tables):
                    if t in dst_meta.tables:
                        dst.execute(dst_meta.tables[t].delete())

        for table_name in present_tables:
            src_table = src_meta.tables[table_name]
            dst_table = dst_meta.tables.get(table_name)
            if dst_table is None:
                continue

            rows = [dict(r) for r in src.execute(select(src_table)).mappings().all()]
            if rows:
                dst.execute(dst_table.insert(), rows)
            print(f"table={table_name} rows={len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite DB content to PostgreSQL target")
    parser.add_argument("--sqlite-url", type=str, default="sqlite:///./backend/data/app.db")
    parser.add_argument("--postgres-url", type=str, default="")
    parser.add_argument("--postgres-url-file", type=str, default="")
    parser.add_argument("--truncate-target", action="store_true", help="Truncate target tables before import")
    args = parser.parse_args()

    target_url = _resolve_target_url(args.postgres_url, args.postgres_url_file)
    migrate(sqlite_url=args.sqlite_url, target_url=target_url, truncate_target=bool(args.truncate_target))
    print("migration=done")


if __name__ == "__main__":
    main()
