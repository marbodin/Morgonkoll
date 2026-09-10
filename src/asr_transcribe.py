"""Isolated faster-whisper worker used to avoid TTS/ASR runtime conflicts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional


def transcribe(paths: List[Path], model_name: str) -> Dict[str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "ASR requested but faster-whisper is not installed; install .[asr]"
        ) from exc
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
    )
    results: Dict[str, str] = {}
    for path in paths:
        segments, _ = model.transcribe(
            str(path),
            language="sv",
            beam_size=5,
            vad_filter=True,
        )
        results[str(path)] = " ".join(
            segment.text.strip() for segment in segments
        ).strip()
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = transcribe(args.audio, model_name=args.model)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

