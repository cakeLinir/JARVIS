from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable

from security.config_guard import is_configured_secret, is_configured_url

LogFn = Callable[[str, str], None]


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def request_json(
    backend_url: str,
    agent_token: str,
    endpoint: str,
    method: str,
    payload: dict[str, Any] | None,
    log: LogFn,
    timeout_seconds: int = 5,
quiet_success: bool = False,
) -> dict[str, Any] | None:
    if not is_configured_url(backend_url):
        log("WARN", "Backend-URL fehlt oder ist ein Platzhalter. Backend-Anfrage übersprungen.")
        return None

    if not is_configured_secret(agent_token):
        log("WARN", "Agent-Token fehlt oder ist ein Platzhalter. Backend-Anfrage übersprungen.")
        return None

    url = backend_url.rstrip("/") + endpoint

    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_token}",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=url,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            if not quiet_success:
                log("OK", f"Backend {method} erfolgreich: {endpoint} | HTTP {response.status}")

            if not response_body:
                return {}

            return json.loads(response_body)

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        log("ERROR", f"Backend HTTP-Fehler: {endpoint} | HTTP {exc.code} | {error_body[:700]}")
        return None

    except urllib.error.URLError as exc:
        log("ERROR", f"Backend nicht erreichbar: {endpoint} | {exc.reason}")
        return None

    except Exception as exc:
        log("ERROR", f"Backend-Anfrage fehlgeschlagen: {endpoint} | {exc}")
        return None


def post_json(
    backend_url: str,
    agent_token: str,
    endpoint: str,
    payload: dict[str, Any],
    log: LogFn,
    timeout_seconds: int = 5,
) -> bool:
    result = request_json(
        backend_url=backend_url,
        agent_token=agent_token,
        endpoint=endpoint,
        method="POST",
        payload=payload,
        log=log,
        timeout_seconds=timeout_seconds,
    )

    if result is not None:
        log("BACKEND", json.dumps(result, ensure_ascii=False)[:1200])
        return True

    return False


def send_agent_status(config: dict[str, Any], log: LogFn, status: str) -> bool:
    payload = {
        "agentName": "jarvis-desktop-agent",
        "hostname": get_hostname(),
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }

    return post_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/agent/status",
        payload=payload,
        log=log,
    )


def send_morning_log(
    config: dict[str, Any],
    log: LogFn,
    started_apps: list[str],
    failed_apps: list[str],
    todos: list[str],
    project_summary: str | None = None,
    todo_provider: str | None = None,
    todo_status: dict[str, Any] | None = None,
) -> bool:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "startedApps": started_apps,
        "failedApps": failed_apps,
        "todos": todos,
        "projectSummary": project_summary,
    }

    if todo_provider:
        payload["todoProvider"] = todo_provider

    if todo_status:
        payload["todoStatus"] = todo_status

    return post_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/agent/morning-log",
        payload=payload,
        log=log,
    )


def get_next_command(config: dict[str, Any], log: LogFn) -> dict[str, Any] | None:
    agent_name = urllib.parse.quote("jarvis-desktop-agent")

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/commands/next?agentName={agent_name}",
        method="GET",
        payload=None,
        log=log,
        timeout_seconds=5,
        quiet_success=True,
    )

    if not result:
        return None

    command = result.get("command")

    if not command:
        return None

    return command


def complete_command(
    config: dict[str, Any],
    log: LogFn,
    command_id: str,
    status: str,
    result: str,
    details: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> bool:
    payload: dict[str, Any] = {
        "status": status,
        "result": result,
        "details": details or {},
    }

    if error_code:
        payload["errorCode"] = error_code

    return post_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/commands/{command_id}/complete",
        payload=payload,
        log=log,
    )


# ── TODO-Endpunkte ────────────────────────────────────────────────────────────

def get_todos_today(config: dict[str, Any], log: LogFn) -> list[dict[str, Any]]:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/todos/today",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if not isinstance(result, dict):
        return []
    return result.get("todos", [])


def create_todo(
    config: dict[str, Any],
    log: LogFn,
    title: str,
    due_date: str | None = None,
    due_time: str | None = None,
    priority: int = 3,
    category: str | None = None,
    reminder_minutes: int | None = None,
    source: str = "agent",
    description: str | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"title": title, "priority": priority, "source": source}
    if due_date:
        payload["dueDate"] = due_date
    if due_time:
        payload["dueTime"] = due_time
    if category:
        payload["category"] = category
    if reminder_minutes is not None:
        payload["reminderMinutes"] = reminder_minutes
    if description:
        payload["description"] = description

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/todos",
        method="POST",
        payload=payload,
        log=log,
    )
    return result.get("todo") if isinstance(result, dict) else None


def update_todo(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    data: dict[str, Any],
    actor: str = "agent",
) -> dict[str, Any] | None:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}",
        method="PATCH",
        payload={**data, "actor": actor},
        log=log,
    )
    return result.get("todo") if isinstance(result, dict) else None


def complete_todo(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    actor: str = "agent",
) -> dict[str, Any] | None:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}/complete",
        method="POST",
        payload={"actor": actor},
        log=log,
    )
    return result.get("todo") if isinstance(result, dict) else None