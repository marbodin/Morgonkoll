"""ffmpeg-based segment preparation, normalization, tagging and validation."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .errors import AudioProcessingError
from .models import NarrationChunk


TARGET_SAMPLE_RATE = 44_100
TARGET_LUFS = -19.0
TRUE_PEAK_DB = -1.5
TARGET_LRA = 7.0
MP3_BITRATE = "128k"


def _require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise AudioProcessingError(f"Required executable {name!r} is not on PATH")
    return executable


def _run(command: List[str], description: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-3000:]
        raise AudioProcessingError(f"{description} failed: {detail}")
    return completed


def probe_audio(path: Path) -> Dict[str, Any]:
    ffprobe = _require_tool("ffprobe")
    completed = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        f"ffprobe inspection of {path}",
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AudioProcessingError(f"ffprobe returned invalid JSON for {path}") from exc


def _prepare_segment(
    source: Path,
    destination: Path,
    pause_after_ms: int,
) -> None:
    ffmpeg = _require_tool("ffmpeg")
    pause_seconds = max(0, pause_after_ms) / 1000.0
    filters = (
        "silenceremove="
        "start_periods=1:start_duration=0.03:start_threshold=-50dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.20:start_threshold=-50dB,"
        "areverse,"
        f"aresample={TARGET_SAMPLE_RATE},"
        "aformat=sample_fmts=s16:channel_layouts=mono,"
        f"apad=pad_dur={pause_seconds:.3f}"
    )
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            filters,
            "-ar",
            str(TARGET_SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        f"segment preparation for {source.name}",
    )


def _concat_file_line(path: Path) -> str:
    escaped = str(path.resolve()).replace("'", "'\\''")
    return f"file '{escaped}'"


def _concatenate(prepared_paths: Iterable[Path], list_path: Path, output_path: Path) -> None:
    paths = list(prepared_paths)
    if not paths:
        raise AudioProcessingError("Cannot concatenate zero audio segments")
    list_path.write_text(
        "\n".join(_concat_file_line(path) for path in paths) + "\n",
        encoding="utf-8",
    )
    ffmpeg = _require_tool("ffmpeg")
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        "lossless segment concatenation",
    )


def _measure_loudness(path: Path) -> Dict[str, float]:
    ffmpeg = _require_tool("ffmpeg")
    completed = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            (
                f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:"
                f"LRA={TARGET_LRA}:print_format=json"
            ),
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AudioProcessingError(
            f"loudness analysis failed: {completed.stderr.strip()[-3000:]}"
        )
    matches = re.findall(r"\{\s*\"input_i\".*?\}", completed.stderr, flags=re.DOTALL)
    if not matches:
        raise AudioProcessingError("ffmpeg loudnorm did not return measured values")
    try:
        raw = json.loads(matches[-1])
        values = {
            "input_i": float(raw["input_i"]),
            "input_tp": float(raw["input_tp"]),
            "input_lra": float(raw["input_lra"]),
            "input_thresh": float(raw["input_thresh"]),
            "target_offset": float(raw["target_offset"]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioProcessingError("ffmpeg returned unusable loudness measurements") from exc
    if not all(math.isfinite(value) for value in values.values()):
        raise AudioProcessingError("ffmpeg returned non-finite loudness measurements")
    return values


def _encode_mp3(
    source: Path,
    destination: Path,
    title: str,
    show_title: str,
    episode_date: str,
    voice_attribution: str,
    cover_path: Optional[Path],
) -> None:
    ffmpeg = _require_tool("ffmpeg")
    measured = _measure_loudness(source)
    loudnorm = (
        f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA={TARGET_LRA}:"
        f"measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=summary"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
    ]
    if cover_path is not None:
        if not cover_path.is_file():
            raise AudioProcessingError(f"Cover artwork does not exist: {cover_path}")
        command.extend(["-i", str(cover_path)])
    command.extend(
        [
            "-map",
            "0:a:0",
            "-af",
            loudnorm,
            "-c:a",
            "libmp3lame",
            "-b:a",
            MP3_BITRATE,
            "-ar",
            str(TARGET_SAMPLE_RATE),
            "-ac",
            "1",
            "-id3v2_version",
            "3",
            "-write_id3v1",
            "1",
            "-metadata",
            f"title={title}",
            "-metadata",
            f"album={show_title}",
            "-metadata",
            f"artist={show_title}",
            "-metadata",
            f"date={episode_date}",
            "-metadata",
            f"comment={voice_attribution}",
        ]
    )
    if cover_path is not None:
        command.extend(
            [
                "-map",
                "1:v:0",
                "-c:v",
                "mjpeg",
                "-disposition:v:0",
                "attached_pic",
                "-metadata:s:v",
                "title=Album cover",
                "-metadata:s:v",
                "comment=Cover (front)",
            ]
        )
    command.append(str(destination))
    _run(command, "MP3 normalization and encoding")


def verify_telegram_audio(path: Path, maximum_bytes: int = 50 * 1024 * 1024) -> Dict[str, Any]:
    if not path.is_file():
        raise AudioProcessingError(f"Audio file does not exist: {path}")
    if path.stat().st_size > maximum_bytes:
        raise AudioProcessingError(
            f"{path.name} exceeds the conservative 50 MB Telegram audio limit"
        )
    data = probe_audio(path)
    audio_streams = [
        stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise AudioProcessingError("Telegram audio must contain exactly one audio stream")
    stream = audio_streams[0]
    if stream.get("codec_name") != "mp3":
        raise AudioProcessingError(f"Expected MP3 codec, got {stream.get('codec_name')!r}")
    if int(stream.get("sample_rate", 0)) not in {44_100, 48_000}:
        raise AudioProcessingError("MP3 sample rate is not a conventional Telegram rate")
    if int(stream.get("channels", 0)) not in {1, 2}:
        raise AudioProcessingError("MP3 must be mono or stereo")
    duration = float(data.get("format", {}).get("duration", 0.0))
    if duration <= 0:
        raise AudioProcessingError("MP3 has no positive duration")
    tags = data.get("format", {}).get("tags", {})
    required_tags = ("title", "album", "artist", "date")
    missing_tags = [tag for tag in required_tags if not tags.get(tag)]
    if missing_tags:
        raise AudioProcessingError(f"MP3 is missing ID3 tags: {', '.join(missing_tags)}")
    return {
        "codec": stream["codec_name"],
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_seconds": duration,
        "size_bytes": path.stat().st_size,
        "tags": {tag: tags[tag] for tag in required_tags},
        "telegram_container_compatible": True,
    }


def assemble_episode(
    segment_paths: List[Path],
    chunks: List[NarrationChunk],
    output_path: Path,
    working_dir: Path,
    title: str,
    show_title: str,
    episode_date: str,
    voice_attribution: str,
    cover_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if len(segment_paths) != len(chunks):
        raise AudioProcessingError("Every narration chunk must have one generated segment")
    working_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir = working_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)

    prepared: List[Path] = []
    for segment, chunk in zip(segment_paths, chunks):
        target = prepared_dir / f"{chunk.index:04d}.wav"
        _prepare_segment(segment, target, chunk.pause_after_ms)
        prepared.append(target)

    combined = working_dir / "combined.wav"
    _concatenate(prepared, working_dir / "concat.txt", combined)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_name(f".{output_path.stem}.tmp.mp3")
    try:
        _encode_mp3(
            combined,
            temporary_output,
            title=title,
            show_title=show_title,
            episode_date=episode_date,
            voice_attribution=voice_attribution,
            cover_path=cover_path,
        )
        verification = verify_telegram_audio(temporary_output)
        os.replace(temporary_output, output_path)
        return verification
    finally:
        temporary_output.unlink(missing_ok=True)
