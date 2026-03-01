#!/usr/bin/env python3
"""
Validate bake-off dataset manifest structure and basic field constraints.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Dict, List

REQUIRED_COLUMNS = [
    "sample_id",
    "split",
    "audio_path",
    "reference_text_path",
    "channel_mode",
    "sample_rate_hz",
    "duration_sec",
    "domain_tag",
    "noise_level",
    "accent_tag",
]

VALID_SPLITS = {"dev", "validation", "holdout"}
VALID_CHANNELS = {"mono", "multi"}
VALID_NOISE = {"low", "medium", "high"}


def validate_row(idx: int, row: Dict[str, str], seen_ids: set[str]) -> List[str]:
    errors: List[str] = []

    sample_id = row["sample_id"].strip()
    if not sample_id:
        errors.append(f"row {idx}: sample_id is empty")
    elif sample_id in seen_ids:
        errors.append(f"row {idx}: duplicate sample_id '{sample_id}'")
    else:
        seen_ids.add(sample_id)

    split = row["split"].strip().lower()
    if split not in VALID_SPLITS:
        errors.append(f"row {idx}: invalid split '{row['split']}'")

    channel_mode = row["channel_mode"].strip().lower()
    if channel_mode not in VALID_CHANNELS:
        errors.append(f"row {idx}: invalid channel_mode '{row['channel_mode']}'")

    noise_level = row["noise_level"].strip().lower()
    if noise_level not in VALID_NOISE:
        errors.append(f"row {idx}: invalid noise_level '{row['noise_level']}'")

    try:
        sr = int(row["sample_rate_hz"])
        if sr <= 0:
            errors.append(f"row {idx}: sample_rate_hz must be > 0")
    except ValueError:
        errors.append(f"row {idx}: sample_rate_hz must be int")

    try:
        duration = float(row["duration_sec"])
        if duration <= 0:
            errors.append(f"row {idx}: duration_sec must be > 0")
    except ValueError:
        errors.append(f"row {idx}: duration_sec must be numeric")

    if not row["audio_path"].strip():
        errors.append(f"row {idx}: audio_path is empty")
    if not row["reference_text_path"].strip():
        errors.append(f"row {idx}: reference_text_path is empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bake-off manifest CSV.")
    parser.add_argument("--manifest", required=True, help="Path to dataset manifest CSV")
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}")
        return 2

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: manifest has no header")
            return 2

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            print(f"ERROR: missing required columns: {', '.join(missing)}")
            return 2

        seen_ids: set[str] = set()
        all_errors: List[str] = []
        row_count = 0
        for i, row in enumerate(reader, start=2):
            row_count += 1
            all_errors.extend(validate_row(i, row, seen_ids))

    if all_errors:
        print("Manifest validation failed:")
        for e in all_errors:
            print(f"- {e}")
        return 1

    print(f"Manifest is valid. rows={row_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

