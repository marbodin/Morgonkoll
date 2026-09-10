"""Generate a normalized, tagged Morgonkoll MP3 from a Swedish source script."""

from __future__ import annotations

import argparse
import gc
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .audio import assemble_episode
from .chunking import semantic_chunks
from .engines import create_engine
from .engines.base import VoiceEngine
from .errors import MorgonkollError, VoiceUnavailableError
from .health_check import SAFE_FAILURE_MESSAGE
from .models import Candidate, HealthResult, PipelineResult
from .paths import ROOT
from .pronunciation import apply_pronunciations
from .voice_registry import resolve_voice_order


EngineFactory = Callable[[Candidate], VoiceEngine]


def run_pipeline(
    script_path: Path,
    output_path: Path,
    episode_date: str,
    title: Optional[str] = None,
    show_title: str = "Morgonkoll",
    cover_path: Optional[Path] = None,
    candidates: Optional[Iterable[Candidate]] = None,
    engine_factory: EngineFactory = create_engine,
    build_dir: Optional[Path] = None,
) -> PipelineResult:
    if not script_path.is_file():
        raise MorgonkollError(f"Source script does not exist: {script_path}")
    source_text = script_path.read_text(encoding="utf-8")
    if not source_text.strip():
        raise MorgonkollError(f"Source script is empty: {script_path}")

    ordered = list(candidates) if candidates is not None else resolve_voice_order()
    if not ordered:
        raise VoiceUnavailableError(SAFE_FAILURE_MESSAGE)
    workspace = build_dir or ROOT / "build"
    workspace.mkdir(parents=True, exist_ok=True)
    attempts: List[HealthResult] = []

    for candidate in ordered:
        started = time.monotonic()
        engine: Optional[VoiceEngine] = None
        try:
            engine = engine_factory(candidate)
            engine.prepare()
            narration = apply_pronunciations(source_text, engine=candidate.engine)
            chunks = semantic_chunks(narration, max_chars=260)
            with tempfile.TemporaryDirectory(
                prefix=f"{candidate.id}-", dir=str(workspace)
            ) as temporary:
                attempt_dir = Path(temporary)
                raw_dir = attempt_dir / "raw"
                raw_dir.mkdir()
                segments: List[Path] = []
                for chunk in chunks:
                    segment = raw_dir / f"{chunk.index:04d}.wav"
                    engine.synthesize(chunk.text, segment)
                    if not segment.is_file() or segment.stat().st_size < 128:
                        raise VoiceUnavailableError(
                            f"{candidate.label} produced an empty segment at index {chunk.index}"
                        )
                    segments.append(segment)

                narration_path = workspace / "narration.txt"
                narration_path.write_text(narration, encoding="utf-8")
                verification = assemble_episode(
                    segment_paths=segments,
                    chunks=chunks,
                    output_path=output_path,
                    working_dir=attempt_dir / "audio",
                    title=title or f"Morgonkoll {episode_date}",
                    show_title=show_title,
                    episode_date=episode_date,
                    voice_attribution=(
                        f"Voice: {candidate.label}; model license: {candidate.license}"
                    ),
                    cover_path=cover_path,
                )
            attempts.append(
                HealthResult(
                    candidate_id=candidate.id,
                    healthy=True,
                    detail="Full episode generated",
                    elapsed_seconds=time.monotonic() - started,
                )
            )
            return PipelineResult(
                output_path=output_path,
                candidate_id=candidate.id,
                duration_seconds=float(verification["duration_seconds"]),
                chunk_count=len(chunks),
                narration_path=narration_path,
                attempts=attempts,
            )
        except VoiceUnavailableError as exc:
            attempts.append(
                HealthResult(
                    candidate_id=candidate.id,
                    healthy=False,
                    detail=str(exc),
                    elapsed_seconds=time.monotonic() - started,
                )
            )
        finally:
            if engine is not None:
                engine.close()
            gc.collect()

    details = "; ".join(f"{item.candidate_id}: {item.detail}" for item in attempts)
    raise VoiceUnavailableError(f"{SAFE_FAILURE_MESSAGE} Attempts: {details}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--script",
        type=Path,
        default=ROOT / "content" / "script.txt",
        help="Human-readable Swedish source script",
    )
    parser.add_argument("--date", default=date.today().isoformat(), dest="episode_date")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--show-title", default="Morgonkoll")
    parser.add_argument("--cover", type=Path)
    args = parser.parse_args(argv)

    output = args.output or ROOT / "output" / f"morgonkoll-{args.episode_date}.mp3"
    try:
        result = run_pipeline(
            script_path=args.script,
            output_path=output,
            episode_date=args.episode_date,
            title=args.title,
            show_title=args.show_title,
            cover_path=args.cover,
        )
    except MorgonkollError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        f"Created {result.output_path} with {result.candidate_id}: "
        f"{result.chunk_count} chunks, {result.duration_seconds:.1f} seconds"
    )
    print(f"TTS narration copy: {result.narration_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
