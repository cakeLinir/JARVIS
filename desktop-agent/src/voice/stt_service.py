from __future__ import annotations

from typing import Any, Callable


class STTService:
    def __init__(self, config: dict[str, Any]) -> None:
        import speech_recognition as sr

        self._sr = sr
        self._recognizer = sr.Recognizer()

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._language = str(voice_cfg.get("language", "de-DE"))
        self._timeout = int(voice_cfg.get("sttTimeoutSeconds", 5))
        self._phrase_limit = int(voice_cfg.get("sttPhraseLimitSeconds", 10))

        self._calibrate()

    def _calibrate(self) -> None:
        try:
            with self._sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception:
            pass

    def listen_once(self) -> str | None:
        try:
            with self._sr.Microphone() as source:
                audio = self._recognizer.listen(
                    source,
                    timeout=self._timeout,
                    phrase_time_limit=self._phrase_limit,
                )
            text = self._recognizer.recognize_google(audio, language=self._language)
            return str(text).strip().lower() if text else None
        except self._sr.WaitTimeoutError:
            return None
        except self._sr.UnknownValueError:
            return None
        except Exception:
            return None

    def listen_background(self, callback: Callable[[str], None]) -> Callable[[], None]:
        recognizer = self._recognizer
        language = self._language
        phrase_limit = self._phrase_limit
        sr = self._sr

        def handle(rec: Any, audio: Any) -> None:
            try:
                text = rec.recognize_google(audio, language=language)
                if text:
                    callback(str(text).strip().lower())
            except Exception:
                pass

        stop_fn = recognizer.listen_in_background(
            sr.Microphone(),
            handle,
            phrase_time_limit=phrase_limit,
        )
        return stop_fn


def create_stt(config: dict[str, Any]) -> STTService:
    return STTService(config)
