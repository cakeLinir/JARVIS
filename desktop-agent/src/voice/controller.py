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


def get_voice_status(config: dict[str, Any]) -> VoiceStatus:
    voice_config = config.get("voice", {})
    if not isinstance(voice_config, dict):
        voice_config = {}

    enabled = bool(voice_config.get("enabled", False))
    mode = str(voice_config.get("mode", "text")).strip().lower() or "text"
    wake_word_enabled = bool(voice_config.get("wakeWordEnabled", False))
    stt_provider = str(voice_config.get("sttProvider", "disabled")).strip().lower() or "disabled"
    tts_provider = str(voice_config.get("ttsProvider", "disabled")).strip().lower() or "disabled"

    if not enabled:
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=False,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason="Voice ist deaktiviert. Textmodus bleibt aktiv.",
        )

    if mode != "text":
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=wake_word_enabled,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason="Voice-Audio ist noch nicht implementiert. Nur Textmodus ist freigegeben.",
        )

    return VoiceStatus(
        enabled=True,
        mode="text",
        wakeWordEnabled=False,
        sttProvider="disabled",
        ttsProvider="disabled",
        reason="Voice-Skeleton aktiv. Audio-STT/TTS ist noch deaktiviert.",
    )


def log_voice_status(config: dict[str, Any], log: LogFn) -> None:
    status = get_voice_status(config)

    if status.enabled:
        log("INFO", f"Voice-Skeleton aktiv: mode={status.mode}, stt={status.sttProvider}, tts={status.ttsProvider}")
        return

    log("INFO", status.reason or "Voice deaktiviert.")
