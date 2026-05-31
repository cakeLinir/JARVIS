from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

from execution.app_launcher import detached_popen, start_app  # noqa: F401
from security.config_guard import (
    CONFIG_REQUIRED_MARKER,
    contains_placeholder,
    redact,
    validate_agent_config,
)

# ── JARVIS_PATCH_026_1: Projektanalyse-Rauschfilter ───────────────────────────

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


def jarvis_is_noise_path(path_value: Any) -> bool:
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
# und fehlendes "return False" am Ende ergänzt.
def jarvis_is_todo_noise_path(path_value: Any) -> bool:
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


# ── JARVIS_PATCH_026_3: zentrale Log-Normalisierung ───────────────────────────

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


def jarvis_normalize_log_text(message_value: Any) -> str:
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


def jarvis_normalize_log_event(level_value: Any, message_value: Any) -> tuple[str, str]:
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
def jarvis_should_suppress_log(level_value: Any, message_value: Any) -> bool:
    level_text = str(level_value).upper()
    message_text = str(message_value).replace("\\", "/").lower()
    if level_text != "PROJECT":
        return False
    for pattern in JARVIS_PROJECT_LOG_SUPPRESS_PATTERNS:
        if pattern in message_text:
            return True
    return False


# ── Console-Encoding (Windows UTF-8) ─────────────────────────────────────────


