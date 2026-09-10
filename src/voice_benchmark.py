"""Benchmark registered free Swedish voices and optionally persist the winner."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .audio import assemble_episode
from .benchmark_metrics import inspect_sample, score_candidate
from .chunking import semantic_chunks
from .engines import create_engine
from .engines.base import VoiceEngine
from .models import BenchmarkResult, Candidate
from .paths import ROOT
from .pronunciation import apply_pronunciations
from .voice_registry import (
    AUTOMATIC_PATH,
    SELECTED_PATH,
    discover_candidates,
    load_registry,
    load_selected,
    registry_by_id,
    restore_automatic_selection,
    save_selection,
)


BENCHMARK_TEXT_PATH = ROOT / "benchmark" / "swedish_benchmark.txt"
DEFAULT_OUTPUT_DIR = ROOT / "voice_samples"
EngineFactory = Callable[[Candidate], VoiceEngine]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _candidate_letter(index: int) -> str:
    if index >= 26:
        return str(index + 1)
    return chr(ord("A") + index)


def benchmark_candidate(
    candidate: Candidate,
    benchmark_text: str,
    output_path: Path,
    engine_factory: EngineFactory = create_engine,
    transcriber: Optional[Callable[[Path], str]] = None,
) -> BenchmarkResult:
    engine: Optional[VoiceEngine] = None
    started = time.monotonic()
    try:
        engine = engine_factory(candidate)
        engine.prepare()
        narration = apply_pronunciations(benchmark_text, engine=candidate.engine)
        chunks = semantic_chunks(narration, max_chars=260)
        with tempfile.TemporaryDirectory(prefix=f"benchmark-{candidate.id}-") as temporary:
            working = Path(temporary)
            raw_dir = working / "raw"
            raw_dir.mkdir()
            segment_paths: List[Path] = []
            synthesis_started = time.monotonic()
            for chunk in chunks:
                segment_path = raw_dir / f"{chunk.index:04d}.wav"
                engine.synthesize(chunk.text, segment_path)
                segment_paths.append(segment_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            assemble_episode(
                segment_paths=segment_paths,
                chunks=chunks,
                output_path=output_path,
                working_dir=working / "audio",
                title=f"Morgonkoll voice sample - {candidate.label}",
                show_title="Morgonkoll voice audition",
                episode_date=date.today().isoformat(),
                voice_attribution=(
                    f"Voice: {candidate.label}; model license: {candidate.license}"
                ),
            )
            generation_seconds = time.monotonic() - synthesis_started

        transcription = transcriber(output_path) if transcriber is not None else None
        metrics = inspect_sample(
            output_path,
            reference_text=benchmark_text,
            spoken_text=narration,
            transcription=transcription,
        )
        total, breakdown = score_candidate(candidate, metrics, generation_seconds)
        return BenchmarkResult(
            candidate=candidate,
            sample_path=output_path,
            generated=True,
            generation_seconds=generation_seconds,
            metrics=metrics,
            weighted_score=total,
            score_breakdown=breakdown,
        )
    except Exception as exc:
        return BenchmarkResult(
            candidate=candidate,
            sample_path=None,
            generated=False,
            generation_seconds=time.monotonic() - started,
            metrics=None,
            weighted_score=0.0,
            score_breakdown={},
            error=str(exc),
        )
    finally:
        if engine is not None:
            engine.close()
        gc.collect()


def _result_payload(result: BenchmarkResult) -> Dict[str, object]:
    metrics = result.metrics.__dict__ if result.metrics else None
    return {
        "candidate_id": result.candidate.id,
        "label": result.candidate.label,
        "engine": result.candidate.engine,
        "model": result.candidate.model,
        "voice": result.candidate.voice,
        "license": result.candidate.license,
        "generated": result.generated,
        "sample": _display_path(result.sample_path) if result.sample_path else None,
        "generation_seconds": round(result.generation_seconds, 3),
        "weighted_score": round(result.weighted_score, 3),
        "score_breakdown": {
            key: round(value, 3) for key, value in result.score_breakdown.items()
        },
        "metrics": metrics,
        "error": result.error,
    }


def write_report(
    results: List[BenchmarkResult],
    output_dir: Path,
    benchmark_text_path: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    successful = sorted(
        (result for result in results if result.generated),
        key=lambda result: result.weighted_score,
        reverse=True,
    )
    selected_id = str(load_selected().get("candidate_id", ""))
    selected_result = next(
        (result for result in successful if result.candidate.id == selected_id), None
    )
    lines = [
        "# Morgonkoll voice comparison",
        "",
        f"Benchmark date: {date.today().isoformat()}  ",
        f"Fixed script: `{_display_path(benchmark_text_path)}`",
        "",
        "## Important limit",
        "",
        "The automatic score is an engineering filter, not a claim that software can "
        "measure whether a voice is warm, natural or pleasant. Naturalness, prosody "
        "and pleasantness use documented capability plus the maintained registry "
        "assessment. Generated-audio checks measure pacing, clipping, silence, "
        "consistency, reliability and runtime. Optional Swedish ASR can add a "
        "pronunciation/intelligibility signal, but ASR errors are not automatically "
        "TTS errors. Listen before changing the production voice.",
        "",
        "## Results",
        "",
        f"Current configured voice: `{selected_id}`",
        "",
        "| Candidate | Voice | Score / 10 | Duration | WPM | Runtime | ASR similarity | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for index, result in enumerate(results):
        letter = _candidate_letter(index)
        if result.generated and result.metrics:
            asr = (
                f"{result.metrics.transcription_similarity:.1%}"
                if result.metrics.transcription_similarity is not None
                else "not run"
            )
            lines.append(
                f"| Candidate {letter} | {result.candidate.label} | "
                f"{result.weighted_score:.2f} | {result.metrics.duration_seconds:.1f}s | "
                f"{result.metrics.words_per_minute:.1f} | "
                f"{result.generation_seconds:.1f}s | {asr} | generated |"
            )
        else:
            lines.append(
                f"| Candidate {letter} | {result.candidate.label} | - | - | - | "
                f"{result.generation_seconds:.1f}s | - | failed/skipped |"
            )
    lines.extend(["", "## Samples", ""])
    for index, result in enumerate(results):
        letter = _candidate_letter(index)
        if result.sample_path:
            lines.append(
                f"- **Candidate {letter}: {result.candidate.label}** - "
                f"`{result.sample_path.name}` ({result.candidate.license})"
            )
        else:
            lines.append(
                f"- **Candidate {letter}: {result.candidate.label}** - unavailable: "
                f"{result.error}"
            )
    if successful:
        recommendation = successful[0]
        if selected_result is None:
            comparison = (
                "The current configured voice did not complete this run, so no automatic "
                "replacement is safe. Inspect the failure and listen to successful samples."
            )
        else:
            delta = recommendation.weighted_score - selected_result.weighted_score
            if recommendation.candidate.id == selected_id:
                comparison = "The current configured voice remains the engineering-score leader."
            elif delta >= 0.35:
                comparison = (
                    f"{recommendation.candidate.label} scored {delta:.2f} points above "
                    "the current voice. Treat this as a recommendation to audition, not "
                    "permission to replace the stable voice automatically."
                )
            else:
                comparison = (
                    f"The leading alternative is only {delta:.2f} points above the current "
                    "voice, which is not clear evidence of a meaningful improvement."
                )
        lines.extend(
            [
                "",
                "## Automatic recommendation",
                "",
                f"Highest successful engineering score: **{successful[0].candidate.label}** "
                f"({successful[0].weighted_score:.2f}/10). This recommendation is only "
                "eligible for automatic persistence when the candidate is marked "
                "`production` for the minimum GitHub runner.",
                "",
                comparison,
                "",
                "**Listen to the samples and choose the voice you like most.**",
            ]
        )

    report_path = output_dir / "comparison_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "comparison_report.json").write_text(
        json.dumps(
            {
                "benchmark_date": date.today().isoformat(),
                "benchmark_text": _display_path(benchmark_text_path),
                "results": [_result_payload(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return report_path


def run_benchmark(
    candidates: Iterable[Candidate],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    with_asr: bool = False,
    asr_model: str = "small",
    runner_ram_gb: float = 8.0,
    engine_factory: EngineFactory = create_engine,
) -> List[BenchmarkResult]:
    benchmark_text = BENCHMARK_TEXT_PATH.read_text(encoding="utf-8").strip()
    chosen = list(candidates)
    results: List[BenchmarkResult] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_sample in output_dir.glob("candidate-*.mp3"):
        stale_sample.unlink()
    for index, candidate in enumerate(chosen):
        letter = _candidate_letter(index)
        output_path = output_dir / f"candidate-{letter}_{candidate.id}.mp3"
        if candidate.minimum_ram_gb > runner_ram_gb:
            results.append(
                BenchmarkResult(
                    candidate=candidate,
                    sample_path=None,
                    generated=False,
                    generation_seconds=0.0,
                    metrics=None,
                    weighted_score=0.0,
                    score_breakdown={},
                    error=(
                        f"Registry requires {candidate.minimum_ram_gb:.1f} GB RAM; "
                        f"benchmark envelope is {runner_ram_gb:.1f} GB"
                    ),
                )
            )
            continue
        result = benchmark_candidate(
            candidate,
            benchmark_text=benchmark_text,
            output_path=output_path,
            engine_factory=engine_factory,
            transcriber=None,
        )
        results.append(result)
    if with_asr:
        successful = [result for result in results if result.generated and result.sample_path]
        if successful:
            with tempfile.TemporaryDirectory(prefix="morgonkoll-asr-") as temporary:
                transcription_path = Path(temporary) / "transcriptions.json"
                command = [
                    sys.executable,
                    "-m",
                    "src.asr_transcribe",
                    "--model",
                    asr_model,
                    "--output",
                    str(transcription_path),
                    *[str(result.sample_path) for result in successful],
                ]
                completed = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        "Isolated ASR failed: " + completed.stderr.strip()[-2000:]
                    )
                transcriptions = json.loads(
                    transcription_path.read_text(encoding="utf-8")
                )
            for result in successful:
                assert result.sample_path is not None
                narration = apply_pronunciations(
                    benchmark_text, engine=result.candidate.engine
                )
                result.metrics = inspect_sample(
                    result.sample_path,
                    reference_text=benchmark_text,
                    spoken_text=narration,
                    transcription=str(transcriptions[str(result.sample_path)]),
                )
                result.weighted_score, result.score_breakdown = score_candidate(
                    result.candidate,
                    result.metrics,
                    result.generation_seconds,
                )
    write_report(results, output_dir=output_dir, benchmark_text_path=BENCHMARK_TEXT_PATH)
    return results


def _print_registry(candidates: Iterable[Candidate]) -> None:
    print("ID\tSTATUS\tENGINE\tMODEL\tLICENSE\tRAM_GB")
    for candidate in candidates:
        print(
            f"{candidate.id}\t{candidate.status}\t{candidate.engine}\t"
            f"{candidate.model}\t{candidate.license}\t{candidate.minimum_ram_gb:g}"
        )
        if candidate.excluded_reason:
            print(f"  excluded: {candidate.excluded_reason}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("automatic", "audition"),
        default="automatic",
        help="Automatic uses production-safe candidates; audition also includes heavier viable candidates",
    )
    parser.add_argument("--candidate", action="append", dest="candidate_ids")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--with-asr", action="store_true")
    parser.add_argument("--asr-model", default="small")
    parser.add_argument("--runner-ram-gb", type=float, default=8.0)
    parser.add_argument(
        "--no-select",
        action="store_true",
        help="Generate samples and reports without changing selected_voice.json",
    )
    parser.add_argument("--list", action="store_true", dest="list_candidates")
    parser.add_argument("--restore-automatic", action="store_true")
    args = parser.parse_args(argv)

    if args.restore_automatic:
        restore_automatic_selection()
        print(f"Restored {SELECTED_PATH} from {AUTOMATIC_PATH}")
        return 0
    all_candidates = load_registry()
    if args.list_candidates:
        _print_registry(all_candidates)
        return 0

    if args.candidate_ids:
        indexed = registry_by_id(all_candidates)
        missing = [candidate_id for candidate_id in args.candidate_ids if candidate_id not in indexed]
        if missing:
            parser.error(f"Unknown candidate(s): {', '.join(missing)}")
        candidates = [indexed[candidate_id] for candidate_id in args.candidate_ids]
    else:
        candidates = discover_candidates(args.mode)

    results = run_benchmark(
        candidates,
        output_dir=args.output_dir,
        with_asr=args.with_asr,
        asr_model=args.asr_model,
        runner_ram_gb=args.runner_ram_gb,
    )
    successful = sorted(
        (
            result
            for result in results
            if result.generated and result.candidate.automatic_eligible
        ),
        key=lambda result: result.weighted_score,
        reverse=True,
    )
    if not args.no_select:
        if not successful:
            print("No production-safe candidate completed; selection was not changed.")
            return 2
        winner = successful[0]
        fallback_ids = [result.candidate.id for result in successful[1:]]
        reason = (
            f"Automatic benchmark winner at {winner.weighted_score:.2f}/10 among "
            "production-safe candidates. Subjective listening remains recommended; "
            f"see {_display_path(args.output_dir / 'comparison_report.md')}."
        )
        for path in (SELECTED_PATH, AUTOMATIC_PATH):
            save_selection(
                winner.candidate,
                reason=reason,
                fallback_ids=fallback_ids,
                benchmark_date=date.today().isoformat(),
                path=path,
            )
        print(f"Selected {winner.candidate.id}; fallback order: {fallback_ids}")

    print(f"Samples and report: {args.output_dir}")
    return 0 if any(result.generated for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
