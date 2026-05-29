from __future__ import annotations

import os
import queue
import tempfile
import threading
from typing import Any

_SENTINEL = object()

_FEMALE_VOICE_FRAGMENTS = frozenset({
    "hedda", "zira", "helena", "sabina", "katja", "hortense",
    "hazel", "susan", "linda", "anna", "maria", "laura",
})


class TTSService:
    def __init__(self, config: dict[str, Any]) -> None:
        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._provider = str(voice_cfg.get("ttsProvider", "sapi")).strip().lower()
        self._voice_name = str(voice_cfg.get("ttsVoice", "")).strip()
        self._gender = str(voice_cfg.get("ttsGender", "male")).strip().lower()
        self._language = str(voice_cfg.get("language", "de-DE"))

        pyttsx3_rate = int(voice_cfg.get("ttsRate", 170))
        # SAPI Rate: -10..10
        self._sapi_rate = max(-10, min(10, (pyttsx3_rate - 150) // 20))
        # Edge Rate: "+20%" etc. (150 = 0%, jede Einheit = 1%)
        self._edge_rate = f"{pyttsx3_rate - 150:+d}%"

        raw_volume = float(voice_cfg.get("ttsVolume", 0.9))
        self._volume = min(100, max(0, int(raw_volume * 100)))

        self._queue: queue.Queue[Any] = queue.Queue()
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._worker, daemon=True, name="tts-worker")
        self._thread.start()
        if not self._ready.wait(timeout=8):
            raise RuntimeError("TTS-Worker konnte nicht initialisiert werden (Timeout).")
        if self._error:
            raise self._error

    # ── SAPI-Backend ───────────────────────────────────────────────────────

    def _select_voice(self, speaker: Any) -> None:
        lang_prefix = self._language.lower().split("-")[0]
        try:
            voices = speaker.GetVoices()
            candidates: list[Any] = []

            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = (voice.GetDescription() or "").lower()

                if self._voice_name and self._voice_name.lower() in desc:
                    speaker.Voice = voice
                    return

                if lang_prefix in desc or "german" in desc or "deutsch" in desc:
                    candidates.append((voice, desc))

            if not candidates:
                return

            if self._gender == "male":
                male = [
                    (v, d) for v, d in candidates
                    if not any(f in d for f in _FEMALE_VOICE_FRAGMENTS)
                ]
                if male:
                    speaker.Voice = male[0][0]
                    return
            elif self._gender == "female":
                female = [
                    (v, d) for v, d in candidates
                    if any(f in d for f in _FEMALE_VOICE_FRAGMENTS)
                ]
                if female:
                    speaker.Voice = female[0][0]
                    return

            speaker.Voice = candidates[0][0]
        except Exception:
            pass

    def _worker_sapi(self) -> None:
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

    # ── Edge-TTS-Backend ──────────────────────────────────────────────────

    def _worker_edge(self) -> None:
        try:
            import edge_tts  # noqa: F401 — früh prüfen, damit Fehler sichtbar ist
        except ImportError:
            self._error = RuntimeError(
                "edge-tts nicht installiert. Führe aus: pip install edge-tts"
            )
            self._ready.set()
            return

        import asyncio

        self._ready.set()

        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                self._queue.task_done()
                break
            try:
                asyncio.run(self._speak_edge(str(item)))
            except Exception as exc:
                print(f"[TTS-Edge] Wiedergabefehler: {exc}", flush=True)
            finally:
                self._queue.task_done()

    async def _speak_edge(self, text: str) -> None:
        import ctypes
        import edge_tts

        voice = self._voice_name or "de-DE-ConradNeural"
        communicate = edge_tts.Communicate(text, voice, rate=self._edge_rate)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fh:
            tmp_path = fh.name

        mci = ctypes.windll.winmm.mciSendStringW
        try:
            await communicate.save(tmp_path)
            mci("close jarvis_audio", None, 0, None)
            ret = mci(
                f'open "{tmp_path}" type mpegvideo alias jarvis_audio', None, 0, None
            )
            if ret != 0:
                raise RuntimeError(f"MCI open fehlgeschlagen (Code {ret})")
            mci("play jarvis_audio wait", None, 0, None)
        finally:
            mci("close jarvis_audio", None, 0, None)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ── Dispatch ──────────────────────────────────────────────────────────

    def _worker(self) -> None:
        if self._provider == "edge":
            self._worker_edge()
        else:
            self._worker_sapi()

    # ── Public API ────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        stripped = (text or "").strip()
        if stripped and self._thread.is_alive():
            self._queue.put(stripped)

    def wait_done(self, timeout: float = 15.0) -> None:
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
