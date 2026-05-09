from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_REQUIRED_MARKER = "KONFIGURATION_ERFORDERLICH"
SECURITY_RISK_MARKER = "SICHERHEITSRISIKO"

PLACEHOLDER_FRAGMENTS = (
    "CHANGE_ME",
    "DEIN_",
    "NUR_LOKALER",
    "PATH\\TO",
    "PATH/TO",
    "example",
    "TOKEN_OR_SET_ENV",
)


@dataclass(slots=True)
class ConfigFinding:
    level: str
    code: str
    message: str
    field: str | None = None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def redact(value: Any) -> str:
    text = _as_str(value)
    if not text:
        return ""

    if len(text) <= 8:
        return "***"

    return f"{text[:4]}â€¦{text[-4:]}"


def contains_placeholder(value: Any) -> bool:
    text = _as_str(value)
    if not text:
        return True

    upper = text.upper()
    return any(fragment.upper() in upper for fragment in PLACEHOLDER_FRAGMENTS)


def is_configured_secret(value: Any) -> bool:
    text = _as_str(value)
    return bool(text) and not contains_placeholder(text)


def is_configured_url(value: Any) -> bool:
    text = _as_str(value)
    if not text or contains_placeholder(text):
        return False

    lowered = text.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def is_configured_path(value: Any) -> bool:
    text = _as_str(value)
    if not text or contains_placeholder(text):
        return False

    return Path(text).exists()


def validate_agent_config(config: dict[str, Any]) -> list[ConfigFinding]:
    findings: list[ConfigFinding] = []

    backend_url = config.get("backendUrl")
    if not is_configured_url(backend_url):
        findings.append(
            ConfigFinding(
                level="error",
                code="backend_url_missing_or_placeholder",
                field="backendUrl",
                message=f"{CONFIG_REQUIRED_MARKER}: backendUrl fehlt oder ist ein Platzhalter.",
            )
        )

    agent_token = config.get("agentToken")
    if not is_configured_secret(agent_token):
        findings.append(
            ConfigFinding(
                level="error",
                code="agent_token_missing_or_placeholder",
                field="agentToken",
                message=f"{CONFIG_REQUIRED_MARKER}: agentToken fehlt oder ist ein Platzhalter.",
            )
        )

    local_api = config.get("localApi", {})
    if isinstance(local_api, dict) and local_api.get("enabled", False):
        local_token = local_api.get("token")
        if not is_configured_secret(local_token):
            findings.append(
                ConfigFinding(
                    level="error",
                    code="local_api_token_missing_or_placeholder",
                    field="localApi.token",
                    message=f"{CONFIG_REQUIRED_MARKER}: localApi.token fehlt oder ist ein Platzhalter. Lokale API wird deaktiviert.",
                )
            )

        host = _as_str(local_api.get("host", "127.0.0.1"))
        if host not in {"127.0.0.1", "localhost"}:
            findings.append(
                ConfigFinding(
                    level="error",
                    code="local_api_host_not_loopback",
                    field="localApi.host",
                    message=f"{SECURITY_RISK_MARKER}: localApi.host muss für den MVP auf 127.0.0.1 oder localhost gebunden sein.",
                )
            )

    apps = config.get("apps", {})
    if not isinstance(apps, dict):
        findings.append(
            ConfigFinding(
                level="error",
                code="apps_config_invalid",
                field="apps",
                message=f"{CONFIG_REQUIRED_MARKER}: apps muss ein Objekt sein.",
            )
        )
    else:
        for app_name, app_config in apps.items():
            if not isinstance(app_config, dict) or not app_config.get("enabled", False):
                continue

            mode = _as_str(app_config.get("mode"))
            if mode == "path":
                path_value = app_config.get("path")
                if contains_placeholder(path_value):
                    findings.append(
                        ConfigFinding(
                            level="warning",
                            code="app_path_placeholder",
                            field=f"apps.{app_name}.path",
                            message=f"{CONFIG_REQUIRED_MARKER}: App-Pfad für {app_name} ist ein Platzhalter.",
                        )
                    )
                elif not Path(_as_str(path_value)).exists():
                    findings.append(
                        ConfigFinding(
                            level="warning",
                            code="app_path_not_found",
                            field=f"apps.{app_name}.path",
                            message=f"{CONFIG_REQUIRED_MARKER}: App-Pfad für {app_name} existiert nicht.",
                        )
                    )

            elif mode == "uri":
                uri = _as_str(app_config.get("uri"))
                if not uri or contains_placeholder(uri):
                    findings.append(
                        ConfigFinding(
                            level="warning",
                            code="app_uri_missing_or_placeholder",
                            field=f"apps.{app_name}.uri",
                            message=f"{CONFIG_REQUIRED_MARKER}: URI für {app_name} fehlt oder ist ein Platzhalter.",
                        )
                    )

            elif mode == "command":
                findings.append(
                    ConfigFinding(
                        level="warning",
                        code="app_command_mode_requires_explicit_allow",
                        field=f"apps.{app_name}.mode",
                        message=f"{SECURITY_RISK_MARKER}: command-Modus für {app_name} wird nur mit allowCommandMode=true ausgeführt.",
                    )
                )

            else:
                findings.append(
                    ConfigFinding(
                        level="warning",
                        code="app_mode_unknown",
                        field=f"apps.{app_name}.mode",
                        message=f"{CONFIG_REQUIRED_MARKER}: Unbekannter Startmodus für {app_name}: {mode}",
                    )
                )

    todo_config = config.get("todo", {})
    if isinstance(todo_config, dict) and todo_config.get("provider") == "markdown":
        todo_path = todo_config.get("markdownPath")
        if contains_placeholder(todo_path):
            findings.append(
                ConfigFinding(
                    level="warning",
                    code="todo_markdown_path_placeholder",
                    field="todo.markdownPath",
                    message=f"{CONFIG_REQUIRED_MARKER}: TODO Markdown-Pfad ist ein Platzhalter.",
                )
            )
        elif not Path(_as_str(todo_path)).exists():
            findings.append(
                ConfigFinding(
                    level="warning",
                    code="todo_markdown_path_not_found",
                    field="todo.markdownPath",
                    message=f"{CONFIG_REQUIRED_MARKER}: TODO Markdown-Datei existiert nicht.",
                )
            )

    return findings


def has_blocking_config_errors(findings: list[ConfigFinding]) -> bool:
    return any(item.level == "error" for item in findings)