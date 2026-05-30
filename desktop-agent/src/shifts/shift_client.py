"""
Client für die Schicht-API des Backends.
Wrapper um backend_client.request_json für shift-spezifische Calls.
Letzte 7 abgerufene Schichten werden lokal gecacht (offline-fähig).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from core.config_loader import AGENT_DIR
from integrations.backend_client import request_json

LogFn = Callable[[str, str], None]

_CACHE_FILE = AGENT_DIR / ".runtime" / "cache" / "shifts.json"


# ── Cache-Hilfsfunktionen ─────────────────────────────────────────────────────

def _load_cache() -> list[dict[str, Any]]:
    if not _CACHE_FILE.exists():
        return []
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_cache(shifts: list[dict[str, Any]]) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(shifts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _update_cache(shift: dict[str, Any]) -> None:
    """Ersetzt oder fügt Schicht im Cache ein — behält max. 7 Einträge."""
    cache = _load_cache()
    date = shift.get("date", "")
    # Alten Eintrag für dasselbe Datum entfernen
    cache = [s for s in cache if s.get("date") != date]
    cache.append(shift)
    # Sortieren und auf 7 Einträge begrenzen
    cache.sort(key=lambda s: s.get("date", ""))
    _save_cache(cache[-7:])


def _get_from_cache(date: str) -> dict[str, Any] | None:
    for entry in _load_cache():
        if entry.get("date") == date:
            return entry
    return None


# ── Öffentliche API ───────────────────────────────────────────────────────────

def get_shift(
    config: dict[str, Any],
    log: LogFn,
    date: str,
) -> dict[str, Any] | None:
    """Gibt die Schicht für ein Datum zurück. Cache-Fallback bei Offline."""
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
        shift = result.get("shift")
        if isinstance(shift, dict):
            _update_cache(shift)
        return shift

    # Backend nicht erreichbar → Cache nutzen
    cached = _get_from_cache(date)
    if cached:
        log("WARN", f"Schicht aus Cache geladen (offline): {date}")
    return cached


def set_shift(
    config: dict[str, Any],
    log: LogFn,
    date: str,
    shift_type: str,
    source: str = "voice",
    notes: str | None = None,
) -> dict[str, Any] | None:
    """
    Trägt eine Schicht im Backend ein (POST — Conflict 409 wenn Datum schon belegt).
    Gibt das erstellte Shift-Objekt zurück oder None bei Fehler.
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
        shift = result.get("shift")
        if isinstance(shift, dict):
            _update_cache(shift)
        return shift

    # 409-Konflikt: Datum bereits belegt
    if isinstance(result, dict) and result.get("error") == "shift_conflict":
        log("WARN", f"Schicht-Konflikt: {date} bereits eingetragen.")
    return None


def get_today_shift(config: dict[str, Any], log: LogFn) -> dict[str, Any] | None:
    from datetime import date as _date
    today = _date.today().isoformat()
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
        shift = result.get("shift")
        if isinstance(shift, dict):
            _update_cache(shift)
        return shift

    # Cache-Fallback
    cached = _get_from_cache(today)
    if cached:
        log("WARN", "Heutige Schicht aus Cache geladen (offline).")
    return cached


def get_availability(
    config: dict[str, Any],
    log: LogFn,
    date: str,
) -> dict[str, Any] | None:
    """
    Holt die Verfügbarkeits-/Stream-Empfehlung für ein Datum.
    Returns AvailabilityResult oder None bei Fehler.
    """
    result = request_json(
        backend_url=config.get("backendUrl", ""),
        agent_token=config.get("agentToken", ""),
        endpoint=f"/api/availability/{date}",
        method="GET",
        payload=None,
        log=log,
        quiet_success=True,
    )
    if result and result.get("ok"):
        return result.get("availability")
    return None


def get_stream_recommendation_text(
    config: dict[str, Any],
    log: LogFn,
    date: str | None = None,
) -> str:
    """
    Gibt einen deutschen Satz zurück, den JARVIS per TTS sprechen kann.
    Beispiel: "Heute Nachtschicht ab 19 Uhr. Stream am Nachmittag bis 17 Uhr möglich."
    """
    from datetime import date as _date_cls, datetime as _datetime

    target = date or _date_cls.today().isoformat()

    avail = get_availability(config, log, target)

    if not avail:
        return "Ich konnte keine Streaming-Empfehlung abrufen."

    rec = avail.get("streamRecommendation", "conditional")
    reason = str(avail.get("reason", "")).strip()
    window = avail.get("streamWindow")
    shift_info = avail.get("shift")

    # Emoji aus reason entfernen für TTS
    for emoji in ["🟢", "🟡", "🟠", "🔴", "🛌"]:
        reason = reason.replace(emoji, "").strip()

    if rec == "blocked":
        return f"Kein Stream empfohlen. {reason}"

    if rec == "discouraged":
        return f"Stream heute nicht ideal. {reason}"

    if rec == "free":
        if window:
            return f"Freier Tag — Stream von {window.get('from')} Uhr bis {window.get('to')} Uhr möglich."
        return "Freier Tag — Stream jederzeit möglich."

    # conditional
    if window:
        return (
            f"Stream möglich von {window.get('from')} bis {window.get('to')} Uhr. {reason}"
        )

    return f"Streaming bedingt möglich. {reason}"


def get_streaming_advice(
    config: dict[str, Any],
    log: LogFn,
    date: str | None = None,
) -> dict[str, Any] | None:
    """
    Holt die detaillierte Streaming-Empfehlung vom Backend.
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
