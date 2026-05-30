from __future__ import annotations

from typing import Any


DEFAULT_WAKE_WORDS = (
    "guten morgen jarvis",
    "hallo jarvis",
    "jarvis",
)

DEFAULT_STOP_PHRASES = (
    "jarvis, stopp",
    "jarvis stopp",
    "jarvis, stop",
    "jarvis stop",
    "jarvis, abbrechen",
    "jarvis abbrechen",
    "jarvis, beenden",
    "jarvis beenden",
    "stopp",
    "abbrechen",
)


def normalize_phrase(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _list_from_config(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue

        normalized = normalize_phrase(item)
        if normalized:
            result.append(normalized)

    return result


def get_wake_words(config: dict[str, Any]) -> list[str]:
    voice_config = config.get("voice", {})
    voice_wake_words = _list_from_config(voice_config.get("wakeWords")) if isinstance(voice_config, dict) else []

    if voice_wake_words:
        return voice_wake_words

    legacy_wake_words = _list_from_config(config.get("wakeWords"))
    if legacy_wake_words:
        return legacy_wake_words

    return list(DEFAULT_WAKE_WORDS)


def get_stop_phrases(config: dict[str, Any]) -> list[str]:
    voice_config = config.get("voice", {})
    voice_stop_phrases = _list_from_config(voice_config.get("stopPhrases")) if isinstance(voice_config, dict) else []

    if voice_stop_phrases:
        return voice_stop_phrases

    return list(DEFAULT_STOP_PHRASES)


def is_wake_phrase(command: str, config: dict[str, Any]) -> bool:
    normalized = normalize_phrase(command)
    return normalized in set(get_wake_words(config))


def is_stop_phrase(command: str, config: dict[str, Any]) -> bool:
    normalized = normalize_phrase(command)
    return normalized in set(get_stop_phrases(config))


def is_morning_phrase(command: str) -> bool:
    return normalize_phrase(command) == "guten morgen jarvis"


# ── Schicht-Phrasen ───────────────────────────────────────────────────────────

SHIFT_PHRASES: dict[str, str] = {
    "tagschicht":      "tag",
    "tag schicht":     "tag",
    "tagesschicht":    "tag",
    "nachtschicht":    "nacht",
    "nacht schicht":   "nacht",
    "fakt ist früh":   "fakt_frueh",
    "fakt-ist früh":   "fakt_frueh",
    "fakt früh":       "fakt_frueh",
    "faktist früh":    "fakt_frueh",
    "fakt ist spaet":  "fakt_spaet",
    "fakt-ist spät":   "fakt_spaet",
    "fakt ist spät":   "fakt_spaet",
    "fakt spät":       "fakt_spaet",
    "faktist spät":    "fakt_spaet",
    "frei":            "frei",
    "freier tag":      "frei",
    "freizeit":        "frei",
    "frei tag":        "frei",
    "urlaub":          "frei",
}

# ── TODO-Trigger-Phrasen ──────────────────────────────────────────────────────

TODO_TRIGGERS: list[str] = [
    "erinnere mich",
    "erinnere mich an",
    "nicht vergessen",
    "todo:",
    "aufgabe:",
    "merk dir",
    "auf die liste",
    "trag ein",
    "füg hinzu",
    "füge hinzu",
    "auf meine liste",
]

# ── Prioritäts-Phrasen ────────────────────────────────────────────────────────

PRIORITY_PHRASES: dict[str, str] = {
    "wichtig":       "high",
    "sehr wichtig":  "critical",
    "dringend":      "high",
    "dringend!":     "critical",
    "kritisch":      "critical",
    "unwichtig":     "low",
    "irgendwann":    "low",
    "optional":      "low",
    "normal":        "normal",
    "mittelmäßig":   "normal",
}
