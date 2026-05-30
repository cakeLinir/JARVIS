"""
Unit-Tests für IntentRouter und date_parser.
Kein echter API-Aufruf — Anthropic-Client wird gemockt.

Ausführen: python -m pytest desktop-agent/tests/test_intent_router.py -v
Oder:       cd desktop-agent && python -m pytest tests/test_intent_router.py -v
"""

from __future__ import annotations

import sys
import os
import unittest
from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

# Sicherstellen, dass desktop-agent/src im Suchpfad liegt
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from integrations.intent_router import (
    IntentResult,
    IntentRouter,
    INTENT_CLARIFY,
    INTENT_MORNING_ROUTINE,
    INTENT_SHIFT_SET,
    INTENT_STREAM_QUERY,
    INTENT_TODO_CREATE,
    INTENT_TODO_QUERY,
    INTENT_TODO_UPDATE_PRIORITY,
)
from core.date_parser import parse_german_date


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _noop_log(level: str, message: str, **_: Any) -> None:
    pass


def _mock_tool_call(name: str, input_dict: dict) -> MagicMock:
    """Erstellt einen Mock-Block wie ihn die Anthropic-API zurückgibt."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_dict
    return block


def _make_router(tool_name: str, tool_input: dict) -> IntentRouter:
    """Erstellt einen IntentRouter mit gemocktem Anthropic-Client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [_mock_tool_call(tool_name, tool_input)]
    mock_client.messages.create.return_value = mock_response

    router = IntentRouter(config={"anthropicApiKey": "test-key"}, client=mock_client)
    return router


# ── Testklassen ───────────────────────────────────────────────────────────────

class TestDateParser(unittest.TestCase):

    def test_heute(self) -> None:
        assert parse_german_date("heute") == date.today()

    def test_morgen(self) -> None:
        assert parse_german_date("morgen") == date.today() + timedelta(days=1)

    def test_uebermorgen(self) -> None:
        assert parse_german_date("übermorgen") == date.today() + timedelta(days=2)

    def test_iso_format(self) -> None:
        assert parse_german_date("2026-06-15") == date(2026, 6, 15)

    def test_german_short(self) -> None:
        # "3.6." → nächster 3. Juni
        result = parse_german_date("3.6.")
        assert result is not None
        assert result.month == 6
        assert result.day == 3

    def test_german_full(self) -> None:
        result = parse_german_date("03.06.2026")
        assert result == date(2026, 6, 3)

    def test_day_month_name(self) -> None:
        result = parse_german_date("am 3. juni")
        assert result is not None
        assert result.month == 6
        assert result.day == 3

    def test_wochentag_montag(self) -> None:
        result = parse_german_date("montag")
        assert result is not None
        assert result.weekday() == 0  # Montag

    def test_naechsten_montag(self) -> None:
        result = parse_german_date("nächsten montag")
        assert result is not None
        today = date.today()
        delta = (result - today).days
        assert delta >= 7, f"Nächsten Montag sollte ≥7 Tage entfernt sein, war {delta}"

    def test_naechste_woche(self) -> None:
        result = parse_german_date("nächste woche")
        assert result == date.today() + timedelta(weeks=1)

    def test_ungueltig(self) -> None:
        assert parse_german_date("kein datum hier") is None

    def test_leer(self) -> None:
        assert parse_german_date("") is None


class TestIntentRouterTodoCreate(unittest.TestCase):

    def test_erinnerung_morgen(self) -> None:
        """'Erinnere mich morgen an Rechnung bezahlen' → todo.create"""
        router = _make_router("create_todo", {
            "title": "Rechnung bezahlen",
            "due_date": "morgen",
        })
        result = router.route(
            "Erinnere mich morgen an Rechnung bezahlen",
            config={}, log=_noop_log,
        )
        assert result.intent == INTENT_TODO_CREATE
        assert result.slots["title"] == "Rechnung bezahlen"
        assert result.slots["due_date"] == "morgen"
        assert result.confidence >= 0.75

    def test_hohe_prioritaet(self) -> None:
        """TODO mit hoher Priorität"""
        router = _make_router("create_todo", {
            "title": "Server-Ausfall beheben",
            "priority": "critical",
        })
        result = router.route("Dringend: Server-Ausfall beheben", config={}, log=_noop_log)
        assert result.intent == INTENT_TODO_CREATE
        assert result.slots.get("priority") == "critical"

    def test_fehlender_titel_erzeugt_clarify(self) -> None:
        """Kein Titel → Konfidenz fällt, clarify erwartet"""
        router = _make_router("create_todo", {})  # title fehlt
        result = router.route("Füg etwas hinzu", config={}, log=_noop_log)
        assert result.intent == INTENT_CLARIFY


