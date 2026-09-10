"""Project path helpers."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def cache_dir() -> Path:
    configured = os.environ.get("MORGONKOLL_CACHE_DIR")
    path = Path(configured).expanduser() if configured else ROOT / ".cache"
    path.mkdir(parents=True, exist_ok=True)
    return path

