"""
Windows-Systemsteuerung: Lautstärke (pycaw) und Helligkeit (WMI via PowerShell).
Alle Imports in try/except — graceful fail wenn Abhängigkeiten fehlen.
"""

from __future__ import annotations

import subprocess
from typing import Any

CREATE_NO_WINDOW = 0x08000000

# ── pycaw: Windows-Lautstärke über COM ───────────────────────────────────────

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _PYCAW_AVAILABLE = True
except ImportError:
    _PYCAW_AVAILABLE = False


def _audio_interface():
    """Gibt pycaw-Volume-Interface zurück oder wirft RuntimeError."""
    if not _PYCAW_AVAILABLE:
        raise RuntimeError("pycaw nicht installiert — 'pip install pycaw comtypes'")
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> int:
    """Gibt aktuelle Systemlautstärke 0–100 zurück. Bei Fehler: -1."""
    try:
        vol = _audio_interface()
        return int(round(vol.GetMasterVolumeLevelScalar() * 100))
    except Exception:
        return -1


def set_volume(level: int) -> bool:
    """Setzt Systemlautstärke auf 0–100. Gibt True bei Erfolg zurück."""
    try:
        clamped = max(0, min(100, int(level)))
        vol = _audio_interface()
        vol.SetMasterVolumeLevelScalar(clamped / 100.0, None)
        return True
    except Exception:
        return False


def mute() -> bool:
    """Stummschalten. Gibt True bei Erfolg zurück."""
    try:
        _audio_interface().SetMute(1, None)
        return True
    except Exception:
        # Fallback via ctypes (kein pycaw nötig)
        try:
            import ctypes
            ctypes.windll.winmm.waveOutSetVolume(0, 0)
            return True
        except Exception:
            return False


def unmute() -> bool:
    """Stummschaltung aufheben (setzt auf 50%). Gibt True bei Erfolg zurück."""
    try:
        vol = _audio_interface()
        vol.SetMute(0, None)
        return True
    except Exception:
        try:
            import ctypes
            level = int(65535 * 0.5)
            ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
            return True
        except Exception:
            return False


# ── Helligkeit via WMI/PowerShell ────────────────────────────────────────────


def _ps_run(command: str, timeout: int = 5) -> str:
    """Führt PowerShell-Befehl aus und gibt stdout zurück."""
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-NoProfile", "-command", command],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
    return result.stdout.strip()


def get_brightness() -> int:
    """
    Liest aktuelle Bildschirmhelligkeit 0–100 via WMI.
    Funktioniert nur auf Laptops/Displays mit WMI-Unterstützung.
    Gibt -1 zurück wenn nicht unterstützt.
    """
    try:
        value = _ps_run(
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness "
            "-ErrorAction Stop).CurrentBrightness"
        )
        return int(value) if value.isdigit() else -1
    except Exception:
        return -1


def set_brightness(level: int) -> bool:
    """
    Setzt Bildschirmhelligkeit 0–100 via WMI.
    Gibt True bei Erfolg zurück.
    """
    clamped = max(0, min(100, int(level)))
    try:
        _ps_run(
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods "
            f"-ErrorAction Stop).WmiSetBrightness(1, {clamped})"
        )
        return True
    except Exception:
        return False


# ── Zusammenfassung für Backend-Antworten ────────────────────────────────────


def get_audio_status() -> dict[str, Any]:
    """Gibt Lautstärke und Mute-Status als strukturiertes Dict zurück."""
    try:
        vol = _audio_interface()
        level = int(round(vol.GetMasterVolumeLevelScalar() * 100))
        muted = bool(vol.GetMute())
        return {"volume": level, "muted": muted, "source": "pycaw"}
    except Exception as exc:
        return {"volume": -1, "muted": False, "source": "unavailable", "error": str(exc)}
