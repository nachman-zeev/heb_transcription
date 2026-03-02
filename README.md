# Transcription System (Hebrew) - Project Workspace

This repository follows the staged implementation plan in:

- `TRANSCRIPTION_SYSTEM_MASTER_PLAN_HE.md`

Primary ASR model policy:

- Main model: `ivrit-ai/whisper-large-v3`
- Language mode: fixed Hebrew (`he`)

Current status:

- Stage 0-10 completed.
- Release Candidate checks passed (`overall_status=pass`).

## Quick Start (Compose)

```powershell
docker compose build
docker compose up -d
```

Enterprise profile (PostgreSQL + scalable workers):

```powershell
docker compose -f docker-compose.enterprise.yml up -d --build --scale worker=4
```

## Release Gate

Run full RC check:

```powershell
python scripts/ops/release_candidate_check.py --repo-root .
```

Artifacts:

- `data/release/release_candidate_report.json`
- `data/release/release_candidate_report.md`

## Folder Layout

- `backend/` - API + DB + worker + static UI app
- `deploy/` - Kubernetes deployment templates
- `docs/` - stage specs and operational docs
- `config/` - deployment and policy templates
- `scripts/` - helper scripts for evaluation and operations
- `data/` - runtime outputs/reports/backups
