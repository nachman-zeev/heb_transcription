#!/usr/bin/env python3
"""
Transcribe Hebrew audio files with ivrit-ai/whisper-large-v3.

Default behavior:
- language locked to Hebrew ("he")
- sequential processing (safe on CPU-only machines)
- supports .mp3 and .wav
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from typing import Iterable, List

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


SUPPORTED_EXTENSIONS = {".mp3", ".wav"}
DEFAULT_MODEL_ID = "ivrit-ai/whisper-large-v3"


def discover_audio_files(input_path: pathlib.Path, recursive: bool) -> List[pathlib.Path]:
    if input_path.is_file():
        if input_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [input_path]
        return []

    if not input_path.is_dir():
        return []

    pattern_iter: Iterable[pathlib.Path]
    pattern_iter = input_path.rglob("*") if recursive else input_path.glob("*")
    return sorted(
        p for p in pattern_iter if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def make_pipeline(model_id: str):
    has_cuda = torch.cuda.is_available()
    device = "cuda:0" if has_cuda else "cpu"
    dtype = torch.float16 if has_cuda else torch.float32

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    processor = AutoProcessor.from_pretrained(model_id)
    asr = pipeline(
        task="automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=dtype,
        device=device,
    )
    return asr, device, str(dtype)


def save_result(
    output_dir: pathlib.Path,
    model_id: str,
    audio_path: pathlib.Path,
    elapsed_sec: float,
    result: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = audio_path.stem
    out_json = output_dir / f"{stem}.json"
    out_txt = output_dir / f"{stem}.txt"

    text = (result.get("text") or "").strip()
    payload = {
        "model_id": model_id,
        "audio_path": str(audio_path),
        "elapsed_sec": round(elapsed_sec, 3),
        "text": text,
        "chunks": result.get("chunks", []),
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_txt.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe Hebrew audio with ivrit-ai/whisper-large-v3.")
    parser.add_argument("--input-path", required=True, help="Audio file path or directory path")
    parser.add_argument(
        "--output-dir",
        default="data/transcriptions/ivrit_whisper_large_v3",
        help="Directory for transcript outputs",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="ASR model id (default is the project primary model)",
    )
    parser.add_argument("--recursive", action="store_true", help="Recursively scan directories")
    parser.add_argument("--max-files", type=int, default=0, help="0 means all files")
    parser.add_argument(
        "--timestamps",
        choices=["none", "segment", "word"],
        default="segment",
        help="Timestamp granularity",
    )
    args = parser.parse_args()

    input_path = pathlib.Path(args.input_path)
    output_dir = pathlib.Path(args.output_dir)

    files = discover_audio_files(input_path, recursive=args.recursive)
    if not files:
        print(f"No supported audio files found in: {input_path}")
        return 2

    if args.max_files > 0:
        files = files[: args.max_files]

    asr, device, dtype = make_pipeline(args.model_id)
    print(f"Model loaded: {args.model_id}")
    print(f"Device: {device}")
    print(f"DType: {dtype}")
    print(f"Files to process: {len(files)}")

    ts_arg = None if args.timestamps == "none" else args.timestamps
    for i, audio_path in enumerate(files, start=1):
        started = time.time()
        result = asr(
            str(audio_path),
            generate_kwargs={"language": "he", "task": "transcribe"},
            return_timestamps=ts_arg,
        )
        elapsed = time.time() - started
        save_result(output_dir, args.model_id, audio_path, elapsed, result)
        text = (result.get("text") or "").strip()
        print(f"[{i}/{len(files)}] done: {audio_path.name} | elapsed={elapsed:.2f}s | chars={len(text)}")

    print(f"Completed. Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
