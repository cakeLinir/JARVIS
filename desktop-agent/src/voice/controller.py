from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

LogFn = Callable[[str, str], None]


@dataclass(slots=True)
class VoiceStatus:
    enabled: bool
    mode: str
    wakeWordEnabled: bool
    sttProvider: str
    ttsProvider: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tts_available(provider: str) -> bool:
    if provider in ("disabled", "none", ""):
        return True
    if provider == "pyttsx3":
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def _stt_available(provider: str) -> bool:
    if provider in ("disabled", "none", ""):
        return True
    if provider == "google":
        try:
            import speech_recognition  # noqa: F401
            import pyaudio  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def get_voice_status(config: dict[str, Any]) -> VoiceStatus:
    voice_cfg = config.get("voice", {})
    if not isinstance(voice_cfg, dict):
        voice_cfg = {}

    enabled = bool(voice_cfg.get("enabled", False))
    mode = str(voice_cfg.get("mode", "text")).strip().lower() or "text"
    wake_word_enabled = bool(voice_cfg.get("wakeWordEnabled", False))
    stt_provider = str(voice_cfg.get("sttProvider", "disabled")).strip().lower() or "disabled"
    tts_provider = str(voice_cfg.get("ttsProvider", "disabled")).strip().lower() or "disabled"

    if not enabled:
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=False,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason="Voice ist deaktiviert. Textmodus aktiv.",
        )

    if not _tts_available(tts_provider):
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=False,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason=f"TTS '{tts_provider}' nicht verfügbar. Installiere: pip install pyttsx3",
        )

    if not _stt_available(stt_provider):
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=False,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason=f"STT '{stt_provider}' nicht verfügbar. Installiere: pip install SpeechRecognition pyaudio",
        )

    return VoiceStatus(
        enabled=True,
        mode=mode,
        wakeWordEnabled=wake_word_enabled,
        sttProvider=stt_provider,
        ttsProvider=tts_provider,
    )


def log_voice_status(config: dict[str, Any], log: LogFn) -> None:
    status = get_voice_status(config)
    if status.enabled:
        log(
            "INFO",
            f"Voice aktiv: mode={status.mode}, stt={status.sttProvider}, "
            f"tts={status.ttsProvider}, wakeWord={status.wakeWordEnabled}",
        )
    else:
        log("INFO", status.reason or "Voice deaktiviert.")
