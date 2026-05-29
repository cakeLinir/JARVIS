from __future__ import annotations
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from execution.app_launcher import detached_popen, start_app
from security.config_guard import ( CONFIG_REQUIRED_MARKER, contains_placeholder, redact, validate_agent_config,)
from utils.date_resolver import resolve_date, resolve_time
from shifts.shift_parser import parse_shift_type, shift_label


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


AGENT_DIR = Path(__file__).resolve().parents[1]
JARVIS_ROOT = AGENT_DIR.parent

CONFIG_PATH = AGENT_DIR / "config.json"
LOCAL_CONFIG_PATH = AGENT_DIR / "config.local.json"
LOG_DIR = JARVIS_ROOT / "logs"
LOG_FILE = LOG_DIR / "desktop-agent.log"
JSON_LOG_FILE = LOG_DIR / "desktop-agent.jsonl"

MORNING_ROUTINE_LOCK = threading.Lock()


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


# FIX Bug 3: get_todo_path() war definiert, wurde aber nirgends aufgerufen.
# Die Funktion bleibt erhalten, ist aber als "aktuell ungenutzt" markiert.
# Wenn open_todo() / read_todos() den Pfad direkt prüfen sollen,
# kann get_todo_path() dort eingebunden werden.
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


# JARVIS_PATCH_027_3_4: Morning Routine TODO Review Integration.
def run_todo_review_for_morning(config: dict[str, Any]) -> dict[str, Any] | None:
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
                f"TODO Review Morning Routine fehlgeschlagen: {result.get('message', 'unbekannt')}",
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


def analyze_current_project(config: dict[str, Any]) -> str:
    try:
        from integrations.project_analyzer import analyze_project, build_human_summary

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
                    "ERROR", f"App-Start fehlgeschlagen: {app_name} | {result.message}"
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

        todo_review_result = run_todo_review_for_morning(config)
        todo_review_summary = (
            todo_review_result.get("summary", {})
            if isinstance(todo_review_result, dict)
            else None
        )
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
    config: dict[str, Any], command: dict[str, Any], speak: Any = None
) -> None:
    command_id = command.get("id")
    command_type = command.get("type")
    correlation_id = command.get("correlationId")

    if not command_id:
        log(
            "ERROR", "Backend-Command ohne ID erhalten.", errorCode="command_id_missing"
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
                details={"type": command_type, "correlationId": correlation_id},
            )
            return

        if command_type == "dev_news":
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result="Dev-News werden aktuell über Backend /api/news/dev bereitgestellt.",
                details={"type": command_type, "correlationId": correlation_id},
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
                result="System-Stop Command erhalten. Agent bleibt bis zum lokalen Loop-Ende aktiv.",
                details={"type": command_type, "correlationId": correlation_id},
            )
            return

        complete_backend_command(
            config=config,
            command_id=command_id,
            status="rejected",
            result=f"Unbekannter Command-Typ: {command_type}",
            details={"type": command_type, "correlationId": correlation_id},
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
                details={"type": command_type, "correlationId": correlation_id},
                error_code="command_execution_failed",
            )
        except Exception as inner_exc:
            log(
                "ERROR",
                f"Command-Fehler konnte nicht ans Backend gesendet werden: {inner_exc}",
                errorCode="command_failure_report_failed",
            )


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
    config: dict[str, Any], stop_event: threading.Event, speak: Any = None
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


def normalize_command(command: str) -> str:
    try:
        from voice.phrases import normalize_phrase

        return normalize_phrase(command)
    except Exception:
        return " ".join(command.strip().lower().split())


def _add_markdown_todo(config: dict[str, Any], text: str) -> bool:
    todo_config = config.get("todo", {})
    path_value = todo_config.get("markdownPath") if isinstance(todo_config, dict) else None
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


