# Go-Live Checklist (Stage 6)

## 1. Preflight

Run from repo root:

```powershell
$env:APP_ENV='prod'
$env:DB_URL='sqlite:///./backend/data/app.db'
$env:PRIMARY_MODEL_ID='ivrit-ai/whisper-large-v3'
python scripts/ops/preflight_check.py --recordings-path "Recordings Examples"
```

Use strict mode for CI/CD gate:

```powershell
python scripts/ops/preflight_check.py --strict
```

## 2. Build and Run (Docker Compose)

```powershell
docker compose build
docker compose up -d
```

Verify:

```powershell
curl http://127.0.0.1:8080/health/live
curl http://127.0.0.1:8080/health/ready
curl http://127.0.0.1:8080/metrics
```

## 3. Data Safety

Before any major release or migration:

```powershell
python scripts/ops/backup_sqlite.py --db-path backend/data/app.db --out-dir data/backups
```

Restore drill (test environment):

```powershell
python scripts/ops/restore_sqlite.py --backup-path data/backups/<file>.sqlite --target-db-path backend/data/app_restore_test.db --force
```

## 4. Load Smoke

```powershell
python scripts/loadtest/http_benchmark.py --base-url http://127.0.0.1:8080 --endpoint /health --requests 1000 --concurrency 50
```

Acceptance baseline:

- no non-2xx failures on health endpoint
- stable p95 latency
- no worker crash loops

## 5. Security Gate

For internet-facing production:

1. Set `ENFORCE_HTTPS=true`.
2. Set strict `CORS_ALLOWED_ORIGINS` (only your UI domains).
3. Keep `RATE_LIMIT_ENABLED=true`.
4. Run behind reverse proxy with TLS termination and `x-forwarded-proto=https`.

## 6. Rollback Plan

1. Stop services: `docker compose down`
2. Restore last known good DB backup.
3. Start previous image version.
4. Recheck `/health/ready` and tenant login path.
