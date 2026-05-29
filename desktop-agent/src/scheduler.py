from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Any, Callable

LogFn = Callable[[str, str], None]
RoutineRunFn = Callable[[dict[str, Any]], None]

# Wochentag-Mapping: DE + EN Kürzel → Python weekday (0=Mo)
_WEEKDAY = {
    "mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}

_CHECK_INTERVAL_S = 30  # alle 30s prüfen ob eine Routine fällig ist


class RoutineScheduler:
    def __init__(
        self,
        config: dict[str, Any],
        log: LogFn,
        run_routine: RoutineRunFn,
        stop_event: threading.Event,
    ) -> None:
        self._config = config
        self._log = log
        self._run_routine = run_routine
        self._stop_event = stop_event
        # Protokoll: routine_name → Datum des letzten Laufs (verhindert Doppelauslösung)
        self._ran_today: dict[str, date] = {}
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="routine-scheduler"
        )

    def start(self) -> None:
        self._thread.start()

    # ── Prüflogik ────────────────────────────────────────────────────────

    def _parse_time(self, time_str: str) -> tuple[int, int] | None:
        try:
            h, m = time_str.strip().split(":")
            return int(h), int(m)
        except Exception:
            return None

    def _is_allowed_day(self, days: Any) -> bool:
        if not isinstance(days, list) or not days:
            return True  # kein Filter → immer erlaubt
        today = datetime.now().weekday()
        allowed = {_WEEKDAY[d.lower()] for d in days if isinstance(d, str) and d.lower() in _WEEKDAY}
        return today in allowed

    def _should_run(self, routine: dict[str, Any], now: datetime) -> bool:
        if not bool(routine.get("enabled", True)):
            return False

        name = str(routine.get("name", "")).strip()
        if not name:
            return False

        parsed = self._parse_time(str(routine.get("time", "")))
        if parsed is None:
            return False
        hour, minute = parsed

        if now.hour != hour or now.minute != minute:
            return False

        if not self._is_allowed_day(routine.get("days")):
            return False

        if self._ran_today.get(name) == now.date():
            return False  # heute bereits gelaufen

        return True

    # ── Haupt-Loop ───────────────────────────────────────────────────────

    def _loop(self) -> None:
        self._log("INFO", "Routine-Scheduler gestartet.")

        while not self._stop_event.wait(_CHECK_INTERVAL_S):
            routines = self._config.get("routines", [])
            if not isinstance(routines, list):
                continue

            now = datetime.now()

            for routine in routines:
                if not isinstance(routine, dict):
                    continue
                try:
                    if self._should_run(routine, now):
                        name = str(routine.get("name", ""))
                        self._log("INFO", f"Zeitgesteuerte Routine startet: {name} ({routine.get('time')})")
                        self._ran_today[name] = now.date()
                        threading.Thread(
                            target=self._run_routine,
                            args=(routine,),
                            daemon=True,
                            name=f"routine-{name}",
                        ).start()
                except Exception as exc:
                    self._log(
                        "ERROR",
                        f"Routine-Fehler: {exc}",
                        errorCode="scheduler_routine_failed",
                    )

        self._log("INFO", "Routine-Scheduler beendet.")
