from __future__ import annotations

import threading
from typing import Any, Callable

from voice.phrases import get_stop_phrases, normalize_phrase, is_morning_phrase

LogFn = Callable[[str, str], None]
CommandFn = Callable[[str], None]

# Google STT (de-DE) kennt "Jarvis" nicht. Mögliche Transkriptionen auffangen.
_JARVIS_VARIANTS = frozenset({
    "jarvis", "jar", "jarvi", "paris", "jarfis", "jarbis", "jabis",
    "jar vis", "jar-vis",
})

# Begrüßungspräfixe VOR einem Jarvis-Variant
_GREETING_PREFIXES = frozenset({
    "hallo", "hey", "hi", "hello", "guten tag", "guten abend", "moin",
})

# Begrüßungsworte die als Follow-Up nach bare "jarvis" kommen können
_GREETING_FOLLOWUP_WORDS = frozenset({
    "hallo", "hey", "hi", "hello", "moin",
})

# Morgenpräfixe — auch ohne Jarvis-Suffix als Morgen-Trigger erkannt
_MORNING_PREFIXES = frozenset({
    "guten morgen",
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

    # ── Erkennung ──────────────────────────────────────────────────────────

    def _is_jarvis_variant(self, word: str) -> bool:
        return word in _JARVIS_VARIANTS

    def _contains_wake_word(self, text: str) -> bool:
        normalized = normalize_phrase(text)
        words = normalized.split()

        # Letztes Wort oder irgendein Wort ist Jarvis-Variante
        if words and self._is_jarvis_variant(words[-1]):
            return True
        if any(self._is_jarvis_variant(w) for w in words):
            return True

        # Morgenpräfix allein → Jarvis wurde von STT verschluckt
        if any(normalized == p or normalized.startswith(p + " ") for p in _MORNING_PREFIXES):
            return True

        return False

    def _is_morning_trigger(self, text: str) -> bool:
        """True wenn der Text eine Morgenroutine auslösen soll."""
        normalized = normalize_phrase(text)
        if is_morning_phrase(text):
            return True
        if any(normalized == p or normalized.startswith(p) for p in _MORNING_PREFIXES):
            return True
        return False

    def _is_complete_greeting(self, text: str) -> bool:
        """True wenn der Text eine vollständige Begrüßung ist (kein Befehl dahinter)."""
        normalized = normalize_phrase(text)
        words = normalized.split()

        if not words:
            return False

        # Bare "jarvis"-Variante allein → nicht als Greeting, sondern Aktivierung
        if len(words) == 1 and self._is_jarvis_variant(words[0]):
            return False

        # Morgenpräfix (mit oder ohne Jarvis) → KEIN greeting, sondern Routine
        if self._is_morning_trigger(text):
            return False

        # Präfix + Jarvis-Variante → Begrüßung
        last = words[-1]
        prefix = " ".join(words[:-1])
        if self._is_jarvis_variant(last) and prefix in _GREETING_PREFIXES:
            return True

        return False

    def _is_greeting_followup(self, text: str) -> bool:
        """True wenn der Text nach bare 'jarvis' eine nachgereichte Begrüßung ist.

        Tritt auf wenn der User 'Hallo Jarvis' sagt, STT aber 'jarvis' und
        danach 'hallo jar' als zwei getrennte Erkennungen liefert.
        """
        normalized = normalize_phrase(text)
        words = normalized.split()

        if not words:
            return False

        # Erstes Wort ist ein Begrüßungswort
        if words[0] in _GREETING_FOLLOWUP_WORDS:
            return True

        # Begrüßung + Jarvis-Variante (z.B. "hallo jar")
        if len(words) >= 2 and self._is_jarvis_variant(words[-1]) and words[0] in _GREETING_FOLLOWUP_WORDS:
            return True

        return False

    def _extract_inline_command(self, text: str) -> str:
        """Extrahiert Befehlsanteil nach dem Jarvis-Variant, falls vorhanden."""
        normalized = normalize_phrase(text)
        words = normalized.split()
        for i, word in enumerate(words):
            if self._is_jarvis_variant(word) and i < len(words) - 1:
                return " ".join(words[i + 1:]).strip().lstrip(",").strip()
        return ""

    # ── Hilfsmethoden ──────────────────────────────────────────────────────

    def _speak_and_wait(self, text: str) -> None:
        self._tts.speak(text)
        try:
            self._tts.wait_done()
        except Exception:
            pass

    # ── Haupt-Loop ─────────────────────────────────────────────────────────

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

            # Morgenroutine (auch wenn "jarvis" von STT verschluckt wurde)
            if self._is_morning_trigger(text):
                self._log("INFO", "Morgenroutine erkannt.")
                self._on_command("guten morgen jarvis")
                self._tts.wait_done()
                continue

            # Vollständige Begrüßung: "Hallo Jarvis", "Hallo Jar" etc.
            if self._is_complete_greeting(text):
                self._log("INFO", f"Begrüßung erkannt: {normalized}")
                self._speak_and_wait("Ja, ich bin bereit.")
                continue

            # Inline-Befehl: "Jarvis, öffne Spotify"
            inline = self._extract_inline_command(text)
            if inline:
                self._log("INFO", f"Inline-Befehl: {inline}")
                self._speak_and_wait("Einen Moment.")
                self._on_command(inline)
                self._tts.wait_done()
                continue

            # Bare "jarvis" → nach Befehl fragen
            self._speak_and_wait("Ja?")

            command = self._stt.listen_once()
            if not command:
                self._speak_and_wait("Ich habe nichts verstanden.")
                continue

            self._log("STT", f"Befehl nach Wake: {command}")

            # Nachgereichte Begrüßung abfangen ("hallo jar" nach bare "jarvis")
            if self._is_greeting_followup(command) or self._is_complete_greeting(command):
                self._speak_and_wait("Ja, ich bin bereit.")
                continue

            # Morgenroutine als Follow-Up
            if self._is_morning_trigger(command):
                self._log("INFO", "Morgenroutine als Follow-Up erkannt.")
                self._on_command("guten morgen jarvis")
                self._tts.wait_done()
                continue

            self._on_command(normalize_phrase(command))
            self._tts.wait_done()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="wake-word")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
