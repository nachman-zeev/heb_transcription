# Enterprise Hardening (Stage 8)

## Scope

1. HA database migration path from SQLite to PostgreSQL.
2. Secret-file based runtime configuration (`*_FILE` support).
3. Multi-node worker fleet readiness.
4. Enterprise deployment templates (Compose + Kubernetes).

## 1. SQLite -> PostgreSQL Migration

Run:

```powershell
python scripts/ops/migrate_sqlite_to_postgres.py \
  --sqlite-url sqlite:///./backend/data/app.db \
  --postgres-url postgresql+psycopg://user:pass@host:5432/transcription \
  --truncate-target
```

Or with URL in secret file:

```powershell
python scripts/ops/migrate_sqlite_to_postgres.py \
  --sqlite-url sqlite:///./backend/data/app.db \
  --postgres-url-file C:\secrets\db_url.txt \
  --truncate-target
```

## 2. Secret Files

Supported secret file env vars:

- `DB_URL_FILE`
- `TOKEN_HASH_PEPPER_FILE`

Example:

```powershell
$env:DB_URL_FILE='C:\secrets\db_url.txt'
$env:TOKEN_HASH_PEPPER_FILE='C:\secrets\token_hash_pepper.txt'
```

## 3. Multi-Node Worker Fleet

- Worker IDs now include node identity.
- PostgreSQL queue acquisition uses `FOR UPDATE SKIP LOCKED` (when enabled).
- Configure node identity with:
  - `NODE_ID`

Examples:

```powershell
python backend/worker.py --node-id node-a
python backend/worker.py --node-id node-b
```

## 4. Enterprise Deployment Templates

Compose with PostgreSQL:

```powershell
docker compose -f docker-compose.enterprise.yml up -d --build --scale worker=4
```

Kubernetes templates:

- `deploy/k8s/namespace.yaml`
- `deploy/k8s/api-deployment.yaml`
- `deploy/k8s/worker-deployment.yaml`
- `deploy/k8s/worker-hpa.yaml`

## 5. Recommended Production Baseline

1. Move primary DB to PostgreSQL.
2. Use `DB_URL_FILE` and `TOKEN_HASH_PEPPER_FILE` from secret manager mounts.
3. Run multiple worker replicas across nodes.
4. Keep `ENABLE_POSTGRES_SKIP_LOCKED=true`.
