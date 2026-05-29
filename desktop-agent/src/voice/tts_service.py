from __future__ import annotations

import queue
import threading
from typing import Any

_SENTINEL = object()


class TTSService:
    def __init__(self, config: dict[str, Any]) -> None:
        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._rate = int(voice_cfg.get("ttsRate", 170))
        self._volume = float(voice_cfg.get("ttsVolume", 0.9))
        self._language = str(voice_cfg.get("language", "de-DE"))
        self._queue: queue.Queue[str | object] = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="tts-worker")
        self._thread.start()
        self._ready.wait(timeout=5)

    def _set_voice(self, engine: Any) -> None:
        lang_prefix = self._language.lower().split("-")[0]
        try:
            voices = engine.getProperty("voices") or []
        except Exception:
            return
        for voice in voices:
            vid = (voice.id or "").lower()
            vname = (voice.name or "").lower()
            if lang_prefix in vid or lang_prefix in vname or "german" in vname or "deutsch" in vname:
                engine.setProperty("voice", voice.id)
                return

    def _worker(self) -> None:
        # pyttsx3 muss auf demselben Thread initialisiert und genutzt werden (Windows COM).
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", self._rate)
        engine.setProperty("volume", self._volume)
        self._set_voice(engine)
        self._ready.set()

        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                self._queue.task_done()
                break
            try:
                engine.say(str(item))
                engine.runAndWait()
            except Exception:
                pass
            self._queue.task_done()

        try:
            engine.stop()
        except Exception:
            pass

    def speak(self, text: str) -> None:
        stripped = (text or "").strip()
        if stripped:
            self._queue.put(stripped)

    def wait_done(self, timeout: float = 15.0) -> None:
        """Blockiert bis alle queued Texte gesprochen wurden."""
        self._queue.join()

    def stop(self) -> None:
        self._queue.put(_SENTINEL)


def create_tts(config: dict[str, Any]) -> TTSService:
    return TTSService(config)
