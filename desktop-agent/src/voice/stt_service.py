from __future__ import annotations

import re
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
        self._initial_prompt = str(voice_cfg.get("sttInitialPrompt", ""))
        self._silence_secs = float(voice_cfg.get("sttSilenceSeconds", 1.2))
        self._max_secs = float(voice_cfg.get("sttMaxDurationSeconds", 12.0))
        self._timeout_secs = float(voice_cfg.get("sttTimeoutSeconds", 8.0))
        # Halluzinations-Filter: Segmente mit zu hoher no_speech_prob oder zu niedrigem logprob verwerfen
        self._no_speech_threshold = float(voice_cfg.get("sttNoSpeechThreshold", 0.6))
        self._logprob_threshold = float(voice_cfg.get("sttLogprobThreshold", -0.7))
        # Mikrofon-Schwelle: höherer Multiplikator = weniger Fehlauslöser durch Umgebungsgeräusche
        self._threshold_multiplier = float(voice_cfg.get("sttThresholdMultiplier", 5.0))

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
        return max(0.005, ambient * self._threshold_multiplier)

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
            initial_prompt=self._initial_prompt or None,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 300},
        )

        parts: list[str] = []
        for seg in segments:
            # Segment verwerfen wenn Whisper selbst sagt: wahrscheinlich kein Mensch
            if seg.no_speech_prob > self._no_speech_threshold:
                continue
            # Segment verwerfen wenn Konfidenz zu niedrig (typisches Halluzinationsmuster)
            if seg.avg_logprob < self._logprob_threshold:
                continue
            parts.append(seg.text)

        text = " ".join(parts).strip()
        if not text:
            return None

        # Wiederholungs-Halluzination: Satzzeichen entfernen, dann prüfen ob alle Wörter gleich.
        # Ohne Stripping würde "Jarvis, Jarvis" → ["jarvis,", "jarvis"] → 2 verschiedene Einträge.
        clean = re.sub(r"[^\w\s]", "", text.lower())
        words = clean.split()
        if len(words) > 1 and len(set(words)) == 1:
            return None

        return text.lower()


def create_stt(config: dict[str, Any]) -> STTService:
    return STTService(config)


# ── Modul-Level-Cache für lokales Whisper-Modell ──────────────────────────────
_cached_model: dict[str, Any] = {}


def _get_cached_model(model_size: str) -> Any:
    """Whisper-Modell einmalig laden und cachen (1,5 GB beim ersten Aufruf)."""
    if model_size not in _cached_model:
        from faster_whisper import WhisperModel
        _cached_model[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _cached_model[model_size]


# ── Standalone-Funktion: Aufnahme nach Wake-Word ──────────────────────────────

def record_after_wake_word(
    max_seconds: int = 8,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
) -> np.ndarray | None:
    """
    Nimmt Audio via sounddevice auf bis:
    - silence_duration Sekunden Stille erkannt, oder
    - max_seconds erreicht, oder
    - 5 s ohne Sprache (False-Positive-Schutz).
    Gibt float32-Array zurück oder None wenn kein Sprache erkannt.
    """
    import queue as _queue
    try:
        import sounddevice as sd
    except ImportError:
        return None

    RATE = 16_000
    CHUNK = 1_024
    chunks_per_sec = RATE / CHUNK

    silence_needed = int(chunks_per_sec * silence_duration)
    max_chunks = int(chunks_per_sec * max_seconds)
    timeout_chunks = int(chunks_per_sec * 5.0)  # 5 s → False-Positive → stille Deaktivierung

    audio_queue: _queue.Queue[np.ndarray] = _queue.Queue(maxsize=200)

    def _callback(indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        try:
            audio_queue.put_nowait(indata[:, 0].copy())
        except _queue.Full:
            pass

    frames: list[np.ndarray] = []
    speech_started = False
    silence_count = 0
    waited = 0

    try:
        with sd.InputStream(
            samplerate=RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK,
            callback=_callback,
        ):
            while True:
                try:
                    chunk = audio_queue.get(timeout=1.0)
                except _queue.Empty:
                    break

                rms = float(np.sqrt(np.mean(chunk ** 2)))
                is_speech = rms > silence_threshold

                if is_speech:
                    speech_started = True
                    silence_count = 0
                    frames.append(chunk)
                elif speech_started:
                    frames.append(chunk)
                    silence_count += 1
                    if silence_count >= silence_needed:
                        break
                else:
                    waited += 1
                    if waited >= timeout_chunks:
                        break  # Stille Deaktivierung nach 5 s ohne Sprache

                if len(frames) >= max_chunks:
                    break

    except Exception:
        return None

    if not speech_started or not frames:
        return None

    return np.concatenate(frames).astype(np.float32)


# ── Standalone-Funktion: Transkription ────────────────────────────────────────

def transcribe(audio: np.ndarray, config: dict[str, Any]) -> str | None:
    """
    Transkribiert Audio-Array via:
    - 'openai'        → OpenAI Whisper API (config.openaiApiKey / OPENAI_API_KEY)
    - alle anderen   → lokales faster-whisper (cached)
    """
    voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
    provider = str(voice_cfg.get("sttProvider", "faster-whisper")).strip().lower()

    if provider == "openai":
        return _transcribe_openai(audio, config)
    return _transcribe_local(audio, config)


def _transcribe_local(audio: np.ndarray, config: dict[str, Any]) -> str | None:
    """Lokal via faster-whisper mit gecachtem Modell."""
    voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
    model_size = str(voice_cfg.get("sttModel", "medium"))
    language = str(voice_cfg.get("language", "de-DE")).split("-")[0].lower()
    no_speech_thr = float(voice_cfg.get("sttNoSpeechThreshold", 0.6))
    logprob_thr = float(voice_cfg.get("sttLogprobThreshold", -0.7))

    try:
        model = _get_cached_model(model_size)
        segments, _ = model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 300},
        )
        parts = [
            seg.text for seg in segments
            if seg.no_speech_prob <= no_speech_thr and seg.avg_logprob >= logprob_thr
        ]
        text = " ".join(parts).strip().lower()
        return text or None
    except Exception as exc:
        return None


def _transcribe_openai(audio: np.ndarray, config: dict[str, Any]) -> str | None:
    """Via OpenAI Whisper API — benötigt openai-Paket + API-Key."""
    import io
    import os
    import wave

    api_key = str(config.get("openaiApiKey", "")).strip() or os.getenv("OPENAI_API_KEY", "")
    if not api_key or "CHANGE_ME" in api_key.upper():
        return None

    # Audio als WAV-Bytes serialisieren (stdlib wave, kein zusätzliches Paket nötig)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-Bit
        wf.setframerate(16_000)
        audio_int16 = (audio * 32_767).clip(-32_768, 32_767).astype(np.int16)
        wf.writeframes(audio_int16.tobytes())
    buf.seek(0)
    buf.name = "audio.wav"  # OpenAI SDK prüft Dateiendung

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
            language="de",
        )
        text = response.text.strip().lower()
        return text or None
    except Exception:
        return None
