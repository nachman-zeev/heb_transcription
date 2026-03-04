from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, JobChannel, TranscriptWord
from app.services.alignment import align_words_robust, timestamps_need_repair
from app.services.diarization import diarize_words
from app.services.hebrew_text import normalize_hebrew_text

_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)")


def _probe_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0.0
    try:
        payload = json.loads(proc.stdout)
        return float(payload.get("format", {}).get("duration") or 0.0)
    except Exception:
        return 0.0


def _extract_channel_wav(input_file: Path, channel_index: int) -> Path:
    temp = tempfile.NamedTemporaryFile(prefix="repair_ch_", suffix=".wav", delete=False)
    temp_path = Path(temp.name)
    temp.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_file),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-filter:a",
        f"pan=mono|c0=c{channel_index}",
        str(temp_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg channel extraction failed: {proc.stderr[-300:]}")
    return temp_path


def _detect_speech_segments(audio_path: Path, duration_sec: float) -> list[tuple[float, float]]:
    duration = max(0.0, float(duration_sec or 0.0))
    if duration <= 0:
        return []

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(audio_path),
        "-af",
        "silencedetect=noise=-35dB:d=0.15",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    logs = proc.stderr or ""

    silences: list[tuple[float, float]] = []
    open_silence_start: float | None = None
    for line in logs.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            open_silence_start = max(0.0, min(duration, float(start_match.group(1))))
            continue

        end_match = _SILENCE_END_RE.search(line)
        if end_match:
            end_sec = max(0.0, min(duration, float(end_match.group(1))))
            start_sec = open_silence_start if open_silence_start is not None else 0.0
            if end_sec > start_sec:
                silences.append((start_sec, end_sec))
            open_silence_start = None

    if open_silence_start is not None and open_silence_start < duration:
        silences.append((open_silence_start, duration))

    if not silences:
        return [(0.0, duration)]

    silences.sort(key=lambda x: x[0])
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in silences:
        s_start = max(cursor, s_start)
        if s_start > cursor:
            speech.append((cursor, s_start))
        cursor = max(cursor, s_end)
    if cursor < duration:
        speech.append((cursor, duration))

    cleaned = [(round(s, 6), round(e, 6)) for s, e in speech if (e - s) >= 0.03]
    if not cleaned:
        return [(0.0, duration)]
    return cleaned


def _collect_speech_segments_for_channel(source_file: Path, channel_index: int) -> tuple[float, list[tuple[float, float]]]:
    wav_path = _extract_channel_wav(source_file, channel_index)
    try:
        duration = _probe_duration(wav_path)
        segments = _detect_speech_segments(wav_path, duration)
    finally:
        wav_path.unlink(missing_ok=True)
    return duration, segments


def _extract_raw_words(channel: JobChannel) -> tuple[str, list[dict[str, Any]]]:
    raw_text = (channel.transcript_text or "").strip()
    raw_words: list[dict[str, Any]] = []

    if channel.transcript_json:
        try:
            payload = json.loads(channel.transcript_json)
            raw = payload.get("raw") if isinstance(payload, dict) else None
            if isinstance(raw, dict):
                raw_text = (str(raw.get("text") or raw_text)).strip()
                chunks = raw.get("chunks") or []
                for idx, chunk in enumerate(chunks):
                    token = str(chunk.get("text") or "").strip()
                    if not token:
                        continue
                    ts = chunk.get("timestamp")
                    start_sec = None
                    end_sec = None
                    if isinstance(ts, (list, tuple)) and len(ts) == 2:
                        start_sec = float(ts[0]) if ts[0] is not None else None
                        end_sec = float(ts[1]) if ts[1] is not None else None
                    raw_words.append(
                        {
                            "seq": idx,
                            "text": token,
                            "start_sec": start_sec,
                            "end_sec": end_sec,
                        }
                    )
        except Exception:
            raw_words = []

    if not raw_words:
        existing = sorted(channel.words, key=lambda x: x.seq)
        raw_words = [
            {
                "seq": idx,
                "text": str(w.text or "").strip(),
                "start_sec": float(w.start_sec),
                "end_sec": float(w.end_sec),
            }
            for idx, w in enumerate(existing)
            if str(w.text or "").strip()
        ]
        if not raw_text:
            raw_text = " ".join(w["text"] for w in raw_words).strip()

    return raw_text, raw_words


def _current_word_dicts(channel: JobChannel) -> list[dict[str, Any]]:
    return [
        {
            "seq": int(w.seq),
            "text": str(w.text or ""),
            "start_sec": float(w.start_sec),
            "end_sec": float(w.end_sec),
        }
        for w in sorted(channel.words, key=lambda x: x.seq)
    ]


def repair_job_timestamps_if_needed(db: Session, job: Job) -> bool:
    if job.status != "completed":
        return False

    source = Path(job.source_file_path)
    if not source.exists():
        return False

    updated = False
    total_channels = max(1, int(job.source_channel_count or 1))
    default_duration = float(job.source_duration_sec or 0.0)

    for channel in sorted(job.channels, key=lambda x: x.channel_index):
        current_words = _current_word_dicts(channel)
        if len(current_words) < 2:
            continue

        try:
            channel_duration, speech_segments = _collect_speech_segments_for_channel(source, int(channel.channel_index))
        except Exception:
            continue

        effective_duration = channel_duration if channel_duration > 0 else default_duration
        if not timestamps_need_repair(current_words, effective_duration, speech_segments):
            continue

        raw_text, raw_words = _extract_raw_words(channel)
        aligned_words, alignment_status = align_words_robust(
            raw_text,
            raw_words,
            duration_sec=effective_duration,
            speech_segments=speech_segments,
        )
        if not aligned_words:
            continue

        diarized = diarize_words(
            aligned_words,
            total_channels=total_channels,
            channel_index=int(channel.channel_index),
        )

        for existing in list(channel.words):
            db.delete(existing)
        db.flush()

        for word in diarized.words:
            channel.words.append(
                TranscriptWord(
                    seq=int(word.get("seq", 0)),
                    text=str(word.get("text", "")).strip(),
                    normalized_text=str(word.get("normalized_text", "")).strip() or None,
                    speaker_label=str(word.get("speaker_label", "")).strip() or None,
                    speaker_confidence=float(word.get("speaker_confidence", 0.0)) if word.get("speaker_confidence") is not None else None,
                    start_sec=float(word.get("start_sec", 0.0)),
                    end_sec=float(word.get("end_sec", 0.0)),
                )
            )

        if raw_text and not channel.transcript_text:
            channel.transcript_text = raw_text
        channel.transcript_normalized_text = normalize_hebrew_text(channel.transcript_text or raw_text)
        channel.alignment_status = alignment_status
        channel.diarization_status = diarized.status
        channel.diarization_json = json.dumps(diarized.payload, ensure_ascii=False)
        updated = True

    return updated
