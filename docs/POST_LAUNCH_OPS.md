# Post-Launch Operations (Stage 7+9)

## Goals

1. Run continuous SLO snapshots.
2. Evaluate alert policies automatically.
3. Execute scheduled backups with retention.
4. Run periodic restore drills automatically.
5. Track performance and projected cost budget.

## 1. SLO Snapshot

Generate runtime snapshot JSON + Markdown:

```powershell
python scripts/ops/slo_snapshot.py \
  --base-url http://127.0.0.1:8080 \
  --json-out data/ops/slo_latest.json \
  --md-out data/ops/slo_latest.md
```

## 2. Alert Policy Evaluation

Create local policy file:

```powershell
copy config/alert_policy.example.json config/alert_policy.json
```

Run policy check:

```powershell
python scripts/ops/alert_policy_check.py \
  --base-url http://127.0.0.1:8080 \
  --policy-file config/alert_policy.json \
  --json-out data/ops/alert_latest.json
```

Exit codes:

- `0`: policy OK
- `1`: alerts triggered
- `2`: monitoring collection failure

## 3. Performance and Cost Report

```powershell
python scripts/ops/perf_cost_report.py \
  --base-url http://127.0.0.1:8080 \
  --monthly-budget 1000 \
  --json-out data/ops/perf_cost_report.json \
  --md-out data/ops/perf_cost_report.md
```

## 4. Backup Scheduler + Restore Drills

Run scheduled job loop:

```powershell
python scripts/ops/backup_scheduler.py \
  --db-path backend/data/app.db \
  --backup-dir data/backups \
  --interval-minutes 60 \
  --keep-last 48 \
  --restore-drill-every 24 \
  --restore-drill-dir data/restore_drills
```

## 5. Operational Review Cadence

1. Daily: check alert output and dead-letter trends.
2. Daily: review projected monthly cost versus budget.
3. Weekly: review SLO snapshots and queue behavior.
4. Weekly: verify latest restore drill passed.
5. Monthly: retune autoscaling and ASR batch/chunk settings.
