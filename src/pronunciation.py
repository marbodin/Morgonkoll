"""Pronunciation substitutions isolated from the human-readable source."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .errors import ConfigurationError
from .paths import CONFIG_DIR


DEFAULT_PATH = CONFIG_DIR / "pronunciations.yml"


@dataclass(frozen=True)
class PronunciationRule:
    written: str
    spoken: str
    engine_overrides: Dict[str, str]


def load_rules(path: Path = DEFAULT_PATH) -> List[PronunciationRule]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not read pronunciation rules {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ConfigurationError(f"Unsupported pronunciation schema in {path}")

    rules: List[PronunciationRule] = []
    seen = set()
    for raw in payload.get("rules", []):
        written = str(raw.get("written", "")).strip()
        spoken = str(raw.get("spoken", "")).strip()
        if not written or not spoken:
            raise ConfigurationError("Pronunciation rules need non-empty written and spoken values")
        folded = written.casefold()
        if folded in seen:
            raise ConfigurationError(f"Duplicate pronunciation rule for {written!r}")
        seen.add(folded)
        rules.append(
            PronunciationRule(
                written=written,
                spoken=spoken,
                engine_overrides={
                    str(key): str(value)
                    for key, value in dict(raw.get("engines", {})).items()
                },
            )
        )
    return sorted(rules, key=lambda rule: len(rule.written), reverse=True)


def apply_pronunciations(
    text: str,
    engine: Optional[str] = None,
    rules: Optional[List[PronunciationRule]] = None,
) -> str:
    active = rules if rules is not None else load_rules()
    if not active:
        return text

    by_written = {rule.written.casefold(): rule for rule in active}
    alternatives = "|".join(re.escape(rule.written) for rule in active)
    pattern = re.compile(rf"(?<!\w)({alternatives})(?!\w)", flags=re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        rule = by_written[match.group(0).casefold()]
        if engine and engine in rule.engine_overrides:
            return rule.engine_overrides[engine]
        return rule.spoken

    return pattern.sub(replace, text)


def write_narration_copy(
    source_path: Path,
    destination: Path,
    engine: str,
    rules_path: Path = DEFAULT_PATH,
) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    narration = apply_pronunciations(source_text, engine=engine, rules=load_rules(rules_path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(narration, encoding="utf-8")
    return narration

