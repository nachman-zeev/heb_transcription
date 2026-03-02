from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AudioProbeResult:
    path: Path
    extension: str
    duration_sec: float
    channel_count: int


def probe_audio(path: Path) -> AudioProbeResult:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=channels:format=duration",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()}")

    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError(f"No audio streams found for {path}")

    channel_count = int(streams[0].get("channels") or 1)
    duration_sec = float(data.get("format", {}).get("duration") or 0.0)
    if duration_sec <= 0:
        duration_sec = 0.001

    return AudioProbeResult(
        path=path,
        extension=path.suffix.lower(),
        duration_sec=duration_sec,
        channel_count=channel_count,
    )


def discover_audio_files(folder_path: Path, recursive: bool, extensions: set[str]) -> list[Path]:
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    items = folder_path.rglob("*") if recursive else folder_path.glob("*")
    return sorted(
        p for p in items if p.is_file() and p.suffix.lower() in extensions
    )
