"""
Löst natürlichsprachige Datumsangaben (Deutsch) zu ISO-Strings auf.
Eingabe:  "heute", "morgen", "übermorgen", "Sonntag", "nächste Woche", "2026-06-01"
Ausgabe:  "YYYY-MM-DD"
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_WEEKDAY_MAP: dict[str, int] = {
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonntag": 6,
    "mo": 0,
    "di": 1,
    "mi": 2,
    "do": 3,
    "fr": 4,
    "sa": 5,
    "so": 6,
}

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_date(text: str, reference: date | None = None) -> str | None:
    """
    Gibt ein ISO-Datum (YYYY-MM-DD) zurück oder None wenn nicht auflösbar.
    reference: Ausgangsdatum für relative Berechnungen (Standard: heute)
    """
    today = reference or date.today()
    clean = text.strip().lower()

    # Bereits im ISO-Format
    if _ISO_RE.match(clean):
        return clean

    if clean in ("heute", "today", "jetzt"):
        return today.isoformat()

    if clean in ("morgen", "tomorrow"):
        return (today + timedelta(days=1)).isoformat()

    if clean in ("übermorgen", "uebermorgen"):
        return (today + timedelta(days=2)).isoformat()

    if clean in ("gestern", "yesterday"):
        return (today - timedelta(days=1)).isoformat()

    if clean in ("nächste woche", "next week"):
        return (today + timedelta(weeks=1)).isoformat()

    # Wochentag → nächstes Vorkommen (frühestens übermorgen)
    for name, wd in _WEEKDAY_MAP.items():
        if name in clean:
            # "nächsten X" → mind. 7 Tage voraus
            min_days = 7 if "nächst" in clean else 1
            days_ahead = (wd - today.weekday()) % 7 or 7
            if days_ahead < min_days:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

    return None  # Nicht auflösbar → Agent soll nachfragen


def resolve_time(text: str) -> str | None:
    """
    Löst Zeitangaben zu HH:MM auf.
    Eingabe: "09:00", "9 Uhr", "halb zehn", "halb 10", "14:30"
    """
    clean = text.strip().lower()

    # HH:MM direkt
    m = re.match(r"^(\d{1,2}):(\d{2})$", clean)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return f"{h:02d}:{mn:02d}"

    # "9 Uhr" / "14 uhr"
    m = re.match(r"^(\d{1,2})\s*uhr$", clean)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    # "halb 10" → 09:30
    m = re.match(r"^halb\s+(\d{1,2})$", clean)
    if m:
        h = int(m.group(1))
        if 1 <= h <= 24:
            return f"{(h - 1):02d}:30"

    # "viertel nach 9" → 09:15
    m = re.match(r"^viertel nach\s+(\d{1,2})$", clean)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:15"

    return None
