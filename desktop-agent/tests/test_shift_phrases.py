"""
Tests für voice.phrases.SHIFT_PHRASES — kein Backend, kein Internet.
Ausführen: python -m pytest desktop-agent/tests/test_shift_phrases.py -v
"""

from __future__ import annotations

import sys
import os
import unittest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from voice.phrases import SHIFT_PHRASES, PRIORITY_PHRASES, TODO_TRIGGERS, normalize_phrase
from shifts.shift_parser import parse_shift_type, shift_label


class TestShiftPhrases(unittest.TestCase):
    """Alle definierten Shift-Phrasen → korrekter ShiftType."""

    def _assert_phrase(self, phrase: str, expected: str) -> None:
        """Hilfsmethode: prüft SHIFT_PHRASES-Lookup und normalisierte Form."""
        normalized = normalize_phrase(phrase)
        result = SHIFT_PHRASES.get(normalized)
        self.assertEqual(
            result,
            expected,
            f"Phrase '{phrase}' (normalisiert: '{normalized}') → erwartet '{expected}', got '{result}'",
        )

    # ── Tagschicht ────────────────────────────────────────────────────────────

    def test_tagschicht(self) -> None:
        self._assert_phrase("tagschicht", "tag")

    def test_tag_schicht_mit_leerzeichen(self) -> None:
        self._assert_phrase("tag schicht", "tag")

    def test_tagesschicht(self) -> None:
        self._assert_phrase("tagesschicht", "tag")

    # ── Nachtschicht ──────────────────────────────────────────────────────────

    def test_nachtschicht(self) -> None:
        self._assert_phrase("nachtschicht", "nacht")

    def test_nacht_schicht_mit_leerzeichen(self) -> None:
        self._assert_phrase("nacht schicht", "nacht")

    # ── FAKT IST! Früh ────────────────────────────────────────────────────────

    def test_fakt_ist_frueh(self) -> None:
        self._assert_phrase("fakt ist früh", "fakt_frueh")

    def test_fakt_bindestrich_frueh(self) -> None:
        self._assert_phrase("fakt-ist früh", "fakt_frueh")

    def test_fakt_frueh_kurz(self) -> None:
        self._assert_phrase("fakt früh", "fakt_frueh")

    def test_faktist_frueh(self) -> None:
        self._assert_phrase("faktist früh", "fakt_frueh")

    # ── FAKT IST! Spät ────────────────────────────────────────────────────────

    def test_fakt_ist_spaet(self) -> None:
        self._assert_phrase("fakt ist spät", "fakt_spaet")

    def test_fakt_bindestrich_spaet(self) -> None:
        self._assert_phrase("fakt-ist spät", "fakt_spaet")

    def test_fakt_spaet_kurz(self) -> None:
        self._assert_phrase("fakt spät", "fakt_spaet")

    def test_faktist_spaet(self) -> None:
        self._assert_phrase("faktist spät", "fakt_spaet")

    def test_fakt_ist_spaet_ascii(self) -> None:
        self._assert_phrase("fakt ist spaet", "fakt_spaet")

    # ── Frei ──────────────────────────────────────────────────────────────────

    def test_frei(self) -> None:
        self._assert_phrase("frei", "frei")

    def test_freier_tag(self) -> None:
        self._assert_phrase("freier tag", "frei")

    def test_freizeit(self) -> None:
        self._assert_phrase("freizeit", "frei")

    def test_frei_tag(self) -> None:
        self._assert_phrase("frei tag", "frei")

    def test_urlaub(self) -> None:
        self._assert_phrase("urlaub", "frei")

    # ── Vollständigkeit ───────────────────────────────────────────────────────

    def test_alle_werte_sind_gueltige_typen(self) -> None:
        """Jeder SHIFT_PHRASES-Wert muss ein gültiger ShiftType sein."""
        valid_types = {"tag", "nacht", "fakt_frueh", "fakt_spaet", "frei"}
        for phrase, shift_type in SHIFT_PHRASES.items():
            with self.subTest(phrase=phrase):
                self.assertIn(
                    shift_type, valid_types,
                    f"'{phrase}' → '{shift_type}' ist kein gültiger ShiftType",
                )


