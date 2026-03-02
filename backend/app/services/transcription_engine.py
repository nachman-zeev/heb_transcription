from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from app.core.config import get_settings


@dataclass
class ChannelTranscript:
    text: str
    payload: dict[str, Any]
    words: list[dict[str, Any]]
    audio_duration_sec: float


class IvritWhisperEngine:
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

    def transcribe_channel(self, input_file: Path, channel_index: int) -> ChannelTranscript:
        self._ensure_loaded()
        wav_path = self._extract_channel_wav(input_file, channel_index)
        audio_duration_sec = self._probe_duration(wav_path)

        try:
            result = self._pipe(
                str(wav_path),
                generate_kwargs={"language": "he", "task": "transcribe"},
                return_timestamps="word",
                chunk_length_s=max(5.0, float(self.settings.asr_chunk_length_sec)),
                batch_size=self._inference_batch_size(),
            )
        finally:
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)

        text = (result.get("text") or "").strip()
        chunks = result.get("chunks") or []
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

        payload = {
            "model_id": self.model_id,
            "language": "he",
            "task": "transcribe",
            "chunk_length_s": max(5.0, float(self.settings.asr_chunk_length_sec)),
            "batch_size": self._inference_batch_size(),
            "raw": result,
        }
        return ChannelTranscript(
            text=text,
            payload=payload,
            words=words,
            audio_duration_sec=audio_duration_sec,
        )
