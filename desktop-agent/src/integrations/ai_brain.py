from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

LogFn = Callable[[str, str], None]
ContextFn = Callable[[], str]

# ── Tool-Definitionen ──────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "open_app",
        "description": (
            "Öffnet eine beliebige Anwendung oder ein Programm auf dem PC. "
            "Funktioniert mit konfigurierten Apps (spotify, discord, obs, vscode, whatsapp) "
            "und mit beliebigen anderen Programmen (z.B. notepad, chrome, firefox, rechner, "
            "explorer, word, excel, teams, telegram). "
            "Übergib den Programmnamen so wie der Nutzer ihn nennt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": (
                        "Programmname, z.B. 'notepad', 'chrome', 'spotify', "
                        "'rechner', 'discord'"
                    ),
                }
            },
            "required": ["app"],
        },
    },
    {
        "name": "system_control",
        "description": (
            "Systemsteuerung: Lautstärke setzen, stummschalten, "
            "Computer schlafen legen oder herunterfahren."
        ),
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
                    "description": (
                        "Minuten vor Fälligkeit für Erinnerung (z.B. 120 = 2h vorher)"
                    ),
                },
                "category": {
                    "type": "string",
                    "description": (
                        "Kategorie: 'arbeit', 'privat', 'streaming', 'haushalt'"
                    ),
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
                    "description": (
                        "set=Schicht eintragen, get=Schicht abrufen, "
                        "streaming_advice=Empfehlung"
                    ),
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
        "name": "weather_action",
        "description": (
            "Aktuelles Wetter oder Vorhersage für eine Stadt abrufen. "
            "Nutze dieses Tool bei allen Wetterfragen. "
            "Wenn keine Stadt genannt wird, nutze die konfigurierte Heimatstadt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        "Stadtname auf Englisch oder Deutsch "
                        "(leer = Heimatstadt aus Config)"
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["current", "forecast"],
                    "description": (
                        "current=aktuelles Wetter, forecast=Vorhersage für heute/morgen"
                    ),
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "open_url",
        "description": "Öffnet eine Website oder URL im Standard-Browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Vollständige URL mit https://",
                }
            },
            "required": ["url"],
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
            "Nutze dieses Tool auch wenn du Rückfragen stellen musst "
            "(z.B. welches TODO gemeint ist)."
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
    "Wenn eine App oder ein Programm geöffnet werden soll, nutze immer 'open_app' — "
    "auch für unbekannte Programme. "
    "Bei Wetterfragen nutze immer 'weather_action', nie 'answer'. "
    "Für Schichten und Streaming-Fragen nutze 'shift_action'. "
    "Für TODOs nutze 'todo_action'. "
    "Wenn bei TODOs unklar ist welches gemeint ist, frage nach mit 'answer'. "
    "Datumsangaben wie 'morgen', 'Sonntag' etc. übergibst du unverändert — "
    "sie werden automatisch aufgelöst. "
    "Schichttypen: tag, nacht, frei, fakt_frueh, fakt_spaet."
)


# ── AIBrain ───────────────────────────────────────────────────────────────────


