"""
Parst natürlichsprachige deutsche Datumsangaben zu datetime.date-Objekten.
Erweitert utils.date_resolver um explizite Datumsformate und Monatsangaben.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

# Monatsnamen → Monatsnummer
_MONTH_MAP: dict[str, int] = {
    "januar": 1,  "jan": 1,
    "februar": 2, "feb": 2,
    "märz": 3,    "maerz": 3, "mär": 3, "mar": 3,
    "april": 4,   "apr": 4,
    "mai": 5,
    "juni": 6,    "jun": 6,
    "juli": 7,    "jul": 7,
    "august": 8,  "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10,  "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "dez": 12, "dec": 12,
}

_WEEKDAY_MAP: dict[str, int] = {
    "montag": 0,    "mo": 0,
    "dienstag": 1,  "di": 1,
    "mittwoch": 2,  "mi": 2,
    "donnerstag": 3, "do": 3,
    "freitag": 4,   "fr": 4,
    "samstag": 5,   "sa": 5,
    "sonntag": 6,   "so": 6,
}

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_german_date(text: str, reference_date: date | None = None) -> date | None:
    """
    Parst deutschen Freitext zu einem date-Objekt.

    Unterstützte Formate:
    - "heute" / "morgen" / "übermorgen"
    - "nächsten montag" / "nächsten mo" / "montag"
    - "nächste woche" → +7 Tage
    - "am 3. juni" / "3. juni" / "3 juni"
    - "3.6." / "03.06." / "03.06.2026"
    - "2026-06-03" (ISO direkt)
    """
    if not text:
        return None

    today = reference_date or date.today()
    clean = text.strip().lower()

    # ISO-Format direkt
    if _ISO_RE.match(clean):
        try:
            return date.fromisoformat(clean)
        except ValueError:
            return None

    # Schlüsselwörter
    if clean in ("heute", "today", "jetzt"):
        return today

    if clean in ("morgen", "tomorrow"):
        return today + timedelta(days=1)

    if clean in ("übermorgen", "uebermorgen"):
        return today + timedelta(days=2)

    if clean in ("gestern", "yesterday"):
        return today - timedelta(days=1)

    if "nächste woche" in clean or "next week" in clean:
        return today + timedelta(weeks=1)

    # Wochentag (mit optionalem "nächsten")
    is_next = "nächst" in clean or "next" in clean
    for name, wd in _WEEKDAY_MAP.items():
        if re.search(rf"\b{re.escape(name)}\b", clean):
            days_ahead = (wd - today.weekday()) % 7 or 7
            if is_next and days_ahead < 7:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # "am 3. juni" / "3. juni" / "3 juni" / "3.juni"
    m = re.search(r"(?:am\s+)?(\d{1,2})\.?\s+(" + "|".join(_MONTH_MAP) + r")\b", clean)
    if m:
        day = int(m.group(1))
        month = _MONTH_MAP.get(m.group(2))
        if month:
            return _resolve_day_month(day, month, today)

    # "3.6." / "03.06." / "3.6.2026" / "03.06.2026"
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?$", clean.rstrip("."))
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year_raw = m.group(3)
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
            try:
                return date(year, month, day)
            except ValueError:
                return None
        return _resolve_day_month(day, month, today)

    # Fallback: nutze bestehenden date_resolver
    try:
        from utils.date_resolver import resolve_date
        iso = resolve_date(text, reference_date)
        return date.fromisoformat(iso) if iso else None
    except Exception:
        return None


def _resolve_day_month(day: int, month: int, today: date) -> date | None:
    """Wählt aktuelles oder nächstes Jahr, falls Datum schon vorbei."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
            if d >= today:
                return d
        except ValueError:
            continue
    return None
