# Transcription System (Hebrew) - Project Workspace

This repository follows the staged implementation plan in:

- `TRANSCRIPTION_SYSTEM_MASTER_PLAN_HE.md`

Primary ASR model policy:

- Main model: `ivrit-ai/whisper-large-v3`
- Language mode: fixed Hebrew (`he`)
- Runtime script: `scripts/transcription/transcribe_with_ivrit_whisper.py`

Current status:

- Stage 0 is in progress with model decision already locked.

## Stage Flow

1. Stage 0: Data baseline, KPI targets, and primary-model smoke validation
2. Stage 1: Core MVP backend (auth, ingest, queue, worker, DB)
3. Stage 2: Hebrew accuracy pipeline hardening (normalization, diarization, alignment)
4. Stage 3: Full UI + live updates
5. Stage 4: Scale and hardening

## Folder Layout

- `docs/` - stage specs and operational docs
- `config/` - tunable project configuration
- `data/` - dataset manifests and transcript outputs
- `scripts/` - helper scripts for evaluation and transcription
