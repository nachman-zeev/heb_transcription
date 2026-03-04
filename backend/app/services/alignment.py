from __future__ import annotations

from typing import Any

from app.services.hebrew_text import normalize_hebrew_word, split_words


def _tokens_from_raw_words(raw_words: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for word in raw_words:
        token = str(word.get("text", "")).strip()
        if token:
            out.append(token)
    return out


def _fallback_even_alignment_tokens(tokens: list[str], duration_sec: float) -> list[dict[str, Any]]:
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


def _normalize_speech_segments(
    speech_segments: list[tuple[float, float]] | None,
    duration_sec: float,
) -> list[tuple[float, float]]:
    if not speech_segments:
        return []

    duration = max(0.0, float(duration_sec or 0.0))
    if duration <= 0:
        return []

    cleaned: list[tuple[float, float]] = []
    for raw_start, raw_end in speech_segments:
        start = max(0.0, min(duration, float(raw_start)))
        end = max(0.0, min(duration, float(raw_end)))
        if end > start:
            cleaned.append((start, end))

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: x[0])
    merged: list[tuple[float, float]] = [cleaned[0]]
    for start, end in cleaned[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _fallback_segment_alignment(
    tokens: list[str],
    duration_sec: float,
    speech_segments: list[tuple[float, float]] | None,
) -> list[dict[str, Any]]:
    if not tokens:
        return []

    segments = _normalize_speech_segments(speech_segments, duration_sec)
    if not segments:
        return _fallback_even_alignment_tokens(tokens, duration_sec)

    total_voiced = sum(max(0.0, end - start) for start, end in segments)
    if total_voiced <= 0.0:
        return _fallback_even_alignment_tokens(tokens, duration_sec)

    duration = max(duration_sec, 0.001)
    seg_lengths = [max(0.0, end - start) for start, end in segments]
    quotas = [(seg_len / total_voiced) * len(tokens) for seg_len in seg_lengths]
    counts = [int(q) for q in quotas]
    remaining = len(tokens) - sum(counts)

    if remaining > 0:
        ranked = sorted(
            range(len(segments)),
            key=lambda i: ((quotas[i] - counts[i]), seg_lengths[i]),
            reverse=True,
        )
        for i in range(remaining):
            counts[ranked[i % len(ranked)]] += 1

    # If rounding produced too many words, trim from smallest-fraction segments first.
    overflow = sum(counts) - len(tokens)
    if overflow > 0:
        ranked = sorted(
            range(len(segments)),
            key=lambda i: ((quotas[i] - counts[i]), -seg_lengths[i]),
        )
        for idx in ranked:
            if overflow <= 0:
                break
            if counts[idx] <= 0:
                continue
            take = min(counts[idx], overflow)
            counts[idx] -= take
            overflow -= take

    out: list[dict[str, Any]] = []
    token_idx = 0
    for seg_idx, (seg_start, seg_end) in enumerate(segments):
        cnt = counts[seg_idx]
        if cnt <= 0:
            continue

        seg_len = max(0.0001, seg_end - seg_start)
        slot = seg_len / cnt
        for local_idx in range(cnt):
            if token_idx >= len(tokens):
                break
            start = seg_start + (local_idx * slot)
            end = seg_start + ((local_idx + 1) * slot)
            end = min(end, seg_end)
            if end <= start:
                end = min(seg_end, start + min(0.05, duration / max(len(tokens), 10)))

            token = tokens[token_idx]
            out.append(
                {
                    "seq": token_idx,
                    "text": token,
                    "normalized_text": normalize_hebrew_word(token),
                    "start_sec": round(start, 6),
                    "end_sec": round(end, 6),
                }
            )
            token_idx += 1

    # Safety: if due to edge rounding some tokens remain, place them at end of last speech segment.
    while token_idx < len(tokens):
        last_start, last_end = segments[-1]
        token = tokens[token_idx]
        out.append(
            {
                "seq": token_idx,
                "text": token,
                "normalized_text": normalize_hebrew_word(token),
                "start_sec": round(last_start, 6),
                "end_sec": round(last_end, 6),
            }
        )
        token_idx += 1

    return out


def _coerce_timestamps(word: dict[str, Any], default_start: float, default_end: float) -> tuple[float, float]:
    start = float(word.get("start_sec", default_start) or default_start)
    end = float(word.get("end_sec", default_end) or default_end)
    if end < start:
        end = start
    return start, end


def _fallback_even_alignment(raw_text: str, duration_sec: float) -> list[dict[str, Any]]:
    return _fallback_even_alignment_tokens(split_words(raw_text), duration_sec)


def _stabilize_timestamps(words: list[dict[str, Any]], duration_sec: float) -> list[dict[str, Any]]:
    if not words:
        return []

    prepared: list[tuple[dict[str, Any], str]] = []
    for word in words:
        token = str(word.get("text", "")).strip()
        if token:
            prepared.append((word, token))

    if not prepared:
        return []

    duration = max(duration_sec, 0.001)
    min_step = min(0.05, duration / max(len(prepared), 10))

    stabilized: list[dict[str, Any]] = []
    prev_end = 0.0
    total = len(prepared)
    for idx, (word, token) in enumerate(prepared):
        start, end = _coerce_timestamps(word, prev_end, prev_end + min_step)
        start = max(start, prev_end)

        # Keep enough timeline budget for the remaining words so they won't collapse at duration.
        remaining = total - idx - 1
        max_end_for_current = max(min_step, duration - (remaining * min_step))
        max_start_for_current = max(prev_end, max_end_for_current - min_step)
        if start > max_start_for_current:
            start = max_start_for_current

        start = min(max(start, 0.0), duration)
        end = max(end, start + min_step)
        if end > max_end_for_current:
            end = max_end_for_current
        end = min(max(end, start), duration)
        if end <= start:
            end = min(duration, start + min_step)
        if end <= start:
            end = start

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


def _timestamps_look_unreliable(
    aligned_words: list[dict[str, Any]],
    duration_sec: float,
    speech_segments: list[tuple[float, float]] | None,
) -> bool:
    if not aligned_words:
        return True

    duration = max(duration_sec, 0.001)
    first_start = float(aligned_words[0].get("start_sec") or 0.0)
    last_end = float(aligned_words[-1].get("end_sec") or first_start)
    span = max(0.0, last_end - first_start)

    # Severe collapse: many words squeezed to tiny window.
    if len(aligned_words) >= 4 and span <= min(0.35, duration * 0.08):
        return True

    # End-collapsed pattern (common failure mode from ASR word timestamps).
    if len(aligned_words) >= 4 and first_start >= duration * 0.85 and last_end >= duration * 0.98:
        return True

    return False


def align_words_robust(
    raw_text: str,
    raw_words: list[dict[str, Any]],
    duration_sec: float,
    speech_segments: list[tuple[float, float]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    segments = _normalize_speech_segments(speech_segments, duration_sec)
    raw_tokens = _tokens_from_raw_words(raw_words)
    fallback_tokens = raw_tokens or split_words(raw_text)

    if not raw_words:
        if segments:
            return _fallback_segment_alignment(split_words(raw_text), duration_sec, segments), "fallback_speech_segments"
        return _fallback_even_alignment(raw_text, duration_sec), "fallback_even_alignment"

    has_any_timestamps = any((w.get("start_sec") is not None or w.get("end_sec") is not None) for w in raw_words)
    if not has_any_timestamps:
        if fallback_tokens and segments:
            return _fallback_segment_alignment(fallback_tokens, duration_sec, segments), "fallback_speech_segments"
        return _fallback_even_alignment_tokens(fallback_tokens, duration_sec), "fallback_even_alignment"

    aligned = _stabilize_timestamps(raw_words, duration_sec)
    if aligned and not _timestamps_look_unreliable(aligned, duration_sec, segments):
        return aligned, "model_word_timestamps_stabilized"

    if fallback_tokens and segments:
        segment_aligned = _fallback_segment_alignment(fallback_tokens, duration_sec, segments)
        if segment_aligned:
            return segment_aligned, "fallback_speech_segments"

    if aligned:
        return aligned, "model_word_timestamps_stabilized"

    return _fallback_even_alignment_tokens(fallback_tokens, duration_sec), "fallback_even_alignment"


def timestamps_need_repair(
    words: list[dict[str, Any]],
    duration_sec: float,
    speech_segments: list[tuple[float, float]] | None = None,
) -> bool:
    return _timestamps_look_unreliable(words, duration_sec, speech_segments)
