"""
Wake-Word-Erkennung via openWakeWord + sounddevice.
Neue Schnittstelle: WakeWordDetector ruft on_activation() auf — keine STT/TTS mehr hier.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable

import numpy as np

LogFn = Callable[[str, str], None]
ActivationFn = Callable[[], None]

# openWakeWord erwartet 16 kHz Int16-Audio in 80 ms-Chunks (1280 Samples)
_OWW_RATE = 16_000
_OWW_CHUNK = 1_280


class WakeWordDetector:
    """
    Lauscht kontinuierlich auf das Wake-Word und ruft bei Erkennung on_activation() auf.
    Keine STT/TTS-Logik — die gehört in den VoiceController.
    """

    def __init__(
        self,
        config: dict[str, Any],
        log: LogFn,
        on_activation: ActivationFn,
    ) -> None:
        self._config = config
        self._log = log
        self._on_activation = on_activation

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._model_name = str(voice_cfg.get("wakeWordModel", "hey_jarvis"))
        self._threshold = float(voice_cfg.get("wakeWordThreshold", 0.5))
        # Optionaler VAD-Vorfilter: überspringt sehr leise Chunks vor dem Modell
        self._vad_enabled = bool(voice_cfg.get("vadEnabled", True))
        self._vad_threshold = float(voice_cfg.get("vadThreshold", 0.003))

        self._stop_event = threading.Event()
        # Verhindert erneutes Auslösen während on_activation läuft
        self._processing = threading.Event()
        self._model: Any | None = None
        self._thread: threading.Thread | None = None

    # ── Audio-Chunk-Verarbeitung ──────────────────────────────────────────────

    def _process_audio_chunk(self, audio_chunk: np.ndarray) -> bool:
        """
        Führt openWakeWord-Prediction durch.
        audio_chunk: int16-Array mit 1280 Samples @ 16 kHz.
        Gibt True zurück wenn Schwellenwert überschritten.
        """
        if self._model is None or self._processing.is_set():
            return False

        # VAD-Vorfilter: reine Stille nicht an das Modell übergeben
        if self._vad_enabled:
            rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
            if rms / 32_767 < self._vad_threshold:
                return False

        try:
            prediction = self._model.predict(audio_chunk)
            triggered = any(score >= self._threshold for score in prediction.values())
            if triggered:
                scores = ", ".join(f"{k}={v:.2f}" for k, v in prediction.items())
                self._log("INFO", f"Wake-Word erkannt: {scores}")
            return triggered
        except Exception as exc:
            self._log("WARN", f"Wake-Word Prediction-Fehler: {exc}")
            return False

    # ── Haupt-Loop ────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        # Modell laden (lädt ONNX beim ersten Start herunter)
        try:
            from openwakeword.model import Model

            self._model = Model(
                wakeword_models=[self._model_name],
                inference_framework="onnx",
            )
        except Exception as exc:
            self._log(
                "ERROR",
                f"openWakeWord konnte nicht geladen werden: {exc} "
                "— Installiere mit: pip install openwakeword",
                errorCode="oww_load_failed",
            )
            return

        # Audio-Queue: Callback → Loop (entkoppelt Aufnahme und Verarbeitung)
        audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=50)

        def _sd_callback(indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
            # float32 → int16 für openWakeWord
            chunk_int16 = (indata[:, 0] * 32_767).clip(-32_768, 32_767).astype(np.int16)
            try:
                audio_queue.put_nowait(chunk_int16)
            except queue.Full:
                pass  # Puffer voll: Chunk verwerfen, kein Crash

        try:
            import sounddevice as sd
        except ImportError:
            self._log(
                "ERROR",
                "sounddevice nicht installiert — pip install sounddevice",
                errorCode="sounddevice_missing",
            )
            return

        self._log(
            "INFO",
            f"Wake-Word Erkennung aktiv: Modell={self._model_name}, "
            f"Schwelle={self._threshold}, VAD={self._vad_enabled}",
        )

        try:
            with sd.InputStream(
                samplerate=_OWW_RATE,
                channels=1,
                dtype="float32",
                blocksize=_OWW_CHUNK,
                callback=_sd_callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if not self._process_audio_chunk(chunk):
                        continue

                    # Wake-Word erkannt
                    self._model.reset()
                    self._processing.set()

                    # Audio-Puffer leeren damit kein TTS-Echo einläuft
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            break

                    try:
                        self._on_activation()
                    except Exception as exc:
                        self._log(
                            "ERROR",
                            f"on_activation Fehler: {exc}",
                            errorCode="voice_activation_failed",
                        )
                    finally:
                        self._processing.clear()
                        self._model.reset()

        except Exception as exc:
            self._log(
                "ERROR",
                f"Wake-Word Stream-Fehler: {exc}",
                errorCode="oww_stream_failed",
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="wake-word"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
