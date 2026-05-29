from __future__ import annotations

import threading
from typing import Any, Callable

from voice.phrases import get_stop_phrases, normalize_phrase, is_morning_phrase

LogFn = Callable[[str, str], None]
CommandFn = Callable[[str], None]

# Google STT (de-DE) kennt "Jarvis" nicht — mögliche Transkriptionen auffangen.
_JARVIS_VARIANTS = frozenset({
    "jarvis", "jar", "jarvi", "jarvis", "paris", "jarfis", "jarbis", "jabis",
    "jar vis", "jar-vis",
})

_GREETING_PREFIXES = frozenset({
    "hallo", "hey", "hi", "guten morgen", "guten tag", "guten abend",
})


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
        self._stop_phrases = set(get_stop_phrases(config))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _is_jarvis_variant(self, word: str) -> bool:
        return word in _JARVIS_VARIANTS

    def _contains_wake_word(self, text: str) -> bool:
        normalized = normalize_phrase(text)
        words = normalized.split()

        # Letztes Wort ist eine Jarvis-Variante?
        if words and self._is_jarvis_variant(words[-1]):
            return True

        # Irgendein Wort ist eine Jarvis-Variante?
        if any(self._is_jarvis_variant(w) for w in words):
            return True

        # Exakte Standard-Wake-Phrasen
        if normalized in {"guten morgen jarvis", "hallo jarvis", "jarvis"}:
            return True

        return False

    def _is_complete_greeting(self, text: str) -> bool:
        """True wenn der Text eine vollständige Begrüßungsphrase ist (kein Befehl dahinter)."""
        normalized = normalize_phrase(text)
        words = normalized.split()

        if not words:
            return False

        # Nur Jarvis-Variante allein (bare "jarvis" oder "jar") → NICHT als greeting,
        # sondern als Aktivierung mit anschließendem Zuhören.
        if len(words) == 1 and self._is_jarvis_variant(words[0]):
            return False

        # Prefix + Jarvis-Variante, nichts dahinter → vollständige Begrüßung
        last = words[-1]
        prefix = " ".join(words[:-1])
        if self._is_jarvis_variant(last) and prefix in _GREETING_PREFIXES:
            return True

        # "guten morgen jarvis" komplett
        if is_morning_phrase(text):
            return True

        return False

    def _extract_inline_command(self, text: str) -> str:
        """Extrahiert Befehlsanteil nach dem Wake-Word, falls vorhanden."""
        normalized = normalize_phrase(text)
        words = normalized.split()

        if not words:
            return ""

        # Jarvis-Variante irgendwo in der Mitte → alles danach ist Befehl
        for i, word in enumerate(words):
            if self._is_jarvis_variant(word) and i < len(words) - 1:
                return " ".join(words[i + 1:]).strip().lstrip(",").strip()

        return ""

    def _speak_and_wait(self, text: str) -> None:
        self._tts.speak(text)
        try:
            self._tts.wait_done()
        except Exception:
            pass

    def _loop(self) -> None:
        self._log("INFO", "Wake-Word Erkennung aktiv. Sage 'Jarvis' zum Aktivieren.")
        self._speak_and_wait("JARVIS ist bereit.")

        while not self._stop_event.is_set():
            text = self._stt.listen_once()

            if not text:
                continue

            self._log("STT", f"Gehört: {text}")
            normalized = normalize_phrase(text)

            # Stop-Phrase
            if normalized in self._stop_phrases:
                self._log("INFO", "Stop-Phrase erkannt.")
                self._speak_and_wait("JARVIS wird beendet.")
                self._on_command("exit")
                break

            if not self._contains_wake_word(text):
                continue

            # Inline-Befehl: "Jarvis, öffne Spotify"
            inline = self._extract_inline_command(text)
            if inline:
                self._log("INFO", f"Inline-Befehl erkannt: {inline}")
                self._speak_and_wait("Einen Moment.")
                self._on_command(inline)
                self._tts.wait_done()
                continue

            # Vollständige Begrüßung: "Hallo Jarvis", "Guten Morgen Jarvis"
            if self._is_complete_greeting(text):
                if is_morning_phrase(text):
                    self._log("INFO", "Morgenroutine erkannt.")
                    self._on_command("guten morgen jarvis")
                else:
                    self._log("INFO", f"Begrüßung erkannt: {normalized}")
                    self._speak_and_wait("Ja, ich bin bereit.")
                self._tts.wait_done()
                continue

            # Bare "Jarvis" → nach Befehl fragen
            self._speak_and_wait("Ja?")

            command = self._stt.listen_once()
            if not command:
                self._speak_and_wait("Ich habe nichts verstanden.")
                continue

            self._log("INFO", f"Befehl nach Wake: {command}")
            self._on_command(normalize_phrase(command))
            self._tts.wait_done()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="wake-word")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
