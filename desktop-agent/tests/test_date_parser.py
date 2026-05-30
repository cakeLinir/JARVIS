"""
Tests für core.date_parser — kein Backend, kein Internet erforderlich.
Ausführen: python -m pytest desktop-agent/tests/test_date_parser.py -v
"""

from __future__ import annotations

import sys
import os
import unittest
from datetime import date, timedelta

# Suchpfad so setzen, dass src-Importe funktionieren
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.date_parser import parse_german_date


# Festes Referenzdatum für deterministische Tests (2026-06-01 = Montag)
REF = date(2026, 6, 1)


class TestRelativeDates(unittest.TestCase):
    """Relative Datumsangaben."""

    def test_heute(self) -> None:
        result = parse_german_date("heute", REF)
        self.assertEqual(result, REF)

    def test_morgen(self) -> None:
        result = parse_german_date("morgen", REF)
        self.assertEqual(result, REF + timedelta(days=1))

    def test_uebermorgen(self) -> None:
        result = parse_german_date("übermorgen", REF)
        self.assertEqual(result, REF + timedelta(days=2))

    def test_uebermorgen_ascii(self) -> None:
        result = parse_german_date("uebermorgen", REF)
        self.assertEqual(result, REF + timedelta(days=2))

    def test_gestern(self) -> None:
        result = parse_german_date("gestern", REF)
        self.assertEqual(result, REF - timedelta(days=1))

    def test_naechste_woche(self) -> None:
        result = parse_german_date("nächste woche", REF)
        self.assertEqual(result, REF + timedelta(weeks=1))


class TestWeekdays(unittest.TestCase):
    """Wochentag-Auflösung."""

    def test_montag_naechster(self) -> None:
        # REF = Montag 2026-06-01 → nächster Montag = 2026-06-08
        result = parse_german_date("montag", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 0, "muss Montag sein")
        self.assertGreater(result, REF, "muss in der Zukunft liegen")

    def test_naechsten_montag(self) -> None:
        # "nächsten montag" → mind. 7 Tage voraus
        result = parse_german_date("nächsten montag", REF)
        self.assertIsNotNone(result)
        delta = (result - REF).days
        self.assertGreaterEqual(delta, 7)

    def test_dienstag(self) -> None:
        result = parse_german_date("dienstag", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 1)

    def test_samstag(self) -> None:
        result = parse_german_date("samstag", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 5)

    def test_kuerzel_mo(self) -> None:
        result = parse_german_date("mo", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 0)

    def test_kuerzel_so(self) -> None:
        result = parse_german_date("so", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 6)


class TestExplicitDates(unittest.TestCase):
    """Explizite Datumsformate."""

    def test_iso_format(self) -> None:
        result = parse_german_date("2026-06-03", REF)
        self.assertEqual(result, date(2026, 6, 3))

    def test_am_3_juni(self) -> None:
        result = parse_german_date("am 3. juni", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 3)

    def test_3_juni_ohne_am(self) -> None:
        result = parse_german_date("3. juni", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 3)

    def test_3_juni_jahr_2026(self) -> None:
        result = parse_german_date("3. juni", date(2026, 5, 1))
        self.assertEqual(result, date(2026, 6, 3))

    def test_punkt_notation_kurz(self) -> None:
        # "3.6." → nächster 3. Juni
        result = parse_german_date("3.6.", REF)
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 3)

    def test_punkt_notation_voll(self) -> None:
        result = parse_german_date("03.06.2026", REF)
        self.assertEqual(result, date(2026, 6, 3))

    def test_zweistelliges_jahr(self) -> None:
        result = parse_german_date("03.06.26", REF)
        self.assertEqual(result, date(2026, 6, 3))

    def test_alle_monate(self) -> None:
        monate = [
            ("januar", 1), ("februar", 2), ("märz", 3), ("april", 4),
            ("mai", 5), ("juni", 6), ("juli", 7), ("august", 8),
            ("september", 9), ("oktober", 10), ("november", 11), ("dezember", 12),
        ]
        ref_jan = date(2026, 1, 1)
        for name, num in monate:
            with self.subTest(monat=name):
                result = parse_german_date(f"15. {name}", ref_jan)
                self.assertIsNotNone(result, f"{name} konnte nicht geparst werden")
                self.assertEqual(result.month, num)

    def test_monatskuerzel_jan(self) -> None:
        result = parse_german_date("1. jan", date(2025, 12, 1))
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 1)

    def test_vergangenes_datum_naechstes_jahr(self) -> None:
        # "1. januar" wenn REF = 2026-06-01 → 2027-01-01
        result = parse_german_date("1. januar", REF)
        self.assertIsNotNone(result)
        self.assertGreater(result.year, REF.year)


class TestEdgeCases(unittest.TestCase):
    """Fehlerbehandlung und Randfälle."""

    def test_leerer_string(self) -> None:
        result = parse_german_date("", REF)
        self.assertIsNone(result)

    def test_kein_datum(self) -> None:
        result = parse_german_date("hallo welt", REF)
        self.assertIsNone(result)

    def test_ungueltige_monatsangabe(self) -> None:
        # Kein Monat, nur Zahl → kein Match
        result = parse_german_date("der 32.", REF)
        self.assertIsNone(result)

    def test_today_fallback_ohne_referenz(self) -> None:
        # Ohne reference_date → date.today()
        result = parse_german_date("heute")
        self.assertEqual(result, date.today())


if __name__ == "__main__":
    unittest.main(verbosity=2)
