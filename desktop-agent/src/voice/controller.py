from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any, Callable

LogFn = Callable[[str, str], None]
CommandHandlerFn = Callable[..., str | None]  # handle_text_input(config, log, text, ...) → str|None


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
    if provider in ("sapi", "win32com", "winsapi"):
        try:
            import pythoncom  # noqa: F401
            import win32com.client  # noqa: F401
            return True
        except ImportError:
            return False
    if provider == "edge":
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def _stt_available(provider: str) -> bool:
    if provider in ("disabled", "none", ""):
        return True
    if provider in ("whisper", "faster-whisper"):
        try:
            import faster_whisper  # noqa: F401
            import pyaudio  # noqa: F401
            import numpy  # noqa: F401
            return True
        except ImportError:
            return False
    if provider == "google":
        try:
            import speech_recognition  # noqa: F401
            import pyaudio  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def _oww_available() -> bool:
    try:
        import openwakeword  # noqa: F401
        return True
    except ImportError:
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
            reason=f"STT '{stt_provider}' nicht verfügbar. Installiere: pip install faster-whisper pyaudio",
        )

    if wake_word_enabled and not _oww_available():
        return VoiceStatus(
            enabled=False,
            mode=mode,
            wakeWordEnabled=False,
            sttProvider=stt_provider,
            ttsProvider=tts_provider,
            reason="openWakeWord nicht verfügbar. Installiere: pip install openwakeword",
        )

    return VoiceStatus(
        enabled=True,
        mode=mode,
        wakeWordEnabled=wake_word_enabled,
        sttProvider=stt_provider,
        ttsProvider=tts_provider,
    )


