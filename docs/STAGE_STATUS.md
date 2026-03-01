# Stage Status

## Current Stage

- Stage 0: In progress (near completion)

## Completed in this iteration

1. Stage 0 execution plan created and updated with fixed primary model.
2. KPI target file created.
3. Bake-off tooling created (manifest validator + WER/CER scorer).
4. Real dataset manifest generated from `Recordings Examples`.
5. Primary ASR model decision documented: `ivrit-ai/whisper-large-v3`.
6. Runtime transcription script added: `scripts/transcription/transcribe_with_ivrit_whisper.py`.
7. Real smoke transcription run executed successfully with the primary model.
8. Markdown consistency review completed after model-lock change.

## Real Dataset Snapshot

- Source folder: `Recordings Examples`
- Audio files discovered: `70`
- Total duration: `1.732` hours
- Manifest validation: passed (`rows=70`)

## Runtime Validation Snapshot

- Model: `ivrit-ai/whisper-large-v3`
- Device used: `cpu`
- Test file transcribed successfully
- Output saved under: `data/transcriptions/ivrit_whisper_large_v3/`

## Remaining to close Stage 0

1. Approve final KPI thresholds (or request adjustments).
2. Confirm Stage 1 kickoff with current model policy.

## Next Stage After Approval

- Stage 1: Core backend MVP scaffolding (API + auth + ingest + queue + worker + DB schema),
  with `ivrit-ai/whisper-large-v3` as default transcription backend.

