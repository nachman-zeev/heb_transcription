from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiarizationResult:
    words: list[dict]
    status: str
    payload: dict


def _channel_based(words: list[dict], channel_index: int) -> DiarizationResult:
    speaker = f"spk_ch_{channel_index + 1}"
    out = []
    for item in words:
        n = dict(item)
        n["speaker_label"] = speaker
        n["speaker_confidence"] = 1.0
        out.append(n)

    payload = {
        "mode": "channel_based",
        "speakers": [speaker],
        "segments": [
            {
                "speaker": speaker,
                "start_sec": out[0]["start_sec"] if out else 0.0,
                "end_sec": out[-1]["end_sec"] if out else 0.0,
                "confidence": 1.0,
            }
        ],
    }
    return DiarizationResult(words=out, status="channel_based", payload=payload)


def _mono_pause_heuristic(words: list[dict]) -> DiarizationResult:
    if not words:
        return DiarizationResult(words=[], status="mono_no_words", payload={"mode": "mono_pause_heuristic", "segments": []})

    turns: list[tuple[int, int]] = []
    start_idx = 0
    for i in range(1, len(words)):
        gap = float(words[i]["start_sec"]) - float(words[i - 1]["end_sec"])
        if gap >= 1.2:
            turns.append((start_idx, i - 1))
            start_idx = i
    turns.append((start_idx, len(words) - 1))

    out = [dict(w) for w in words]
    segments = []
    for turn_idx, (a, b) in enumerate(turns):
        speaker = "spk_1" if turn_idx % 2 == 0 else "spk_2"
        confidence = 0.45
        for i in range(a, b + 1):
            out[i]["speaker_label"] = speaker
            out[i]["speaker_confidence"] = confidence
        segments.append(
            {
                "speaker": speaker,
                "start_sec": out[a]["start_sec"],
                "end_sec": out[b]["end_sec"],
                "confidence": confidence,
            }
        )

    payload = {
        "mode": "mono_pause_heuristic",
        "gap_threshold_sec": 1.2,
        "segments": segments,
    }
    return DiarizationResult(words=out, status="mono_pause_heuristic", payload=payload)


def diarize_words(words: list[dict], total_channels: int, channel_index: int) -> DiarizationResult:
    if total_channels > 1:
        return _channel_based(words, channel_index)
    return _mono_pause_heuristic(words)
