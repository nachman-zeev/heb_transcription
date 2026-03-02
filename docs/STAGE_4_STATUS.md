# Stage 4 Status

## Scope Implemented

Stage 4 (Scale + Hardening) is implemented and validated.

1. Queue hardening with worker locks and stale-lock release.
2. Retry pipeline with exponential backoff (`retry_wait`) and terminal `dead_letter` state.
3. Worker heartbeat tracking and online worker visibility.
4. Dynamic worker manager (`worker_manager.py`) with resource-aware scaling loop.
5. Resource guard snapshot (CPU/RAM/GPU) and recommended worker count.
6. Extended tenant live updates (`retry_wait`, `dead_letter`, `workers_online`).
7. Prometheus-style metrics endpoint (`/metrics`).
8. Health payload expanded with queue/resource/worker details.
9. UI live queue text updated to include retry/dead-letter/worker counters.

## Backend Additions

1. Queue and locking:
- `backend/app/services/queueing.py`
- Fair candidate pick from `queued` + due `retry_wait`
- Atomic lock acquisition (`locked_by_worker`, `locked_at`, `last_heartbeat_at`)

2. Worker reliability:
- `backend/worker.py`
- Heartbeats while idle/processing
- Retry scheduling and dead-letter terminal flow
- Structured JSON events

3. Dynamic scaling:
- `backend/worker_manager.py`
- Spawns/stops workers based on queue depth and resource manager recommendation

4. Observability:
- `backend/app/api/routes_metrics.py` (`/metrics`)
- `backend/app/services/metrics_store.py`
- `backend/app/services/logging_utils.py`

5. Heartbeat visibility:
- `backend/app/services/heartbeat.py`
- Online workers now filtered by fresh heartbeat window
- `/queue/workers`, `/health`, and `/ws/tenant` use online-count logic

6. Data model updates:
- `backend/app/models.py` and `backend/app/database.py`
- Retry/lock fields on jobs + `worker_heartbeats` table

## Validation Results

Validation date: `2026-03-02`

1. Syntax validation: `python -m compileall backend` passed.
2. DB init/migration: `init_db()` created/verified Stage 4 columns and `worker_heartbeats` table.
3. API smoke checks passed:
- `GET /health`
- `GET /queue/stats`
- `GET /queue/workers`
- `GET /metrics`
4. WebSocket smoke check passed:
- `/ws/tenant` payload includes `retry_wait`, `dead_letter`, `workers_online`.
5. Retry/dead-letter behavior verified:
- Forced missing-file job moved through `retry_wait` and ended in `dead_letter` after max retries.
6. Worker manager smoke check passed:
- `python worker_manager.py --max-ticks 3` completed cleanly.

## Model Policy Check

Stage 4 keeps the primary transcription model unchanged:

- `ivrit-ai/whisper-large-v3`
