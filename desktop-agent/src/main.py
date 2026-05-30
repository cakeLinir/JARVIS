from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from core.config_loader import load_config
from core.logging import log
from execution.app_launcher import start_app
from handlers.command_handler import handle_backend_command
from routines.morning import run_morning_routine, read_todos
from shifts.shift_parser import parse_shift_type, shift_label
from utils.date_resolver import resolve_date, resolve_time


def send_agent_status_safe(config: dict[str, Any], status: str) -> None:
    try:
        from integrations.backend_client import send_agent_status

        send_agent_status(config, log, status)

    except Exception as exc:
        log(
            "ERROR",
            f"Agent-Status konnte nicht ans Backend gesendet werden: {exc}",
            errorCode="agent_status_send_failed",
        )


# FIX Bug 3: get_todo_path() war definiert, wurde aber nirgends aufgerufen.
# Die Funktion bleibt erhalten, ist aber als "aktuell ungenutzt" markiert.
def get_todo_path(config: dict[str, Any]) -> Path | None:
    todo_config = config.get("todo", {})
    provider = str(todo_config.get("provider", "markdown")).strip().lower()

    if provider != "markdown":
        return None

    todo_path_value = todo_config.get("markdownPath")

    if not todo_path_value:
        log("ERROR", "KONFIGURATION_ERFORDERLICH: TODO Markdown-Pfad fehlt.")
        return None

    todo_path = Path(str(todo_path_value))

    if not todo_path.exists():
        log(
            "ERROR",
            f"KONFIGURATION_ERFORDERLICH: TODO-Datei existiert nicht: {todo_path}",
        )
        return None

    return todo_path


def _add_markdown_todo(config: dict[str, Any], text: str) -> bool:
    todo_config = config.get("todo", {})
    path_value = todo_config.get("markdownPath") if isinstance(todo_config, dict) else None
    if not path_value:
        return False
    path = Path(str(path_value))
    if not path.exists():
        return False
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n- [ ] {text}")
        return True
    except Exception as exc:
        log("ERROR", f"TODO konnte nicht hinzugefügt werden: {exc}")
        return False


def _handle_system_control(action: str, value: Any, speak: Any) -> None:
    import ctypes
    import subprocess

    if action == "set_volume":
        pct = max(0, min(100, int(value or 50)))
        level = int(65535 * pct / 100)
        packed = level | (level << 16)
        ctypes.windll.winmm.waveOutSetVolume(0, packed)
        speak(f"Lautstärke auf {pct} Prozent gesetzt.")

    elif action == "mute":
        ctypes.windll.winmm.waveOutSetVolume(0, 0)
        speak("Stummgeschaltet.")

    elif action == "unmute":
        level = int(65535 * 0.5)
        ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
        speak("Stummschaltung aufgehoben.")

    elif action == "sleep":
        speak("Computer wird in den Ruhemodus versetzt.")
        subprocess.run(
            [
                "powershell", "-NonInteractive", "-NoProfile", "-command",
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
            ],
            capture_output=True,
            timeout=10,
        )

    elif action == "shutdown":
        speak("Computer wird in 30 Sekunden heruntergefahren.")
        subprocess.run(["shutdown", "/s", "/t", "30"])