def _handle_system_control(action: str, value: Any, speak: Any) -> None:
    import ctypes
    import subprocess

    if action == "set_volume":
        pct = max(0, min(100, int(value or 50)))
        level = int(65535 * pct / 100)
        packed = level | (level << 16)
        ctypes.windll.winmm.waveOutSetVolume(0, packed)
        speak(f"Lautstärke auf {pct} Prozent gesetzt.")

    elif action == "mute":
        ctypes.windll.winmm.waveOutSetVolume(0, 0)
        speak("Stummgeschaltet.")

    elif action == "unmute":
        level = int(65535 * 0.5)
        ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
        speak("Stummschaltung aufgehoben.")

    elif action == "sleep":
        speak("Computer wird in den Ruhemodus versetzt.")
        subprocess.run(
            [
                "powershell", "-NonInteractive", "-NoProfile", "-command",
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
            ],
            capture_output=True,
            timeout=10,
        )

    elif action == "shutdown":
        speak("Computer wird in 30 Sekunden heruntergefahren.")
        subprocess.run(["shutdown", "/s", "/t", "30"])


def _execute_ai_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    config: dict[str, Any],
    speak: Any,
) -> bool:
    """Führt einen von Claude gewählten Tool-Call aus. Gibt True zurück wenn Agent stoppen soll."""

    # ── open_app ──────────────────────────────────────────────────────────────
    if tool_name == "open_app":
        app_name = str(tool_input.get("app", "")).strip().lower()
        app_config = (
            config.get("apps", {}).get(app_name)
            if isinstance(config.get("apps"), dict)
            else None
        )
        if not isinstance(app_config, dict):
            speak(f"Ich habe keine Konfiguration für {app_name}.")
            return False
        result = start_app(app_name, app_config, log)
        speak(
            f"{app_name} wird geöffnet."
            if result.success
            else f"Ich konnte {app_name} nicht öffnen."
        )
        return False

    # ── system_control ────────────────────────────────────────────────────────
    if tool_name == "system_control":
        try:
            _handle_system_control(
                str(tool_input.get("action", "")), tool_input.get("value"), speak
            )
        except Exception as exc:
            log(
                "ERROR",
                f"Systemsteuerung fehlgeschlagen: {exc}",
                errorCode="system_control_failed",
            )
            speak("Die Systemsteuerung hat nicht funktioniert.")
        return False

    # ── todo_action ───────────────────────────────────────────────────────────
    if tool_name == "todo_action":
        action = str(tool_input.get("action", ""))

        if action == "read":
            # Backend-Todos bevorzugen, Fallback auf lokalen Provider
            try:
                from todo.todo_client import get_due_today

                todos_data = get_due_today(config, log)
                if todos_data:
                    titles = [t.get("title", "") for t in todos_data[:5]]
                    speak(
                        f"Du hast {len(todos_data)} fällige TODOs: " + ", ".join(titles)
                    )
                else:
                    speak("Du hast keine fälligen TODOs.")
            except Exception:
                # Offline-Fallback auf lokalen Provider
                todos = read_todos(config)
                if todos:
                    speak(f"Du hast {len(todos)} offene TODOs: " + ", ".join(todos[:5]))
                else:
                    speak("Du hast keine offenen TODOs.")
            return False

        if action == "add":
            title = str(tool_input.get("text", "")).strip()
            if not title:
                speak("Wie soll das TODO heißen?")
                return False

            # Datum auflösen
            raw_date = tool_input.get("due_date")
            due_date = resolve_date(str(raw_date)) if raw_date else None

            raw_time = tool_input.get("due_time")
            due_time = resolve_time(str(raw_time)) if raw_time else None

            priority = int(tool_input.get("priority", 3))
            reminder_minutes = tool_input.get("reminder_minutes")
            category = tool_input.get("category")
            description = tool_input.get("description")

            try:
                from todo.todo_client import create_todo

                todo = create_todo(
                    config=config,
                    log=log,
                    title=title,
                    due_date=due_date,
                    due_time=due_time,
                    priority=priority,
                    category=category,
                    reminder_minutes=reminder_minutes,
                    source="voice",
                    description=description,
                )
                if todo:
                    date_hint = f" für {due_date}" if due_date else ""
                    time_hint = f" um {due_time} Uhr" if due_time else ""
                    speak(f"TODO hinzugefügt: {title}{date_hint}{time_hint}.")
                else:
                    # Offline-Fallback
                    _add_markdown_todo(config, title)
                    speak(f"TODO lokal gespeichert: {title}")
            except Exception as exc:
                log("WARN", f"Todo-Backend nicht erreichbar, lokaler Fallback: {exc}")
                _add_markdown_todo(config, title)
                speak(f"TODO lokal gespeichert: {title}")
            return False

        if action == "complete":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            try:
                from todo.todo_client import (
                    find_todo_by_title,
                    complete_todo as _complete,
                )

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Ich konnte das TODO nicht finden. Welches meinst du?")
                    return False
                result = _complete(config, log, todo["id"], actor="voice")
                speak(f"Erledigt: {todo.get('title', todo_ref)}.")
            except Exception as exc:
                log("WARN", f"Todo-Complete fehlgeschlagen: {exc}")
                speak("Ich konnte das TODO nicht als erledigt markieren.")
            return False

        if action == "reschedule":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            raw_date = tool_input.get("due_date")
            new_date = resolve_date(str(raw_date)) if raw_date else None

            if not new_date:
                speak("Auf welches Datum soll ich es verschieben?")
                return False

            raw_time = tool_input.get("due_time")
            new_time = resolve_time(str(raw_time)) if raw_time else None

            try:
                from todo.todo_client import (
                    find_todo_by_title,
                    reschedule_todo as _reschedule,
                )

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Ich konnte das TODO nicht finden.")
                    return False
                _reschedule(config, log, todo["id"], new_date, new_time, actor="voice")
                speak(f"{todo.get('title', todo_ref)} verschoben auf {new_date}.")
            except Exception as exc:
                log("WARN", f"Todo-Reschedule fehlgeschlagen: {exc}")
                speak("Das Verschieben hat nicht geklappt.")
            return False

        if action == "set_priority":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            priority = int(tool_input.get("priority", 2))
            prio_labels = {
                1: "kritisch",
                2: "hoch",
                3: "mittel",
                4: "niedrig",
                5: "optional",
            }
            try:
                from todo.todo_client import find_todo_by_title, update_todo as _update

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Welches TODO meinst du?")
                    return False
                _update(config, log, todo["id"], {"priority": priority}, actor="voice")
                speak(
                    f"Priorität von '{todo.get('title', todo_ref)}' auf {prio_labels.get(priority, priority)} gesetzt."
                )
            except Exception as exc:
                log("WARN", f"Todo-Priority fehlgeschlagen: {exc}")
                speak("Die Priorität konnte nicht geändert werden.")
            return False

        if action == "set_reminder":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            reminder_minutes = int(tool_input.get("reminder_minutes", 30))
            try:
                from todo.todo_client import find_todo_by_title, update_todo as _update

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Für welches TODO soll ich die Erinnerung setzen?")
                    return False
                _update(
                    config,
                    log,
                    todo["id"],
                    {"reminderMinutes": reminder_minutes},
                    actor="voice",
                )
                hours = reminder_minutes // 60
                mins = reminder_minutes % 60
                hint = (
                    f"{hours} Stunden"
                    if hours and not mins
                    else (f"{mins} Minuten" if not hours else f"{hours}h {mins}min")
                )
                speak(
                    f"Erinnerung für '{todo.get('title', '')}' auf {hint} vorher gesetzt."
                )
            except Exception as exc:
                log("WARN", f"Todo-Reminder fehlgeschlagen: {exc}")
                speak("Die Erinnerung konnte nicht gesetzt werden.")
            return False

    # ── shift_action ──────────────────────────────────────────────────────────
    if tool_name == "shift_action":
        action = str(tool_input.get("action", ""))

        if action == "set":
            raw_date = tool_input.get("date")
            raw_type = tool_input.get("shift_type", "")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            shift_type = parse_shift_type(str(raw_type)) if raw_type else None

            if not date_str:
                speak("Für welches Datum soll ich die Schicht eintragen?")
                return False
            if not shift_type:
                speak("Welche Schicht? Tag, Nacht, FAKT Früh, FAKT Spät oder Frei?")
                return False

            try:
                from shifts.shift_client import set_shift

                shift = set_shift(
                    config, log, date=date_str, shift_type=shift_type, source="voice"
                )
                if shift:
                    speak(
                        f"{shift_label(shift_type)} für {date_str} eingetragen: {shift.get('startTime', '')}–{shift.get('endTime', '')} Uhr."
                    )
                else:
                    speak("Die Schicht konnte nicht gespeichert werden.")
            except Exception as exc:
                log("WARN", f"Shift-Set fehlgeschlagen: {exc}")
                speak("Ich konnte die Schicht nicht eintragen.")
            return False

        if action == "get":
            raw_date = tool_input.get("date")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            try:
                from shifts.shift_client import get_shift, get_today_shift

                shift = (
                    get_shift(config, log, date_str)
                    if date_str
                    else get_today_shift(config, log)
                )
                if shift:
                    speak(
                        f"{shift.get('label', '')} am {shift.get('date', '')}: {shift.get('startTime', '')}–{shift.get('endTime', '')} Uhr."
                    )
                else:
                    speak("Für dieses Datum ist keine Schicht eingetragen.")
            except Exception as exc:
                log("WARN", f"Shift-Get fehlgeschlagen: {exc}")
                speak("Ich konnte die Schicht nicht abrufen.")
            return False

        if action == "streaming_advice":
            raw_date = tool_input.get("date")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            try:
                from shifts.shift_client import get_streaming_advice

                advice = get_streaming_advice(config, log, date=date_str)
                if not advice:
                    speak("Ich konnte keine Streaming-Empfehlung abrufen.")
                    return False

                rec = advice.get("recommendation", "unknown")
                label_map = {
                    "yes": "Ja, Streaming ist heute sinnvoll.",
                    "conditional": "Bedingt sinnvoll.",
                    "no": "Nein, heute kein Streaming empfohlen.",
                    "unknown": "Keine Schicht eingetragen — bitte zuerst Schicht eintragen.",
                }
                base = label_map.get(rec, rec)

                reasons = advice.get("reasons", [])
                warnings = advice.get("warnings", [])
                latest = advice.get("latestStreamEnd")

                parts = [base]
                if reasons:
                    parts.append(reasons[0])
                if latest:
                    parts.append(f"Empfohlenes Stream-Ende: {latest} Uhr.")
                if warnings:
                    parts.append(warnings[0])

                speak(" ".join(parts))

            except Exception as exc:
                log("WARN", f"Streaming-Advice fehlgeschlagen: {exc}")
                speak("Ich konnte die Streaming-Empfehlung nicht laden.")
            return False

    # ── run_routine ───────────────────────────────────────────────────────────
    if tool_name == "run_routine":
        name = str(tool_input.get("name", ""))
        if name == "morning_routine":
            threading.Thread(
                target=run_morning_routine, args=(config, speak), daemon=True
            ).start()
        return False

    # ── answer ────────────────────────────────────────────────────────────────
    if tool_name == "answer":
        speak(str(tool_input.get("text", "")))
        return False

    return False


