from __future__ import annotations

import queue
import threading
from typing import Any

_SENTINEL = object()


class TTSService:
    def __init__(self, config: dict[str, Any]) -> None:
        import pyttsx3

        self._engine = pyttsx3.init()
        self._queue: queue.Queue[str | object] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        rate = int(voice_cfg.get("ttsRate", 170))
        volume = float(voice_cfg.get("ttsVolume", 0.9))
        language = str(voice_cfg.get("language", "de-DE"))

        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)
        self._set_voice(language)
        self._thread.start()

    def _set_voice(self, language: str) -> None:
        lang_prefix = language.lower().split("-")[0]
        try:
            voices = self._engine.getProperty("voices") or []
        except Exception:
            return

        for voice in voices:
            vid = (voice.id or "").lower()
            vname = (voice.name or "").lower()
            if lang_prefix in vid or lang_prefix in vname or "german" in vname or "deutsch" in vname:
                self._engine.setProperty("voice", voice.id)
                return

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                self._queue.task_done()
                break
            try:
                self._engine.say(str(item))
                self._engine.runAndWait()
            except Exception:
                pass
            self._queue.task_done()

    def speak(self, text: str) -> None:
        stripped = (text or "").strip()
        if stripped:
            self._queue.put(stripped)

    def stop(self) -> None:
        self._queue.put(_SENTINEL)
        try:
            self._engine.stop()
        except Exception:
            pass


def create_tts(config: dict[str, Any]) -> TTSService:
    return TTSService(config)