class TestShiftParser(unittest.TestCase):
    """Fuzzy-Parser für Sprachbefehle (shift_parser.py)."""

    def test_tagschicht_volltext(self) -> None:
        self.assertEqual(parse_shift_type("Tagschicht"), "tag")

    def test_nachtschicht(self) -> None:
        self.assertEqual(parse_shift_type("Nachtschicht"), "nacht")

    def test_fakt_frueh(self) -> None:
        self.assertEqual(parse_shift_type("FAKT IST früh"), "fakt_frueh")

    def test_fakt_spaet(self) -> None:
        self.assertEqual(parse_shift_type("FAKT IST spät"), "fakt_spaet")

    def test_frei_klein(self) -> None:
        self.assertEqual(parse_shift_type("frei"), "frei")

    def test_freier_tag(self) -> None:
        self.assertEqual(parse_shift_type("Freier Tag"), "frei")

    def test_tag_kurz(self) -> None:
        self.assertEqual(parse_shift_type("Tag"), "tag")

    def test_nacht_kurz(self) -> None:
        self.assertEqual(parse_shift_type("Nacht"), "nacht")

    def test_unbekannt_gibt_none(self) -> None:
        self.assertIsNone(parse_shift_type("Urlaub auf Hawaii"))

    def test_leerer_string_gibt_none(self) -> None:
        self.assertIsNone(parse_shift_type(""))

    def test_stt_fehler_faktist(self) -> None:
        """STT transkribiert 'fakt ist' ohne Leerzeichen."""
        self.assertEqual(parse_shift_type("faktist früh"), "fakt_frueh")


class TestShiftLabel(unittest.TestCase):
    """shift_label() gibt deutschen Bezeichner zurück."""

    def test_tag_label(self) -> None:
        self.assertIn("07:00", shift_label("tag"))

    def test_nacht_label(self) -> None:
        self.assertIn("19:00", shift_label("nacht"))

    def test_fakt_frueh_label(self) -> None:
        self.assertIn("Früh", shift_label("fakt_frueh"))

    def test_fakt_spaet_label(self) -> None:
        self.assertIn("Spät", shift_label("fakt_spaet"))

    def test_frei_label(self) -> None:
        self.assertEqual(shift_label("frei"), "Frei")


class TestPriorityPhrases(unittest.TestCase):
    """PRIORITY_PHRASES korrekt definiert."""

    def test_wichtig_ist_high(self) -> None:
        self.assertEqual(PRIORITY_PHRASES.get("wichtig"), "high")

    def test_dringend_ist_high(self) -> None:
        self.assertEqual(PRIORITY_PHRASES.get("dringend"), "high")

    def test_kritisch_ist_critical(self) -> None:
        self.assertEqual(PRIORITY_PHRASES.get("kritisch"), "critical")

    def test_sehr_wichtig_ist_critical(self) -> None:
        self.assertEqual(PRIORITY_PHRASES.get("sehr wichtig"), "critical")

    def test_irgendwann_ist_low(self) -> None:
        self.assertEqual(PRIORITY_PHRASES.get("irgendwann"), "low")


class TestTodoTriggers(unittest.TestCase):
    """TODO_TRIGGERS enthält erwartete Phrasen."""

    def test_erinnere_mich(self) -> None:
        self.assertIn("erinnere mich", TODO_TRIGGERS)

    def test_nicht_vergessen(self) -> None:
        self.assertIn("nicht vergessen", TODO_TRIGGERS)

    def test_trag_ein(self) -> None:
        self.assertIn("trag ein", TODO_TRIGGERS)

    def test_keine_duplikate(self) -> None:
        self.assertEqual(len(TODO_TRIGGERS), len(set(TODO_TRIGGERS)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
