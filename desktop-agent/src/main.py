import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


AGENT_DIR = Path(__file__).resolve().parents[1]
JARVIS_ROOT = AGENT_DIR.parent

CONFIG_PATH = AGENT_DIR / "config.json"
LOG_DIR = JARVIS_ROOT / "logs"
LOG_FILE = LOG_DIR / "desktop-agent.log"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def log(level: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    line = f"{datetime.now().isoformat()} [{level}] {message}"
    print(line)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        log("ERROR", f"Config nicht gefunden: {CONFIG_PATH}")
        sys.exit(1)

    with CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


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



def analyze_current_project(config: dict[str, Any]) -> None:
    try:
        from integrations.project_analyzer import analyze_project

        project_config = config.get("project", {})
        project_path = project_config.get("lastProjectPath")

        analyze_project(project_path, log)

    except Exception as exc:
        log("ERROR", f"Projektanalyse fehlgeschlagen: {exc}")

def arrange_windows() -> None:
    try:
        from windows.window_manager import arrange_morning_windows

        arrange_morning_windows(log)

    except ImportError as exc:
        log("ERROR", f"Fenster-Manager Abhängigkeit fehlt: {exc}")
        log("ERROR", "Installiere mit: py -3 -m pip install pywin32 psutil")

    except Exception as exc:
        log("ERROR", f"Fensteranordnung fehlgeschlagen: {exc}")


def normalize_command(command: str) -> str:
    return command.strip().lower()


def run_morning_routine(config: dict[str, Any]) -> None:
    log("INFO", "Guten Morgen. Starte Morgenroutine.")

    apps = config.get("apps", {})

    for app_name in ["obs", "discord", "spotify", "whatsapp", "vscode"]:
        app_config = apps.get(app_name)

        if not app_config:
            log("WARN", f"Keine App-Konfiguration gefunden: {app_name}")
            continue

        start_app(app_name, app_config)

    open_todo(config)

    todos = read_todos(config)

    if todos:
        log("INFO", "Heutige TODOs:")
        for item in todos:
            log("TODO", item)
    else:
        log("INFO", "Keine offenen TODOs für heute gefunden.")

    analyze_current_project(config)

    log("INFO", "Warte kurz auf Programmfenster.")
    time.sleep(5)

    arrange_windows()

    log("INFO", "Morgenroutine MVP abgeschlossen.")


def main() -> None:
    config = load_config()
    wake_words = config.get("wakeWords", [])

    log("INFO", "JARVIS Local Client gestartet.")
    log("INFO", "Textmodus aktiv. Voice kommt in einer späteren Phase.")
    log("INFO", 'Teste mit: guten morgen jarvis')
    log("INFO", 'Beenden mit: exit')

    while True:
        try:
            command = normalize_command(input("> "))

            if command in ["exit", "quit", "beenden"]:
                log("INFO", "JARVIS Local Client wird beendet.")
                break

            if command == "jarvis, stopp":
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
            log("WARN", "Abbruch durch Benutzer.")
            break


if __name__ == "__main__":
    main()