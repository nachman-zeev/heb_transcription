from __future__ import annotations

from typing import Any

from app.services.hebrew_text import normalize_hebrew_word, split_words


def _coerce_timestamps(word: dict[str, Any], default_start: float, default_end: float) -> tuple[float, float]:
    start = float(word.get("start_sec", default_start) or default_start)
    end = float(word.get("end_sec", default_end) or default_end)
    if end < start:
        end = start
    return start, end


def _fallback_even_alignment(raw_text: str, duration_sec: float) -> list[dict[str, Any]]:
    tokens = split_words(raw_text)
    if not tokens:
        return []

    duration = max(duration_sec, 0.001)
    slot = duration / max(len(tokens), 1)
    items: list[dict[str, Any]] = []
    for idx, token in enumerate(tokens):
        start = round(idx * slot, 6)
        end = round((idx + 1) * slot, 6)
        items.append(
            {
                "seq": idx,
                "text": token,
                "normalized_text": normalize_hebrew_word(token),
                "start_sec": start,
                "end_sec": end,
            }
        )
    return items


def _stabilize_timestamps(words: list[dict[str, Any]], duration_sec: float) -> list[dict[str, Any]]:
    if not words:
        return []

    duration = max(duration_sec, 0.001)
    min_step = min(0.05, duration / max(len(words), 10))

    stabilized: list[dict[str, Any]] = []
    prev_end = 0.0
    for idx, word in enumerate(words):
        start, end = _coerce_timestamps(word, prev_end, prev_end + min_step)
        start = max(start, prev_end)
        end = max(end, start + min_step)
        start = min(start, duration)
        end = min(end, duration)
        if end <= start:
            end = min(duration, start + min_step)

        token = str(word.get("text", "")).strip()
        if not token:
            continue

        stabilized.append(
            {
                "seq": len(stabilized),
                "text": token,
                "normalized_text": normalize_hebrew_word(token),
                "start_sec": round(start, 6),
                "end_sec": round(end, 6),
            }
        )
        prev_end = end

    if not stabilized:
        return stabilized

    # Ensure final word closes at duration when model gave incomplete ending timestamp.
    stabilized[-1]["end_sec"] = max(stabilized[-1]["end_sec"], round(duration, 6))
    return stabilized


def align_words_robust(
    raw_text: str,
    raw_words: list[dict[str, Any]],
    duration_sec: float,
) -> tuple[list[dict[str, Any]], str]:
    if not raw_words:
        return _fallback_even_alignment(raw_text, duration_sec), "fallback_even_alignment"

    has_any_timestamps = any((w.get("start_sec") is not None or w.get("end_sec") is not None) for w in raw_words)
    if not has_any_timestamps:
        return _fallback_even_alignment(raw_text, duration_sec), "fallback_even_alignment"

    aligned = _stabilize_timestamps(raw_words, duration_sec)
    if aligned:
        return aligned, "model_word_timestamps_stabilized"

    return _fallback_even_alignment(raw_text, duration_sec), "fallback_even_alignment"
