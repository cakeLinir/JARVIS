from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable

from core.config_loader import AGENT_DIR

LogFn = Callable[[str, str], None]

_RUNTIME_DIR = AGENT_DIR / ".runtime"
_CACHE_FILE = _RUNTIME_DIR / "cache" / "todos_today.json"
_QUEUE_FILE = _RUNTIME_DIR / "pending_queue.json"


# ── Cache-Hilfsfunktionen ─────────────────────────────────────────────────────

def _load_cache() -> list[dict[str, Any]]:
    if not _CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_cache(todos: list[dict[str, Any]]) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ── Pending-Queue (Offline-Fallback) ──────────────────────────────────────────

def _load_queue() -> list[dict[str, Any]]:
    if not _QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_queue(queue: list[dict[str, Any]]) -> None:
    try:
        _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _QUEUE_FILE.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _enqueue(entry: dict[str, Any]) -> None:
    queue = _load_queue()
    queue.append({**entry, "queuedAt": datetime.now().isoformat()})
    _save_queue(queue)


def _flush_pending_queue(config: dict[str, Any], log: LogFn) -> None:
    queue = _load_queue()
    if not queue:
        return

    log("INFO", f"Pending-Queue flushen: {len(queue)} Einträge.")
    remaining: list[dict[str, Any]] = []

    from integrations.backend_client import request_json

    backend_url = config.get("backendUrl", "")
    agent_token = config.get("agentToken", "")

    for entry in queue:
        action = entry.get("action")
        success = False

        try:
            if action == "create":
                result = request_json(
                    backend_url, agent_token,
                    "/api/todos", "POST",
                    entry.get("payload"), log, quiet_success=True,
                )
                success = result is not None

            elif action == "update":
                todo_id = entry.get("id", "")
                result = request_json(
                    backend_url, agent_token,
                    f"/api/todos/{todo_id}", "PATCH",
                    entry.get("data"), log, quiet_success=True,
                )
                success = result is not None

            elif action == "complete":
                todo_id = entry.get("id", "")
                result = request_json(
                    backend_url, agent_token,
                    f"/api/todos/{todo_id}/complete", "POST",
                    {"actor": "agent"}, log, quiet_success=True,
                )
                success = result is not None

        except Exception as exc:
            log("WARN", f"Queue-Flush Fehler ({action}): {exc}")

        if not success:
            remaining.append(entry)

    _save_queue(remaining)

    flushed = len(queue) - len(remaining)
    if flushed:
        log("OK", f"Pending-Queue: {flushed} Einträge gesendet, {len(remaining)} verbleibend.")


# ── Öffentliche Sync-Funktionen ───────────────────────────────────────────────

def sync_todos_from_backend(config: dict[str, Any], log: LogFn) -> list[dict[str, Any]]:
    """GET /api/todos/today — lokal cachen. Bei Offline-Fallback Cache zurückgeben."""
    from integrations.backend_client import request_json

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/todos/today",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )

    if result is None:
        cached = _load_cache()
        log("WARN", f"Backend nicht erreichbar — {len(cached)} TODOs aus Cache geladen.")
        return cached

    todos: list[dict[str, Any]] = result.get("todos", [])
    _save_cache(todos)

    # Bei erfolgreicher Verbindung: Queue flushen
    _flush_pending_queue(config, log)

    return todos


def push_todo_to_backend(
    config: dict[str, Any],
    log: LogFn,
    todo_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """POST /api/todos — bei Offline in pending_queue.json speichern."""
    from integrations.backend_client import request_json

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/todos",
        method="POST",
        payload=todo_dict,
        log=log,
    )

    if result is None:
        _enqueue({"action": "create", "payload": todo_dict})
        log("WARN", "TODO konnte nicht gesendet werden — in Pending-Queue gespeichert.")
        return None

    return result.get("todo") if isinstance(result, dict) else None


def update_todo_on_backend(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """PATCH /api/todos/:id — bei Offline in pending_queue.json speichern."""
    from integrations.backend_client import request_json

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}",
        method="PATCH",
        payload=data,
        log=log,
    )

    if result is None:
        _enqueue({"action": "update", "id": todo_id, "data": data})
        log("WARN", f"TODO-Update konnte nicht gesendet werden — in Pending-Queue gespeichert: {todo_id}")
        return None

    return result.get("todo") if isinstance(result, dict) else None


def complete_todo_on_backend(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
) -> dict[str, Any] | None:
    """POST /api/todos/:id/complete — bei Offline in pending_queue.json speichern."""
    from integrations.backend_client import request_json

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}/complete",
        method="POST",
        payload={"actor": "agent"},
        log=log,
    )

    if result is None:
        _enqueue({"action": "complete", "id": todo_id})
        log("WARN", f"TODO-Complete konnte nicht gesendet werden — in Pending-Queue gespeichert: {todo_id}")
        return None

    return result.get("todo") if isinstance(result, dict) else None
