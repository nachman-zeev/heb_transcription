# Production Runbook (Final)

## 1. Preflight

```powershell
$env:APP_ENV='prod'
$env:DB_URL='sqlite:///./backend/data/app.db'
$env:PRIMARY_MODEL_ID='ivrit-ai/whisper-large-v3'
python scripts/ops/preflight_check.py --recordings-path "Recordings Examples"
```

## 2. Start Services

Baseline:

```powershell
docker compose build
docker compose up -d
```

Enterprise (PostgreSQL + scaled workers):

```powershell
docker compose -f docker-compose.enterprise.yml up -d --build --scale worker=4
```

## 3. Health and Perf

- `/health/live`
- `/health/ready`
- `/health`
- `/metrics`
- `/perf/summary`

## 4. Database Migration

```powershell
python scripts/ops/migrate_sqlite_to_postgres.py --sqlite-url sqlite:///./backend/data/app.db --postgres-url postgresql+psycopg://user:pass@host:5432/transcription --truncate-target
```

## 5. Operations Automation

```powershell
python scripts/ops/slo_snapshot.py --base-url http://127.0.0.1:8080 --json-out data/ops/slo_latest.json --md-out data/ops/slo_latest.md
python scripts/ops/alert_policy_check.py --base-url http://127.0.0.1:8080 --policy-file config/alert_policy.json --json-out data/ops/alert_latest.json
python scripts/ops/perf_cost_report.py --base-url http://127.0.0.1:8080 --monthly-budget 1000 --json-out data/ops/perf_cost_report.json --md-out data/ops/perf_cost_report.md
python scripts/ops/backup_scheduler.py --db-path backend/data/app.db --backup-dir data/backups --interval-minutes 60 --keep-last 48 --restore-drill-every 24 --restore-drill-dir data/restore_drills
```

## 6. Release Candidate Gate

```powershell
python scripts/ops/release_candidate_check.py --repo-root .
```

Approve release only if `overall_status=pass`.
