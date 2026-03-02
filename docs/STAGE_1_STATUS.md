# Stage 1 Status

## Scope Implemented

Stage 1 MVP backend is implemented with the following components:

1. API service (FastAPI)
2. Auth (tenant bootstrap, login, bearer token, logout, me)
3. Ingestion endpoints (single file + folder scan)
4. DB-backed queue and jobs
5. Worker process with per-channel transcription
6. Transcript + word timestamps persistence

## Primary Model Enforcement

The worker and runtime transcription path use:

- `ivrit-ai/whisper-large-v3`

Validated in code:

- `config/model_policy.yaml` (project-level policy)
- `backend/app/core/config.py` (`primary_model_id` default)
- `backend/worker.py` (engine initialization)

## End-to-End Validation

Completed checks:

1. Health endpoint: `200`
2. Bootstrap tenant/user: `200`
3. Login: `200`
4. Create job: `200`
5. Worker `--once` processed queued job successfully
6. Job status moved to `completed`
7. Queue stats reflect completed jobs

## Open Items for Stage 2

1. Hebrew normalization pipeline hardening.
2. Stronger diarization logic for mono calls.
3. Richer word alignment guarantees.
4. Export formats and UI integration.