class VoiceController:
    """
    Orchestriert die vollständige Voice-Pipeline:
    Wake-Word → STT (record + transcribe) → IntentRouter → TTS.
    Nutzt WakeWordDetector (sounddevice/openWakeWord) und standalone STT-Funktionen.
    """

    def __init__(
        self,
        config: dict[str, Any],
        log: LogFn,
        command_handler: CommandHandlerFn,
    ) -> None:
        self._config = config
        self._log = log
        self._command_handler = command_handler

        voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
        self._max_record = int(voice_cfg.get("maxRecordSeconds", 8))
        self._silence_threshold = float(voice_cfg.get("silenceThreshold", 0.01))
        self._silence_duration = float(voice_cfg.get("silenceDuration", 1.5))

        # TTS-Instanz (persistent für geringe Latenz) mit automatischem SAPI-Fallback
        from voice.tts_service import create_tts, RESPONSES
        self._tts = self._init_tts(config, log)
        self._responses = RESPONSES

        # Mutex: verhindert gleichzeitige Aktivierungen
        self._processing = threading.Lock()

        # WakeWordDetector (neue Schnittstelle: nur on_activation)
        from voice.wake_word import WakeWordDetector
        self._detector = WakeWordDetector(
            config=config,
            log=log,
            on_activation=self._on_wake_word,
        )

        # STT-Modell im Hintergrund vorwärmen — verhindert 30-60s Freeze beim ersten Befehl
        threading.Thread(target=self._warmup_stt, daemon=True, name="stt-warmup").start()

    # ── Initialisierung ───────────────────────────────────────────────────────

    @staticmethod
    def _init_tts(config: dict[str, Any], log: LogFn) -> Any:
        """TTS-Instanz mit automatischem SAPI-Fallback falls edge-tts nicht verfügbar."""
        from voice.tts_service import create_tts
        try:
            svc = create_tts(config)
            return svc
        except Exception as primary_exc:
            log("WARN", f"TTS primär fehlgeschlagen ({primary_exc}), versuche SAPI-Fallback.")
            try:
                voice_cfg = config.get("voice", {}) if isinstance(config, dict) else {}
                if str(voice_cfg.get("ttsProvider", "")).lower() != "sapi":
                    fallback = {**config, "voice": {**voice_cfg, "ttsProvider": "sapi"}}
                    svc = create_tts(fallback)
                    log("INFO", "TTS: SAPI-Fallback aktiv.")
                    return svc
            except Exception as fallback_exc:
                log("ERROR", f"TTS SAPI-Fallback fehlgeschlagen: {fallback_exc}")
            raise primary_exc

    def _warmup_stt(self) -> None:
        """
        Lädt das faster-whisper-Modell im Hintergrund beim Start.
        Verhindert den 30–60 Sekunden Freeze beim ersten Sprachbefehl.
        Beim allerersten Start: Modell wird heruntergeladen (~1,5 GB).
        """
        voice_cfg = self._config.get("voice", {}) if isinstance(self._config, dict) else {}
        provider = str(voice_cfg.get("sttProvider", "faster-whisper")).lower()
        if provider == "openai":
            return  # Kein lokales Modell nötig
        model_size = str(voice_cfg.get("sttModel", "medium"))
        try:
            self._log(
                "INFO",
                f"STT-Modell wird geladen: {model_size} "
                "(beim ersten Start Download ~1.5 GB — bitte warten)…",
            )
            from voice.stt_service import _get_cached_model
            _get_cached_model(model_size)
            self._log("OK", f"STT-Modell bereit: {model_size}.")
        except Exception as exc:
            self._log("WARN", f"STT-Warmup fehlgeschlagen: {exc}", errorCode="stt_warmup_failed")

    # ── TTS-Helfer ────────────────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        """Spricht Text via persistenter TTS-Instanz. Fehler werden nur geloggt."""
        try:
            self._tts.speak(text)
            self._tts.wait_done()
        except Exception as exc:
            self._log("WARN", f"TTS-Fehler: {exc}", errorCode="tts_speak_failed")

    def _speak_response(self, key: str, **kwargs: Any) -> None:
        """Spricht eine vordefinierte Antwort aus RESPONSES mit optionalen Platzhaltern."""
        template = self._responses.get(key, "")
        try:
            text = template.format(**kwargs) if kwargs else template
        except KeyError:
            text = template
        if text:
            self._speak(text)

    # ── Wake-Word-Callback ────────────────────────────────────────────────────

    def _on_wake_word(self) -> None:
        """
        Wird vom WakeWordDetector-Thread bei Erkennung aufgerufen.
        Führt die vollständige Pipeline aus: TTS → STT → Intent → TTS.
        """
        # Keine gleichzeitigen Aktivierungen zulassen
        if not self._processing.acquire(blocking=False):
            self._log("INFO", "Wake-Word ignoriert (Pipeline bereits aktiv).")
            return

        try:
            # 1. Bestätigung: "Ja?"
            self._speak_response("wake_ack")

            # 2. Audio aufnehmen (sounddevice, mit 5s False-Positive-Schutz)
            from voice.stt_service import record_after_wake_word
            audio = record_after_wake_word(
                max_seconds=self._max_record,
                silence_threshold=self._silence_threshold,
                silence_duration=self._silence_duration,
            )

            # False Positive: kein Audio → stille Deaktivierung nach 5 s
            if audio is None or len(audio) == 0:
                self._log("INFO", "Wake-Word: kein Audio erkannt (stille Deaktivierung).")
                return

            # 3. Transkription
            from voice.stt_service import transcribe
            text = transcribe(audio, self._config)

            if not text:
                self._speak_response("not_understood")
                return

            self._log("STT", f"Erkannt: '{text}'")

            # 4. Intent ausführen via CommandHandler
            response: str | None = None
            try:
                response = self._command_handler(
                    self._config, self._log, text
                )
            except Exception as exc:
                self._log(
                    "ERROR",
                    f"Command-Handler Fehler: {exc}",
                    errorCode="voice_command_failed",
                )
                self._speak_response("error_generic")
                return

            # 5. Antwort sprechen (None = unbekannter Intent → AI-Brain hat es)
            if response:
                self._speak(str(response))
            else:
                self._log("INFO", "Intent unbekannt — kein TTS vom VoiceController.")

        except Exception as exc:
            self._log(
                "ERROR",
                f"Voice-Pipeline Fehler: {exc}",
                errorCode="voice_pipeline_failed",
            )
            try:
                self._speak_response("error_generic")
            except Exception:
                pass
        finally:
            self._processing.release()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._log("INFO", "VoiceController startet.")
        self._detector.start()

    def stop(self) -> None:
        self._log("INFO", "VoiceController wird beendet.")
        self._detector.stop()
        try:
            self._tts.stop()
        except Exception:
            pass

    def get_status(self) -> VoiceStatus:
        return get_voice_status(self._config)

    @property
    def tts(self) -> Any:
        """Gibt TTS-Instanz zurück — für Reminder-Engine und Morning-Routine."""
        return self._tts


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
