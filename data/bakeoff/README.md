# Bake-off Dataset Folder

Do not commit raw customer audio files to source control.

Store only metadata and controlled evaluation artifacts.

## Files

- `dataset_manifest.template.csv` - template to register benchmark samples
- `runs/` - output folder for evaluation runs (metrics and logs)

## Required Manifest Columns

1. `sample_id` - unique stable id
2. `split` - one of `dev`, `validation`, `holdout`
3. `audio_path` - local path or object storage URI
4. `reference_text_path` - ground truth transcript path
5. `channel_mode` - `mono` or `multi`
6. `sample_rate_hz` - original source sample rate
7. `duration_sec` - total duration
8. `domain_tag` - for example `support`, `sales`, `collections`
9. `noise_level` - `low`, `medium`, `high`
10. `accent_tag` - optional accent label