def _execute_ai_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    config: dict[str, Any],
    speak: Any,
) -> bool:
    """Führt einen von Claude gewählten Tool-Call aus. Gibt True zurück wenn Agent stoppen soll."""

    # ── open_app ──────────────────────────────────────────────────────────────
    if tool_name == "open_app":
        import shutil
        import subprocess
        app_name = str(tool_input.get("app", "")).strip().lower()
        app_config = (
            config.get("apps", {}).get(app_name)
            if isinstance(config.get("apps"), dict)
            else None
        )
        if isinstance(app_config, dict):
            result = start_app(app_name, app_config, log)
            speak(f"{app_name} wird geöffnet." if result.success else f"Ich konnte {app_name} nicht öffnen.")
            return False

        # Nicht konfiguriert → Windows-Fallback
        _WIN_ALIASES = {
            "rechner": "calc", "taschenrechner": "calc",
            "explorer": "explorer", "datei-explorer": "explorer",
            "editor": "notepad", "notizblock": "notepad",
            "aufgabenmanager": "taskmgr", "task-manager": "taskmgr",
            "einstellungen": "ms-settings:", "systemsteuerung": "control",
            "paint": "mspaint", "wordpad": "wordpad",
        }
        launch_name = _WIN_ALIASES.get(app_name, app_name)
        exe = shutil.which(launch_name)
        try:
            if exe:
                subprocess.Popen([exe])
            else:
                subprocess.Popen(["cmd", "/c", "start", "", launch_name], shell=False)
            speak(f"{app_name} wird geöffnet.")
            log("INFO", f"App geöffnet (Fallback): {launch_name}")
        except Exception as exc:
            log("WARN", f"App-Fallback fehlgeschlagen: {launch_name}: {exc}")
            speak(f"Ich konnte {app_name} nicht öffnen.")
        return False

    # ── system_control ────────────────────────────────────────────────────────
    if tool_name == "system_control":
        try:
            _handle_system_control(
                str(tool_input.get("action", "")), tool_input.get("value"), speak
            )
        except Exception as exc:
            log(
                "ERROR",
                f"Systemsteuerung fehlgeschlagen: {exc}",
                errorCode="system_control_failed",
            )
            speak("Die Systemsteuerung hat nicht funktioniert.")
        return False

    # ── todo_action ───────────────────────────────────────────────────────────
    if tool_name == "todo_action":
        action = str(tool_input.get("action", ""))

        if action == "read":
            # Backend-Todos bevorzugen, Fallback auf lokalen Provider
            try:
                from todo.todo_client import get_due_today

                todos_data = get_due_today(config, log)
                if todos_data:
                    titles = [t.get("title", "") for t in todos_data[:5]]
                    speak(
                        f"Du hast {len(todos_data)} fällige TODOs: " + ", ".join(titles)
                    )
                else:
                    speak("Du hast keine fälligen TODOs.")
            except Exception:
                # Offline-Fallback auf lokalen Provider
                todos = read_todos(config)
                if todos:
                    speak(f"Du hast {len(todos)} offene TODOs: " + ", ".join(todos[:5]))
                else:
                    speak("Du hast keine offenen TODOs.")
            return False

        if action == "add":
            title = str(tool_input.get("text", "")).strip()
            if not title:
                speak("Wie soll das TODO heißen?")
                return False

            raw_date = tool_input.get("due_date")
            due_date = resolve_date(str(raw_date)) if raw_date else None

            raw_time = tool_input.get("due_time")
            due_time = resolve_time(str(raw_time)) if raw_time else None

            priority = int(tool_input.get("priority", 3))
            reminder_minutes = tool_input.get("reminder_minutes")
            category = tool_input.get("category")
            description = tool_input.get("description")

            try:
                from todo.todo_client import create_todo

                todo = create_todo(
                    config=config,
                    log=log,
                    title=title,
                    due_date=due_date,
                    due_time=due_time,
                    priority=priority,
                    category=category,
                    reminder_minutes=reminder_minutes,
                    source="voice",
                    description=description,
                )
                if todo:
                    date_hint = f" für {due_date}" if due_date else ""
                    time_hint = f" um {due_time} Uhr" if due_time else ""
                    speak(f"TODO hinzugefügt: {title}{date_hint}{time_hint}.")
                else:
                    # Offline-Fallback
                    _add_markdown_todo(config, title)
                    speak(f"TODO lokal gespeichert: {title}")
            except Exception as exc:
                log("WARN", f"Todo-Backend nicht erreichbar, lokaler Fallback: {exc}")
                _add_markdown_todo(config, title)
                speak(f"TODO lokal gespeichert: {title}")
            return False

        if action == "complete":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            try:
                from todo.todo_client import (
                    find_todo_by_title,
                    complete_todo as _complete,
                )

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Ich konnte das TODO nicht finden. Welches meinst du?")
                    return False
                result = _complete(config, log, todo["id"], actor="voice")
                speak(f"Erledigt: {todo.get('title', todo_ref)}.")
            except Exception as exc:
                log("WARN", f"Todo-Complete fehlgeschlagen: {exc}")
                speak("Ich konnte das TODO nicht als erledigt markieren.")
            return False

        if action == "reschedule":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            raw_date = tool_input.get("due_date")
            new_date = resolve_date(str(raw_date)) if raw_date else None

            if not new_date:
                speak("Auf welches Datum soll ich es verschieben?")
                return False

            raw_time = tool_input.get("due_time")
            new_time = resolve_time(str(raw_time)) if raw_time else None

            try:
                from todo.todo_client import (
                    find_todo_by_title,
                    reschedule_todo as _reschedule,
                )

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Ich konnte das TODO nicht finden.")
                    return False
                _reschedule(config, log, todo["id"], new_date, new_time, actor="voice")
                speak(f"{todo.get('title', todo_ref)} verschoben auf {new_date}.")
            except Exception as exc:
                log("WARN", f"Todo-Reschedule fehlgeschlagen: {exc}")
                speak("Das Verschieben hat nicht geklappt.")
            return False

        if action == "set_priority":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            priority = int(tool_input.get("priority", 2))
            prio_labels = {
                1: "kritisch",
                2: "hoch",
                3: "mittel",
                4: "niedrig",
                5: "optional",
            }
            try:
                from todo.todo_client import find_todo_by_title, update_todo as _update

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Welches TODO meinst du?")
                    return False
                _update(config, log, todo["id"], {"priority": priority}, actor="voice")
                speak(
                    f"Priorität von '{todo.get('title', todo_ref)}' auf {prio_labels.get(priority, priority)} gesetzt."
                )
            except Exception as exc:
                log("WARN", f"Todo-Priority fehlgeschlagen: {exc}")
                speak("Die Priorität konnte nicht geändert werden.")
            return False

        if action == "set_reminder":
            todo_ref = str(tool_input.get("todo_ref", "")).strip()
            reminder_minutes = int(tool_input.get("reminder_minutes", 30))
            try:
                from todo.todo_client import find_todo_by_title, update_todo as _update

                todo = find_todo_by_title(config, log, todo_ref) if todo_ref else None
                if not todo:
                    speak("Für welches TODO soll ich die Erinnerung setzen?")
                    return False
                _update(
                    config,
                    log,
                    todo["id"],
                    {"reminderMinutes": reminder_minutes},
                    actor="voice",
                )
                hours = reminder_minutes // 60
                mins = reminder_minutes % 60
                hint = (
                    f"{hours} Stunden"
                    if hours and not mins
                    else (f"{mins} Minuten" if not hours else f"{hours}h {mins}min")
                )
                speak(
                    f"Erinnerung für '{todo.get('title', '')}' auf {hint} vorher gesetzt."
                )
            except Exception as exc:
                log("WARN", f"Todo-Reminder fehlgeschlagen: {exc}")
                speak("Die Erinnerung konnte nicht gesetzt werden.")
            return False

    # ── shift_action ──────────────────────────────────────────────────────────
    if tool_name == "shift_action":
        action = str(tool_input.get("action", ""))

        if action == "set":
            raw_date = tool_input.get("date")
            raw_type = tool_input.get("shift_type", "")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            shift_type = parse_shift_type(str(raw_type)) if raw_type else None

            if not date_str:
                speak("Für welches Datum soll ich die Schicht eintragen?")
                return False
            if not shift_type:
                speak("Welche Schicht? Tag, Nacht, FAKT Früh, FAKT Spät oder Frei?")
                return False

            try:
                from shifts.shift_client import set_shift

                shift = set_shift(
                    config, log, date=date_str, shift_type=shift_type, source="voice"
                )
                if shift:
                    speak(
                        f"{shift_label(shift_type)} für {date_str} eingetragen: {shift.get('startTime', '')}–{shift.get('endTime', '')} Uhr."
                    )
                else:
                    speak("Die Schicht konnte nicht gespeichert werden.")
            except Exception as exc:
                log("WARN", f"Shift-Set fehlgeschlagen: {exc}")
                speak("Ich konnte die Schicht nicht eintragen.")
            return False

        if action == "get":
            raw_date = tool_input.get("date")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            try:
                from shifts.shift_client import get_shift, get_today_shift

                shift = (
                    get_shift(config, log, date_str)
                    if date_str
                    else get_today_shift(config, log)
                )
                if shift:
                    speak(
                        f"{shift.get('label', '')} am {shift.get('date', '')}: {shift.get('startTime', '')}–{shift.get('endTime', '')} Uhr."
                    )
                else:
                    speak("Für dieses Datum ist keine Schicht eingetragen.")
            except Exception as exc:
                log("WARN", f"Shift-Get fehlgeschlagen: {exc}")
                speak("Ich konnte die Schicht nicht abrufen.")
            return False

        if action == "streaming_advice":
            raw_date = tool_input.get("date")
            date_str = resolve_date(str(raw_date)) if raw_date else None
            try:
                from shifts.shift_client import get_streaming_advice

                advice = get_streaming_advice(config, log, date=date_str)
                if not advice:
                    speak("Ich konnte keine Streaming-Empfehlung abrufen.")
                    return False

                rec = advice.get("recommendation", "unknown")
                label_map = {
                    "yes": "Ja, Streaming ist heute sinnvoll.",
                    "conditional": "Bedingt sinnvoll.",
                    "no": "Nein, heute kein Streaming empfohlen.",
                    "unknown": "Keine Schicht eingetragen — bitte zuerst Schicht eintragen.",
                }
                base = label_map.get(rec, rec)

                reasons = advice.get("reasons", [])
                warnings = advice.get("warnings", [])
                latest = advice.get("latestStreamEnd")

                parts = [base]
                if reasons:
                    parts.append(reasons[0])
                if latest:
                    parts.append(f"Empfohlenes Stream-Ende: {latest} Uhr.")
                if warnings:
                    parts.append(warnings[0])

                speak(" ".join(parts))

            except Exception as exc:
                log("WARN", f"Streaming-Advice fehlgeschlagen: {exc}")
                speak("Ich konnte die Streaming-Empfehlung nicht laden.")
            return False

    # ── weather_action ────────────────────────────────────────────────────────
    if tool_name == "weather_action":
        import json as _json
        import urllib.request
        action = str(tool_input.get("action", "current"))
        city = str(tool_input.get("city", "")).strip()
        if not city:
            weather_cfg = config.get("weather", {}) if isinstance(config, dict) else {}
            city = str(weather_cfg.get("city", "")).strip()
        if not city:
            speak("Für welche Stadt soll ich das Wetter abrufen?")
            return False
        try:
            req = urllib.request.Request(
                f"https://wttr.in/{urllib.request.quote(city)}?format=j1",
                headers={"User-Agent": "JARVIS/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            cur = data["current_condition"][0]
            temp = cur["temp_C"]
            feels = cur["FeelsLikeC"]
            humidity = cur["humidity"]
            desc_list = cur.get("lang_de") or cur.get("weatherDesc") or [{}]
            desc = str(desc_list[0].get("value", "")).strip()
            if action == "forecast":
                days = data.get("weather", [])
                parts = [f"In {city} aktuell {temp} Grad, {desc}."]
                for day in days[:2]:
                    date = day.get("date", "")
                    hi = day.get("maxtempC", "?")
                    lo = day.get("mintempC", "?")
                    parts.append(f"{date}: {lo}–{hi} Grad.")
                speak(" ".join(parts))
            else:
                speak(f"In {city} aktuell {temp} Grad, gefühlt {feels} Grad. {desc}. Luftfeuchtigkeit {humidity} Prozent.")
        except Exception as exc:
            log("WARN", f"Wetter fehlgeschlagen: {city}: {exc}")
            speak(f"Ich konnte das Wetter für {city} leider nicht abrufen.")
        return False

    # ── open_url ──────────────────────────────────────────────────────────────
    if tool_name == "open_url":
        import subprocess as _sp
        url = str(tool_input.get("url", "")).strip()
        if not url:
            return False
        try:
            _sp.Popen(["cmd", "/c", "start", "", url], shell=False)
            speak("Seite wird geöffnet.")
            log("INFO", f"URL geöffnet: {url}")
        except Exception as exc:
            log("WARN", f"URL-Öffnen fehlgeschlagen: {url}: {exc}")
            speak("Ich konnte die Seite nicht öffnen.")
        return False

    # ── run_routine ───────────────────────────────────────────────────────────
    if tool_name == "run_routine":
        name = str(tool_input.get("name", ""))
        if name == "morning_routine":
            threading.Thread(
                target=run_morning_routine, args=(config, speak), daemon=True
            ).start()
        return False

    # ── answer ────────────────────────────────────────────────────────────────
    if tool_name == "answer":
        speak(str(tool_input.get("text", "")))
        return False

    return False


def _handle_local_command(
    command: str,
    config: dict[str, Any],
    wake_words: list[str],
    stop_event: threading.Event,
    speak: Any,
    brain: Any = None,
) -> bool:
    """Returns True if the agent should stop."""
    if command in ["exit", "quit", "beenden"]:
        send_agent_status_safe(config, "offline")
        stop_event.set()
        log("INFO", "JARVIS Local Client wird beendet.")
        return True

    if command in ["jarvis, stopp", "jarvis, abbrechen", "jarvis, beenden"]:
        send_agent_status_safe(config, "stopped")
        stop_event.set()
        log("WARN", "Not-Aus ausgelöst.")
        return True

    if command == "guten morgen jarvis":
        run_morning_routine(config, speak=speak)
        return False

    if command in wake_words:
        log("INFO", "JARVIS ist aktiv.")
        speak("Ja, ich bin bereit.")
        return False

    # Erst Intent-Router versuchen (strukturiertes Tool-Calling)
    try:
        from handlers.command_handler import handle_text_input

        response = handle_text_input(config, log, command, stop_event=stop_event)
        if response is not None:
            if response:
                speak(response)
            return stop_event.is_set() if stop_event else False
    except Exception as exc:
        log("WARN", f"Intent-Router fehlgeschlagen, Fallback auf AI-Brain: {exc}")

    # Fallback: AI-Brain für freie Antworten und unbekannte Intents
    if brain is None:
        speak("Das habe ich nicht verstanden.")
        return False

    try:
        log("INFO", f"AI-Brain verarbeitet: {command}")
        tool_calls = brain.process(command)

        for call in tool_calls:
            should_stop = _execute_ai_tool(
                call.get("name", ""),
                call.get("input", {}),
                config,
                speak,
            )
            if should_stop:
                return True

    except Exception as exc:
        log("ERROR", f"AI-Brain Ausführung fehlgeschlagen: {exc}", errorCode="ai_brain_exec_failed")
        speak("Das habe ich nicht verstanden.")

    return False


def get_heartbeat_interval_seconds(config: dict[str, Any]) -> int:
    runtime_config = config.get("runtime", {})
    raw_value = (
        runtime_config.get("heartbeatIntervalSeconds", 30)
        if isinstance(runtime_config, dict)
        else 30
    )

    try:
        interval = int(raw_value)
    except Exception:
        interval = 30

    return max(10, min(interval, 300))


def heartbeat_loop(config: dict[str, Any], stop_event: threading.Event) -> None:
    interval = get_heartbeat_interval_seconds(config)
    log("INFO", f"Agent Heartbeat gestartet: alle {interval}s.")

    while not stop_event.wait(interval):
        send_agent_status_safe(config, "online")

    log("INFO", "Agent Heartbeat beendet.")


def command_poll_loop(
    config: dict[str, Any], stop_event: threading.Event, speak: Any = None
) -> None:
    log("INFO", "Backend Command Polling gestartet.")

    while not stop_event.is_set():
        try:
            from integrations.backend_client import get_next_command

            command = get_next_command(config, log)

            if command:
                handle_backend_command(config, command, speak=speak)

        except Exception as exc:
            log(
                "ERROR",
                f"Command Polling Fehler: {exc}",
                errorCode="command_poll_failed",
            )

        stop_event.wait(5)

    log("INFO", "Backend Command Polling beendet.")


def normalize_command(command: str) -> str:
    try:
        from voice.phrases import normalize_phrase

        return normalize_phrase(command)
    except Exception:
        return " ".join(command.strip().lower().split())


def main() -> None:
    config = load_config()

    try:
        from voice.controller import get_voice_status, log_voice_status

        log_voice_status(config, log)
        voice_status = get_voice_status(config)
    except Exception as exc:
        log("ERROR", f"Voice-Status konnte nicht initialisiert werden: {exc}")
        voice_status = None

    try:
        from voice.phrases import get_wake_words

        wake_words = get_wake_words(config)
    except Exception:
        wake_words = config.get("wakeWords", [])

    voice_enabled = voice_status is not None and voice_status.enabled

    tts_service = None
    try:
        from voice.tts_service import create_tts

        tts_service = create_tts(config)
    except Exception as exc:
        log("WARN", f"TTS konnte nicht initialisiert werden: {exc}")
        # Automatischer Fallback auf SAPI wenn z.B. edge-tts fehlt
        voice_cfg = config.get("voice", {})
        if isinstance(voice_cfg, dict) and voice_cfg.get("ttsProvider", "") != "sapi":
            try:
                fallback_cfg = {
                    **config,
                    "voice": {**voice_cfg, "ttsProvider": "sapi"},
                }
                tts_service = create_tts(fallback_cfg)
                log("INFO", "TTS: Fallback auf SAPI.")
            except Exception as fb_exc:
                log("WARN", f"TTS SAPI-Fallback fehlgeschlagen: {fb_exc}")

    def speak(text: str) -> None:
        if tts_service:
            tts_service.speak(text)
            try:
                tts_service.wait_done()
            except Exception:
                pass
        else:
            log("INFO", f"[TTS] {text}")

    stop_event = threading.Event()

    log("INFO", "JARVIS Local Client gestartet.")

    if voice_enabled:
        log(
            "INFO",
            f"Voice-Modus aktiv: stt={voice_status.sttProvider}, tts={voice_status.ttsProvider}",
        )
    else:
        log("INFO", "Textmodus aktiv. Tippe 'guten morgen jarvis' oder 'exit'.")

    send_agent_status_safe(config, "online")

    try:
        from integrations.ai_brain import create_brain

        brain = create_brain(config, log)
    except Exception as exc:
        log("WARN", f"AI-Brain konnte nicht geladen werden: {exc}")
        brain = None

    def request_stop() -> None:
        send_agent_status_safe(config, "stopped")
        stop_event.set()
        log("WARN", "Lokaler Stop wurde angefordert.")

    local_api_server = None
    try:
        from local_api import start_local_api

        local_api_server = start_local_api(
            config=config,
            log=log,
            run_morning=lambda: run_morning_routine(config, speak=speak),
            stop_agent=request_stop,
        )
    except Exception as exc:
        log(
            "ERROR",
            f"Lokale Agent-API konnte nicht gestartet werden: {exc}",
            errorCode="local_api_start_failed",
        )

    try:
        from scheduler import RoutineScheduler

        def _dispatch_scheduled_routine(routine: dict[str, Any]) -> None:
            for action in routine.get("actions", []):
                if action == "morning_routine":
                    run_morning_routine(config, speak=speak)
                else:
                    log("WARN", f"Unbekannte Routine-Aktion: {action}", errorCode="unknown_routine_action")

        routine_scheduler = RoutineScheduler(
            config=config,
            log=log,
            run_routine=_dispatch_scheduled_routine,
            stop_event=stop_event,
        )
        routine_scheduler.start()
    except Exception as exc:
        log("WARN", f"Routine-Scheduler konnte nicht gestartet werden: {exc}")

    try:
        from todo.reminder_engine import ReminderEngine
        reminder_engine = ReminderEngine(
            config=config, log=log, speak=speak, stop_event=stop_event
        )
        reminder_engine.start()
    except Exception as exc:
        log("WARN", f"Reminder-Engine konnte nicht gestartet werden: {exc}")

    polling_thread = threading.Thread(
        target=command_poll_loop,
        args=(config, stop_event, speak),
        daemon=True,
    )
    polling_thread.start()

    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(config, stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    if voice_enabled:
        try:
            from handlers.command_handler import handle_text_input
            from voice.controller import VoiceController

            voice_ctrl = VoiceController(config, log, handle_text_input)
            voice_ctrl.start()
            log("INFO", "Voice-Pipeline aktiv. Wake-Word: 'Hey Jarvis'")

            stop_event.wait()
            voice_ctrl.stop()

        except Exception as exc:
            log(
                "ERROR",
                f"Voice-Pipeline fehlgeschlagen: {exc}. Fallback auf Textmodus.",
                errorCode="voice_mode_failed",
            )
            voice_enabled = False

    if not voice_enabled:
        while not stop_event.is_set():
            try:
                command = normalize_command(input("> "))
                should_stop = _handle_local_command(
                    command, config, wake_words, stop_event, speak, brain=brain
                )
                if should_stop:
                    break

            except KeyboardInterrupt:
                send_agent_status_safe(config, "interrupted")
                stop_event.set()
                log("WARN", "Abbruch durch Benutzer.")
                break

    if local_api_server:
        local_api_server.stop()


if __name__ == "__main__":
    main()
