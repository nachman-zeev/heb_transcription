#!/usr/bin/env python3
"""
Build bake-off manifest from a recordings folder that contains audio files
and optional sibling XML metadata files (<audio>.xml).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


SUPPORTED_EXTENSIONS = {".mp3", ".wav"}


@dataclass
class AudioMeta:
    sample_rate_hz: int
    channels: int
    duration_sec: float


def stable_split(sample_id: str) -> str:
    digest = hashlib.sha1(sample_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 70:
        return "dev"
    if bucket < 85:
        return "validation"
    return "holdout"


def parse_xml_duration_seconds(xml_path: pathlib.Path) -> Optional[float]:
    if not xml_path.exists():
        return None
    try:
        root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    duration_el = root.find("Duration")
    if duration_el is None or duration_el.text is None:
        return None
    try:
        return float(duration_el.text.strip())
    except ValueError:
        return None


def ffprobe_audio_meta(audio_path: pathlib.Path) -> AudioMeta:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=sample_rate,channels:format=duration",
        "-of",
        "json",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {audio_path}: {proc.stderr.strip()}")
    payload = json.loads(proc.stdout)
    streams = payload.get("streams", [])
    if not streams:
        raise RuntimeError(f"ffprobe returned no streams for {audio_path}")
    stream0 = streams[0]
    sample_rate_hz = int(stream0.get("sample_rate") or 0)
    channels = int(stream0.get("channels") or 1)
    duration_sec = float(payload.get("format", {}).get("duration") or 0.0)
    if sample_rate_hz <= 0:
        raise RuntimeError(f"invalid sample rate for {audio_path}")
    if duration_sec <= 0:
        raise RuntimeError(f"invalid duration for {audio_path}")
    return AudioMeta(sample_rate_hz=sample_rate_hz, channels=channels, duration_sec=duration_sec)


def build_rows(
    recordings_dir: pathlib.Path,
    references_dir: pathlib.Path,
    default_domain_tag: str,
    default_noise_level: str,
) -> Iterable[Dict[str, str]]:
    audio_paths = sorted(
        p for p in recordings_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    for audio_path in audio_paths:
        sample_id = audio_path.stem
        split = stable_split(sample_id)
        xml_path = pathlib.Path(f"{audio_path}.xml")

        probe = ffprobe_audio_meta(audio_path)
        xml_duration = parse_xml_duration_seconds(xml_path)
        duration_sec = xml_duration if (xml_duration and xml_duration > 0) else probe.duration_sec

        channel_mode = "multi" if probe.channels > 1 else "mono"

        ref_path = references_dir / f"{sample_id}.txt"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        if not ref_path.exists():
            ref_path.write_text("", encoding="utf-8")

        row = {
            "sample_id": sample_id,
            "split": split,
            "audio_path": str(audio_path),
            "reference_text_path": str(ref_path),
            "channel_mode": channel_mode,
            "sample_rate_hz": str(probe.sample_rate_hz),
            "duration_sec": f"{duration_sec:.3f}",
            "domain_tag": default_domain_tag,
            "noise_level": default_noise_level,
            "accent_tag": "",
        }
        yield row


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bake-off manifest from recordings folder.")
    parser.add_argument("--recordings-dir", required=True, help="Root folder of recordings")
    parser.add_argument("--output-manifest", required=True, help="Output CSV path")
    parser.add_argument("--references-dir", required=True, help="Directory to store reference text placeholders")
    parser.add_argument("--default-domain-tag", default="unknown")
    parser.add_argument("--default-noise-level", default="medium")
    args = parser.parse_args()

    recordings_dir = pathlib.Path(args.recordings_dir)
    output_manifest = pathlib.Path(args.output_manifest)
    references_dir = pathlib.Path(args.references_dir)

    if not recordings_dir.exists():
        print(f"ERROR: recordings dir not found: {recordings_dir}")
        return 2

    rows = list(
        build_rows(
            recordings_dir=recordings_dir,
            references_dir=references_dir,
            default_domain_tag=args.default_domain_tag,
            default_noise_level=args.default_noise_level,
        )
    )
    if not rows:
        print("ERROR: no supported audio files found.")
        return 2

    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Manifest written: {output_manifest}")
    print(f"Rows: {len(rows)}")
    print(f"References placeholders dir: {references_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
