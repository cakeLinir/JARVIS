from __future__ import annotations

import threading
from typing import Any

from core.logging import log
from execution.app_launcher import start_app
from routines.morning import run_morning_routine


def complete_backend_command(
    config: dict[str, Any],
    command_id: str,
    status: str,
    result: str,
    details: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    from integrations.backend_client import complete_command

    complete_command(
        config=config,
        log=log,
        command_id=command_id,
        status=status,
        result=result,
        details=details or {},
        error_code=error_code,
    )


def handle_backend_command(
    config: dict[str, Any], command: dict[str, Any], speak: Any = None
) -> None:
    command_id = command.get("id")
    command_type = command.get("type")
    correlation_id = command.get("correlationId")

    if not command_id:
        log(
            "ERROR", "Backend-Command ohne ID erhalten.", errorCode="command_id_missing"
        )
        return

    log(
        "INFO",
        f"Backend-Command erhalten: {command_id} | {command_type}",
        commandId=command_id,
        correlationId=correlation_id,
    )

    try:
        if command_type == "morning_routine":
            run_morning_routine(config, speak=speak)

            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result="Morning Routine wurde lokal ausgeführt.",
                details={"type": command_type, "correlationId": correlation_id},
            )
            return

        if command_type == "dev_news":
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result="Dev-News werden aktuell über Backend /api/news/dev bereitgestellt.",
                details={"type": command_type, "correlationId": correlation_id},
            )
            return

        if command_type == "app_open":
            payload = command.get("payload") or {}
            app_name = (
                str(payload.get("app", "")).strip().lower()
                if isinstance(payload, dict)
                else ""
            )
            app_config = (
                config.get("apps", {}).get(app_name)
                if isinstance(config.get("apps", {}), dict)
                else None
            )

            if not app_name or not isinstance(app_config, dict):
                complete_backend_command(
                    config=config,
                    command_id=command_id,
                    status="rejected",
                    result=f"App nicht konfiguriert: {app_name}",
                    details={
                        "type": command_type,
                        "app": app_name,
                        "correlationId": correlation_id,
                    },
                    error_code="app_not_configured",
                )
                return

            launch_result = start_app(app_name, app_config, log)
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if launch_result.success else "failed",
                result=launch_result.message,
                details={
                    "type": command_type,
                    "app": app_name,
                    "correlationId": correlation_id,
                },
                error_code=launch_result.error_code,
            )
            return

        if command_type == "system_stop":
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result="System-Stop Command erhalten. Agent bleibt bis zum lokalen Loop-Ende aktiv.",
                details={"type": command_type, "correlationId": correlation_id},
            )
            return

        # ── set_volume ─────────────────────────────────────────────────────────
        if command_type == "set_volume":
            payload = command.get("payload") or {}
            level = int(payload.get("level", 50)) if isinstance(payload, dict) else 50

            from execution.system_control import set_volume, get_volume
            ok = set_volume(level)
            actual = get_volume()
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if ok else "failed",
                result=f"Lautstärke auf {level}% gesetzt. Aktuell: {actual}%." if ok
                       else f"Lautstärke konnte nicht gesetzt werden (Ziel: {level}%).",
                details={"type": command_type, "level": level, "actual": actual,
                         "correlationId": correlation_id},
                error_code=None if ok else "volume_set_failed",
            )
            return

        # ── set_brightness ─────────────────────────────────────────────────────
        if command_type == "set_brightness":
            payload = command.get("payload") or {}
            level = int(payload.get("level", 80)) if isinstance(payload, dict) else 80

            from execution.system_control import set_brightness, get_brightness
            ok = set_brightness(level)
            actual = get_brightness()
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if ok else "failed",
                result=f"Helligkeit auf {level}% gesetzt. Aktuell: {actual}%." if ok
                       else f"Helligkeit konnte nicht gesetzt werden (WMI nicht unterstützt?).",
                details={"type": command_type, "level": level, "actual": actual,
                         "correlationId": correlation_id},
                error_code=None if ok else "brightness_set_failed",
            )
            return

        # ── system_info ────────────────────────────────────────────────────────
        if command_type == "system_info":
            from execution.system_info import get_full_status
            from execution.system_control import get_audio_status
            status = get_full_status()
            status["audio"] = get_audio_status()
            battery = status.get("battery", {})
            sys = status.get("system", {})
            summary = (
                f"Akku: {battery.get('percent', '?')}%"
                + (" (lädt)" if battery.get("plugged") else "")
                + f" | CPU: {sys.get('cpu_percent', '?')}%"
                + f" | RAM: {sys.get('ram_percent', '?')}%"
                + f" | Lautstärke: {status.get('audio', {}).get('volume', '?')}%"
            )
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed",
                result=summary,
                details={"type": command_type, "correlationId": correlation_id, **status},
            )
            return

        # ── audio_check ────────────────────────────────────────────────────────
        if command_type == "audio_check":
            from execution.audio_check import run_audio_check
            report = run_audio_check()
            mic_ok = report.get("microphone", {}).get("status") == "ok"
            spk_ok = report.get("speaker", {}).get("status") == "ok"
            summary = (
                f"Mikrofon: {'OK' if mic_ok else 'FEHLER'} "
                f"({report.get('microphone', {}).get('device', '?')}) | "
                f"Lautsprecher: {'OK' if spk_ok else 'FEHLER'} "
                f"({report.get('speaker', {}).get('device', '?')})"
            )
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if report.get("status") == "ok" else "failed",
                result=summary,
                details={"type": command_type, "correlationId": correlation_id, **report},
                error_code=None if report.get("status") == "ok" else "audio_check_failed",
            )
            return

        # ── play_music ─────────────────────────────────────────────────────────
        if command_type == "play_music":
            payload = command.get("payload") or {}
            platform = str(payload.get("platform", "youtube")).strip().lower() \
                if isinstance(payload, dict) else "youtube"
            query = str(payload.get("query", "")).strip() \
                if isinstance(payload, dict) else ""

            if not query:
                complete_backend_command(
                    config=config,
                    command_id=command_id,
                    status="rejected",
                    result="Suchanfrage fehlt.",
                    details={"type": command_type, "correlationId": correlation_id},
                    error_code="play_music_query_missing",
                )
                return

            from execution.media_control import play_music
            result_dict = play_music(platform, query)

            complete_backend_command(
                config=config,
                command_id=command_id,
                status="completed" if result_dict["ok"] else "failed",
                result=f"Musik gestartet: {query} auf {platform}." if result_dict["ok"]
                       else result_dict.get("error", "Unbekannter Fehler."),
                details={"type": command_type, "correlationId": correlation_id,
                         "platform": platform, "query": query, **result_dict},
                error_code=None if result_dict["ok"] else "play_music_failed",
            )
            return

        complete_backend_command(
            config=config,
            command_id=command_id,
            status="rejected",
            result=f"Unbekannter Command-Typ: {command_type}",
            details={"type": command_type, "correlationId": correlation_id},
            error_code="unknown_command_type",
        )

    except Exception as exc:
        log(
            "ERROR",
            f"Backend-Command fehlgeschlagen: {command_id} | {exc}",
            commandId=command_id,
            errorCode="command_execution_failed",
        )

        try:
            complete_backend_command(
                config=config,
                command_id=command_id,
                status="failed",
                result=str(exc),
                details={"type": command_type, "correlationId": correlation_id},
                error_code="command_execution_failed",
            )
        except Exception as inner_exc:
            log(
                "ERROR",
                f"Command-Fehler konnte nicht ans Backend gesendet werden: {inner_exc}",
                errorCode="command_failure_report_failed",
            )


