"""
Audio-Diagnose: Mikrofon und Lautsprecher prüfen via sounddevice.
Windows-only Fallback via Windows Multimedia API falls sounddevice fehlt.
"""

from __future__ import annotations

from typing import Any

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False


# ── Mikrofon-Check ────────────────────────────────────────────────────────────


def check_microphone() -> dict[str, Any]:
    """
    Prüft ob das Standard-Mikrofon verfügbar und nutzbar ist.
    Returns: {"status": "ok"|"error", "device": str, "message": str}
    """
    if not _SD_AVAILABLE:
        return _fallback_mic_check()

    try:
        default_in = sd.query_devices(kind="input")
        device_name = str(default_in.get("name", "Unknown"))
        max_ch = int(default_in.get("max_input_channels", 0))

        if max_ch == 0:
            return {
                "status": "error",
                "device": device_name,
                "message": "Eingabegerät hat keine Input-Kanäle.",
            }

        # Kurzen Stream öffnen und sofort schließen — bestätigt Geräte-Verfügbarkeit
        with sd.InputStream(
            samplerate=16_000,
            channels=min(max_ch, 1),
            blocksize=1024,
            dtype="int16",
        ):
            pass

        return {
            "status": "ok",
            "device": device_name,
            "message": f"Mikrofon verfügbar: {device_name}",
        }

    except sd.PortAudioError as exc:
        return {
            "status": "error",
            "device": "unknown",
            "message": f"PortAudio-Fehler: {exc}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "device": "unknown",
            "message": str(exc),
        }


def _fallback_mic_check() -> dict[str, Any]:
    """Fallback ohne sounddevice: prüft via Windows-Registry ob Mikrofone vorhanden sind."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture",
        )
        count = winreg.QueryInfoKey(key)[0]
        winreg.CloseKey(key)
        if count > 0:
            return {"status": "ok", "device": "system", "message": f"{count} Mikrofon(e) registriert."}
        return {"status": "error", "device": "none", "message": "Kein Mikrofon in der Registry gefunden."}
    except Exception as exc:
        return {"status": "error", "device": "unknown", "message": f"sounddevice fehlt, Registry-Fallback fehlgeschlagen: {exc}"}


# ── Lautsprecher-Check ────────────────────────────────────────────────────────


def check_speaker() -> dict[str, Any]:
    """
    Prüft ob das Standard-Ausgabegerät verfügbar ist.
    Returns: {"status": "ok"|"error", "device": str, "message": str}
    """
    if not _SD_AVAILABLE:
        return _fallback_speaker_check()

    try:
        default_out = sd.query_devices(kind="output")
        device_name = str(default_out.get("name", "Unknown"))
        max_ch = int(default_out.get("max_output_channels", 0))

        if max_ch == 0:
            return {
                "status": "error",
                "device": device_name,
                "message": "Ausgabegerät hat keine Output-Kanäle.",
            }

        return {
            "status": "ok",
            "device": device_name,
            "message": f"Lautsprecher verfügbar: {device_name}",
        }

    except sd.PortAudioError as exc:
        return {
            "status": "error",
            "device": "unknown",
            "message": f"PortAudio-Fehler: {exc}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "device": "unknown",
            "message": str(exc),
        }


def _fallback_speaker_check() -> dict[str, Any]:
    """Fallback ohne sounddevice."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render",
        )
        count = winreg.QueryInfoKey(key)[0]
        winreg.CloseKey(key)
        if count > 0:
            return {"status": "ok", "device": "system", "message": f"{count} Wiedergabegerät(e) registriert."}
        return {"status": "error", "device": "none", "message": "Kein Wiedergabegerät gefunden."}
    except Exception as exc:
        return {"status": "error", "device": "unknown", "message": f"sounddevice fehlt, Registry-Fallback fehlgeschlagen: {exc}"}


# ── Gerät-Auflistung ──────────────────────────────────────────────────────────


def list_audio_devices() -> dict[str, Any]:
    """
    Listet alle verfügbaren Audio-Ein- und Ausgabegeräte auf.
    Returns: {"inputs": [...], "outputs": [...]}
    """
    if not _SD_AVAILABLE:
        return {
            "inputs": [],
            "outputs": [],
            "error": "sounddevice nicht installiert — 'pip install sounddevice'",
        }

    try:
        all_devices = sd.query_devices()
        inputs: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []

        for idx, dev in enumerate(all_devices):
            name = str(dev.get("name", f"Device {idx}"))
            in_ch = int(dev.get("max_input_channels", 0))
            out_ch = int(dev.get("max_output_channels", 0))

            if in_ch > 0:
                inputs.append({"id": idx, "name": name, "channels": in_ch})

            if out_ch > 0:
                outputs.append({"id": idx, "name": name, "channels": out_ch})

        try:
            default_in = sd.query_devices(kind="input")
            default_out = sd.query_devices(kind="output")
        except Exception:
            default_in = default_out = None

        return {
            "inputs": inputs,
            "outputs": outputs,
            "defaultInput": str(default_in.get("name", "")) if default_in else None,
            "defaultOutput": str(default_out.get("name", "")) if default_out else None,
        }

    except Exception as exc:
        return {"inputs": [], "outputs": [], "error": str(exc)}


# ── Schnell-Diagnose für Backend-Antworten ────────────────────────────────────


def run_audio_check() -> dict[str, Any]:
    """Führt Mikrofon- und Lautsprecher-Check aus und gibt kombinierten Report zurück."""
    mic = check_microphone()
    spk = check_speaker()
    overall = "ok" if mic["status"] == "ok" and spk["status"] == "ok" else "error"
    return {
        "status": overall,
        "microphone": mic,
        "speaker": spk,
    }
