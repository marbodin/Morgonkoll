from pathlib import Path

from src.pronunciation import apply_pronunciations, write_narration_copy


def test_overlapping_pronunciations_are_applied_once() -> None:
    result = apply_pronunciations("OpenAI använder AI och Google DeepMind.")
    assert result == "Open A I använder A I och Google Diip Majnd."


def test_engine_override_preserves_neural_g2p_spelling() -> None:
    result = apply_pronunciations(
        "OpenAI och DeepMind använder AI.", engine="kokoro_sv"
    )
    assert result == "OpenAI och DeepMind använder A I."


def test_only_narration_copy_is_modified(tmp_path: Path) -> None:
    source = tmp_path / "script.txt"
    destination = tmp_path / "build" / "narration.txt"
    original = "GitHub och Microsoft bygger AI."
    source.write_text(original, encoding="utf-8")

    narration = write_narration_copy(source, destination, engine="piper")

    assert source.read_text(encoding="utf-8") == original
    assert destination.read_text(encoding="utf-8") == narration
    assert narration == "Gitt-habb och Majkrosoft bygger A I."
