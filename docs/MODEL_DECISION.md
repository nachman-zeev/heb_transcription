# Model Decision (2026-03-02)

## Decision

The project primary transcription model is fixed to:

- `ivrit-ai/whisper-large-v3`

This decision was requested by product direction and is now part of the baseline plan.

## Runtime Validation

A real transcription smoke run was executed successfully in this workspace using:

- script: `scripts/transcription/transcribe_with_ivrit_whisper.py`
- input file: `Recordings Examples/20260226/215/00100016003_20260226_1416000900_215.mp3`
- output files:
  - `data/transcriptions/ivrit_whisper_large_v3/00100016003_20260226_1416000900_215.txt`
  - `data/transcriptions/ivrit_whisper_large_v3/00100016003_20260226_1416000900_215.json`

## Implications for Stages

1. Stage 0 no longer blocks on model-selection.
2. Stage 1 must integrate this model as default worker path.
3. Stage 2 focuses on Hebrew quality hardening (normalization, diarization, alignment), not choosing a different primary model.
4. KPI validation remains required, as quality tracking/regression checks.
