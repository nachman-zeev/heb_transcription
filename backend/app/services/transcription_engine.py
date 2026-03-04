from __future__ import annotations

import json
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from app.core.config import get_settings
from app.services.hebrew_text import split_words


@dataclass
class ChannelTranscript:
    text: str
    payload: dict[str, Any]
    words: list[dict[str, Any]]
    audio_duration_sec: float
    speech_segments: list[tuple[float, float]]


class IvritWhisperEngine:
    _SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)")
    _SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9]+(?:\.[0-9]+)?)")

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.settings = get_settings()
        self._pipe = None
        self._has_cuda = False
        self._dtype = torch.float32

    def _ensure_loaded(self) -> None:
        if self._pipe is not None:
            return

        self._has_cuda = bool(torch.cuda.is_available())
        self._dtype = torch.float16 if self._has_cuda else torch.float32
        device = "cuda:0" if self._has_cuda else "cpu"

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            torch_dtype=self._dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        processor = AutoProcessor.from_pretrained(self.model_id)
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=self._dtype,
            device=device,
        )

    def _inference_batch_size(self) -> int:
        if self._has_cuda:
            return max(1, int(self.settings.asr_batch_size_gpu))
        return max(1, int(self.settings.asr_batch_size_cpu))

    def _words_look_collapsed(self, words: list[dict[str, Any]], duration_sec: float) -> bool:
        if len(words) < 4:
            return False

        pairs = []
        for w in words:
            s = w.get("start_sec")
            e = w.get("end_sec")
            if s is None and e is None:
                continue
            s_val = float(s or 0.0)
            e_val = float(e if e is not None else s_val)
            if e_val < s_val:
                e_val = s_val
            pairs.append((round(s_val, 3), round(e_val, 3)))

        if len(pairs) < 3:
            return True

        unique_pairs = set(pairs)
        starts = [p[0] for p in pairs]
        ends = [p[1] for p in pairs]
        span = max(ends) - min(starts)
        duration = max(float(duration_sec or 0.0), 0.001)

        if len(unique_pairs) <= 2 and span <= max(0.35, duration * 0.08):
            return True
        if min(starts) >= duration * 0.85:
            return True
        return False

    def _words_from_segment_chunks(self, chunks: list[dict[str, Any]], duration_sec: float) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        idx = 0
        duration = max(float(duration_sec or 0.0), 0.001)
        for chunk in chunks:
            ts = chunk.get("timestamp")
            if not (isinstance(ts, (list, tuple)) and len(ts) == 2 and ts[0] is not None and ts[1] is not None):
                continue

            seg_start = max(0.0, min(duration, float(ts[0])))
            seg_end = max(0.0, min(duration, float(ts[1])))
            if seg_end <= seg_start:
                continue

            tokens = split_words(str(chunk.get("text") or ""))
            if not tokens:
                continue

            slot = (seg_end - seg_start) / len(tokens)
            for i, token in enumerate(tokens):
                start = seg_start + (i * slot)
                end = seg_start + ((i + 1) * slot)
                if end <= start:
                    end = min(seg_end, start + 0.04)

                out.append(
                    {
                        "seq": idx,
                        "text": token,
                        "start_sec": round(start, 6),
                        "end_sec": round(end, 6),
                    }
                )
                idx += 1
        return out

    def _words_from_word_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        words: list[dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            ts = chunk.get("timestamp")
            token = str(chunk.get("text") or "").strip()
            if not token:
                continue

            start_sec = None
            end_sec = None
            if isinstance(ts, (list, tuple)) and len(ts) == 2:
                start_sec = float(ts[0]) if ts[0] is not None else None
                end_sec = float(ts[1]) if ts[1] is not None else None

            words.append(
                {
                    "seq": idx,
                    "text": token,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                }
            )
        return words

    def _run_word_pass(
        self,
        audio_path: Path,
        *,
        chunk_length_s: float,
        batch_size: int,
        stride_length_s: float | None = None,
        num_beams: int | None = None,
    ) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
        generate_kwargs: dict[str, Any] = {"language": "he", "task": "transcribe"}
        if num_beams is not None:
            generate_kwargs["num_beams"] = int(max(1, num_beams))

        kwargs: dict[str, Any] = {
            "generate_kwargs": generate_kwargs,
            "return_timestamps": "word",
            "chunk_length_s": max(5.0, float(chunk_length_s)),
            "batch_size": max(1, int(batch_size)),
        }
        if stride_length_s is not None:
            kwargs["stride_length_s"] = max(0.5, float(stride_length_s))

        result = self._pipe(str(audio_path), **kwargs)
        text = (result.get("text") or "").strip()
        words = self._words_from_word_chunks(result.get("chunks") or [])
        return result, text, words

    def _timing_anomaly_stats(self, words: list[dict[str, Any]], duration_sec: float) -> dict[str, float]:
        duration = max(float(duration_sec or 0.0), 0.001)
        if not words:
            return {
                "word_count": 0.0,
                "long_words_ge_2_5": 0.0,
                "very_long_words_ge_5": 0.0,
                "huge_words_ge_10": 0.0,
                "long_word_ratio": 1.0,
                "max_word_duration_sec": 0.0,
                "coverage_ratio": 0.0,
            }

        spans: list[float] = []
        first_start = None
        last_end = None
        for w in words:
            s = w.get("start_sec")
            e = w.get("end_sec")
            if s is None and e is None:
                continue
            s_val = float(s or 0.0)
            e_val = float(e if e is not None else s_val)
            if e_val < s_val:
                e_val = s_val
            spans.append(max(0.0, e_val - s_val))
            first_start = s_val if first_start is None else min(first_start, s_val)
            last_end = e_val if last_end is None else max(last_end, e_val)

        if not spans:
            return {
                "word_count": float(len(words)),
                "long_words_ge_2_5": 0.0,
                "very_long_words_ge_5": 0.0,
                "huge_words_ge_10": 0.0,
                "long_word_ratio": 0.0,
                "max_word_duration_sec": 0.0,
                "coverage_ratio": 0.0,
            }

        long_2_5 = sum(1 for d in spans if d >= 2.5)
        long_5 = sum(1 for d in spans if d >= 5.0)
        long_10 = sum(1 for d in spans if d >= 10.0)
        coverage = 0.0
        if first_start is not None and last_end is not None:
            coverage = max(0.0, min(1.0, (last_end - first_start) / duration))

        return {
            "word_count": float(len(words)),
            "long_words_ge_2_5": float(long_2_5),
            "very_long_words_ge_5": float(long_5),
            "huge_words_ge_10": float(long_10),
            "long_word_ratio": float(long_2_5) / float(max(1, len(spans))),
            "max_word_duration_sec": float(max(spans)),
            "coverage_ratio": float(coverage),
        }

    def _needs_refined_pass(self, words: list[dict[str, Any]], duration_sec: float) -> bool:
        stats = self._timing_anomaly_stats(words, duration_sec)
        if int(stats["word_count"]) <= 0:
            return True
        if stats["huge_words_ge_10"] >= 1:
            return True
        if stats["very_long_words_ge_5"] >= 2:
            return True
        if stats["long_word_ratio"] >= 0.06 and stats["word_count"] >= 40:
            return True
        if stats["coverage_ratio"] <= 0.45 and stats["word_count"] >= 30:
            return True
        return False

    def _candidate_quality_score(self, words: list[dict[str, Any]], text: str, duration_sec: float) -> float:
        stats = self._timing_anomaly_stats(words, duration_sec)
        text_tokens = len(split_words(text))
        score = 0.0
        score += float(stats["word_count"])
        score += min(float(text_tokens), 400.0) * 0.25
        score -= float(stats["long_words_ge_2_5"]) * 2.0
        score -= float(stats["very_long_words_ge_5"]) * 4.0
        score -= float(stats["huge_words_ge_10"]) * 10.0
        score -= max(0.0, (0.50 - float(stats["coverage_ratio"]))) * 80.0
        return score

    def _probe_duration(self, audio_path: Path) -> float:
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

    def _extract_channel_wav(self, input_file: Path, channel_index: int) -> Path:
        temp = tempfile.NamedTemporaryFile(prefix="ch_", suffix=".wav", delete=False)
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

    def _detect_speech_segments(self, audio_path: Path, duration_sec: float) -> list[tuple[float, float]]:
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
            start_match = self._SILENCE_START_RE.search(line)
            if start_match:
                open_silence_start = max(0.0, min(duration, float(start_match.group(1))))
                continue

            end_match = self._SILENCE_END_RE.search(line)
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

    def transcribe_channel(self, input_file: Path, channel_index: int) -> ChannelTranscript:
        self._ensure_loaded()
        wav_path = self._extract_channel_wav(input_file, channel_index)
        audio_duration_sec = self._probe_duration(wav_path)
        speech_segments = self._detect_speech_segments(wav_path, audio_duration_sec)
        segment_result = None
        refined_result = None
        text = ""
        words: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        selected_pass = "primary_word"
        quality_diagnostics: dict[str, Any] = {"passes": []}
        resource_peak = {"cpu_percent": 0.0, "ram_percent": 0.0}
        resource_error = ""

        stop_sampler = threading.Event()

        def _sample_resources() -> None:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                return
            while not stop_sampler.is_set():
                try:
                    resource_peak["cpu_percent"] = max(resource_peak["cpu_percent"], float(psutil.cpu_percent(interval=None)))
                    resource_peak["ram_percent"] = max(resource_peak["ram_percent"], float(psutil.virtual_memory().percent))
                except Exception:
                    break
                time.sleep(0.25)

        sampler = threading.Thread(target=_sample_resources, daemon=True)
        sampler.start()

        try:
            primary_chunk = max(5.0, float(self.settings.asr_chunk_length_sec))
            if not self._has_cuda:
                # On CPU, smaller chunks reduce RAM spikes and limit long-context drift.
                primary_chunk = min(primary_chunk, 20.0)
            primary_batch = self._inference_batch_size()
            result, text, words = self._run_word_pass(
                wav_path,
                chunk_length_s=primary_chunk,
                batch_size=primary_batch,
            )
            primary_score = self._candidate_quality_score(words, text, audio_duration_sec)
            quality_diagnostics["passes"].append(
                {
                    "name": "primary_word",
                    "chunk_length_s": primary_chunk,
                    "batch_size": primary_batch,
                    "word_count": len(words),
                    "score": round(primary_score, 3),
                    "timing_stats": self._timing_anomaly_stats(words, audio_duration_sec),
                }
            )

            needs_refine = self._words_look_collapsed(words, audio_duration_sec) or self._needs_refined_pass(words, audio_duration_sec)
            if needs_refine:
                try:
                    refined_chunk = max(8.0, min(18.0, primary_chunk * 0.6))
                    refined_batch = 1 if not self._has_cuda else max(1, min(2, primary_batch))
                    refined_stride = max(2.0, min(6.0, refined_chunk * 0.3))
                    refined_result, refined_text, refined_words = self._run_word_pass(
                        wav_path,
                        chunk_length_s=refined_chunk,
                        batch_size=refined_batch,
                        stride_length_s=refined_stride,
                        num_beams=4,
                    )
                    refined_score = self._candidate_quality_score(refined_words, refined_text, audio_duration_sec)
                    quality_diagnostics["passes"].append(
                        {
                            "name": "refined_word",
                            "chunk_length_s": refined_chunk,
                            "batch_size": refined_batch,
                            "stride_length_s": refined_stride,
                            "num_beams": 4,
                            "word_count": len(refined_words),
                            "score": round(refined_score, 3),
                            "timing_stats": self._timing_anomaly_stats(refined_words, audio_duration_sec),
                        }
                    )

                    if refined_score > (primary_score + 1.5):
                        result = refined_result
                        text = refined_text
                        words = refined_words
                        selected_pass = "refined_word"
                        primary_score = refined_score
                except Exception as exc:
                    quality_diagnostics["refined_error"] = str(exc)

            if self._words_look_collapsed(words, audio_duration_sec):
                try:
                    segment_result = self._pipe(
                        str(wav_path),
                        generate_kwargs={"language": "he", "task": "transcribe"},
                        return_timestamps=True,
                        chunk_length_s=max(12.0, min(20.0, float(self.settings.asr_chunk_length_sec))),
                        batch_size=1 if not self._has_cuda else max(1, min(2, self._inference_batch_size())),
                    )
                    segment_chunks = segment_result.get("chunks") or []
                    segment_words = self._words_from_segment_chunks(segment_chunks, audio_duration_sec)
                    if segment_words:
                        segment_text = (segment_result.get("text") or text).strip()
                        segment_score = self._candidate_quality_score(segment_words, segment_text, audio_duration_sec)
                        quality_diagnostics["passes"].append(
                            {
                                "name": "segment_fallback",
                                "word_count": len(segment_words),
                                "score": round(segment_score, 3),
                                "timing_stats": self._timing_anomaly_stats(segment_words, audio_duration_sec),
                            }
                        )
                        if segment_score > (primary_score + 1.0):
                            words = segment_words
                            text = segment_text
                            selected_pass = "segment_fallback"
                            primary_score = segment_score
                except Exception as exc:
                    quality_diagnostics["segment_error"] = str(exc)
        except Exception:
            raise
        finally:
            stop_sampler.set()
            try:
                sampler.join(timeout=0.5)
            except Exception as exc:
                resource_error = str(exc)
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)

        payload = {
            "model_id": self.model_id,
            "language": "he",
            "task": "transcribe",
            "chunk_length_s": max(5.0, float(self.settings.asr_chunk_length_sec)),
            "batch_size": self._inference_batch_size(),
            "selected_pass": selected_pass,
            "quality_diagnostics": quality_diagnostics,
            "resource_peak": resource_peak,
            "resource_sampling_error": resource_error or None,
            "raw": result,
            "raw_refined": refined_result or None,
            "raw_segments": segment_result or None,
        }
        return ChannelTranscript(
            text=text,
            payload=payload,
            words=words,
            audio_duration_sec=audio_duration_sec,
            speech_segments=speech_segments,
        )
