"""Validate final MP3 codec/container/tag compatibility for Telegram audio upload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from .audio import verify_telegram_audio
from .errors import AudioProcessingError


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_telegram_audio(args.audio)
    except AudioProcessingError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Container/codec checks passed. No Telegram delivery was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

