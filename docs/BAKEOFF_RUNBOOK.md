# Bake-off Runbook (Hebrew ASR)

## 1. Prepare Manifest

Copy:

- `data/bakeoff/dataset_manifest.template.csv`

to:

- `data/bakeoff/dataset_manifest.csv`

Fill all rows with real sample metadata and reference transcript paths.

## 2. Validate Manifest

Run:

```powershell
python scripts/bakeoff/validate_manifest.py --manifest data/bakeoff/dataset_manifest.csv
```

Expected:

- `Manifest is valid. rows=<N>`

## 3. Prepare Predictions CSV

Create a CSV with columns:

- `sample_id`
- `predicted_text`

Example path:

- `data/bakeoff/predictions_ivrit_largev3.csv`

## 4. Score WER/CER

Run:

```powershell
python scripts/bakeoff/score_transcripts.py `
  --manifest data/bakeoff/dataset_manifest.csv `
  --predictions data/bakeoff/predictions_ivrit_largev3.csv `
  --run-id ivrit_largev3_20260301 `
  --output-dir data/bakeoff/runs
```

Generated artifacts:

- `data/bakeoff/runs/<run-id>/summary.json`
- `data/bakeoff/runs/<run-id>/per_sample_scores.csv`

## 5. Regression Tracking

Repeat step 4 for each benchmark run and compare:

1. `global_wer`
2. `global_cer`
3. `p95_wer`
4. `p95_cer`

Use holdout split metrics as the final quality/regression signal for the fixed primary model `ivrit-ai/whisper-large-v3`.
