import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


AGENT_DIR = Path(__file__).resolve().parents[1]
JARVIS_ROOT = AGENT_DIR.parent

CONFIG_PATH = AGENT_DIR / "config.json"
LOCAL_CONFIG_PATH = AGENT_DIR / "config.local.json"
LOG_DIR = JARVIS_ROOT / "logs"
LOG_FILE = LOG_DIR / "desktop-agent.log"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

MORNING_ROUTINE_LOCK = threading.Lock()


def log(level: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    line = f"{datetime.now().isoformat()} [{level}] {message}"
    print(line)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log("ERROR", f"Config nicht gefunden: {CONFIG_PATH}")
        sys.exit(1)

    config = load_json_file(CONFIG_PATH)

    if LOCAL_CONFIG_PATH.exists():
        config = deep_merge(config, load_json_file(LOCAL_CONFIG_PATH))
        log("INFO", f"Lokale Config geladen: {LOCAL_CONFIG_PATH}")

    env_agent_token = os.getenv("JARVIS_AGENT_TOKEN", "").strip()
    if env_agent_token:
        config["agentToken"] = env_agent_token

    env_backend_url = os.getenv("JARVIS_BACKEND_URL", "").strip()
    if env_backend_url:
        config["backendUrl"] = env_backend_url

    return config


def detached_popen(command: list[str], working_dir: str | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        cwd=working_dir if working_dir else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True
    )


def open_uri(uri: str) -> bool:
    try:
        detached_popen(["cmd", "/c", "start", "", uri])
        log("OK", f"URI geöffnet: {uri}")
        return True
    except Exception as exc:
        log("ERROR", f"URI konnte nicht geöffnet werden: {uri} | {exc}")
        return False


def start_path(
    path_value: str | None,
    args: list[str] | None = None,
    working_dir: str | None = None
) -> bool:
    if not path_value:
        log("WARN", "Kein Programmpfad konfiguriert.")
        return False

    path = Path(path_value)

    if not path.exists():
        log("ERROR", f"Programmpfad existiert nicht: {path}")
        return False

    try:
        command = [str(path)]
        if args:
            command.extend(args)

        detached_popen(command, working_dir)
        log("OK", f"Programm gestartet: {path}")
        return True

    except Exception as exc:
        log("ERROR", f"Programm konnte nicht gestartet werden: {path} | {exc}")
        return False


def start_command(command: str | None, args: list[str] | None = None) -> bool:
    if not command:
        log("WARN", "Kein Command konfiguriert.")
        return False

    try:
        full_command = [command]
        if args:
            full_command.extend(args)

        detached_popen(full_command)
        log("OK", f"Command gestartet: {' '.join(full_command)}")
        return True

    except FileNotFoundError:
        log("ERROR", f"Command nicht gefunden: {command}")
        return False

    except Exception as exc:
        log("ERROR", f"Command konnte nicht gestartet werden: {command} | {exc}")
        return False


def start_app(name: str, app_config: dict[str, Any]) -> bool:
    if not app_config.get("enabled", False):
        log("INFO", f"App deaktiviert: {name}")
        return False

    mode = app_config.get("mode")

    log("INFO", f"Starte App: {name} | Modus: {mode}")

    if mode == "uri":
        uri = app_config.get("uri")
        if not uri:
            log("ERROR", f"URI fehlt für App: {name}")
            return False
        return open_uri(uri)

    if mode == "path":
        return start_path(
            app_config.get("path"),
            app_config.get("args", []),
            app_config.get("workingDir")
        )

    if mode == "command":
        return start_command(
            app_config.get("command"),
            app_config.get("args", [])
        )

    log("ERROR", f"Unbekannter Startmodus für {name}: {mode}")
    return False


def get_todo_path(config: dict[str, Any]) -> Path | None:
    todo_config = config.get("todo", {})
    todo_path_value = todo_config.get("markdownPath")

    if not todo_path_value:
        log("ERROR", "TODO Markdown-Pfad fehlt.")
        return None

    todo_path = Path(todo_path_value)

    if not todo_path.exists():
        log("ERROR", f"TODO-Datei existiert nicht: {todo_path}")
        return None

    return todo_path


def open_todo(config: dict[str, Any]) -> bool:
    todo_path = get_todo_path(config)

    if not todo_path:
        return False

    try:
        detached_popen(["notepad.exe", str(todo_path)])
        log("OK", f"TODO-Datei mit Notepad geöffnet: {todo_path}")
        return True
    except Exception as exc:
        log("ERROR", f"TODO-Datei konnte nicht geöffnet werden: {todo_path} | {exc}")
        return False


def read_todos(config: dict[str, Any]) -> list[str]:
    todo_config = config.get("todo", {})
    provider = todo_config.get("provider")

    if provider != "markdown":
        log("ERROR", f"TODO Provider noch nicht implementiert: {provider}")
        return []

    todo_path = get_todo_path(config)

    if not todo_path:
        return []

    lines = todo_path.read_text(encoding="utf-8-sig").splitlines()

    items = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            items.append(stripped.replace("- [ ]", "").strip())

    return items


def arrange_windows() -> None:
    try:
        from windows.window_manager import arrange_morning_windows

        arrange_morning_windows(log)

    except ImportError as exc:
        log("ERROR", f"Fenster-Manager Abhängigkeit fehlt: {exc}")
        log("ERROR", "Installiere mit: py -3 -m pip install pywin32 psutil")

    except Exception as exc:
        log("ERROR", f"Fensteranordnung fehlgeschlagen: {exc}")


def analyze_current_project(config: dict[str, Any]) -> str:
    try:
        from integrations.project_analyzer import analyze_project, build_human_summary

        project_config = config.get("project", {})
        project_path = project_config.get("lastProjectPath")

        analysis = analyze_project(project_path, log)
        return str(analysis.get("summary") or build_human_summary(analysis))

    except Exception as exc:
        log("ERROR", f"Projektanalyse fehlgeschlagen: {exc}")
        return f"Projektanalyse fehlgeschlagen: {exc}"


def send_agent_status_safe(config: dict[str, Any], status: str) -> None:
    try:
        from integrations.backend_client import send_agent_status

        send_agent_status(config, log, status)

    except Exception as exc:
        log("ERROR", f"Agent-Status konnte nicht ans Backend gesendet werden: {exc}")


def send_morning_log_safe(
    config: dict[str, Any],
    started_apps: list[str],
    failed_apps: list[str],
    todos: list[str],
    project_summary: str,
) -> None:
    try:
        from integrations.backend_client import send_morning_log

        send_morning_log(
            config=config,
            log=log,
            started_apps=started_apps,
            failed_apps=failed_apps,
            todos=todos,
            project_summary=project_summary,
        )

    except Exception as exc:
        log("ERROR", f"Morgenroutine-Log konnte nicht ans Backend gesendet werden: {exc}")


def run_morning_routine(config: dict[str, Any]) -> None:
    if not MORNING_ROUTINE_LOCK.acquire(blocking=False):
        log("WARN", "Morgenroutine läuft bereits. Neuer Start wurde blockiert.")
        return

    try:
        log("INFO", "Guten Morgen. Starte Morgenroutine.")

        started_apps: list[str] = []
        failed_apps: list[str] = []

        apps = config.get("apps", {})

        for app_name in ["obs", "discord", "spotify", "whatsapp", "vscode"]:
            app_config = apps.get(app_name)

            if not app_config:
                log("WARN", f"Keine App-Konfiguration gefunden: {app_name}")
                failed_apps.append(app_name)
                continue

            success = start_app(app_name, app_config)

            if success:
                started_apps.append(app_name)
            else:
                failed_apps.append(app_name)

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

    finally:
        MORNING_ROUTINE_LOCK.release()


def handle_backend_command(config: dict[str, Any], command: dict[str, Any]) -> None:
    command_id = command.get("id")
    command_type = command.get("type")

    if not command_id:
        log("ERROR", "Backend-Command ohne ID erhalten.")
        return

    log("INFO", f"Backend-Command erhalten: {command_id} | {command_type}")

    try:
        from integrations.backend_client import complete_command

        if command_type == "morning_routine":
            run_morning_routine(config)

            complete_command(
                config=config,
                log=log,
                command_id=command_id,
                status="completed",
                result="Morning Routine wurde lokal ausgeführt.",
                details={"type": command_type},
            )
            return

        if command_type == "dev_news":
            complete_command(
                config=config,
                log=log,
                command_id=command_id,
                status="completed",
                result="Dev-News werden aktuell über Backend /api/news/dev bereitgestellt.",
                details={"type": command_type},
            )
            return

        if command_type == "app_open":
            payload = command.get("payload") or {}
            app_name = str(payload.get("app", "")) if isinstance(payload, dict) else ""
            app_config = config.get("apps", {}).get(app_name)

            if not app_name or not app_config:
                complete_command(
                    config=config,
                    log=log,
                    command_id=command_id,
                    status="rejected",
                    result=f"App nicht konfiguriert: {app_name}",
                    details={"type": command_type, "app": app_name},
                )
                return

            success = start_app(app_name, app_config)
            complete_command(
                config=config,
                log=log,
                command_id=command_id,
                status="completed" if success else "failed",
                result=f"App-Start {'erfolgreich' if success else 'fehlgeschlagen'}: {app_name}",
                details={"type": command_type, "app": app_name},
            )
            return

        if command_type == "system_stop":
            complete_command(
                config=config,
                log=log,
                command_id=command_id,
                status="completed",
                result="System-Stop Command erhalten. Agent bleibt bis zum lokalen Loop-Ende aktiv.",
                details={"type": command_type},
            )
            return

        complete_command(
            config=config,
            log=log,
            command_id=command_id,
            status="rejected",
            result=f"Unbekannter Command-Typ: {command_type}",
            details={"type": command_type},
        )

    except Exception as exc:
        log("ERROR", f"Backend-Command fehlgeschlagen: {command_id} | {exc}")

        try:
            from integrations.backend_client import complete_command

            complete_command(
                config=config,
                log=log,
                command_id=command_id,
                status="failed",
                result=str(exc),
                details={"type": command_type},
            )
        except Exception as inner_exc:
            log("ERROR", f"Command-Fehler konnte nicht ans Backend gesendet werden: {inner_exc}")


def command_poll_loop(config: dict[str, Any], stop_event: threading.Event) -> None:
    log("INFO", "Backend Command Polling gestartet.")

    while not stop_event.is_set():
        try:
            from integrations.backend_client import get_next_command

            command = get_next_command(config, log)

            if command:
                handle_backend_command(config, command)

        except Exception as exc:
            log("ERROR", f"Command Polling Fehler: {exc}")

        stop_event.wait(5)

    log("INFO", "Backend Command Polling beendet.")


def normalize_command(command: str) -> str:
    return command.strip().lower()


def main() -> None:
    config = load_config()
    wake_words = config.get("wakeWords", [])

    stop_event = threading.Event()

    log("INFO", "JARVIS Local Client gestartet.")
    log("INFO", "Textmodus aktiv. Voice kommt in einer späteren Phase.")
    log("INFO", 'Teste mit: guten morgen jarvis')
    log("INFO", 'Beenden mit: exit')

    send_agent_status_safe(config, "online")

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
            run_morning=lambda: run_morning_routine(config),
            stop_agent=request_stop,
        )
    except Exception as exc:
        log("ERROR", f"Lokale Agent-API konnte nicht gestartet werden: {exc}")

    polling_thread = threading.Thread(
        target=command_poll_loop,
        args=(config, stop_event),
        daemon=True,
    )
    polling_thread.start()

    while not stop_event.is_set():
        try:
            command = normalize_command(input("> "))

            if command in ["exit", "quit", "beenden"]:
                send_agent_status_safe(config, "offline")
                stop_event.set()
                log("INFO", "JARVIS Local Client wird beendet.")
                break

            if command == "jarvis, stopp":
                send_agent_status_safe(config, "stopped")
                stop_event.set()
                log("WARN", "Not-Aus ausgelöst.")
                break

            if command in wake_words:
                if command == "guten morgen jarvis":
                    run_morning_routine(config)
                else:
                    log("INFO", "JARVIS ist aktiv.")
                continue

            log("WARN", f"Unbekannter Befehl: {command}")

        except KeyboardInterrupt:
            send_agent_status_safe(config, "interrupted")
            stop_event.set()
            log("WARN", "Abbruch durch Benutzer.")
            break

    if local_api_server:
        local_api_server.stop()


if __name__ == "__main__":
    main()
