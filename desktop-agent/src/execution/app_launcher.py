from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from security.config_guard import CONFIG_REQUIRED_MARKER, contains_placeholder

LogFn = Callable[[str, str], None]

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

ALLOWED_URI_SCHEMES = {"discord", "spotify", "whatsapp"}
ALLOWED_COMMANDS = {"notepad.exe", "explorer.exe"}


@dataclass(slots=True)
class LaunchResult:
    success: bool
    error_code: str | None
    message: str


def detached_popen(command: list[str], working_dir: str | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        cwd=working_dir if working_dir else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True,
    )


def _validate_working_dir(working_dir: str | None) -> tuple[bool, str | None]:
    if not working_dir:
        return True, None

    if contains_placeholder(working_dir):
        return False, f"{CONFIG_REQUIRED_MARKER}: workingDir ist ein Platzhalter."

    path = Path(working_dir)
    if not path.exists() or not path.is_dir():
        return False, f"{CONFIG_REQUIRED_MARKER}: workingDir existiert nicht oder ist kein Ordner: {path}"

    return True, None


def open_uri(uri: str | None, log: LogFn) -> LaunchResult:
    if not uri or contains_placeholder(uri):
        return LaunchResult(False, "uri_missing_or_placeholder", f"{CONFIG_REQUIRED_MARKER}: URI fehlt oder ist ein Platzhalter.")

    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()

    if scheme not in ALLOWED_URI_SCHEMES:
        return LaunchResult(False, "uri_scheme_not_allowed", f"SICHERHEITSRISIKO: URI-Schema ist nicht erlaubt: {scheme}")

    try:
        detached_popen(["cmd", "/c", "start", "", uri])
        log("OK", f"URI geÃ¶ffnet: {scheme}:")
        return LaunchResult(True, None, f"URI geÃ¶ffnet: {scheme}:")
    except Exception as exc:
        return LaunchResult(False, "uri_open_failed", f"URI konnte nicht geÃ¶ffnet werden: {scheme}: | {exc}")


def start_path(path_value: str | None, args: list[str] | None, working_dir: str | None, log: LogFn) -> LaunchResult:
    if not path_value or contains_placeholder(path_value):
        return LaunchResult(False, "path_missing_or_placeholder", f"{CONFIG_REQUIRED_MARKER}: Programmpfad fehlt oder ist ein Platzhalter.")

    path = Path(path_value)

    if not path.exists() or not path.is_file():
        return LaunchResult(False, "path_not_found", f"{CONFIG_REQUIRED_MARKER}: Programmpfad existiert nicht: {path}")

    working_dir_ok, working_dir_error = _validate_working_dir(working_dir)
    if not working_dir_ok:
        return LaunchResult(False, "working_dir_invalid", working_dir_error or "workingDir ist ungÃ¼ltig.")

    safe_args = args if isinstance(args, list) else []

    try:
        command = [str(path), *[str(item) for item in safe_args]]
        detached_popen(command, working_dir)
        log("OK", f"Programm gestartet: {path.name}")
        return LaunchResult(True, None, f"Programm gestartet: {path.name}")

    except Exception as exc:
        return LaunchResult(False, "path_start_failed", f"Programm konnte nicht gestartet werden: {path.name} | {exc}")


def start_command(app_config: dict[str, Any], log: LogFn) -> LaunchResult:
    if app_config.get("allowCommandMode") is not True:
        return LaunchResult(
            False,
            "command_mode_not_explicitly_allowed",
            "SICHERHEITSRISIKO: command-Modus ist ohne allowCommandMode=true nicht erlaubt.",
        )

    command = str(app_config.get("command", "")).strip()
    if not command or contains_placeholder(command):
        return LaunchResult(False, "command_missing_or_placeholder", f"{CONFIG_REQUIRED_MARKER}: Command fehlt oder ist ein Platzhalter.")

    command_name = os.path.basename(command).lower()
    if command_name not in ALLOWED_COMMANDS:
        return LaunchResult(False, "command_not_allowed", f"SICHERHEITSRISIKO: Command ist nicht erlaubt: {command_name}")

    args = app_config.get("args", [])
    safe_args = args if isinstance(args, list) else []

    try:
        detached_popen([command, *[str(item) for item in safe_args]])
        log("OK", f"Command gestartet: {command_name}")
        return LaunchResult(True, None, f"Command gestartet: {command_name}")
    except FileNotFoundError:
        return LaunchResult(False, "command_not_found", f"{CONFIG_REQUIRED_MARKER}: Command nicht gefunden: {command_name}")
    except Exception as exc:
        return LaunchResult(False, "command_start_failed", f"Command konnte nicht gestartet werden: {command_name} | {exc}")


def start_app(name: str, app_config: dict[str, Any], log: LogFn) -> LaunchResult:
    if not app_config.get("enabled", False):
        return LaunchResult(False, "app_disabled", f"App deaktiviert: {name}")

    mode = str(app_config.get("mode", "")).strip().lower()
    log("INFO", f"Starte App: {name} | Modus: {mode}")

    if mode == "uri":
        return open_uri(app_config.get("uri"), log)

    if mode == "path":
        return start_path(
            app_config.get("path"),
            app_config.get("args", []),
            app_config.get("workingDir"),
            log,
        )

    if mode == "command":
        return start_command(app_config, log)

    return LaunchResult(False, "unknown_start_mode", f"{CONFIG_REQUIRED_MARKER}: Unbekannter Startmodus fÃ¼r {name}: {mode}")