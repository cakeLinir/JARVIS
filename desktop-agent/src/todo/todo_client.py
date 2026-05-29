"""
Sync-Client für die Todo-API des Backends.
Legt sich über todo/provider.py (lokaler Cache bleibt Offline-Fallback).
"""

from __future__ import annotations

from typing import Any, Callable

from integrations.backend_client import request_json

LogFn = Callable[[str, str], None]


def get_todos(
    config: dict[str, Any],
    log: LogFn,
    status: str | None = "open",
) -> list[dict[str, Any]]:
    """Gibt offene (oder gefilterte) Todos vom Backend zurück."""
    endpoint = "/api/todos"
    if status:
        endpoint += f"?status={status}"

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=endpoint,
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if result and result.get("ok"):
        return result.get("todos", [])
    return []


def get_due_today(config: dict[str, Any], log: LogFn) -> list[dict[str, Any]]:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/todos/due-today",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if result and result.get("ok"):
        return result.get("todos", [])
    return []


def create_todo(
    config: dict[str, Any],
    log: LogFn,
    title: str,
    due_date: str | None = None,
    due_time: str | None = None,
    priority: int = 3,
    category: str | None = None,
    reminder_minutes: int | None = None,
    source: str = "voice",
    description: str | None = None,
) -> dict[str, Any] | None:
    """Erstellt ein neues Todo im Backend. Gibt das erstellte Todo zurück."""
    payload: dict[str, Any] = {
        "title": title,
        "source": source,
        "priority": priority,
    }
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
    if result and result.get("ok"):
        return result.get("todo")
    return None


def complete_todo(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    actor: str = "voice",
) -> dict[str, Any] | None:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}/complete",
        method="POST",
        payload={"actor": actor},
        log=log,
    )
    if result and result.get("ok"):
        return result.get("todo")
    return None


def reschedule_todo(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    new_due_date: str,
    new_due_time: str | None = None,
    actor: str = "voice",
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"dueDate": new_due_date, "actor": actor}
    if new_due_time:
        payload["dueTime"] = new_due_time

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}/reschedule",
        method="POST",
        payload=payload,
        log=log,
    )
    if result and result.get("ok"):
        return result.get("todo")
    return None


def update_todo(
    config: dict[str, Any],
    log: LogFn,
    todo_id: str,
    changes: dict[str, Any],
    actor: str = "voice",
) -> dict[str, Any] | None:
    payload = {**changes, "actor": actor}
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/todos/{todo_id}",
        method="PATCH",
        payload=payload,
        log=log,
    )
    if result and result.get("ok"):
        return result.get("todo")
    return None


def find_todo_by_title(
    config: dict[str, Any],
    log: LogFn,
    title_fragment: str,
) -> dict[str, Any] | None:
    """
    Sucht das erste offene Todo dessen Titel den Fragment enthält (case-insensitive).
    Wird für Sprachbefehle wie 'mach Rechnung wichtig' genutzt.
    """
    todos = get_todos(config, log, status="open")
    fragment_lower = title_fragment.strip().lower()
    # Exakter Treffer zuerst
    for todo in todos:
        if todo.get("title", "").lower() == fragment_lower:
            return todo
    # Teilstring-Treffer
    for todo in todos:
        if fragment_lower in todo.get("title", "").lower():
            return todo
    return None
