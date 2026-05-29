from __future__ import annotations

import os
from typing import Any, Callable

LogFn = Callable[[str, str], None]

# ── Tool-Definitionen ──────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "open_app",
        "description": "Öffnet eine Anwendung wie Spotify, Discord, OBS, VSCode oder WhatsApp.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": "App-Name in Kleinbuchstaben (spotify, discord, obs, vscode, whatsapp)",
                }
            },
            "required": ["app"],
        },
    },
    {
        "name": "system_control",
        "description": "Systemsteuerung: Lautstärke setzen, stummschalten, Computer schlafen legen oder herunterfahren.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set_volume", "mute", "unmute", "sleep", "shutdown"],
                },
                "value": {
                    "type": "integer",
                    "description": "Lautstärke 0–100 (nur bei set_volume)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "todo_action",
        "description": (
            "TODOs verwalten: lesen, hinzufügen, als erledigt markieren, verschieben, "
            "Priorität setzen, Erinnerung setzen. "
            "Wenn unklar welches TODO gemeint ist (z.B. 'mach das wichtig' ohne Kontext), "
            "nutze das 'answer'-Tool um nachzufragen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "read",
                        "add",
                        "complete",
                        "reschedule",
                        "set_priority",
                        "set_reminder",
                    ],
                    "description": (
                        "read=vorlesen, add=hinzufügen, complete=erledigt, "
                        "reschedule=verschieben, set_priority=Priorität ändern, "
                        "set_reminder=Erinnerung setzen"
                    ),
                },
                "text": {
                    "type": "string",
                    "description": "Titel des neuen TODOs (nur bei action=add)",
                },
                "todo_ref": {
                    "type": "string",
                    "description": "Titel oder Titelausschnitt des zu ändernden TODOs",
                },
                "due_date": {
                    "type": "string",
                    "description": (
                        "Fälligkeitsdatum. Kann sein: 'heute', 'morgen', 'übermorgen', "
                        "'Sonntag', 'YYYY-MM-DD'. Wird automatisch aufgelöst."
                    ),
                },
                "due_time": {
                    "type": "string",
                    "description": "Uhrzeit HH:MM oder '9 Uhr', 'halb zehn'",
                },
                "priority": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "1=kritisch, 2=hoch, 3=mittel, 4=niedrig, 5=optional",
                },
                "reminder_minutes": {
                    "type": "integer",
                    "description": "Minuten vor Fälligkeit für Erinnerung (z.B. 120 = 2h vorher)",
                },
                "category": {
                    "type": "string",
                    "description": "Kategorie: 'arbeit', 'privat', 'streaming', 'haushalt'",
                },
                "description": {
                    "type": "string",
                    "description": "Optionale Notizen / Details zum TODO",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "shift_action",
        "description": (
            "Schichten eintragen oder abrufen, Streaming-Empfehlung holen. "
            "Schichttypen: tag (07:00–19:00), nacht (19:00–07:00), frei, "
            "fakt_frueh (07:00–14:30), fakt_spaet (14:30–21:30). "
            "Datumsangaben wie 'heute', 'morgen', 'Sonntag' werden automatisch aufgelöst."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "get", "streaming_advice"],
                    "description": "set=Schicht eintragen, get=Schicht abrufen, streaming_advice=Empfehlung",
                },
                "date": {
                    "type": "string",
                    "description": "Datum: 'heute', 'morgen', 'Sonntag' oder YYYY-MM-DD",
                },
                "shift_type": {
                    "type": "string",
                    "enum": ["tag", "nacht", "frei", "fakt_frueh", "fakt_spaet"],
                    "description": "Schichttyp (nur bei action=set)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "run_routine",
        "description": "Startet eine vordefinierte Routine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": ["morning_routine"],
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "answer",
        "description": (
            "Beantwortet eine Frage oder gibt eine Information aus. "
            "Nutze dieses Tool auch wenn du Rückfragen stellen musst (z.B. welches TODO gemeint ist)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Antwort auf Deutsch, kurz und präzise (max. 2 Sätze)",
                }
            },
            "required": ["text"],
        },
    },
]

_SYSTEM_PROMPT = (
    "Du bist JARVIS, ein lokaler Desktop-Assistent auf Windows für Justin. "
    "Du empfängst Sprachbefehle auf Deutsch und wählst exakt ein passendes Tool aus. "
    "Antworte im 'answer'-Tool immer auf Deutsch, kurz und direkt (max. 2 Sätze). "
    "Wenn eine App geöffnet werden soll, nutze 'open_app'. "
    "Für Schichten und Streaming-Fragen nutze 'shift_action'. "
    "Für TODOs nutze 'todo_action'. "
    "Wenn bei TODOs unklar ist welches gemeint ist, frage nach mit 'answer'. "
    "Datumsangaben wie 'morgen', 'Sonntag' etc. übergibst du unverändert — "
    "sie werden automatisch aufgelöst. "
    "Schichttypen: tag, nacht, frei, fakt_frueh, fakt_spaet."
)


# ── AIBrain ───────────────────────────────────────────────────────────────────


class AIBrain:
    def __init__(self, config: dict[str, Any], log: LogFn) -> None:
        self._log = log
        api_key = str(config.get("anthropicApiKey", "")).strip()
        if not api_key or "CHANGE_ME" in api_key.upper():
            api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = str(config.get("aiModel", "claude-haiku-4-5-20251001"))

    def process(self, command: str) -> list[dict[str, Any]]:
        """Sendet Befehl an Claude und gibt Liste von Tool-Calls zurück."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=[{"role": "user", "content": command}],
            )
            tool_calls: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({"name": block.name, "input": block.input})

            # Fallback: Text-Antwort wenn kein Tool gewählt wurde
            if not tool_calls:
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        tool_calls.append(
                            {"name": "answer", "input": {"text": block.text}}
                        )
                        break

            return tool_calls

        except Exception as exc:
            self._log("ERROR", f"AI-Brain Fehler: {exc}", errorCode="ai_brain_failed")
            return [
                {
                    "name": "answer",
                    "input": {
                        "text": "Entschuldigung, ich konnte die Anfrage nicht verarbeiten."
                    },
                }
            ]


def create_brain(config: dict[str, Any], log: LogFn) -> "AIBrain | None":
    """Erstellt AIBrain. Gibt None zurück wenn kein API-Key konfiguriert."""
    api_key = str(config.get("anthropicApiKey", "")).strip()
    if not api_key or "CHANGE_ME" in api_key.upper():
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        log(
            "WARN",
            "Kein Anthropic API-Key konfiguriert. AI-Brain deaktiviert. "
            "Setze 'anthropicApiKey' in config oder ANTHROPIC_API_KEY als ENV.",
            errorCode="ai_brain_no_api_key",
        )
        return None
    try:
        return AIBrain(config, log)
    except Exception as exc:
        log(
            "ERROR",
            f"AI-Brain konnte nicht initialisiert werden: {exc}",
            errorCode="ai_brain_init_failed",
        )
        return None