def _handle_local_command(
    command: str,
    config: dict[str, Any],
    wake_words: list[str],
    stop_event: threading.Event,
    speak: Any,
    brain: Any = None,
) -> bool:
    """Returns True if the agent should stop."""
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

    # Unbekannter Befehl → an AI-Brain weiterleiten
    if brain is None:
        speak("Das habe ich nicht verstanden.")
        return False

    try:
        log("INFO", f"AI-Brain verarbeitet: {command}")
        tool_calls = brain.process(command)

        for call in tool_calls:
            should_stop = _execute_ai_tool(
                call.get("name", ""),
                call.get("input", {}),
                config,
                speak,
            )
            if should_stop:
                return True

    except Exception as exc:
        log("ERROR", f"AI-Brain Ausführung fehlgeschlagen: {exc}", errorCode="ai_brain_exec_failed")
        speak("Das habe ich nicht verstanden.")

    return False


def main() -> None:
    config = load_config()

    try:
        from voice.controller import get_voice_status, log_voice_status

        log_voice_status(config, log)
        voice_status = get_voice_status(config)
    except Exception as exc:
        log("ERROR", f"Voice-Status konnte nicht initialisiert werden: {exc}")
        voice_status = None

    try:
        from voice.phrases import get_wake_words

        wake_words = get_wake_words(config)
    except Exception:
        wake_words = config.get("wakeWords", [])

    voice_enabled = voice_status is not None and voice_status.enabled

    tts_service = None
    try:
        from voice.tts_service import create_tts

        tts_service = create_tts(config)
    except Exception as exc:
        log("WARN", f"TTS konnte nicht initialisiert werden: {exc}")
        # Automatischer Fallback auf SAPI wenn z.B. edge-tts fehlt
        voice_cfg = config.get("voice", {})
        if isinstance(voice_cfg, dict) and voice_cfg.get("ttsProvider", "") != "sapi":
            try:
                fallback_cfg = {
                    **config,
                    "voice": {**voice_cfg, "ttsProvider": "sapi"},
                }
                tts_service = create_tts(fallback_cfg)
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
            f"Voice-Modus aktiv: stt={voice_status.sttProvider}, tts={voice_status.ttsProvider}",
        )
    else:
        log("INFO", "Textmodus aktiv. Tippe 'guten morgen jarvis' oder 'exit'.")

    send_agent_status_safe(config, "online")

    try:
        from integrations.ai_brain import create_brain

        brain = create_brain(config, log)
    except Exception as exc:
        log("WARN", f"AI-Brain konnte nicht geladen werden: {exc}")
        brain = None

    def request_stop() -> None:
        send_agent_status_safe(config, "stopped")
        stop_event.set()
        log("WARN", "Lokaler Stop wurde angefordert.")

    local_api_server = None
    try:
        from local_api import start_local_api

        local_api_server = start_local_api(
            config=config,
            log=log,
            run_morning=lambda: run_morning_routine(config, speak=speak),
            stop_agent=request_stop,
        )
    except Exception as exc:
        log(
            "ERROR",
            f"Lokale Agent-API konnte nicht gestartet werden: {exc}",
            errorCode="local_api_start_failed",
        )

    try:
        from scheduler import RoutineScheduler

        def _dispatch_scheduled_routine(routine: dict[str, Any]) -> None:
            for action in routine.get("actions", []):
                if action == "morning_routine":
                    run_morning_routine(config, speak=speak)
                else:
                    log("WARN", f"Unbekannte Routine-Aktion: {action}", errorCode="unknown_routine_action")

        routine_scheduler = RoutineScheduler(
            config=config,
            log=log,
            run_routine=_dispatch_scheduled_routine,
            stop_event=stop_event,
        )
        routine_scheduler.start()
    except Exception as exc:
        log("WARN", f"Routine-Scheduler konnte nicht gestartet werden: {exc}")
        
    try:
        from todo.reminder_engine import ReminderEngine
        reminder_engine = ReminderEngine(
            config=config, log=log, speak=speak, stop_event=stop_event
        )
        reminder_engine.start()
    except Exception as exc:
        log("WARN", f"Reminder-Engine konnte nicht gestartet werden: {exc}")

    polling_thread = threading.Thread(
        target=command_poll_loop,
        args=(config, stop_event, speak),
        daemon=True,
    )
    polling_thread.start()

    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(config, stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    if voice_enabled:
        try:
            from voice.stt_service import create_stt
            from voice.wake_word import WakeWordDetector

            tts = tts_service
            stt = create_stt(config)

            def on_voice_command(cmd: str) -> None:
                normalized = normalize_command(cmd)
                should_stop = _handle_local_command(
                    normalized, config, wake_words, stop_event, tts.speak, brain=brain
                )
                if should_stop:
                    stop_event.set()

            detector = WakeWordDetector(
                config=config,
                stt=stt,
                tts=tts,
                log=log,
                on_command=on_voice_command,
            )
            detector.start()

            stop_event.wait()
            detector.stop()
            tts.stop()

        except Exception as exc:
            log(
                "ERROR",
                f"Voice-Modus fehlgeschlagen: {exc}. Fallback auf Textmodus.",
                errorCode="voice_mode_failed",
            )
            voice_enabled = False

    if not voice_enabled:
        while not stop_event.is_set():
            try:
                command = normalize_command(input("> "))
                should_stop = _handle_local_command(
                    command, config, wake_words, stop_event, speak, brain=brain
                )
                if should_stop:
                    break

            except KeyboardInterrupt:
                send_agent_status_safe(config, "interrupted")
                stop_event.set()
                log("WARN", "Abbruch durch Benutzer.")
                break

    if local_api_server:
        local_api_server.stop()


if __name__ == "__main__":
    main()
