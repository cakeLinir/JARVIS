from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from core.logging import log

AGENT_DIR = Path(__file__).resolve().parents[2]  # desktop-agent/
JARVIS_ROOT = AGENT_DIR.parent
CONFIG_PATH = AGENT_DIR / "config.json"
LOCAL_CONFIG_PATH = AGENT_DIR / "config.local.json"
LOG_DIR = JARVIS_ROOT / "logs"


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        parsed = json.load(file)

    if not isinstance(parsed, dict):
        raise ValueError(f"Config muss ein JSON-Objekt sein: {path}")

    return parsed


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config() -> dict[str, Any]:
    from security.config_guard import (
        CONFIG_REQUIRED_MARKER,
        redact,
        validate_agent_config,
    )

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