def configure_console_encoding() -> None:
    """
    Force UTF-8 for Windows console and Python streams.
    Prevents mojibake in PowerShell output.
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

# ── Pfad-Konstanten ───────────────────────────────────────────────────────────

AGENT_DIR = Path(__file__).resolve().parents[1]
JARVIS_ROOT = AGENT_DIR.parent
CONFIG_PATH = AGENT_DIR / "config.json"
LOCAL_CONFIG_PATH = AGENT_DIR / "config.local.json"
LOG_DIR = JARVIS_ROOT / "logs"
LOG_FILE = LOG_DIR / "desktop-agent.log"
JSON_LOG_FILE = LOG_DIR / "desktop-agent.jsonl"

MORNING_ROUTINE_LOCK = threading.Lock()

# ── Logging ───────────────────────────────────────────────────────────────────


def log(level: str, message: str, **fields: Any) -> None:
    # JARVIS_PATCH_026_4_LOG_HOOK
    try:
        level, message = jarvis_normalize_log_event(level, message)
        if jarvis_should_suppress_log(level, message):
            return
    except Exception:
        pass

    LOG_DIR.mkdir(parents=True, exist_ok=True)
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
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")
    with JSON_LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


# ── Config laden ──────────────────────────────────────────────────────────────


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        parsed = json.load(file)
    if not isinstance(parsed, dict):
        raise ValueError(f"Config muss ein JSON-Objekt sein: {path}")
    return parsed


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log("ERROR", f"Config nicht gefunden: {CONFIG_PATH}")
        sys.exit(1)
    config = load_json_file(CONFIG_PATH)
    if LOCAL_CONFIG_PATH.exists():
        config = deep_merge(config, load_json_file(LOCAL_CONFIG_PATH))
        log("INFO", f"Lokale Config geladen: {LOCAL_CONFIG_PATH}")
    else:
        log(
            "WARN",
            f"{CONFIG_REQUIRED_MARKER}: Lokale Config fehlt: {LOCAL_CONFIG_PATH}",
        )
    env_agent_token = os.getenv("JARVIS_AGENT_TOKEN", "").strip()
    if env_agent_token:
        config["agentToken"] = env_agent_token
        log("INFO", f"Agent-Token aus ENV geladen: {redact(env_agent_token)}")
    env_backend_url = os.getenv("JARVIS_BACKEND_URL", "").strip()
    if env_backend_url:
        config["backendUrl"] = env_backend_url
        log("INFO", "Backend-URL aus ENV geladen.")
    findings = validate_agent_config(config)
    for finding in findings:
        log(
            finding.level.upper(),
            finding.message,
            code=finding.code,
            field=finding.field,
        )
    return config


# ── TODO-Hilfsfunktionen ──────────────────────────────────────────────────────


# FIX Bug 3: get_todo_path() war definiert aber nie aufgerufen.
# Bleibt erhalten und als "aktuell ungenutzt" markiert.
def get_todo_path(config: dict[str, Any]) -> Path | None:
    todo_config = config.get("todo", {})
    provider = str(todo_config.get("provider", "markdown")).strip().lower()
    if provider != "markdown":
        return None
    todo_path_value = todo_config.get("markdownPath")
    if not todo_path_value:
        log("ERROR", "KONFIGURATION_ERFORDERLICH: TODO Markdown-Pfad fehlt.")
        return None
    todo_path = Path(todo_path_value)
    if not todo_path.exists():
        log(
            "ERROR",
            f"KONFIGURATION_ERFORDERLICH: TODO-Datei existiert nicht: {todo_path}",
        )
        return None
    return todo_path


def open_todo(config: dict[str, Any]) -> bool:
    try:
        from todo.provider import open_todo_provider

        return open_todo_provider(config, log)
    except Exception as exc:
        log("ERROR", f"TODO Provider konnte nicht geöffnet werden: {exc}")
        return False


def read_todos(config: dict[str, Any]) -> list[str]:
    try:
        from todo.provider import read_open_todo_titles

        return read_open_todo_titles(config, log)
    except Exception as exc:
        log("ERROR", f"TODO Provider konnte nicht gelesen werden: {exc}")
        return []


# ── Fenster-Management ────────────────────────────────────────────────────────


def arrange_windows() -> None:
    try:
        from windows.window_manager import arrange_morning_windows

        arrange_morning_windows(log)
    except ImportError as exc:
        log(
            "ERROR",
            f"Fenster-Manager Abhängigkeit fehlt: {exc}",
            errorCode="window_manager_dependency_missing",
        )
        log("ERROR", "Installiere mit: py -3 -m pip install pywin32 psutil")
    except Exception as exc:
        log(
            "ERROR",
            f"Fensteranordnung fehlgeschlagen: {exc}",
            errorCode="window_arrange_failed",
        )


# ── TODO Review (Morning Routine) ─────────────────────────────────────────────


# JARVIS_PATCH_027_3_4: Morning Routine TODO Review Integration.
def run_todo_review_for_morning(
    config: dict[str, Any],
) -> dict[str, Any] | None:
    todo_review_config = (
        config.get("todoReview", {}) if isinstance(config, dict) else {}
    )
    if not isinstance(todo_review_config, dict):
        todo_review_config = {}
    enabled = bool(todo_review_config.get("enabled", True))
    if not enabled:
        log("INFO", "TODO Review für Morning Routine deaktiviert.")
        return None
    apply_during_morning = bool(
        todo_review_config.get("applyDuringMorningRoutine", False)
    )
    try:
        from todo.todo_review_command import run_agent_todo_review

        project_config = config.get("project", {}) if isinstance(config, dict) else {}
        repo_root = None
        if isinstance(project_config, dict):
            repo_root = project_config.get("lastProjectPath")
        result = run_agent_todo_review(
            repo_root=repo_root,
            apply_to_todo=apply_during_morning,
            log=log,
        )
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        if result.get("ok"):
            log(
                "OK",
                "TODO Review Morning Routine abgeschlossen: "
                f"openItems={summary.get('openItems', 0)}, "
                f"scheduledItems={summary.get('scheduledItems', 0)}, "
                f"applied={summary.get('applied', False)}",
            )
        else:
            log(
                "WARN",
                f"TODO Review Morning Routine fehlgeschlagen: "
                f"{result.get('message', 'unbekannt')}",
                errorCode=result.get("errorCode") or "todo_review_failed",
            )
        return result
    except Exception as exc:
        log(
            "ERROR",
            f"TODO Review Morning Routine Fehler: {exc}",
            errorCode="todo_review_exception",
        )
        return {
            "ok": False,
            "errorCode": "todo_review_exception",
            "message": str(exc),
        }


# ── Projekt-Analyse ───────────────────────────────────────────────────────────


def analyze_current_project(config: dict[str, Any]) -> str:
    try:
        from integrations.project_analyzer import (
            analyze_project,
            build_human_summary,
        )

        project_config = config.get("project", {})
        project_path = (
            project_config.get("lastProjectPath")
            if isinstance(project_config, dict)
            else None
        )
        analysis = analyze_project(project_path, log)
        return str(analysis.get("summary") or build_human_summary(analysis))
    except Exception as exc:
        log(
            "ERROR",
            f"Projektanalyse fehlgeschlagen: {exc}",
            errorCode="project_analysis_failed",
        )
        return f"Projektanalyse fehlgeschlagen: {exc}"


# ── Backend-Kommunikation ─────────────────────────────────────────────────────


def send_agent_status_safe(config: dict[str, Any], status: str) -> None:
    try:
        from integrations.backend_client import send_agent_status

        send_agent_status(config, log, status)
    except Exception as exc:
        log(
            "ERROR",
            f"Agent-Status konnte nicht ans Backend gesendet werden: {exc}",
            errorCode="agent_status_send_failed",
        )


def get_todo_status_safe(config: dict[str, Any]) -> dict[str, Any]:
    try:
        from todo.provider import get_todo_status

        return get_todo_status(config, log)
    except Exception as exc:
        log("ERROR", f"TODO Status konnte nicht ermittelt werden: {exc}")
        return {
            "provider": "unknown",
            "errorCode": "todo_status_failed",
            "message": str(exc),
        }


def send_morning_log_safe(
    config: dict[str, Any],
    started_apps: list[str],
    failed_apps: list[str],
    todos: list[str],
    project_summary: str,
) -> None:
    try:
        from integrations.backend_client import send_morning_log

        todo_status = get_todo_status_safe(config)
        todo_provider = str(todo_status.get("provider", "unknown"))
        send_morning_log(
            config=config,
            log=log,
            started_apps=started_apps,
            failed_apps=failed_apps,
            todos=todos,
            project_summary=project_summary,
            todo_provider=todo_provider,
            todo_status=todo_status,
        )
    except Exception as exc:
        log(
            "ERROR",
            f"Morgenroutine-Log konnte nicht ans Backend gesendet werden: {exc}",
        )


# ── Morning Routine ───────────────────────────────────────────────────────────


def run_morning_routine(config: dict[str, Any], speak: Any = None) -> None:
    if not MORNING_ROUTINE_LOCK.acquire(blocking=False):
        log(
            "WARN",
            "Morgenroutine läuft bereits. Neuer Start wurde blockiert.",
            errorCode="morning_routine_already_running",
        )
        return

    _speak = speak or (lambda text: None)
    try:
        log("INFO", "Guten Morgen. Starte Morgenroutine.")
        _speak("Guten Morgen. Ich starte die Morgenroutine.")
        started_apps: list[str] = []
        failed_apps: list[str] = []
        apps = config.get("apps", {})
        if not isinstance(apps, dict):
            log(
                "ERROR",
                f"{CONFIG_REQUIRED_MARKER}: apps-Konfiguration ist ungültig.",
                errorCode="apps_config_invalid",
            )
            apps = {}
        for app_name in ["obs", "discord", "spotify", "whatsapp", "vscode"]:
            app_config = apps.get(app_name)
            if not isinstance(app_config, dict):
                log(
                    "WARN",
                    f"Keine App-Konfiguration gefunden: {app_name}",
                    errorCode="app_config_missing",
                    app=app_name,
                )
                failed_apps.append(app_name)
                continue
            result = start_app(app_name, app_config, log)
            if result.success:
                started_apps.append(app_name)
            else:
                failed_apps.append(app_name)
                app_log_level, app_log_message = jarvis_normalize_log_event(
                    "ERROR",
                    f"App-Start fehlgeschlagen: {app_name} | {result.message}",
                )
                log(
                    app_log_level,
                    app_log_message,
                    errorCode=result.error_code or "app_start_failed",
                    app=app_name,
                )

        todo_opened = open_todo(config)
        if todo_opened:
            started_apps.append("todo")
        else:
            failed_apps.append("todo")

        todos = read_todos(config)
        if todos:
            log("INFO", "Heutige TODOs:")
            for item in todos:
                log("TODO", item)
        else:
            log("INFO", "Keine offenen TODOs für heute gefunden.")

        run_todo_review_for_morning(config)
        project_summary = analyze_current_project(config)
        send_morning_log_safe(
            config=config,
            started_apps=started_apps,
            failed_apps=failed_apps,
            todos=todos,
            project_summary=project_summary,
        )
        log("INFO", "Warte kurz auf Programmfenster.")
        time.sleep(5)
        arrange_windows()
        log("INFO", "Morgenroutine MVP abgeschlossen.")
        _speak("Morgenroutine abgeschlossen.")
    finally:
        MORNING_ROUTINE_LOCK.release()


# ── Backend Command Handling ──────────────────────────────────────────────────


def complete_backend_command(
    config: dict[str, Any],
    command_id: str,
    status: str,
    result: str,
    details: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    from integrations.backend_client import complete_command

    complete_command(
        config=config,
        log=log,
        command_id=command_id,
        status=status,
        result=result,
        details=details or {},
        error_code=error_code,
    )


def handle_backend_command(
    config: dict[str, Any],
    command: dict[str, Any],
    speak: Any = None,
) -> None:
    command_id = command.get("id")
    command_type = command.get("type")
    correlation_id = command.get("correlationId")
    if not command_id:
        log(
            "ERROR",
            "Backend-Command ohne ID erhalten.",
            errorCode="command_id_missing",
        )
        return
    log(
        "INFO",
        f"Backend-Command erhalten: {command_id} | {command_type}",
        commandId=command_id,
        correlationId=correlation_id,
    )
    try:
        if command_type == "morning_routine":
            run_morning_routine(config, speak=speak)
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result="Morning Routine wurde lokal ausgeführt.",
                details={
                    "type": command_type,
                    "correlationId": correlation_id,
                },
            )
            return

        if command_type == "dev_news":
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result=(
                    "Dev-News werden aktuell über Backend /api/news/dev bereitgestellt."
                ),
                details={
                    "type": command_type,
                    "correlationId": correlation_id,
                },
            )
            return

        if command_type == "app_open":
            payload = command.get("payload") or {}
            app_name = (
                str(payload.get("app", "")).strip().lower()
                if isinstance(payload, dict)
                else ""
            )
            app_config = (
                config.get("apps", {}).get(app_name)
                if isinstance(config.get("apps", {}), dict)
                else None
            )
            if not app_name or not isinstance(app_config, dict):
                complete_backend_command(
                    config=config,
                    command_id=command_id,
                    status="rejected",
                    result=f"App nicht konfiguriert: {app_name}",
                    details={
                        "type": command_type,
                        "app": app_name,
                        "correlationId": correlation_id,
                    },
                    error_code="app_not_configured",
                )
                return
            launch_result = start_app(app_name, app_config, log)
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if launch_result.success else "failed",
                result=launch_result.message,
                details={
                    "type": command_type,
                    "app": app_name,
                    "correlationId": correlation_id,
                },
                error_code=launch_result.error_code,
            )
            return

        if command_type == "system_stop":
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result=(
                    "System-Stop Command erhalten. "
                    "Agent bleibt bis zum lokalen Loop-Ende aktiv."
                ),
                details={
                    "type": command_type,
                    "correlationId": correlation_id,
                },
            )
            return

        complete_backend_command(
            config=config,
            command_id=command_id,
            status="rejected",
            result=f"Unbekannter Command-Typ: {command_type}",
            details={
                "type": command_type,
                "correlationId": correlation_id,
            },
            error_code="unknown_command_type",
        )

    except Exception as exc:
        log(
            "ERROR",
            f"Backend-Command fehlgeschlagen: {command_id} | {exc}",
            commandId=command_id,
            errorCode="command_execution_failed",
        )
        try:
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="failed",
                result=str(exc),
                details={
                    "type": command_type,
                    "correlationId": correlation_id,
                },
                error_code="command_execution_failed",
            )
        except Exception as inner_exc:
            log(
                "ERROR",
                f"Command-Fehler konnte nicht ans Backend gesendet werden: {inner_exc}",
                errorCode="command_failure_report_failed",
            )


# ── Heartbeat & Polling ───────────────────────────────────────────────────────


def get_heartbeat_interval_seconds(config: dict[str, Any]) -> int:
    runtime_config = config.get("runtime", {})
    raw_value = (
        runtime_config.get("heartbeatIntervalSeconds", 30)
        if isinstance(runtime_config, dict)
        else 30
    )
    try:
        interval = int(raw_value)
    except Exception:
        interval = 30
    return max(10, min(interval, 300))


def heartbeat_loop(config: dict[str, Any], stop_event: threading.Event) -> None:
    interval = get_heartbeat_interval_seconds(config)
    log("INFO", f"Agent Heartbeat gestartet: alle {interval}s.")
    while not stop_event.wait(interval):
        send_agent_status_safe(config, "online")
    log("INFO", "Agent Heartbeat beendet.")


def command_poll_loop(
    config: dict[str, Any],
    stop_event: threading.Event,
    speak: Any = None,
) -> None:
    log("INFO", "Backend Command Polling gestartet.")
    while not stop_event.is_set():
        try:
            from integrations.backend_client import get_next_command

            command = get_next_command(config, log)
            if command:
                handle_backend_command(config, command, speak=speak)
        except Exception as exc:
            log(
                "ERROR",
                f"Command Polling Fehler: {exc}",
                errorCode="command_poll_failed",
            )
        stop_event.wait(5)
    log("INFO", "Backend Command Polling beendet.")


# ── Hilfs-Utilities ───────────────────────────────────────────────────────────


def normalize_command(command: str) -> str:
    try:
        from voice.phrases import normalize_phrase

        return normalize_phrase(command)
    except Exception:
        return " ".join(command.strip().lower().split())


def _add_markdown_todo(config: dict[str, Any], text: str) -> bool:
    todo_config = config.get("todo", {})
    path_value = (
        todo_config.get("markdownPath") if isinstance(todo_config, dict) else None
    )
    if not path_value:
        return False
    path = Path(str(path_value))
    if not path.exists():
        return False
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n- [ ] {text}")
        return True
    except Exception as exc:
        log("ERROR", f"TODO konnte nicht hinzugefügt werden: {exc}")
        return False


# ── Schicht-Hilfsfunktionen ───────────────────────────────────────────────────

_WEEKDAYS_DE: dict[str, int] = {
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonntag": 6,
}

_SHIFT_LABELS: dict[str, str] = {
    "tag": "Tagschicht (07:00–19:00)",
    "nacht": "Nachtschicht (19:00–07:00)",
    "frei": "Frei",
    "fakt_frueh": "FAKT IST! Früh (07:00–14:30)",
    "fakt_spaet": "FAKT IST! Spät (14:30–21:30)",
}


def _resolve_date(date_str: str) -> date:
    """Löst relative Datumsangaben in ein konkretes date-Objekt auf."""
    today = date.today()
    lower = date_str.strip().lower()
    if lower in ("heute", "today"):
        return today
    if lower in ("morgen", "tomorrow"):
        return today + timedelta(days=1)
    if lower == "übermorgen":
        return today + timedelta(days=2)
    if lower in _WEEKDAYS_DE:
        target_wd = _WEEKDAYS_DE[lower]
        days_ahead = (target_wd - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)
    try:
        return date.fromisoformat(date_str.strip())
    except Exception:
        return today


def _get_shifts_file() -> Path:
    shifts_file = JARVIS_ROOT / "data" / "shifts.json"
    shifts_file.parent.mkdir(parents=True, exist_ok=True)
    return shifts_file


def _load_shifts() -> dict[str, str]:
    shifts_file = _get_shifts_file()
    if shifts_file.exists():
        try:
            with shifts_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _save_shifts(shifts_data: dict[str, str]) -> None:
    shifts_file = _get_shifts_file()
    with shifts_file.open("w", encoding="utf-8") as f:
        json.dump(shifts_data, f, ensure_ascii=False, indent=2)


def _streaming_advice(shift: str | None, date_iso: str) -> str:
    """Gibt eine Streaming-Empfehlung basierend auf dem Schichttyp zurück."""
    if not shift:
        return (
            f"Für {date_iso} ist keine Schicht eingetragen. "
            "Ich kann keine Empfehlung geben."
        )
    recommendations = {
        "frei": (
            "Du hast frei — Streaming ist uneingeschränkt möglich. Genieß den Tag!"
        ),
        "tag": (
            "Tagschicht (07:00–19:00): Abends ab ca. 20:00 Uhr wäre Streaming "
            "möglich, plane aber ein Ende vor Mitternacht ein."
        ),
        "nacht": (
            "Nachtschicht (19:00–07:00): Tagsüber solltest du schlafen. "
            "Streaming davor ist nur bedingt sinnvoll — Erholung hat Vorrang."
        ),
        "fakt_frueh": (
            "FAKT IST! Früh (07:00–14:30): Ab 15:00 Uhr wäre Streaming möglich, "
            "achte aber auf genug Schlaf für den nächsten Tag."
        ),
        "fakt_spaet": (
            "FAKT IST! Spät (14:30–21:30): Morgens wäre Streaming möglich. "
            "Abends rechtzeitig abschalten, damit du fit zur Schicht bist."
        ),
    }
    return recommendations.get(
        shift, f"Unbekannte Schicht '{shift}' — keine Empfehlung möglich."
    )


# ── System-Control ────────────────────────────────────────────────────────────


def _handle_system_control(action: str, value: Any) -> str:
    import ctypes
    import subprocess

    if action == "set_volume":
        pct = max(0, min(100, int(value or 50)))
        level = int(65535 * pct / 100)
        ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
        return f"Lautstärke auf {pct} Prozent gesetzt."

    if action == "mute":
        ctypes.windll.winmm.waveOutSetVolume(0, 0)
        return "Stummgeschaltet."

    if action == "unmute":
        level = int(65535 * 0.5)
        ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
        return "Stummschaltung aufgehoben."

    if action == "sleep":
        subprocess.run(
            [
                "powershell",
                "-NonInteractive",
                "-NoProfile",
                "-command",
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState("
                "'Suspend', $false, $false)",
            ],
            capture_output=True,
            timeout=10,
        )
        return "Computer wurde in den Ruhemodus versetzt."

    if action == "shutdown":
        subprocess.run(["shutdown", "/s", "/t", "30"])
        return "Computer wird in 30 Sekunden heruntergefahren."

    return f"Unbekannte Systemsteuerung: {action}"


# ── AI Tool Execution ─────────────────────────────────────────────────────────


def _execute_ai_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    config: dict[str, Any],
    speak: Any,
    reminder_manager: Any = None,
) -> tuple[bool, str | None]:
    """
    Führt einen von Claude gewählten Tool-Call aus.
    Gibt (should_stop, result_text) zurück.
    result_text ist None wenn die Antwort bereits gesprochen wurde (answer-Tool),
    sonst ein String den brain.submit_tool_result() an Claude zurückmeldet.
    """

    # ── answer ────────────────────────────────────────────────────────────────
    if tool_name == "answer":
        speak(str(tool_input.get("text", "")))
        return False, None

    # ── open_app ──────────────────────────────────────────────────────────────
    if tool_name == "open_app":
        app_name = str(tool_input.get("app", "")).strip().lower()
        app_config = (
            config.get("apps", {}).get(app_name)
            if isinstance(config.get("apps"), dict)
            else None
        )
        if not isinstance(app_config, dict):
            return False, f"Keine Konfiguration für '{app_name}' gefunden."
        result = start_app(app_name, app_config, log)
        if result.success:
            return False, f"'{app_name}' wurde erfolgreich geöffnet."
        return False, f"'{app_name}' konnte nicht geöffnet werden: {result.error}"

    # ── system_control ────────────────────────────────────────────────────────
    if tool_name == "system_control":
        try:
            result_text = _handle_system_control(
                str(tool_input.get("action", "")),
                tool_input.get("value"),
            )
            return False, result_text
        except Exception as exc:
            log(
                "ERROR",
                f"Systemsteuerung fehlgeschlagen: {exc}",
                errorCode="system_control_failed",
            )
            return False, "Die Systemsteuerung hat nicht funktioniert."

    # ── todo_action ───────────────────────────────────────────────────────────
    if tool_name == "todo_action":
        action = str(tool_input.get("action", ""))

        if action == "read":
            todos = read_todos(config)
            if todos:
                return False, f"Du hast {len(todos)} offene TODOs: " + ", ".join(todos[:5])
            return False, "Du hast keine offenen TODOs."

        if action == "add":
            text = str(tool_input.get("text", "")).strip()
            if text and _add_markdown_todo(config, text):
                return False, f"TODO '{text}' wurde hinzugefügt."
            return False, "Das TODO konnte nicht hinzugefügt werden."

        if action == "complete":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            if todo_ref:
                return False, f"'{todo_ref}' wurde als erledigt markiert."
            return False, "Kein TODO-Titel angegeben."

        if action == "reschedule":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            due_date = str(tool_input.get("due_date", "")).strip()
            if todo_ref and due_date:
                return False, f"'{todo_ref}' wurde auf {due_date} verschoben."
            return False, "TODO-Titel und neues Datum werden benötigt."

        if action == "set_priority":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            priority = tool_input.get("priority")
            if todo_ref and priority is not None:
                return False, f"Priorität von '{todo_ref}' auf {priority} gesetzt."
            return False, "TODO-Titel und Prioritätswert werden benötigt."

        if action == "set_reminder":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            minutes = tool_input.get("reminder_minutes")
            if todo_ref and minutes is not None:
                minutes_int = int(minutes)
                if reminder_manager is not None:
                    trigger = reminder_manager.add_in_minutes(todo_ref, minutes_int)
                    return False, (
                        f"Erinnerung für '{todo_ref}' gesetzt: "
                        f"{trigger.strftime('%H:%M')} Uhr."
                    )
                hours = minutes_int // 60
                mins = minutes_int % 60
                time_str = f"{hours}h {mins}min" if hours else f"{mins}min"
                return False, f"Erinnerung für '{todo_ref}' in {time_str} vorgemerkt."
            return False, "TODO-Titel und Erinnerungszeit werden benötigt."

        return False, f"Unbekannte TODO-Aktion: {action}"

    # ── shift_action ──────────────────────────────────────────────────────────
    if tool_name == "shift_action":
        action = str(tool_input.get("action", ""))
        date_str = str(tool_input.get("date", "heute")).strip()
        shift_type = str(tool_input.get("shift_type", "")).strip()

        resolved = _resolve_date(date_str)
        date_iso = resolved.isoformat()
        shifts_data = _load_shifts()

        if action == "set" and shift_type:
            shifts_data[date_iso] = shift_type
            _save_shifts(shifts_data)
            label = _SHIFT_LABELS.get(shift_type, shift_type)
            return False, f"Schicht für {date_iso} eingetragen: {label}"

        if action == "get":
            existing = shifts_data.get(date_iso)
            if existing:
                label = _SHIFT_LABELS.get(existing, existing)
                return False, f"Am {date_iso}: {label}"
            return False, f"Für {date_iso} ist keine Schicht eingetragen."

        if action == "streaming_advice":
            advice = _streaming_advice(shifts_data.get(date_iso), date_iso)
            return False, advice

        return False, "Unbekannte Schicht-Aktion."

    # ── weather_action ────────────────────────────────────────────────────────
    if tool_name == "weather_action":
        city = str(tool_input.get("city", "")).strip()
        if not city:
            weather_cfg = config.get("weather", {})
            city = (
                str(weather_cfg.get("city", "Berlin")).strip()
                if isinstance(weather_cfg, dict)
                else "Berlin"
            )
        try:
            import urllib.parse
            import urllib.request

            encoded_city = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded_city}?format=3&lang=de"
            req = urllib.request.Request(
                url, headers={"User-Agent": "JARVIS-Agent/1.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                weather_text = resp.read().decode("utf-8").strip()
            return False, f"Wetter für {city}: {weather_text}"
        except Exception as exc:
            log(
                "ERROR",
                f"Wetter-Abfrage fehlgeschlagen: {exc}",
                errorCode="weather_fetch_failed",
            )
            return False, f"Wetter für {city} konnte nicht abgerufen werden."

    # ── open_url ──────────────────────────────────────────────────────────────
    if tool_name == "open_url":
        import webbrowser

        url = str(tool_input.get("url", "")).strip()
        if url:
            webbrowser.open(url)
            return False, f"{url} wurde im Browser geöffnet."
        return False, "Keine URL angegeben."

    # ── run_routine ───────────────────────────────────────────────────────────
    if tool_name == "run_routine":
        name = str(tool_input.get("name", ""))
        if name == "morning_routine":
            threading.Thread(
                target=run_morning_routine,
                args=(config, speak),
                daemon=True,
            ).start()
            return False, "Morgenroutine wurde gestartet."
        return False, f"Unbekannte Routine: {name}"

    # ── Unbekanntes Tool ──────────────────────────────────────────────────────
    log(
        "WARN",
        f"Unbekanntes AI-Tool: {tool_name}",
        errorCode="unknown_ai_tool",
    )
    return False, None


# ── Lokaler Command-Handler ───────────────────────────────────────────────────


def _handle_local_command(
    command: str,
    config: dict[str, Any],
    wake_words: list[str],
    stop_event: threading.Event,
    speak: Any,
    brain: Any = None,
    reminder_manager: Any = None,
) -> bool:
    """
    Verarbeitet einen normalisierten Textbefehl.
    Gibt True zurück wenn der Agent stoppen soll.
    """
    if command in ["exit", "quit", "beenden"]:
        send_agent_status_safe(config, "offline")
        stop_event.set()
        log("INFO", "JARVIS Local Client wird beendet.")
        return True

    if command in ["jarvis, stopp", "jarvis, abbrechen", "jarvis, beenden"]:
        send_agent_status_safe(config, "stopped")
        stop_event.set()
        log("WARN", "Not-Aus ausgelöst.")
        return True

    if command == "guten morgen jarvis":
        run_morning_routine(config, speak=speak)
        return False

    if command in wake_words:
        log("INFO", "JARVIS ist aktiv.")
        speak("Ja, ich bin bereit.")
        return False

    # ── Unbekannter Befehl → AI-Brain ─────────────────────────────────────────
    if brain is None:
        speak("Das habe ich nicht verstanden.")
        return False

    try:
        log("INFO", f"AI-Brain verarbeitet: {command}")
        tool_calls = brain.process(command)

        feedback: list[dict[str, Any]] = []
        for call in tool_calls:
            stop, result = _execute_ai_tool(
                call.get("name", ""),
                call.get("input", {}),
                config,
                speak,
                reminder_manager=reminder_manager,
            )
            if stop:
                return True
            if result is not None and call.get("id"):
                feedback.append({"id": call["id"], "result": result})

        # Tool-Ergebnisse an Claude zurückmelden → natürliche Antwort
        if feedback:
            synthesized = brain.submit_tool_result(feedback)
            if synthesized:
                speak(synthesized)
            else:
                # Fallback: erstes Ergebnis direkt sprechen
                speak(feedback[0]["result"])

    except Exception as exc:
        log(
            "ERROR",
            f"AI-Brain Ausführung fehlgeschlagen: {exc}",
            errorCode="ai_brain_exec_failed",
        )
        speak("Das habe ich nicht verstanden.")

    return False


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    config = load_config()

    # Voice-Status initialisieren
    try:
        from voice.controller import get_voice_status, log_voice_status

        log_voice_status(config, log)
        voice_status = get_voice_status(config)
    except Exception as exc:
        log("ERROR", f"Voice-Status konnte nicht initialisiert werden: {exc}")
        voice_status = None

    # Wake-Words laden
    try:
        from voice.phrases import get_wake_words

        wake_words = get_wake_words(config)
    except Exception:
        wake_words = config.get("wakeWords", [])

    voice_enabled = voice_status is not None and voice_status.enabled

    # TTS initialisieren
    tts_service = None
    try:
        from voice.tts_service import create_tts

        tts_service = create_tts(config)
    except Exception as exc:
        log("WARN", f"TTS konnte nicht initialisiert werden: {exc}")
        # Automatischer Fallback auf SAPI
        voice_cfg = config.get("voice", {})
        if isinstance(voice_cfg, dict) and voice_cfg.get("ttsProvider", "") != "sapi":
            try:
                fallback_cfg = {
                    **config,
                    "voice": {**voice_cfg, "ttsProvider": "sapi"},
                }
                from voice.tts_service import create_tts as create_tts_fb

                tts_service = create_tts_fb(fallback_cfg)
                log("INFO", "TTS: Fallback auf SAPI.")
            except Exception as fb_exc:
                log("WARN", f"TTS SAPI-Fallback fehlgeschlagen: {fb_exc}")

    def speak(text: str) -> None:
        if tts_service:
            tts_service.speak(text)
            try:
                tts_service.wait_done()
            except Exception:
                pass
        else:
            log("INFO", f"[TTS] {text}")

    stop_event = threading.Event()

    log("INFO", "JARVIS Local Client gestartet.")
    if voice_enabled:
        log(
            "INFO",
            f"Voice-Modus aktiv: stt={voice_status.sttProvider}, "
            f"tts={voice_status.ttsProvider}",
        )
    else:
        log(
            "INFO",
            "Textmodus aktiv. Tippe eine Nachricht oder 'exit' zum Beenden.",
        )

    send_agent_status_safe(config, "online")

    # AI-Brain initialisieren
    brain = None
    try:
        from integrations.ai_brain import create_brain

        _WEEKDAY_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

        def _build_context() -> str:
            now = datetime.now()
            weekday = _WEEKDAY_DE[now.weekday()]
            lines = [f"Datum/Uhrzeit: {weekday}, {now.strftime('%d.%m.%Y, %H:%M')} Uhr"]
            try:
                shifts = _load_shifts()
                shift = shifts.get(now.date().isoformat())
                lines.append(
                    f"Heutige Schicht: {_SHIFT_LABELS.get(shift, shift)}"
                    if shift
                    else "Heutige Schicht: Keine eingetragen"
                )
            except Exception:
                pass
            try:
                todos = read_todos(config)
                lines.append(
                    f"Offene TODOs: {', '.join(todos[:5])}"
                    if todos
                    else "Offene TODOs: Keine"
                )
            except Exception:
                pass
            return "\n".join(lines)

        brain = create_brain(
            config,
            log,
            context_fn=_build_context,
            history_path=JARVIS_ROOT / "data" / "ai_history.json",
        )
        if brain:
            log("INFO", "AI-Brain bereit. Unterhaltungsmodus aktiv.")
        else:
            log("WARN", "AI-Brain nicht verfügbar. Nur Basis-Befehle aktiv.")
    except Exception as exc:
        log("WARN", f"AI-Brain konnte nicht geladen werden: {exc}")

    def request_stop() -> None:
        send_agent_status_safe(config, "stopped")
        stop_event.set()
        log("WARN", "Lokaler Stop wurde angefordert.")

    # Reminder-Manager initialisieren
    reminder_manager = None
    try:
        from utils.reminder import ReminderManager

        reminder_manager = ReminderManager(
            data_path=JARVIS_ROOT / "data" / "reminders.json",
            log=log,
            speak=speak,
        )
        reminder_manager.start()
    except Exception as exc:
        log("WARN", f"Reminder-Manager konnte nicht gestartet werden: {exc}")

    # Lokale Agent-API starten (mit Brain-Referenz)
    local_api_server = None
    try:
        from local_api import start_local_api

        def _noop_speak(_: str) -> None:
            pass

        def _tool_executor(tool_calls: list) -> list:
            feedback = []
            for call in tool_calls:
                _, result = _execute_ai_tool(
                    call.get("name", ""),
                    call.get("input", {}),
                    config,
                    _noop_speak,
                    reminder_manager=reminder_manager,
                )
                if result is not None and call.get("id"):
                    feedback.append({"id": call["id"], "result": result})
            return feedback

        local_api_server = start_local_api(
            config=config,
            log=log,
            run_morning=lambda: run_morning_routine(config, speak=speak),
            stop_agent=request_stop,
            brain=brain,
            tool_executor=_tool_executor,
            speak_fn=speak,
        )
    except Exception as exc:
        log(
            "ERROR",
            f"Lokale Agent-API konnte nicht gestartet werden: {exc}",
            errorCode="local_api_start_failed",
        )

    # Routine-Scheduler starten
    try:
        from scheduler import RoutineScheduler

        def _dispatch_scheduled_routine(routine: dict[str, Any]) -> None:
            for action in routine.get("actions", []):
                if action == "morning_routine":
                    run_morning_routine(config, speak=speak)
                else:
                    log(
                        "WARN",
                        f"Unbekannte Routine-Aktion: {action}",
                        errorCode="unknown_routine_action",
                    )

        routine_scheduler = RoutineScheduler(
            config=config,
            log=log,
            run_routine=_dispatch_scheduled_routine,
            stop_event=stop_event,
        )
        routine_scheduler.start()
    except Exception as exc:
        log("WARN", f"Routine-Scheduler konnte nicht gestartet werden: {exc}")

    # Command-Polling Thread
    polling_thread = threading.Thread(
        target=command_poll_loop,
        args=(config, stop_event, speak),
        daemon=True,
    )
    polling_thread.start()

    # Heartbeat Thread
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(config, stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    # ── Voice-Modus ──────────────────────────────────────────────────────────
    if voice_enabled:
        try:
            from voice.controller import VoiceController

            def _voice_command_handler(_cfg, _log, text: str) -> None:  # noqa: ARG001
                normalized = normalize_command(text)
                should_stop = _handle_local_command(
                    normalized,
                    config,
                    wake_words,
                    stop_event,
                    speak,
                    brain=brain,
                    reminder_manager=reminder_manager,
                )
                if should_stop:
                    stop_event.set()
                return None  # VoiceController spricht nicht noch einmal

            voice_controller = VoiceController(
                config=config,
                log=log,
                command_handler=_voice_command_handler,
                tts=tts_service,  # bestehende TTS-Instanz wiederverwenden
            )
            voice_controller.start()
            stop_event.wait()
            voice_controller.stop()

        except Exception as exc:
            log(
                "ERROR",
                f"VoiceController fehlgeschlagen: {exc}. Fallback auf Textmodus.",
                errorCode="voice_mode_failed",
            )
            voice_enabled = False

    # ── Text-Modus (Fallback / Standard) ─────────────────────────────────────
    if not voice_enabled:
        while not stop_event.is_set():
            try:
                command = normalize_command(input("> "))
                should_stop = _handle_local_command(
                    command,
                    config,
                    wake_words,
                    stop_event,
                    speak,
                    brain=brain,
                    reminder_manager=reminder_manager,
                )
                if should_stop:
                    break
            except KeyboardInterrupt:
                send_agent_status_safe(config, "interrupted")
                stop_event.set()
                log("WARN", "Abbruch durch Benutzer.")
                break

    # ── Aufräumen ─────────────────────────────────────────────────────────────
    if local_api_server:
        local_api_server.stop()


if __name__ == "__main__":
    main()
