# Release Sign-Off

## RC Command

Run from repo root:

```powershell
python scripts/ops/release_candidate_check.py --repo-root .
```

## Generated Artifacts

- `data/release/release_candidate_report.json`
- `data/release/release_candidate_report.md`
- `data/release/perf_cost_report.json`
- `data/release/perf_cost_report.md`

## Acceptance Rule

Release is approved only if:

1. `overall_status = pass`
2. No failed steps in `steps[]`
3. Primary model remains `ivrit-ai/whisper-large-v3`

## Final Manual Checks

1. Confirm production env/secrets are set (`DB_URL_FILE`, `TOKEN_HASH_PEPPER_FILE` where applicable).
2. Confirm `/health/ready` and `/perf/summary` are green on target environment.
3. Confirm latest backup exists and restore drill succeeded.
4. Confirm alert policy check returns `status=ok` or approved exceptions.

## Rollback Trigger

If any RC step fails after deploy:

1. Roll back application image/version.
2. Restore last known-good DB backup if schema/data corruption is suspected.
3. Re-run RC checks before next rollout.
