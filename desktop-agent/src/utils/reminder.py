"""
Zeitgesteuerte Erinnerungen fuer Sprach-Befehle.
"Erinnere mich in 2 Stunden an X" → trigger_at = now + 2h → speak("Erinnerung: X")

Laeuft als Daemon-Thread. Persistiert in data/reminders.json.
Abgelaufene Eintraege werden beim Start automatisch verworfen.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

LogFn = Callable[[str, str], None]
SpeakFn = Callable[[str], None]

_CHECK_INTERVAL_S = 30


class ReminderManager:
    def __init__(self, data_path: Path, log: LogFn, speak: SpeakFn) -> None:
        self._path = data_path
        self._log = log
        self._speak = speak
        self._lock = threading.Lock()
        self._reminders: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="reminder-manager"
        )
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, text: str, trigger_at: datetime) -> None:
        """Fuegt eine Erinnerung hinzu."""
        entry = {"text": text, "trigger_at": trigger_at.isoformat()}
        with self._lock:
            self._reminders.append(entry)
            self._save()
        self._log(
            "INFO",
            f"Erinnerung gesetzt: '{text}' um {trigger_at.strftime('%H:%M')} Uhr",
        )

    def add_in_minutes(self, text: str, minutes: int) -> datetime:
        """Kurzform: Erinnerung in X Minuten. Gibt trigger_at zurueck."""
        trigger_at = datetime.now() + timedelta(minutes=minutes)
        self.add(text, trigger_at)
        return trigger_at

    def start(self) -> None:
        self._thread.start()
        self._log("INFO", "Reminder-Manager gestartet.")

    def stop(self) -> None:
        self._stop.set()

    def pending_count(self) -> int:
        with self._lock:
            return len(self._reminders)

    # ── Persistenz ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return
            now = datetime.now()
            future = [
                r
                for r in raw
                if isinstance(r, dict)
                and "trigger_at" in r
                and datetime.fromisoformat(r["trigger_at"]) > now
            ]
            self._reminders = future
            if future:
                self._log("INFO", f"{len(future)} Erinnerung(en) aus Datei geladen.")
        except Exception as exc:
            self._log("WARN", f"Reminder-Datei konnte nicht geladen werden: {exc}")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._reminders, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self._log("WARN", f"Reminder-Datei konnte nicht gespeichert werden: {exc}")

    # ── Hintergrund-Loop ──────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop.wait(_CHECK_INTERVAL_S):
            self._fire_due()

    def _fire_due(self) -> None:
        now = datetime.now()
        due: list[dict[str, Any]] = []
        remaining: list[dict[str, Any]] = []

        with self._lock:
            for r in self._reminders:
                try:
                    if datetime.fromisoformat(r["trigger_at"]) <= now:
                        due.append(r)
                    else:
                        remaining.append(r)
                except Exception:
                    pass
            self._reminders = remaining
            if due:
                self._save()

        for r in due:
            text = str(r.get("text", "")).strip()
            self._log("INFO", f"Erinnerung faellig: {text}")
            try:
                self._speak(f"Erinnerung: {text}")
            except Exception as exc:
                self._log("WARN", f"Erinnerung sprechen fehlgeschlagen: {exc}")
