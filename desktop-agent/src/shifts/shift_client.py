"""
Client für die Schicht-API des Backends.
Wrapper um backend_client.request_json für shift-spezifische Calls.
"""

from __future__ import annotations

from typing import Any, Callable

from integrations.backend_client import request_json

LogFn = Callable[[str, str], None]


def set_shift(
    config: dict[str, Any],
    log: LogFn,
    date: str,
    shift_type: str,
    source: str = "voice",
    notes: str | None = None,
) -> dict[str, Any] | None:
    """
    Trägt eine Schicht im Backend ein (UPSERT by date).
    Gibt das erstellte/aktualisierte Shift-Objekt zurück oder None bei Fehler.
    """
    payload: dict[str, Any] = {"date": date, "type": shift_type, "source": source}
    if notes:
        payload["notes"] = notes

    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/shifts",
        method="POST",
        payload=payload,
        log=log,
    )
    if result and result.get("ok"):
        return result.get("shift")
    return None


def get_shift(
    config: dict[str, Any],
    log: LogFn,
    date: str,
) -> dict[str, Any] | None:
    """Gibt die Schicht für ein Datum zurück oder None."""
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/shifts/{date}",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if result and result.get("ok"):
        return result.get("shift")
    return None


def get_today_shift(config: dict[str, Any], log: LogFn) -> dict[str, Any] | None:
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint="/api/shifts/today",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if result and result.get("ok"):
        return result.get("shift")
    return None


def get_streaming_advice(
    config: dict[str, Any],
    log: LogFn,
    date: str | None = None,
) -> dict[str, Any] | None:
    """
    Holt die Streaming-Empfehlung vom Backend.
    date=None → heute.
    """
    endpoint = (
        f"/api/streaming/advice?date={date}" if date else "/api/streaming/advice/today"
    )
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
        return result.get("advice")
    return None
