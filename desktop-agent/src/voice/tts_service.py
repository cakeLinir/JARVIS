from __future__ import annotations

import queue
import threading
from typing import Any

_SENTINEL = object()


class TTSService:
    def __init__(self, config: dict[str, Any]) -> None:
        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        pyttsx3_rate = int(voice_cfg.get("ttsRate", 170))
        # SAPI Rate: -10..10 (0 = normal ~150 wpm)
        self._sapi_rate = max(-10, min(10, (pyttsx3_rate - 150) // 20))
        self._volume = min(100, max(0, int(float(voice_cfg.get("ttsVolume", 0.9)) * 100)))
        self._language = str(voice_cfg.get("language", "de-DE"))
        self._queue: queue.Queue[Any] = queue.Queue()
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._worker, daemon=True, name="tts-worker")
        self._thread.start()
        if not self._ready.wait(timeout=8):
            raise RuntimeError("TTS-Worker konnte nicht initialisiert werden (Timeout).")
        if self._error:
            raise self._error

    def _select_voice(self, speaker: Any) -> None:
        lang_prefix = self._language.lower().split("-")[0]
        try:
            voices = speaker.GetVoices()
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = (voice.GetDescription() or "").lower()
                if lang_prefix in desc or "german" in desc or "deutsch" in desc:
                    speaker.Voice = voice
                    return
        except Exception:
            pass

    def _worker(self) -> None:
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = self._sapi_rate
            speaker.Volume = self._volume
            self._select_voice(speaker)
            self._ready.set()

            while True:
                item = self._queue.get()
                if item is _SENTINEL:
                    self._queue.task_done()
                    break
                try:
                    # Flag 0 = SVSFDefault (synchronous): Speak() blockiert bis der Satz
                    # vollständig gesprochen wurde. task_done() danach → wait_done() korrekt.
                    speaker.Speak(str(item), 0)
                except Exception:
                    pass
                finally:
                    self._queue.task_done()

            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

        except Exception as exc:
            self._error = exc
            self._ready.set()
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except Exception:
                    break

    def speak(self, text: str) -> None:
        stripped = (text or "").strip()
        if stripped and self._thread.is_alive():
            self._queue.put(stripped)

    def wait_done(self, timeout: float = 15.0) -> None:
        """Blockiert bis alle queued Texte vollständig gesprochen wurden.

        Nutzt queue.join(): task_done() wird erst nach Speak() aufgerufen,
        daher wartet join() auf das echte Ende der Sprachausgabe.
        """
        if not self._thread.is_alive():
            return
        done = threading.Event()

        def _joiner() -> None:
            self._queue.join()
            done.set()

        t = threading.Thread(target=_joiner, daemon=True)
        t.start()
        done.wait(timeout=timeout)

    def stop(self) -> None:
        if self._thread.is_alive():
            self._queue.put(_SENTINEL)


def create_tts(config: dict[str, Any]) -> TTSService:
    return TTSService(config)