# ── Text-Input Handler ────────────────────────────────────────────────────────


def handle_text_input(
    config: dict[str, Any],
    log: Any,
    text: str,
    stop_event: threading.Event | None = None,
) -> str | None:
    """
    Routed freien deutschen Text durch den IntentRouter und führt die erkannte Aktion aus.
    Gibt die deutsche Antwort zurück, oder None wenn der Intent unbekannt ist
    (Fallback auf ai_brain).
    """
    from integrations.intent_router import IntentRouter, INTENT_UNKNOWN

    try:
        router = IntentRouter(config)
        result = router.route(text, config, log)
    except Exception as exc:
        log("WARN", f"IntentRouter konnte nicht initialisiert werden: {exc}")
        return None

    if result.intent == INTENT_UNKNOWN:
        return None

    return _execute_intent(config, log, result, stop_event=stop_event)


def _execute_intent(
    config: dict[str, Any],
    log: Any,
    result: Any,  # IntentResult
    stop_event: threading.Event | None = None,
) -> str | None:
    """Führt die erkannte Aktion aus und gibt einen deutschen Antworttext zurück."""
    from integrations.intent_router import (
        INTENT_APP_OPEN,
        INTENT_CLARIFY,
        INTENT_MORNING_ROUTINE,
        INTENT_SHIFT_QUERY,
        INTENT_SHIFT_SET,
        INTENT_STREAM_QUERY,
        INTENT_SYSTEM_STOP,
        INTENT_TODO_COMPLETE,
        INTENT_TODO_CREATE,
        INTENT_TODO_QUERY,
        INTENT_TODO_RESCHEDULE,
        INTENT_TODO_SET_REMINDER,
        INTENT_TODO_UPDATE_PRIORITY,
        INTENT_UNKNOWN,
    )

    intent = result.intent
    slots = result.slots

    if intent == INTENT_UNKNOWN:
        return None

    if intent == INTENT_CLARIFY:
        return result.response_text or "Kannst du das genauer beschreiben?"

    # ── system.stop ────────────────────────────────────────────────────────────
    if intent == INTENT_SYSTEM_STOP:
        if stop_event:
            stop_event.set()
        return "Auf Wiedersehen."

    # ── morning_routine ────────────────────────────────────────────────────────
    if intent == INTENT_MORNING_ROUTINE:
        threading.Thread(
            target=run_morning_routine, args=(config,), daemon=True
        ).start()
        return "Ich starte die Morgenroutine."

    # ── app.open ───────────────────────────────────────────────────────────────
    if intent == INTENT_APP_OPEN:
        import subprocess
        app_name = str(slots.get("app", "")).strip()
        if not app_name:
            return "Welche App soll ich öffnen?"
        app_config = config.get("apps", {}).get(app_name.lower())
        if isinstance(app_config, dict):
            r = start_app(app_name, app_config, log)
            return f"{app_name} wird geöffnet." if r.success else f"Ich konnte {app_name} nicht öffnen."
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=False)
            return f"{app_name} wird geöffnet."
        except Exception as exc:
            log("WARN", f"App-Öffnen fehlgeschlagen: {app_name}: {exc}")
            return f"Ich konnte {app_name} nicht öffnen."

    # ── todo.create ────────────────────────────────────────────────────────────
    if intent == INTENT_TODO_CREATE:
        from core.date_parser import parse_german_date
        from integrations.backend_client import create_todo as _create

        title = str(slots.get("title", "")).strip()
        if not title:
            return "Wie soll das TODO heißen?"

        due_date_raw = slots.get("due_date")
        due_date_obj = parse_german_date(str(due_date_raw)) if due_date_raw else None
        due_date = due_date_obj.isoformat() if due_date_obj else None

        due_time = str(slots.get("due_time", "")).strip() or None

        prio_map = {"low": 4, "normal": 3, "high": 2, "critical": 1}
        priority = prio_map.get(str(slots.get("priority", "normal")), 3)

        try:
            todo = _create(
                config,
                log,
                title=title,
                due_date=due_date,
                due_time=due_time,
                priority=priority,
                category=slots.get("category"),
                reminder_minutes=slots.get("reminder_min"),
                source="agent",
                description=None,
            )
            hint = f" für {due_date}" if due_date else ""
            time_hint = f" um {due_time} Uhr" if due_time else ""
            if todo:
                return f"TODO hinzugefügt: {title}{hint}{time_hint}."
            return f"TODO lokal vorgemerkt: {title}{hint}."
        except Exception as exc:
            log("WARN", f"TODO-Erstellen fehlgeschlagen: {exc}")
            return f"TODO konnte nicht gespeichert werden: {exc}"

    # ── todo.update_priority / reschedule / set_reminder ──────────────────────
    if intent in (INTENT_TODO_UPDATE_PRIORITY, INTENT_TODO_RESCHEDULE, INTENT_TODO_SET_REMINDER):
        todo_ref = str(slots.get("todo_ref", "")).strip()
        value = str(slots.get("value", "")).strip()

        if not todo_ref:
            return "Welches TODO meinst du?"
        if not value:
            return "Welchen Wert soll ich setzen?"

        try:
            from todo.todo_client import find_todo_by_title, update_todo as _update

            todo = find_todo_by_title(config, log, todo_ref)
            if not todo:
                return f"Ich konnte kein TODO mit '{todo_ref}' finden."

            if intent == INTENT_TODO_UPDATE_PRIORITY:
                prio_map = {"low": 4, "normal": 3, "high": 2, "critical": 1}
                priority = prio_map.get(value.lower(), 3)
                _update(config, log, todo["id"], {"priority": priority}, actor="agent")
                labels = {1: "kritisch", 2: "hoch", 3: "mittel", 4: "niedrig"}
                return f"Priorität von '{todo['title']}' auf {labels.get(priority, priority)} gesetzt."

            if intent == INTENT_TODO_RESCHEDULE:
                from core.date_parser import parse_german_date
                new_date = parse_german_date(value)
                if not new_date:
                    return f"Das Datum '{value}' konnte ich nicht verstehen."
                _update(config, log, todo["id"], {"dueDate": new_date.isoformat()}, actor="agent")
                return f"'{todo['title']}' verschoben auf {new_date.isoformat()}."

            if intent == INTENT_TODO_SET_REMINDER:
                mins = int(value) if value.isdigit() else 30
                _update(config, log, todo["id"], {"reminderMinutes": mins}, actor="agent")
                h, m = divmod(mins, 60)
                hint = f"{h}h {m}min" if h and m else (f"{h}h" if h else f"{m} Minuten")
                return f"Erinnerung für '{todo['title']}' auf {hint} vor Fälligkeit gesetzt."

        except Exception as exc:
            log("WARN", f"TODO-Update fehlgeschlagen: {exc}")
            return "Das Update hat leider nicht geklappt."

    # ── todo.complete ──────────────────────────────────────────────────────────
    if intent == INTENT_TODO_COMPLETE:
        todo_ref = str(slots.get("todo_ref", "")).strip()
        if not todo_ref:
            return "Welches TODO hast du erledigt?"
        try:
            from todo.todo_client import find_todo_by_title
            from integrations.backend_client import complete_todo as _complete

            todo = find_todo_by_title(config, log, todo_ref)
            if not todo:
                return f"Ich konnte kein TODO mit '{todo_ref}' finden."
            _complete(config, log, todo["id"], actor="agent")
            return f"Erledigt: {todo['title']}."
        except Exception as exc:
            log("WARN", f"TODO-Complete fehlgeschlagen: {exc}")
            return "Das Abhaken hat leider nicht geklappt."

    # ── todo.query ─────────────────────────────────────────────────────────────
    if intent == INTENT_TODO_QUERY:
        try:
            from integrations.backend_client import get_todos_today

            todos = get_todos_today(config, log)
            if not todos:
                return "Keine offenen TODOs für heute gefunden."
            titles = [t.get("title", "") for t in todos[:5]]
            more = f" und {len(todos) - 5} weitere" if len(todos) > 5 else ""
            return f"Heute: {', '.join(titles)}{more}."
        except Exception as exc:
            log("WARN", f"TODO-Query fehlgeschlagen: {exc}")
            return "Ich konnte die TODOs nicht laden."

    # ── shift.set ──────────────────────────────────────────────────────────────
    if intent == INTENT_SHIFT_SET:
        from core.date_parser import parse_german_date
        from shifts.shift_client import set_shift

        date_raw = str(slots.get("date", "")).strip()
        shift_type = str(slots.get("shift_type", "")).strip()

        if not date_raw:
            return "Für welches Datum soll ich die Schicht eintragen?"
        if not shift_type:
            return "Welche Schicht? Tag, Nacht, FAKT Früh, FAKT Spät oder Frei?"

        parsed = parse_german_date(date_raw)
        date_str = parsed.isoformat() if parsed else date_raw

        try:
            shift = set_shift(config, log, date=date_str, shift_type=shift_type, source="agent")
            if shift:
                return f"Schicht eingetragen: {shift.get('label', shift_type)} am {date_str}."
            return f"Schicht konnte nicht eingetragen werden. Eventuell ist {date_str} schon belegt."
        except Exception as exc:
            log("WARN", f"Schicht-Eintragen fehlgeschlagen: {exc}")
            return "Die Schicht konnte nicht eingetragen werden."

    # ── shift.query ────────────────────────────────────────────────────────────
    if intent == INTENT_SHIFT_QUERY:
        from core.date_parser import parse_german_date
        from shifts.shift_client import get_shift

        date_raw = str(slots.get("date", "heute")).strip()
        parsed = parse_german_date(date_raw)
        date_str = parsed.isoformat() if parsed else date_raw

        try:
            shift = get_shift(config, log, date_str)
            if shift:
                return (
                    f"{shift.get('label', '')} am {date_str}: "
                    f"{shift.get('startTime', '')}–{shift.get('endTime', '')} Uhr."
                )
            return f"Keine Schicht für {date_str} eingetragen."
        except Exception as exc:
            log("WARN", f"Schicht-Abfrage fehlgeschlagen: {exc}")
            return "Ich konnte die Schicht nicht abrufen."

    # ── stream.query ───────────────────────────────────────────────────────────
    if intent == INTENT_STREAM_QUERY:
        from core.date_parser import parse_german_date
        from shifts.shift_client import get_stream_recommendation_text

        date_raw = str(slots.get("date", "heute")).strip()
        parsed = parse_german_date(date_raw)
        date_str = parsed.isoformat() if parsed else None

        try:
            return get_stream_recommendation_text(config, log, date=date_str)
        except Exception as exc:
            log("WARN", f"Stream-Empfehlung fehlgeschlagen: {exc}")
            return "Ich konnte die Streaming-Empfehlung nicht laden."

    # Fallback für unbekannte Intents
    log("WARN", f"Unbehandelter Intent: {intent}")
    return None
