from __future__ import annotations

import threading
import time
from typing import Any

from core.logging import log, jarvis_normalize_log_event
from execution.app_launcher import start_app
from security.config_guard import CONFIG_REQUIRED_MARKER

MORNING_ROUTINE_LOCK = threading.Lock()


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
        from todo.review import run_agent_todo_review

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
