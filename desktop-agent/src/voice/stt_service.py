from __future__ import annotations

import tempfile
import threading
import wave
from typing import Any

import numpy as np
import pyaudio


_PA_FORMAT = pyaudio.paFloat32
_SAMPLE_RATE = 16000
_CHANNELS = 1
_CHUNK = 1024


class STTService:
    def __init__(self, config: dict[str, Any]) -> None:
        from faster_whisper import WhisperModel

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        language_tag = str(voice_cfg.get("language", "de-DE"))
        self._language = language_tag.split("-")[0].lower()  # "de"
        self._model_size = str(voice_cfg.get("sttModel", "medium"))
        self._initial_prompt = str(voice_cfg.get("sttInitialPrompt", "Jarvis JARVIS"))
        self._silence_secs = float(voice_cfg.get("sttSilenceSeconds", 1.2))
        self._max_secs = float(voice_cfg.get("sttMaxDurationSeconds", 12.0))
        self._timeout_secs = float(voice_cfg.get("sttTimeoutSeconds", 8.0))

        # Modell laden (erster Start lädt ~1.5GB herunter)
        self._model = WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )

        # Umgebungsgeräusch-Schwelle kalibrieren
        self._threshold = self._calibrate()

    def _calibrate(self) -> float:
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=_PA_FORMAT,
                channels=_CHANNELS,
                rate=_SAMPLE_RATE,
                input=True,
                frames_per_buffer=_CHUNK,
            )
            levels: list[float] = []
            for _ in range(30):  # ~0.3 Sekunden
                raw = stream.read(_CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32)
                levels.append(float(np.sqrt(np.mean(samples ** 2))))
            stream.stop_stream()
            stream.close()
        finally:
            pa.terminate()

        ambient = float(np.mean(levels)) if levels else 0.01
        # Schwelle = 3x Umgebungsgeräusch, mindestens 0.005
        return max(0.005, ambient * 3.0)

    def _record(self, timeout: float, max_duration: float, silence_secs: float) -> np.ndarray | None:
        """Nimmt auf bis Stille erkannt wird. Gibt float32-Array zurück oder None."""
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=_PA_FORMAT,
                channels=_CHANNELS,
                rate=_SAMPLE_RATE,
                input=True,
                frames_per_buffer=_CHUNK,
            )
            frames: list[bytes] = []
            chunks_per_sec = _SAMPLE_RATE / _CHUNK
            silence_needed = int(chunks_per_sec * silence_secs)
            timeout_chunks = int(chunks_per_sec * timeout)
            max_chunks = int(chunks_per_sec * max_duration)

            silence_count = 0
            speech_started = False
            waited = 0

            while True:
                raw = stream.read(_CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32)
                rms = float(np.sqrt(np.mean(samples ** 2)))
                is_speech = rms > self._threshold

                if is_speech:
                    speech_started = True
                    silence_count = 0
                    frames.append(raw)
                elif speech_started:
                    frames.append(raw)
                    silence_count += 1
                    if silence_count >= silence_needed:
                        break
                else:
                    waited += 1
                    if waited >= timeout_chunks:
                        break

                if len(frames) >= max_chunks:
                    break

            stream.stop_stream()
            stream.close()
        finally:
            pa.terminate()

        if not speech_started or not frames:
            return None

        return np.frombuffer(b"".join(frames), dtype=np.float32)

    def listen_once(self) -> str | None:
        audio = self._record(
            timeout=self._timeout_secs,
            max_duration=self._max_secs,
            silence_secs=self._silence_secs,
        )
        if audio is None or len(audio) == 0:
            return None

        segments, _ = self._model.transcribe(
            audio,
            language=self._language,
            initial_prompt=self._initial_prompt,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(s.text for s in segments).strip()
        return text.lower() if text else None


def create_stt(config: dict[str, Any]) -> STTService:
    return STTService(config)
