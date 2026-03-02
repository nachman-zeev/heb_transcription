# Stage Status

## Current Stage

- Stage 10: Implemented (Project implementation phases completed; awaiting your release approval)

## Completed Stages

### Stage 0
1. Planning and KPI baseline.
2. Real dataset manifest and bake-off tooling.
3. Primary model lock: `ivrit-ai/whisper-large-v3`.
4. Runtime smoke validation completed.
5. Markdown consistency review completed after model-lock change.

### Stage 1
1. Backend scaffold (`backend/app`) with FastAPI.
2. DB schema for tenants/users/tokens/jobs/channels/words.
3. Auth APIs: bootstrap/login/logout/me.
4. Ingestion APIs: single file and folder ingestion.
5. Queue API: tenant queue stats.
6. Worker with per-channel transcription using `ivrit-ai/whisper-large-v3`.
7. End-to-end smoke run completed and verified.

### Stage 2
1. Hebrew normalization service integrated into worker pipeline.
2. Robust alignment service with fallback when timestamps are weak/missing.
3. Diarization service:
- Multi-channel speaker attribution by channel.
- Mono pause-based speaker heuristic.
4. DB fields expanded for normalized transcript and speaker metadata.
5. API response expanded with normalized text and per-word speaker fields.
6. Stage 2 E2E smoke tests completed.

### Stage 3
1. Web UI served from backend static app.
2. Dashboard usage/activity endpoints + charts.
3. Date filtering and conversation selection UI.
4. Player + word-level synchronized transcript highlighting.
5. Click-to-seek on words and in-page word search highlight.
6. Details view + export downloads (TXT/SRT/DOCX).
7. Live updates via `/ws/tenant` WebSocket.

### Stage 4
1. Queue locks + stale-lock release to prevent duplicate processing.
2. Retry/backoff flow with `retry_wait` and `dead_letter`.
3. Worker heartbeat tracking and online worker visibility.
4. Resource-aware dynamic worker manager (`worker_manager.py`).
5. Health/metrics observability (`/health`, `/metrics`, queue/worker counters).
6. Live WS payload and UI updated with retry/dead-letter/worker counts.
7. Stage 4 smoke tests completed (API, WS, retry/dead-letter, manager loop).

### Stage 5
1. Production middleware: request-id, security headers, optional HTTPS enforcement.
2. Global/auth rate limiting for API hardening.
3. Liveness/readiness endpoints (`/health/live`, `/health/ready`).
4. Env-driven production configuration and CORS allow-list.
5. Backup/restore automation scripts for SQLite.
6. HTTP load-test utility with latency percentile output.
7. Stage 5 smoke tests completed (security/rate-limit/ops tooling).

### Stage 6
1. Dockerized deployment baseline (`backend/Dockerfile`, `docker-compose.yml`).
2. Production env template (`config/production.env.example`).
3. CI workflow (`.github/workflows/ci.yml`) with compile + smoke checks.
4. Go-live preflight checker (`scripts/ops/preflight_check.py`).
5. Go-live checklist documentation and Stage 6 status docs.
6. Stage 6 validation completed.

### Stage 7
1. SLO snapshot tooling for runtime dashboard data.
2. Alert policy evaluation with configurable thresholds.
3. Scheduled backup automation with retention cleanup.
4. Periodic restore drill automation with integrity checks.
5. Post-launch operations runbook and checklist updates.
6. Stage 7 validation completed.

### Stage 8
1. SQLite->PostgreSQL migration script.
2. Secret-file integration (`DB_URL_FILE`, `TOKEN_HASH_PEPPER_FILE`).
3. Node-aware workers and managers (`NODE_ID`).
4. PostgreSQL `SKIP LOCKED` queue acquisition for multi-node safety.
5. Enterprise deployment templates (Compose + Kubernetes manifests).
6. Stage 8 validation completed.

### Stage 9
1. ASR runtime tuning knobs (chunk size and batch size by CPU/GPU).
2. Autoscaling policy refinement (queue target + cooldown + node cap).
3. Runtime performance and cost telemetry (`/perf/summary`).
4. Throughput/realtime/cost metrics in `/metrics` and `/health`.
5. Performance/cost reporting automation script.
6. Stage 9 validation completed.

### Stage 10
1. Release candidate automation script.
2. Full regression-like RC gate across core runtime and ops tooling.
3. Release sign-off package and checklist.
4. Stage 10 RC execution completed with overall status `pass`.

## Next Step

- Final release approval and production rollout using the sign-off package.
