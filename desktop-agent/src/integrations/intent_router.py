"""
Intent-Router: Parst deutschen Freitext via Anthropic Tool-Calling zu strukturierten Aktionen.
Gibt IntentResult zurück; bei Konfidenz < 0.75 → clarify.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

LogFn = Callable[[str, str], None]


# ── Intent-Bezeichner ─────────────────────────────────────────────────────────

INTENT_TODO_CREATE          = "todo.create"
INTENT_TODO_UPDATE_PRIORITY = "todo.update_priority"
INTENT_TODO_RESCHEDULE      = "todo.reschedule"
INTENT_TODO_COMPLETE        = "todo.complete"
INTENT_TODO_SET_REMINDER    = "todo.set_reminder"
INTENT_TODO_QUERY           = "todo.query"
INTENT_SHIFT_SET            = "shift.set"
INTENT_SHIFT_QUERY          = "shift.query"
INTENT_STREAM_QUERY         = "stream.query"
INTENT_MORNING_ROUTINE      = "morning_routine"
INTENT_APP_OPEN             = "app.open"
INTENT_SYSTEM_STOP          = "system.stop"
INTENT_CLARIFY              = "clarify"
INTENT_UNKNOWN              = "unknown"

CLARIFY_THRESHOLD = 0.75


# ── Ergebnis-Dataclass ────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    intent: str
    slots: dict[str, Any]
    confidence: float
    raw_text: str
    response_text: str


# ── Anthropic-Tool-Definitionen ───────────────────────────────────────────────

_INTENT_TOOLS = [
    {
        "name": "create_todo",
        "description": (
            "Erstellt ein neues TODO / eine neue Aufgabe. "
            "Nutze dieses Tool bei Sätzen wie: 'erinnere mich', 'nicht vergessen', "
            "'trag ein', 'füg hinzu', 'auf die Liste'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Klarer, prägnanter Titel der Aufgabe",
                },
                "due_date": {
                    "type": "string",
                    "description": (
                        "Fälligkeitsdatum als Text (heute, morgen, Montag, 3. Juni, …) "
                        "oder null wenn nicht angegeben"
                    ),
                },
                "due_time": {
                    "type": "string",
                    "description": "Uhrzeit als Text (9 Uhr, 14:30, halb zehn) oder null",
                },
                "reminder_min": {
                    "type": "integer",
                    "description": "Erinnerung X Minuten vor Fälligkeit (z.B. 60 = 1h vorher)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "critical"],
                    "description": "Priorität: low=niedrig, normal=mittel, high=hoch, critical=kritisch",
                },
                "category": {
                    "type": "string",
                    "description": "Kategorie: arbeit, haushalt, streaming, privat",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_todo",
        "description": (
            "Aktualisiert ein bestehendes TODO. "
            "Nutze dieses Tool bei 'mach das wichtig', 'verschiebe X auf Montag', "
            "'stell eine Erinnerung für X'. "
            "WICHTIG: Wenn todo_ref unklar ist, nutze stattdessen das clarify-Tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_ref": {
                    "type": "string",
                    "description": "Titel oder Titelausschnitt des TODOs — muss konkret angegeben sein",
                },
                "field": {
                    "type": "string",
                    "enum": ["priority", "due_date", "reminder"],
                    "description": "Welches Feld soll geändert werden",
                },
                "value": {
                    "type": "string",
                    "description": "Neuer Wert (Priorität: low/normal/high/critical | Datum: Textformat | Minuten: Zahl)",
                },
            },
            "required": ["todo_ref", "field", "value"],
        },
    },
    {
        "name": "complete_todo",
        "description": (
            "Markiert ein TODO als erledigt. "
            "Nutze bei: 'erledigt', 'abhaken', 'fertig', 'hab ich gemacht'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_ref": {
                    "type": "string",
                    "description": "Titel oder Titelausschnitt des TODOs",
                },
            },
            "required": ["todo_ref"],
        },
    },
    {
        "name": "query_todos",
        "description": (
            "Listet TODOs auf. "
            "Nutze bei: 'was steht an', 'was habe ich heute', 'offene Aufgaben'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["today", "open", "overdue", "all"],
                    "description": "today=heute fällig, open=alle offenen, overdue=überfällig, all=alle",
                },
            },
            "required": ["filter"],
        },
    },
    {
        "name": "set_shift",
        "description": (
            "Trägt eine Schicht ein. "
            "Schichttypen: tag=Tagschicht 07–19, nacht=Nachtschicht 19–07, "
            "frei=Frei, fakt_frueh=FAKT IST! Früh 07–14:30, fakt_spaet=FAKT IST! Spät 14:30–21:30. "
            "Nutze bei: 'morgen habe ich Tagschicht', 'ich arbeite Samstag Nacht'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Datum als Text (heute, morgen, Montag, 3.6., …)",
                },
                "shift_type": {
                    "type": "string",
                    "enum": ["tag", "nacht", "fakt_frueh", "fakt_spaet", "frei"],
                },
            },
            "required": ["date", "shift_type"],
        },
    },
    {
        "name": "query_shift",
        "description": "Fragt ab welche Schicht an einem Datum eingetragen ist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Datum als Text",
                },
            },
            "required": ["date"],
        },
    },
    {
        "name": "query_stream",
        "description": (
            "Fragt ob und wann streamen sinnvoll ist. "
            "Nutze bei: 'sinnvoll heute zu streamen', 'kann ich heute streamen', "
            "'wann kann ich streamen'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Datum als Text (Standard: heute)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_morning_routine",
        "description": "Startet die Morgenroutine (Apps öffnen, TODOs vorlesen, Fenster anordnen).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "open_app",
        "description": "Öffnet eine Anwendung oder ein Programm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": "Programmname (spotify, discord, chrome, notepad, …)",
                },
            },
            "required": ["app"],
        },
    },
    {
        "name": "system_stop",
        "description": "Beendet JARVIS. Nutze bei: 'stopp', 'beenden', 'auf Wiedersehen'.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "clarify",
        "description": (
            "Stellt eine Rückfrage wenn der Befehl unklar oder unvollständig ist. "
            "Nutze insbesondere wenn: kein konkretes TODO genannt wurde, "
            "der Satz keinem anderen Tool zugeordnet werden kann."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Rückfrage auf Deutsch",
                },
            },
            "required": ["question"],
        },
    },
]

_SYSTEM_PROMPT = (
    "Du bist JARVIS, ein persönlicher Desktop-Assistent für Justin. "
    "Du empfängst deutsche Texteingaben und wählst genau ein passendes Tool aus. "
    "Antworte nie frei — nutze immer ein Tool. "
    "Bei Schichten: tag=Tagschicht, nacht=Nachtschicht, fakt_frueh=FAKT Früh, fakt_spaet=FAKT Spät. "
    "Bei TODOs: Datum-Angaben EXAKT wie angegeben übergeben (morgen, Montag, 3. Juni, …). "
    "Bei 'mach das wichtig' oder ähnlichem ohne konkretes TODO → clarify-Tool verwenden. "
    "Nutze clarify wenn der Befehl mehrdeutig oder unvollständig ist."
)

# Mapping Tool-Name → Intent-Bezeichner
_TOOL_TO_INTENT: dict[str, str] = {
    "create_todo":         INTENT_TODO_CREATE,
    "complete_todo":       INTENT_TODO_COMPLETE,
    "query_todos":         INTENT_TODO_QUERY,
    "set_shift":           INTENT_SHIFT_SET,
    "query_shift":         INTENT_SHIFT_QUERY,
    "query_stream":        INTENT_STREAM_QUERY,
    "run_morning_routine": INTENT_MORNING_ROUTINE,
    "open_app":            INTENT_APP_OPEN,
    "system_stop":         INTENT_SYSTEM_STOP,
    "clarify":             INTENT_CLARIFY,
}


# ── IntentRouter ──────────────────────────────────────────────────────────────

class IntentRouter:
    def __init__(self, config: dict[str, Any], client: Any = None) -> None:
        self._config = config
        if client is not None:
            self._client = client
        else:
            api_key = str(config.get("anthropicApiKey", "")).strip()
            if not api_key or "CHANGE_ME" in api_key.upper():
                api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)

        self._model = str(config.get("aiModel", "claude-haiku-4-5-20251001"))

    def route(self, text: str, config: dict[str, Any], log: LogFn) -> IntentResult:
        """
        Parst deutschen Freitext und gibt ein IntentResult zurück.

        Edge Cases:
        - Leerer Text → INTENT_UNKNOWN ohne API-Aufruf
        - Konfidenz < 0.75 → INTENT_CLARIFY (nie blind ausführen)
        - update_todo ohne todo_ref → INTENT_CLARIFY (Schicht-Widerspruch explizit nachfragen)
        - API-Fehler → INTENT_UNKNOWN mit confidence=0.0
        """
        # Guard: leere Transkription nicht an Backend schicken
        clean = (text or "").strip()
        if not clean:
            log("WARN", "IntentRouter: leerer Text — kein API-Aufruf.")
            return IntentResult(
                intent=INTENT_UNKNOWN,
                slots={},
                confidence=0.0,
                raw_text=text,
                response_text="",
            )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                tools=_INTENT_TOOLS,
                messages=[{"role": "user", "content": text}],
            )
        except Exception as exc:
            log("ERROR", f"IntentRouter API-Fehler: {exc}", errorCode="intent_router_api_failed")
            return IntentResult(
                intent=INTENT_UNKNOWN,
                slots={},
                confidence=0.0,
                raw_text=text,
                response_text="",
            )

        # Tool-Call extrahieren
        tool_name: str | None = None
        tool_input: dict[str, Any] = {}

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                tool_name = block.name
                tool_input = dict(block.input) if block.input else {}
                break

        if not tool_name:
            return IntentResult(
                intent=INTENT_UNKNOWN,
                slots={},
                confidence=0.30,
                raw_text=text,
                response_text="",
            )

        return self._build_result(text, tool_name, tool_input, log)

    def _build_result(
        self,
        raw_text: str,
        tool_name: str,
        tool_input: dict[str, Any],
        log: LogFn,
    ) -> IntentResult:
        # update_todo → spezialisierte Intent-Bezeichner anhand 'field'
        if tool_name == "update_todo":
            f = str(tool_input.get("field", "")).lower()
            intent_map = {
                "priority": INTENT_TODO_UPDATE_PRIORITY,
                "due_date": INTENT_TODO_RESCHEDULE,
                "reminder": INTENT_TODO_SET_REMINDER,
            }
            intent = intent_map.get(f, INTENT_TODO_UPDATE_PRIORITY)

            # Edge Case: kein konkretes todo_ref → Konfidenz unter Schwellenwert → clarify
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            confidence = 0.85 if todo_ref else 0.45

        # set_shift → Widerspruchs-Check: fehlendes Datum oder Typ → clarify
        elif tool_name == "set_shift":
            intent = _TOOL_TO_INTENT.get(tool_name, INTENT_UNKNOWN)
            date_val = str(tool_input.get("date", "")).strip()
            shift_type = str(tool_input.get("shift_type", "")).strip()
            if not date_val or not shift_type:
                # Unvollständige Schicht-Angabe → explizit nachfragen statt raten
                confidence = 0.40
            else:
                confidence = self._score(tool_name, tool_input)
        else:
            intent = _TOOL_TO_INTENT.get(tool_name, INTENT_UNKNOWN)
            confidence = self._score(tool_name, tool_input)

        # Unter Schwellenwert → clarify (nie blind ausführen)
        if confidence < CLARIFY_THRESHOLD and intent != INTENT_CLARIFY:
            clarify_text = self._clarify_question(intent, tool_input)
            return IntentResult(
                intent=INTENT_CLARIFY,
                slots=tool_input,
                confidence=confidence,
                raw_text=raw_text,
                response_text=clarify_text,
            )

        response_text = ""
        if intent == INTENT_CLARIFY:
            response_text = str(tool_input.get("question", "Kannst du das genauer beschreiben?"))

        log(
            "INFO",
            f"Intent erkannt: {intent} (confidence={confidence:.2f}) | slots={list(tool_input.keys())}",
        )

        return IntentResult(
            intent=intent,
            slots=tool_input,
            confidence=confidence,
            raw_text=raw_text,
            response_text=response_text,
        )

    def _score(self, tool_name: str, tool_input: dict[str, Any]) -> float:
        """Heuristisches Konfidenz-Scoring anhand vorhandener Pflichtfelder."""
        required: dict[str, list[str]] = {
            "create_todo":         ["title"],
            "complete_todo":       ["todo_ref"],
            "query_todos":         ["filter"],
            "set_shift":           ["date", "shift_type"],
            "query_shift":         ["date"],
            "query_stream":        [],
            "run_morning_routine": [],
            "open_app":            ["app"],
            "system_stop":         [],
            "clarify":             ["question"],
        }
        needed = required.get(tool_name, [])
        if not needed:
            return 0.90

        filled = sum(1 for k in needed if str(tool_input.get(k, "")).strip())
        return 0.90 if filled == len(needed) else 0.50 * (filled / len(needed))

    def _clarify_question(self, intent: str, slots: dict[str, Any]) -> str:
        """Generiert eine passende deutsche Rückfrage."""
        questions: dict[str, str] = {
            INTENT_TODO_UPDATE_PRIORITY: "Welches TODO soll ich wichtiger machen?",
            INTENT_TODO_RESCHEDULE:      "Welches TODO soll ich verschieben?",
            INTENT_TODO_SET_REMINDER:    "Für welches TODO soll ich eine Erinnerung setzen?",
            INTENT_TODO_COMPLETE:        "Welches TODO hast du erledigt?",
            INTENT_SHIFT_SET:            "Für welches Datum und welche Schicht?",
            INTENT_APP_OPEN:             "Welche App soll ich öffnen?",
        }
        return questions.get(intent, "Kannst du das genauer beschreiben?")
