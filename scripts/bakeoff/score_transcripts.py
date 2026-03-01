#!/usr/bin/env python3
"""
Score ASR predictions against references using WER and CER.

Input:
- manifest CSV with sample_id + reference_text_path
- predictions CSV with sample_id + predicted_text

Output:
- summary JSON
- per-sample CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


HEBREW_NIQQUD_RE = re.compile(r"[\u0591-\u05C7]")
PUNCTUATION_RE = re.compile(r"[^\w\s\u0590-\u05FF]", flags=re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class SampleScore:
    sample_id: str
    wer: float
    cer: float
    ref_words: int
    ref_chars: int


def normalize_hebrew_text(text: str) -> str:
    # NFKC helps normalize unicode variants before text operations.
    text = unicodedata.normalize("NFKC", text)
    text = HEBREW_NIQQUD_RE.sub("", text)
    text = text.replace("׳", "'").replace("״", '"')
    text = PUNCTUATION_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip().lower()
    return text


def tokenize_words(text: str) -> List[str]:
    if not text:
        return []
    return text.split(" ")


def tokenize_chars(text: str) -> List[str]:
    # CER ignores spaces to avoid word-boundary penalties in char score.
    return [c for c in text if not c.isspace()]


def edit_distance(seq_a: Sequence[str], seq_b: Sequence[str]) -> int:
    if not seq_a:
        return len(seq_b)
    if not seq_b:
        return len(seq_a)

    prev = list(range(len(seq_b) + 1))
    for i, a in enumerate(seq_a, start=1):
        curr = [i]
        for j, b in enumerate(seq_b, start=1):
            cost = 0 if a == b else 1
            curr.append(
                min(
                    prev[j] + 1,      # deletion
                    curr[j - 1] + 1,  # insertion
                    prev[j - 1] + cost,  # substitution
                )
            )
        prev = curr
    return prev[-1]


def read_manifest_references(path: pathlib.Path) -> Dict[str, pathlib.Path]:
    refs: Dict[str, pathlib.Path] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"sample_id", "reference_text_path"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            missing = required.difference(set(reader.fieldnames or []))
            raise ValueError(f"manifest missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            sample_id = row["sample_id"].strip()
            ref_path = pathlib.Path(row["reference_text_path"].strip())
            if sample_id:
                refs[sample_id] = ref_path
    return refs


def read_predictions(path: pathlib.Path) -> Dict[str, str]:
    preds: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"sample_id", "predicted_text"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            missing = required.difference(set(reader.fieldnames or []))
            raise ValueError(f"predictions missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            sample_id = row["sample_id"].strip()
            preds[sample_id] = row["predicted_text"]
    return preds


def read_text(path: pathlib.Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"reference transcript file missing: {path}")
    return path.read_text(encoding="utf-8")


def compute_scores(ref_text: str, pred_text: str) -> Tuple[float, float, int, int]:
    ref_norm = normalize_hebrew_text(ref_text)
    pred_norm = normalize_hebrew_text(pred_text)

    ref_words = tokenize_words(ref_norm)
    pred_words = tokenize_words(pred_norm)

    ref_chars = tokenize_chars(ref_norm)
    pred_chars = tokenize_chars(pred_norm)

    if len(ref_words) == 0:
        wer = 0.0 if len(pred_words) == 0 else 1.0
    else:
        wer = edit_distance(ref_words, pred_words) / len(ref_words)

    if len(ref_chars) == 0:
        cer = 0.0 if len(pred_chars) == 0 else 1.0
    else:
        cer = edit_distance(ref_chars, pred_chars) / len(ref_chars)

    return wer, cer, len(ref_words), len(ref_chars)


def aggregate(scores: Iterable[SampleScore]) -> Dict[str, float]:
    scores = list(scores)
    if not scores:
        return {"sample_count": 0, "global_wer": 0.0, "global_cer": 0.0, "p95_wer": 0.0, "p95_cer": 0.0}

    ordered_wer = sorted(s.wer for s in scores)
    ordered_cer = sorted(s.cer for s in scores)
    idx95 = max(0, int(0.95 * len(scores)) - 1)

    global_wer = sum(s.wer * s.ref_words for s in scores) / max(1, sum(s.ref_words for s in scores))
    global_cer = sum(s.cer * s.ref_chars for s in scores) / max(1, sum(s.ref_chars for s in scores))

    return {
        "sample_count": float(len(scores)),
        "global_wer": global_wer,
        "global_cer": global_cer,
        "p95_wer": ordered_wer[idx95],
        "p95_cer": ordered_cer[idx95],
    }


def write_per_sample_csv(path: pathlib.Path, scores: Sequence[SampleScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_id", "wer", "cer", "ref_words", "ref_chars"])
        for s in scores:
            writer.writerow(
                [
                    s.sample_id,
                    f"{s.wer:.6f}",
                    f"{s.cer:.6f}",
                    s.ref_words,
                    s.ref_chars,
                ]
            )


def write_summary_json(path: pathlib.Path, summary: Dict[str, float], run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "sample_count": int(summary["sample_count"]),
        "global_wer": summary["global_wer"],
        "global_cer": summary["global_cer"],
        "p95_wer": summary["p95_wer"],
        "p95_cer": summary["p95_cer"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score ASR predictions (WER/CER).")
    parser.add_argument("--manifest", required=True, help="Path to dataset manifest CSV")
    parser.add_argument("--predictions", required=True, help="Path to predictions CSV")
    parser.add_argument("--run-id", required=True, help="Run identifier, e.g. ivrit_largev3_20260301")
    parser.add_argument("--output-dir", required=True, help="Output directory for run artifacts")
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest)
    predictions_path = pathlib.Path(args.predictions)
    output_dir = pathlib.Path(args.output_dir)

    try:
        refs = read_manifest_references(manifest_path)
        preds = read_predictions(predictions_path)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    scores: List[SampleScore] = []
    missing_predictions: List[str] = []
    for sample_id, ref_path in refs.items():
        if sample_id not in preds:
            missing_predictions.append(sample_id)
            continue
        try:
            ref_text = read_text(ref_path)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}")
            return 2
        wer, cer, ref_words, ref_chars = compute_scores(ref_text, preds[sample_id])
        scores.append(
            SampleScore(
                sample_id=sample_id,
                wer=wer,
                cer=cer,
                ref_words=ref_words,
                ref_chars=ref_chars,
            )
        )

    if missing_predictions:
        print(f"WARNING: {len(missing_predictions)} samples missing predictions.")

    summary = aggregate(scores)
    run_dir = output_dir / args.run_id
    per_sample_path = run_dir / "per_sample_scores.csv"
    summary_path = run_dir / "summary.json"
    write_per_sample_csv(per_sample_path, scores)
    write_summary_json(summary_path, summary, args.run_id)

    print(f"Run completed: {args.run_id}")
    print(f"Samples scored: {int(summary['sample_count'])}")
    print(f"Global WER: {summary['global_wer']:.4f}")
    print(f"Global CER: {summary['global_cer']:.4f}")
    print(f"P95 WER: {summary['p95_wer']:.4f}")
    print(f"P95 CER: {summary['p95_cer']:.4f}")
    print(f"Artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

