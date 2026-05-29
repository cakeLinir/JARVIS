from __future__ import annotations

import os
from typing import Any, Callable

LogFn = Callable[[str, str], None]

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
                    "description": "Aktion",
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
        "description": "TODOs verwalten: offene TODOs vorlesen oder einen neuen hinzufügen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "add"],
                    "description": "'read' liest offene TODOs vor, 'add' fügt einen neuen hinzu",
                },
                "text": {
                    "type": "string",
                    "description": "Text des neuen TODOs (nur bei action=add)",
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
                    "description": "Name der Routine",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "answer",
        "description": "Beantwortet eine Frage oder gibt eine Information aus. Nutze dieses Tool wenn kein anderes passt.",
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
    "Du bist JARVIS, ein lokaler Desktop-Assistent auf Windows. "
    "Du empfängst Sprachbefehle auf Deutsch und wählst exakt ein passendes Tool aus. "
    "Antworte im 'answer'-Tool immer auf Deutsch, kurz und direkt (max. 2 Sätze). "
    "Wenn eine App geöffnet werden soll, nutze immer 'open_app'."
)


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


def create_brain(config: dict[str, Any], log: LogFn) -> AIBrain | None:
    """Erstellt AIBrain. Gibt None zurück wenn kein API-Key konfiguriert."""
    api_key = str(config.get("anthropicApiKey", "")).strip()
    if not api_key or "CHANGE_ME" in api_key.upper():
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        log(
            "WARN",
            "Kein Anthropic API-Key konfiguriert. AI-Brain deaktiviert. "
            "Setze 'anthropicApiKey' in config oder ANTHROPIC_API_KEY als ENV-Variable.",
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
