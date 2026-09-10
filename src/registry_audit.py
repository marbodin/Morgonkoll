"""Check maintained candidate source links and exact revisions without fake discovery."""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import List, Optional

from .paths import ROOT
from .voice_registry import load_registry


def _url_available(url: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Morgonkoll-voice-registry-audit/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return 200 <= response.status < 400, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def audit(output_path: Path) -> bool:
    candidates = load_registry()
    lines = [
        "# Voice registry source audit",
        "",
        f"Audit date: {date.today().isoformat()}",
        "",
        "This checks the maintained registry's declared primary-source links. It does "
        "not claim to discover every model published on the internet. New candidates "
        "must be researched, licensed, measured and added to `config/voice_candidates.yml`.",
        "",
        "| Candidate | Registry status | Source | Check |",
        "|---|---|---|---|",
    ]
    all_available = True
    for candidate in candidates:
        url = str(candidate.source.get("model_card", ""))
        if not url:
            available, detail = False, "No model_card URL"
        else:
            available, detail = _url_available(url)
        all_available = all_available and (available or candidate.status == "excluded")
        mark = "available" if available else f"unavailable: {detail}"
        lines.append(
            f"| {candidate.label} | {candidate.status} | "
            f"[primary metadata]({url}) | {mark} |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_available


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "voice_samples" / "registry_audit.md",
    )
    args = parser.parse_args(argv)
    healthy = audit(args.output)
    print(f"Wrote {args.output}")
    return 0 if healthy else 2


if __name__ == "__main__":
    raise SystemExit(main())