class AIBrain:
    def __init__(
        self,
        config: dict[str, Any],
        log: LogFn,
        context_fn: ContextFn | None = None,
        history_path: Path | None = None,
    ) -> None:
        self._log = log
        self._context_fn = context_fn
        self._history_path = history_path
        self._history: list[dict[str, Any]] = []
        self._max_history_turns = int(config.get("aiMaxHistoryTurns", 10))
        self._pending_command: str | None = None
        self._pending_response_content: list | None = None
        self._load_history()

        api_key = str(config.get("anthropicApiKey", "")).strip()
        if not api_key or "CHANGE_ME" in api_key.upper():
            api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = str(config.get("aiModel", "claude-haiku-4-5-20251001"))

    def _build_system(self) -> str:
        if self._context_fn is None:
            return _SYSTEM_PROMPT
        try:
            ctx = self._context_fn()
        except Exception:
            return _SYSTEM_PROMPT
        if not ctx:
            return _SYSTEM_PROMPT
        return _SYSTEM_PROMPT + "\n\n--- Aktueller Kontext ---\n" + ctx

    def process(self, command: str) -> list[dict[str, Any]]:
        """
        Sendet Befehl an Claude. Gibt Tool-Calls mit id zurück.
        Für answer-Tool: History sofort fortschreiben.
        Für andere Tools: Pending-State für submit_tool_result speichern.
        """
        messages = list(self._history) + [{"role": "user", "content": command}]

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=self._build_system(),
                tools=_TOOLS,
                messages=messages,
            )

            tool_calls: list[dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            if not tool_calls:
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        tool_calls.append({
                            "id": None,
                            "name": "answer",
                            "input": {"text": block.text},
                        })
                        break

            if tool_calls and tool_calls[0]["name"] == "answer":
                # answer braucht keinen zweiten API-Call
                self._append_history(
                    command, str(tool_calls[0]["input"].get("text", ""))
                )
                self._pending_command = None
                self._pending_response_content = None
            else:
                # Pending-State für submit_tool_result
                self._pending_command = command
                self._pending_response_content = response.content

            return tool_calls

        except Exception as exc:
            self._log("ERROR", f"AI-Brain Fehler: {exc}", errorCode="ai_brain_failed")
            self._pending_command = None
            self._pending_response_content = None
            return [
                {
                    "id": None,
                    "name": "answer",
                    "input": {
                        "text": (
                            "Entschuldigung, ich konnte die Anfrage nicht verarbeiten."
                        )
                    },
                }
            ]

    def submit_tool_result(self, results: list[dict[str, Any]]) -> str | None:
        """
        Zweiter API-Call mit Tool-Ergebnissen damit Claude eine natürliche Antwort
        formulieren kann.
        results: [{"id": "toolu_xxx", "result": "Ergebnis-Text"}]
        Gibt synthetisierten Antwort-Text zurück oder None bei Fehler.
        """
        if not self._pending_command or not self._pending_response_content:
            return None

        tool_result_blocks = [
            {
                "type": "tool_result",
                "tool_use_id": r["id"],
                "content": str(r["result"]),
            }
            for r in results
            if r.get("id")
        ]
        if not tool_result_blocks:
            return None

        command = self._pending_command
        messages = list(self._history) + [
            {"role": "user", "content": command},
            {"role": "assistant", "content": self._pending_response_content},
            {"role": "user", "content": tool_result_blocks},
        ]

        try:
            response2 = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=self._build_system(),
                tools=_TOOLS,
                messages=messages,
            )

            final_text: str | None = None
            for block in response2.content:
                if block.type == "tool_use" and block.name == "answer":
                    final_text = str(block.input.get("text", ""))
                    break
                if hasattr(block, "text") and block.text:
                    final_text = block.text
                    break

            if final_text:
                self._append_history(command, final_text)

            return final_text

        except Exception as exc:
            self._log(
                "ERROR",
                f"AI-Brain tool_result Fehler: {exc}",
                errorCode="ai_brain_tool_result_failed",
            )
            return None
        finally:
            self._pending_command = None
            self._pending_response_content = None

    def _load_history(self) -> None:
        if self._history_path is None or not self._history_path.exists():
            return
        try:
            raw = json.loads(self._history_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._history = raw[-(self._max_history_turns * 2):]
                self._log("INFO", f"History geladen: {self.history_turns} Runden.")
        except Exception as exc:
            self._log("WARN", f"History-Datei konnte nicht geladen werden: {exc}")

    def _save_history(self) -> None:
        if self._history_path is None:
            return
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self._log("WARN", f"History-Datei konnte nicht gespeichert werden: {exc}")

    def _append_history(self, user_text: str, assistant_text: str) -> None:
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})
        max_entries = self._max_history_turns * 2
        if len(self._history) > max_entries:
            self._history = self._history[-max_entries:]
        self._save_history()

    def clear_history(self) -> None:
        """Setzt das Gesprächsgedächtnis zurück."""
        self._history = []
        self._pending_command = None
        self._pending_response_content = None
        self._save_history()
        self._log("INFO", "Gesprächsgedächtnis zurückgesetzt.")

    @property
    def history_turns(self) -> int:
        """Gibt die aktuelle Anzahl der Gesprächsrunden zurück."""
        return len(self._history) // 2


def create_brain(
    config: dict[str, Any],
    log: LogFn,
    context_fn: ContextFn | None = None,
    history_path: Path | None = None,
) -> "AIBrain | None":
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
        return AIBrain(config, log, context_fn=context_fn, history_path=history_path)
    except Exception as exc:
        log(
            "ERROR",
            f"AI-Brain konnte nicht initialisiert werden: {exc}",
            errorCode="ai_brain_init_failed",
        )
        return None
