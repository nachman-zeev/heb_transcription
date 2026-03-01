# Stage 0 Gate Checklist

Use this checklist before moving to Stage 1.

## A. Dataset Readiness

- [ ] At least 100 real Hebrew phone calls are selected.
- [ ] Calls include different accents, speaking speeds, and noise conditions.
- [ ] Ground-truth transcripts exist for each sample.
- [ ] Each sample has metadata: duration, channel count, domain tag, noise level.
- [ ] Data is split into `dev`, `validation`, and `holdout`.

## B. Metric Baseline

- [ ] WER is measured per sample and globally.
- [ ] CER is measured per sample and globally.
- [ ] Diarization quality is measured (speaker attribution checks).
- [ ] End-to-end latency is measured (queue wait and processing time).
- [ ] Failures and retries are measured.

## C. Bake-off Integrity (Regression)

- [ ] Same dataset and split are used for all benchmark runs.
- [ ] Same pre-processing policy is used for all benchmark runs.
- [ ] Same normalization policy is used before scoring.
- [ ] Result artifacts are versioned by run id and timestamp.

## D. Decision Output

- [ ] Primary model is locked to `ivrit-ai/whisper-large-v3`.
- [ ] Runtime validation with the primary model is successful.
- [ ] Fallback model is selected.
- [ ] Risks and edge cases are documented.
- [ ] Approval to continue to Stage 1 is recorded.
