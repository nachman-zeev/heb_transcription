# Stage 0 Execution Plan

## Purpose

Stage 0 ensures we start implementation with measurable quality and operational targets,
while locking and validating the project primary model.

## Deliverables

1. KPI targets for quality and operations (`config/kpi_targets.yaml`)
2. Dataset manifest built from real recordings (`data/bakeoff/dataset_manifest.csv`)
3. Scoring script for WER/CER (`scripts/bakeoff/score_transcripts.py`)
4. Primary model runtime script (`scripts/transcription/transcribe_with_ivrit_whisper.py`)
5. Model decision record (`docs/MODEL_DECISION.md`)

## Scope Boundaries

Included:

- Define quality metrics and thresholds for Hebrew calls.
- Build repeatable data manifests and evaluation tooling.
- Validate successful runtime transcription with the chosen primary model.

Not included:

- Production API
- Queue workers
- Database migrations
- UI implementation

## Exit Criteria

Stage 0 is complete when:

1. KPI thresholds are approved.
2. Representative Hebrew dataset manifests are ready.
3. Primary model (`ivrit-ai/whisper-large-v3`) is successfully run in workspace.
4. Stage 1 baseline model policy is documented.