class TestIntentRouterShiftSet(unittest.TestCase):

    def test_tagschicht_morgen(self) -> None:
        """'Morgen habe ich Tagschicht' → shift.set (type=tag, date=morgen)"""
        router = _make_router("set_shift", {"date": "morgen", "shift_type": "tag"})
        result = router.route("Morgen habe ich Tagschicht", config={}, log=_noop_log)
        assert result.intent == INTENT_SHIFT_SET
        assert result.slots["shift_type"] == "tag"
        assert result.slots["date"] == "morgen"
        assert result.confidence >= 0.75

    def test_fakt_frueh_morgen(self) -> None:
        """'Morgen ist Fakt Ist früh' → shift.set (type=fakt_frueh)"""
        router = _make_router("set_shift", {"date": "morgen", "shift_type": "fakt_frueh"})
        result = router.route("Morgen ist Fakt Ist früh", config={}, log=_noop_log)
        assert result.intent == INTENT_SHIFT_SET
        assert result.slots["shift_type"] == "fakt_frueh"

    def test_nachtschicht_samstag(self) -> None:
        """'Samstag Nachtschicht' → shift.set"""
        router = _make_router("set_shift", {"date": "samstag", "shift_type": "nacht"})
        result = router.route("Samstag Nachtschicht", config={}, log=_noop_log)
        assert result.intent == INTENT_SHIFT_SET
        assert result.slots["shift_type"] == "nacht"

    def test_fehlender_typ_erzeugt_clarify(self) -> None:
        """Nur Datum, kein Typ → Konfidenz niedrig → clarify"""
        router = _make_router("set_shift", {"date": "morgen"})  # shift_type fehlt
        result = router.route("Morgen habe ich Arbeit", config={}, log=_noop_log)
        assert result.intent == INTENT_CLARIFY


class TestIntentRouterStreamQuery(unittest.TestCase):

    def test_streamen_heute_abend(self) -> None:
        """'Streamen heute Abend sinnvoll?' → stream.query"""
        router = _make_router("query_stream", {"date": "heute"})
        result = router.route("Streamen heute Abend sinnvoll?", config={}, log=_noop_log)
        assert result.intent == INTENT_STREAM_QUERY

    def test_kann_ich_streamen(self) -> None:
        """'Kann ich heute streamen?' → stream.query"""
        router = _make_router("query_stream", {})
        result = router.route("Kann ich heute streamen?", config={}, log=_noop_log)
        assert result.intent == INTENT_STREAM_QUERY


class TestIntentRouterTodoQuery(unittest.TestCase):

    def test_was_steht_heute_an(self) -> None:
        """'Was steht heute an?' → todo.query (filter=today)"""
        router = _make_router("query_todos", {"filter": "today"})
        result = router.route("Was steht heute an?", config={}, log=_noop_log)
        assert result.intent == INTENT_TODO_QUERY
        assert result.slots["filter"] == "today"

    def test_offene_aufgaben(self) -> None:
        """'Zeig mir offene Aufgaben' → todo.query"""
        router = _make_router("query_todos", {"filter": "open"})
        result = router.route("Zeig mir offene Aufgaben", config={}, log=_noop_log)
        assert result.intent == INTENT_TODO_QUERY


class TestIntentRouterClarify(unittest.TestCase):

    def test_mach_das_wichtig_kein_bezug(self) -> None:
        """'Mach das wichtig' ohne Bezug → update_todo ohne todo_ref → clarify"""
        router = _make_router("update_todo", {
            "todo_ref": "",   # kein konkretes TODO
            "field": "priority",
            "value": "high",
        })
        result = router.route("Mach das wichtig", config={}, log=_noop_log)
        # Fehlender todo_ref → Konfidenz < 0.75 → clarify
        assert result.intent == INTENT_CLARIFY

    def test_clarify_tool_direkt(self) -> None:
        """Wenn LLM clarify-Tool nutzt → Intent ist clarify"""
        router = _make_router("clarify", {"question": "Welches TODO meinst du?"})
        result = router.route("Mach das", config={}, log=_noop_log)
        assert result.intent == INTENT_CLARIFY
        assert "Welches TODO" in result.response_text

    def test_unbekannter_befehl(self) -> None:
        """Kein Tool-Call → unknown intent"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []  # kein Tool-Call
        mock_client.messages.create.return_value = mock_response

        router = IntentRouter(config={"anthropicApiKey": "test"}, client=mock_client)
        result = router.route("fnord blurp", config={}, log=_noop_log)
        assert result.intent == "unknown"
        assert result.confidence < 0.75


class TestIntentRouterMisc(unittest.TestCase):

    def test_morgenroutine(self) -> None:
        """'Guten Morgen, starte Routine' → morning_routine"""
        router = _make_router("run_morning_routine", {})
        result = router.route("Starte die Morgenroutine", config={}, log=_noop_log)
        assert result.intent == INTENT_MORNING_ROUTINE

    def test_api_fehler_gibt_unknown(self) -> None:
        """Bei API-Fehler → intent=unknown, confidence=0"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection refused")

        router = IntentRouter(config={"anthropicApiKey": "test"}, client=mock_client)
        result = router.route("Hallo", config={}, log=_noop_log)
        assert result.intent == "unknown"
        assert result.confidence == 0.0

    def test_raw_text_erhalten(self) -> None:
        """raw_text im Ergebnis muss dem Eingabetext entsprechen"""
        router = _make_router("query_todos", {"filter": "today"})
        text = "Was habe ich heute?"
        result = router.route(text, config={}, log=_noop_log)
        assert result.raw_text == text


if __name__ == "__main__":
    unittest.main(verbosity=2)
