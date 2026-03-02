# Performance and Cost Controls (Stage 9)

## Goals

1. Improve throughput without reducing transcription quality.
2. Keep system stable under variable queue pressure.
3. Track operational cost estimates continuously.

## 1. ASR Performance Tuning

Environment variables:

- `ASR_CHUNK_LENGTH_SEC` (default `30`)
- `ASR_BATCH_SIZE_CPU` (default `1`)
- `ASR_BATCH_SIZE_GPU` (default `8`)

Guidelines:

1. GPU hosts:
- increase `ASR_BATCH_SIZE_GPU` gradually (8 -> 12 -> 16)
- monitor `gpu_memory_used_percent` and worker crashes

2. CPU-only hosts:
- keep `ASR_BATCH_SIZE_CPU=1`
- use `AUTOSCALE_TARGET_QUEUE_PER_WORKER` and worker count for throughput

3. `ASR_CHUNK_LENGTH_SEC`:
- smaller values reduce memory peaks
- larger values may improve throughput but increase memory pressure

## 2. Autoscaling Policy

Variables:

- `AUTOSCALE_TARGET_QUEUE_PER_WORKER`
- `AUTOSCALE_SCALE_UP_COOLDOWN_SECONDS`
- `AUTOSCALE_SCALE_DOWN_COOLDOWN_SECONDS`
- `AUTOSCALE_MAX_WORKERS_PER_NODE`

Default behavior:

1. desired workers = `ceil(queue_depth / target_queue_per_worker)`
2. capped by resource guard recommendation
3. capped by `AUTOSCALE_MAX_WORKERS_PER_NODE`
4. cooldowns reduce scale flapping

## 3. Runtime Performance Endpoint

Use:

- `GET /perf/summary`

Returns:

- queue status
- worker count
- throughput (audio min/hour, realtime factor)
- estimated cost totals

## 4. Cost Report Automation

Run:

```powershell
python scripts/ops/perf_cost_report.py \
  --base-url http://127.0.0.1:8080 \
  --monthly-budget 1000 \
  --json-out data/ops/perf_cost_report.json \
  --md-out data/ops/perf_cost_report.md
```

## 5. Monthly Optimization Loop

1. Collect daily `perf/summary` snapshots.
2. Compare projected monthly cost to budget.
3. Tune queue target and worker caps before model-level compromises.
4. Keep `ivrit-ai/whisper-large-v3` as primary model (accuracy-first policy).
