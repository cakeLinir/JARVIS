"""
Reminder-Engine: prüft regelmäßig fällige Todos und spricht Erinnerungen aus.
Läuft als eigener Thread — startet mit start(), stoppt mit stop().
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

LogFn = Callable[[str, str], None]
SpeakFn = Callable[[str], None]


class ReminderEngine:
    """
    Polling-basierter Reminder. Alle 60 Sekunden werden fällige Todos
    vom Backend abgerufen und per TTS angesagt.
    """

    POLL_INTERVAL_SECONDS = 60

    def __init__(
        self,
        config: dict[str, Any],
        log: LogFn,
        speak: SpeakFn,
        stop_event: threading.Event,
    ) -> None:
        self._config = config
        self._log = log
        self._speak = speak
        self._stop_event = stop_event
        self._thread: threading.Thread | None = None
        # IDs bereits angesagter Todos (verhindert Doppel-Reminder in derselben Session)
        self._fired: set[str] = set()

    def _check_reminders(self) -> None:
        """Ruft fällige Todos vom Backend ab und sagt sie an."""
        try:
            from integrations.backend_client import request_json

            result = request_json(
                backend_url=self._config.get("backendUrl", ""),
                agent_token=self._config.get("agentToken", ""),
                endpoint="/api/todos/due-today",
                method="GET",
                payload=None,
                log=self._log,
                quiet_success=True,
            )
            if not result or not result.get("ok"):
                return

            todos = result.get("todos", [])
            now_minutes = datetime.now().hour * 60 + datetime.now().minute

            for todo in todos:
                todo_id = todo.get("id", "")
                title = todo.get("title", "")
                reminder_minutes = todo.get("reminderMinutes")
                due_time = todo.get("dueTime")
                due_date = todo.get("dueDate")

                if todo_id in self._fired:
                    continue
                if todo.get("status") not in ("open", "in_progress"):
                    continue

                # Fälligkeitszeit in Minuten
                if due_date and due_time:
                    try:
                        due_h, due_m = map(int, due_time.split(":"))
                        due_total = due_h * 60 + due_m
                        fire_min = due_total - (reminder_minutes or 0)

                        # Innerhalb ±90 Sekunden Toleranz
                        if abs(now_minutes - fire_min) <= 1.5:
                            self._log("INFO", f"Reminder feuert: {title}")
                            self._speak(f"Erinnerung: {title}")
                            self._fired.add(todo_id)

                    except (ValueError, TypeError):
                        pass

                # Todos ohne Uhrzeit: früh morgens einmal ansagen (09:00)
                elif due_date and not due_time and now_minutes == 9 * 60:
                    self._log("INFO", f"Morgen-Reminder: {title}")
                    self._speak(f"Heutiges Todo: {title}")
                    self._fired.add(todo_id)

        except Exception as exc:
            self._log("WARN", f"Reminder-Check fehlgeschlagen: {exc}")

    def _loop(self) -> None:
        self._log("INFO", "Reminder-Engine gestartet.")
        while not self._stop_event.is_set():
            self._check_reminders()
            self._stop_event.wait(self.POLL_INTERVAL_SECONDS)
        self._log("INFO", "Reminder-Engine beendet.")

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="reminder-engine"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
