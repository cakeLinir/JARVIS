from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Pfadkonstanten für den Log-Output (unabhängig von config_loader, kein zirkulärer Import)
_AGENT_DIR = Path(__file__).resolve().parents[2]  # desktop-agent/
_LOG_DIR = _AGENT_DIR.parent / "logs"
_LOG_FILE = _LOG_DIR / "desktop-agent.log"
_JSON_LOG_FILE = _LOG_DIR / "desktop-agent.jsonl"

# JARVIS_PATCH_026_1: Projektanalyse-Rauschfilter.
JARVIS_PROJECT_ANALYSIS_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dashboard/node_modules",
    "dashboard/dist",
    ".jarvis-patch-backups",
    "logs",
    "backend/dist",
    "backend/node_modules",
    "__pycache__",
}

JARVIS_PROJECT_ANALYSIS_EXCLUDE_FILES = {
    "desktop-agent/config.local.json",
}


def jarvis_is_noise_path(path_value):
    normalized = str(path_value).replace("\\", "/").strip("/")
    lower = normalized.lower()

    for excluded in JARVIS_PROJECT_ANALYSIS_EXCLUDE_DIRS:
        excluded_lower = excluded.lower().strip("/")
        if (
            lower == excluded_lower
            or lower.startswith(excluded_lower + "/")
            or ("/" + excluded_lower + "/") in ("/" + lower + "/")
        ):
            return True

    for excluded_file in JARVIS_PROJECT_ANALYSIS_EXCLUDE_FILES:
        if lower == excluded_file.lower():
            return True

    return False


# FIX Bug 1 + 2: Toter Code aus jarvis_should_suppress_log hierher verschoben
# und fehlendes "return False" am Ende ergänzt. Vorher gab die Funktion immer
# implizit None zurück, weil der eigentliche Prüfcode niemals ausgeführt wurde.
def jarvis_is_todo_noise_path(path_value):
    normalized = str(path_value).replace("\\", "/").strip("/")
    lower = normalized.lower()

    if jarvis_is_noise_path(normalized):
        return True

    if lower.startswith("docs/") and "todo" in lower:
        return True

    if (
        lower.endswith("config.json")
        or lower.endswith("config.local.json")
        or lower.endswith("config.local.example.json")
    ):
        return True

    return False


# JARVIS_PATCH_026_3: zentrale Log-Normalisierung und Projektanalyse-Ausgabefilter.
JARVIS_PROJECT_LOG_SUPPRESS_PATTERNS = (
    ".jarvis-patch-backups/",
    "/node_modules/",
    "/dashboard/dist/",
    "/backend/dist/",
    "/logs/",
    "__pycache__/",
    "desktop-agent/config.json:",
    "desktop-agent/config.local.json:",
    "desktop-agent/config.local.example.json:",
    "docs/todo_system.md:",
    "docs/local_agent_vps_connection.md:",
    "docs/runtime_cleanup_analysis_noise.md:",
    ".jarvis-patch-backups\\",
    "docs\\todo_system.md:",
    "docs\\runtime_cleanup_analysis_noise.md:",
    "desktop-agent\\config.json:",
    "desktop-agent\\config.local.json:",
    "desktop-agent\\config.local.example.json:",
)


def jarvis_normalize_log_text(message_value):
    message_text = str(message_value)
    replacements = {
        "ausgefÃ¼hrt": "ausgeführt",
        "geÃ¶ffnet": "geöffnet",
        "spÃ¤ter": "später",
        "fÃ¼r": "für",
        "prÃ¼fen": "prüfen",
        "Ã¼": "ü",
        "Ã¶": "ö",
        "Ã¤": "ä",
        "ÃŸ": "ß",
    }

    for bad, good in replacements.items():
        message_text = message_text.replace(bad, good)

    return message_text


def jarvis_normalize_log_event(level_value, message_value):
    level_text = str(level_value)
    message_text = jarvis_normalize_log_text(message_value)

    if (
        level_text.upper() == "ERROR"
        and "App-Start fehlgeschlagen:" in message_text
        and "App deaktiviert" in message_text
    ):
        message_text = message_text.replace(
            "App-Start fehlgeschlagen:", "App übersprungen:"
        )
        if " | App deaktiviert:" in message_text:
            message_text = (
                message_text.split(" | App deaktiviert:", 1)[0] + " | App deaktiviert"
            )
        level_text = "WARN"

    return level_text, message_text


# FIX Bug 1: Toter Code nach "return False" entfernt.
# Der Code referenzierte außerdem die Variablen "normalized" und "lower",
# die in dieser Funktion nie definiert wurden — NameError bei Aufruf wäre
# die Folge gewesen. Der korrekte Prüfcode liegt jetzt in
# jarvis_is_todo_noise_path (siehe oben).
def jarvis_should_suppress_log(level_value, message_value):
    level_text = str(level_value).upper()
    message_text = str(message_value).replace("\\", "/").lower()

    if level_text != "PROJECT":
        return False

    for pattern in JARVIS_PROJECT_LOG_SUPPRESS_PATTERNS:
        if pattern in message_text:
            return True

    return False


def configure_console_encoding() -> None:
    """
    Force UTF-8 for Windows console and Python streams.
    Prevents mojibake such as späteren/späteren mismatch in PowerShell output.
    """
    if os.name != "nt":
        return

    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


configure_console_encoding()


def log(level: str, message: str, **fields: Any) -> None:
    # JARVIS_PATCH_026_4_LOG_HOOK
    try:
        level, message = jarvis_normalize_log_event(level, message)
        if jarvis_should_suppress_log(level, message):
            return
    except Exception:
        pass
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    safe_message = (
        message.replace(os.getenv("JARVIS_AGENT_TOKEN", ""), "***")
        if os.getenv("JARVIS_AGENT_TOKEN")
        else message
    )

    event = {
        "timestamp": datetime.now().isoformat(),
        "component": "desktop-agent",
        "level": level,
        "message": safe_message,
        **fields,
    }

    line = f"{event['timestamp']} [{level}] {safe_message}"
    print(line)

    with _LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")

    with _JSON_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
