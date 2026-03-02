# Stage 2 Status

## Scope Implemented

Stage 2 (Hebrew accuracy hardening) is implemented on top of Stage 1:

1. Hebrew text normalization pipeline
2. Robust word alignment fallback and stabilization
3. Speaker assignment logic for mono and multi-channel calls
4. Extended transcript storage for quality metadata

## Implemented Components

1. `backend/app/services/hebrew_text.py`
- Unicode normalization
- Niqqud removal
- punctuation cleanup
- normalized tokens for search/storage

2. `backend/app/services/alignment.py`
- `model_word_timestamps_stabilized` path when word timestamps exist
- `fallback_even_alignment` when model timestamps are missing

3. `backend/app/services/diarization.py`
- Multi-channel: deterministic channel-based speakers (`spk_ch_N`)
- Mono: pause-based heuristic diarization (`mono_pause_heuristic`)

4. Database extensions
- `job_channels.transcript_normalized_text`
- `job_channels.diarization_json`
- `job_channels.alignment_status`
- `job_channels.diarization_status`
- `transcript_words.normalized_text`
- `transcript_words.speaker_label`
- `transcript_words.speaker_confidence`

5. Worker integration
- Stage-2 worker applies normalization + alignment + diarization before persistence
- Primary model remains `ivrit-ai/whisper-large-v3`

## Validation Results

1. Mono test job:
- status: completed
- alignment: `model_word_timestamps_stabilized`
- diarization: `mono_pause_heuristic`
- word-level speaker labels saved

2. Multi-channel test job:
- status: completed
- diarization mode: `channel_based`
- channels processed separately

3. API validation:
- `/jobs/{id}` returns normalized transcript and per-word speaker fields.

## Notes

- Mono diarization currently uses a deterministic heuristic (no external diarization model dependency).
- This keeps Stage 2 stable in offline/self-hosted environments.
