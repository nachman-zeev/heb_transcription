# Stage 8 Status

## Scope Implemented

Stage 8 (Enterprise hardening) is implemented.

1. HA database migration path:
- `scripts/ops/migrate_sqlite_to_postgres.py`

2. Secrets integration:
- `DB_URL_FILE` and `TOKEN_HASH_PEPPER_FILE` support in runtime config
- token hash pepper integration for API tokens

3. Multi-node worker readiness:
- node-aware worker and manager IDs (`NODE_ID` / `--node-id`)
- PostgreSQL queue lock strategy with `FOR UPDATE SKIP LOCKED`

4. Enterprise deployment templates:
- `docker-compose.enterprise.yml`
- Kubernetes manifests under `deploy/k8s/`

5. Preflight hardening:
- PostgreSQL-aware DB checks
- secret file validation

## Validation Results

Validation date: `2026-03-02`

1. `python -m compileall backend scripts` passed.
2. API smoke checks passed on SQLite after Stage 8 changes.
3. worker manager smoke (`--max-ticks 3`) passed.
4. preflight script passed in local SQLite profile.
5. SQLite-to-target migration script validated in dry path (sqlite target simulation).

## Model Policy Check

Stage 8 keeps primary transcription model unchanged:

- `ivrit-ai/whisper-large-v3`
