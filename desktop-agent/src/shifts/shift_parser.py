"""
Normalisiert Schicht-Bezeichnungen aus Spracheingaben zu ShiftType-Strings.
Fuzzy-tolerant für STT-Transkriptionsfehler.
"""

from __future__ import annotations

import re

# Kanonische Typen (müssen exakt mit Backend SHIFT_DEFINITIONS übereinstimmen)
ShiftType = str  # "tag" | "nacht" | "frei" | "fakt_frueh" | "fakt_spaet"

_PATTERNS: list[tuple[re.Pattern[str], ShiftType]] = [
    # FAKT IST früh — muss vor allgemeinen "früh"-Matches stehen
    (
        re.compile(r"fakt\s*(ist)?\s*(fr[üu]h|früh|frueh|early|morgen?s?)", re.I),
        "fakt_frueh",
    ),
    # FAKT IST spät
    (
        re.compile(r"fakt\s*(ist)?\s*(sp[äa]t|spaet|spät|abend?s?|late)", re.I),
        "fakt_spaet",
    ),
    # Tagschicht
    (
        re.compile(
            r"tag\s*schicht|tages?schicht|day\s*shift|tagsüber|tags?dienst", re.I
        ),
        "tag",
    ),
    # Nachtschicht
    (re.compile(r"nacht\s*schicht|nacht?dienst|night\s*shift", re.I), "nacht"),
    # Frei
    (
        re.compile(
            r"\bfrei\b|freier?\s*tag|day\s*off|urlaub|kein\s*(dienst|schicht|arbeit)",
            re.I,
        ),
        "frei",
    ),
    # Kurzformen
    (re.compile(r"\btag\b", re.I), "tag"),
    (re.compile(r"\bnacht\b", re.I), "nacht"),
]

_LABEL_MAP: dict[ShiftType, str] = {
    "tag": "Tagschicht (07:00–19:00)",
    "nacht": "Nachtschicht (19:00–07:00)",
    "frei": "Frei",
    "fakt_frueh": "FAKT IST! Früh (07:00–14:30)",
    "fakt_spaet": "FAKT IST! Spät (14:30–21:30)",
}


def parse_shift_type(text: str) -> ShiftType | None:
    """
    Gibt den ShiftType-String zurück oder None wenn nicht erkannt.
    Beispiele:
        "Tagschicht"          → "tag"
        "Nacht"               → "nacht"
        "FAKT IST früh"       → "fakt_frueh"
        "Fakt ist spät"       → "fakt_spaet"
        "Faktist früh"        → "fakt_frueh"  ← STT-Fehler toleriert
        "frei"                → "frei"
    """
    clean = text.strip()
    for pattern, shift_type in _PATTERNS:
        if pattern.search(clean):
            return shift_type
    return None


def shift_label(shift_type: ShiftType) -> str:
    return _LABEL_MAP.get(shift_type, shift_type)
