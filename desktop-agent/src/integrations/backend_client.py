import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable


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
) -> dict[str, Any] | None:
    if not backend_url:
        log("WARN", "Backend-URL fehlt. Backend-Anfrage übersprungen.")
        return None

    if not agent_token:
        log("WARN", "Agent-Token fehlt. Backend-Anfrage übersprungen.")
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
            log("OK", f"Backend {method} erfolgreich: {endpoint} | HTTP {response.status}")

            if not response_body:
                return {}

            return json.loads(response_body)

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        log("ERROR", f"Backend HTTP-Fehler: {endpoint} | HTTP {exc.code} | {error_body}")
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
        log("BACKEND", json.dumps(result, ensure_ascii=False))
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
) -> bool:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "startedApps": started_apps,
        "failedApps": failed_apps,
        "todos": todos,
        "projectSummary": project_summary,
    }

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
) -> bool:
    return post_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/commands/{command_id}/complete",
        payload={
            "status": status,
            "result": result,
            "details": details or {},
        },
        log=log,
    )
