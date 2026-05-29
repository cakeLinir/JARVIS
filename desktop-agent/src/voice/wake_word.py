from __future__ import annotations

import threading
from typing import Any, Callable

import numpy as np
import pyaudio

from voice.phrases import get_stop_phrases, is_morning_phrase, normalize_phrase

LogFn = Callable[[str, str], None]
CommandFn = Callable[[str], None]

# openWakeWord erwartet 16kHz Int16-Audio in 80ms-Chunks (1280 Samples)
_OWW_RATE = 16000
_OWW_CHUNK = 1280
_OWW_FORMAT = pyaudio.paInt16


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

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._model_name = str(voice_cfg.get("wakeWordModel", "hey_jarvis"))
        self._threshold = float(voice_cfg.get("wakeWordThreshold", 0.5))

    # ── Hilfsmethoden ──────────────────────────────────────────────────────

    def _speak_and_wait(self, text: str) -> None:
        self._tts.speak(text)
        try:
            self._tts.wait_done()
        except Exception:
            pass

    def _flush_stream(self, stream: Any, chunks: int = 8) -> None:
        """Veraltete Audio-Daten aus dem PyAudio-Puffer werfen."""
        for _ in range(chunks):
            try:
                stream.read(_OWW_CHUNK, exception_on_overflow=False)
            except Exception:
                break

    def _listen_for_command(self) -> str | None:
        self._speak_and_wait("Ja?")
        return self._stt.listen_once()

    # ── Haupt-Loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        # Modell laden (lädt ONNX-Datei beim ersten Start herunter)
        try:
            from openwakeword.model import Model

            model = Model(
                wakeword_models=[self._model_name],
                inference_framework="onnx",
            )
        except Exception as exc:
            self._log(
                "ERROR",
                f"openWakeWord konnte nicht geladen werden: {exc} "
                f"— Installiere mit: pip install openwakeword",
                errorCode="oww_load_failed",
            )
            return

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=_OWW_FORMAT,
            channels=1,
            rate=_OWW_RATE,
            input=True,
            frames_per_buffer=_OWW_CHUNK,
        )

        self._log(
            "INFO",
            f"Wake-Word Erkennung aktiv ({self._model_name}, "
            f"threshold={self._threshold}). Sage 'Hey Jarvis'.",
        )
        self._speak_and_wait("JARVIS ist bereit.")

        try:
            while not self._stop_event.is_set():
                try:
                    raw = stream.read(_OWW_CHUNK, exception_on_overflow=False)
                except Exception:
                    continue

                audio = np.frombuffer(raw, dtype=np.int16)
                prediction = model.predict(audio)

                triggered = any(
                    score >= self._threshold for score in prediction.values()
                )
                if not triggered:
                    continue

                scores_str = ", ".join(
                    f"{k}={v:.2f}" for k, v in prediction.items()
                )
                self._log("INFO", f"Wake-Word erkannt: {scores_str}")
                model.reset()

                # Puffer leeren bevor STT hört (verhindert TTS-Echo-Feedback)
                self._flush_stream(stream)

                command = self._listen_for_command()

                # Nach dem Sprechen und Hören wieder Puffer leeren
                self._flush_stream(stream)
                model.reset()

                if not command:
                    self._speak_and_wait("Ich habe nichts verstanden.")
                    continue

                self._log("STT", f"Befehl: {command}")
                normalized = normalize_phrase(command)

                if normalized in self._stop_phrases:
                    self._log("INFO", "Stop-Phrase erkannt.")
                    self._speak_and_wait("JARVIS wird beendet.")
                    self._on_command("exit")
                    break

                if is_morning_phrase(command):
                    self._on_command("guten morgen jarvis")
                    self._tts.wait_done()
                    continue

                self._on_command(normalized)
                self._tts.wait_done()

        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="wake-word"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
