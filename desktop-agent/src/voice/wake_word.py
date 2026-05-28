from __future__ import annotations

import threading
from typing import Any, Callable

from voice.phrases import get_wake_words, get_stop_phrases, normalize_phrase, is_morning_phrase

LogFn = Callable[[str, str], None]
CommandFn = Callable[[str], None]


class WakeWordDetector:
    def __init__(
        self,
        config: dict[str, Any],
        stt: Any,
        tts: Any,
        log: LogFn,
        on_command: CommandFn,
    ) -> None:
        self._config = config
        self._stt = stt
        self._tts = tts
        self._log = log
        self._on_command = on_command
        self._wake_words = set(get_wake_words(config))
        self._stop_phrases = set(get_stop_phrases(config))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _extract_command(self, text: str) -> str:
        normalized = normalize_phrase(text)
        for word in self._wake_words:
            if normalized.startswith(word + " "):
                return normalized[len(word):].strip()
            if normalized.startswith(word + ","):
                return normalized[len(word) + 1:].strip()
        return ""

    def _contains_wake_word(self, text: str) -> bool:
        normalized = normalize_phrase(text)
        for word in self._wake_words:
            if normalized == word or normalized.startswith(word + " ") or normalized.startswith(word + ","):
                return True
        return False

    def _loop(self) -> None:
        self._log("INFO", "Wake-Word Erkennung aktiv. Sage 'Jarvis' zum Aktivieren.")
        self._tts.speak("JARVIS ist bereit.")

        while not self._stop_event.is_set():
            text = self._stt.listen_once()

            if not text:
                continue

            self._log("STT", f"Gehört: {text}")

            normalized = normalize_phrase(text)

            if normalized in self._stop_phrases:
                self._log("INFO", "Stop-Phrase erkannt.")
                self._tts.speak("JARVIS wird beendet.")
                self._on_command("exit")
                break

            if not self._contains_wake_word(text):
                continue

            inline_command = self._extract_command(text)

            if inline_command:
                self._log("INFO", f"Inline-Befehl: {inline_command}")
                self._tts.speak("Einen Moment.")
                self._on_command(inline_command)
                continue

            # Wake word alone — wait for command
            self._tts.speak("Ja?")
            command = self._stt.listen_once()

            if not command:
                self._tts.speak("Ich habe nichts verstanden.")
                continue

            self._log("INFO", f"Befehl: {command}")
            self._on_command(normalize_phrase(command))

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="wake-word")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
