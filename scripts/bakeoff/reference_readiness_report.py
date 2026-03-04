#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _safe_float(v: str) -> float:
    try:
        return float(v.strip())
    except Exception:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Report ground-truth reference readiness for bakeoff manifest.")
    parser.add_argument("--manifest", required=True, help="Path to dataset manifest CSV")
    parser.add_argument("--json-out", required=True, help="Output JSON summary path")
    parser.add_argument("--csv-out", required=True, help="Output CSV for missing/empty references")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    rows: list[dict[str, str]] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)
    refs_exist = 0
    refs_non_empty = 0
    missing_or_empty: list[dict[str, str]] = []

    by_split: dict[str, dict[str, int]] = {}

    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        split = (row.get("split") or "unknown").strip()
        ref_path = Path((row.get("reference_text_path") or "").strip())
        audio_path = (row.get("audio_path") or "").strip()
        duration_sec = _safe_float(row.get("duration_sec") or "0")

        by_split.setdefault(split, {"total": 0, "non_empty_refs": 0})
        by_split[split]["total"] += 1

        exists = ref_path.exists() and ref_path.is_file()
        non_empty = False
        if exists:
            refs_exist += 1
            try:
                non_empty = bool(ref_path.read_text(encoding="utf-8").strip())
            except Exception:
                non_empty = False

        if non_empty:
            refs_non_empty += 1
            by_split[split]["non_empty_refs"] += 1
        else:
            missing_or_empty.append(
                {
                    "sample_id": sample_id,
                    "split": split,
                    "audio_path": audio_path,
                    "reference_text_path": str(ref_path),
                    "duration_sec": f"{duration_sec:.3f}",
                    "reason": "missing" if not exists else "empty",
                }
            )

    missing_or_empty.sort(key=lambda r: float(r.get("duration_sec") or 0.0))

    json_payload = {
        "manifest": str(manifest_path),
        "total_samples": total,
        "references_exist": refs_exist,
        "references_non_empty": refs_non_empty,
        "references_non_empty_percent": round((refs_non_empty / max(1, total)) * 100.0, 2),
        "missing_or_empty_count": len(missing_or_empty),
        "by_split": by_split,
    }

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_out = Path(args.csv_out)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id",
                "split",
                "duration_sec",
                "reason",
                "audio_path",
                "reference_text_path",
            ],
        )
        w.writeheader()
        for r in missing_or_empty:
            w.writerow(r)

    print(f"total_samples={total}")
    print(f"references_non_empty={refs_non_empty}")
    print(f"missing_or_empty={len(missing_or_empty)}")
    print(f"summary_json={json_out}")
    print(f"missing_csv={csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

