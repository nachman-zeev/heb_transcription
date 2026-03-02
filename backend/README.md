# Backend Stage 1-10 (Finalized)

This backend implements:

- Multi-tenant Hebrew transcription API and UI
- `ivrit-ai/whisper-large-v3` worker pipeline
- Queue fairness + retries + dead-letter
- Dynamic resource-aware worker scaling
- Security middleware and rate limiting
- Health/performance/cost observability
- Ops automation (backup/restore, alerts, SLO, RC checks)

## Run local API

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## Run worker manager

```powershell
cd backend
python worker_manager.py --min-workers 1 --node-id node-local
```

## Core endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`
- `GET /perf/summary`

## Release candidate gate (repo root)

```powershell
python scripts/ops/release_candidate_check.py --repo-root .
```

RC artifacts:

- `data/release/release_candidate_report.json`
- `data/release/release_candidate_report.md`
