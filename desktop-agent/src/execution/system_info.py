"""
System-Informationen via psutil: Akku, laufende Prozesse, CPU/RAM/Disk.
"""

from __future__ import annotations

from typing import Any

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def _psutil_guard() -> None:
    if not _PSUTIL_AVAILABLE:
        raise RuntimeError("psutil nicht installiert — 'pip install psutil'")


def get_battery_status() -> dict[str, Any]:
    """
    Gibt Akku-Status zurück.
    Returns: {"percent": int, "plugged": bool, "time_left_minutes": int|None}
    """
    try:
        _psutil_guard()
        battery = psutil.sensors_battery()

        if battery is None:
            return {
                "percent": -1,
                "plugged": False,
                "time_left_minutes": None,
                "available": False,
                "message": "Kein Akku erkannt (Desktop oder Fehler).",
            }

        # secsleft = psutil.POWER_TIME_UNLIMITED oder psutil.POWER_TIME_UNKNOWN bei Laden
        secs = getattr(battery, "secsleft", 0) or 0
        time_left: int | None = (
            int(secs // 60)
            if secs > 0 and not battery.power_plugged
            else None
        )

        return {
            "percent": int(battery.percent),
            "plugged": bool(battery.power_plugged),
            "time_left_minutes": time_left,
            "available": True,
        }

    except Exception as exc:
        return {
            "percent": -1,
            "plugged": False,
            "time_left_minutes": None,
            "available": False,
            "error": str(exc),
        }


def is_app_running(name: str) -> bool:
    """
    Prüft ob ein Prozess mit diesem Namen läuft (case-insensitive, .exe optional).
    """
    if not _PSUTIL_AVAILABLE:
        return False

    # .exe-Suffix für Vergleich normalisieren
    needle = name.lower().removesuffix(".exe")

    for proc in psutil.process_iter(["name"]):
        try:
            proc_name = (proc.info.get("name") or "").lower().removesuffix(".exe")
            if needle == proc_name or needle in proc_name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return False


def get_running_apps() -> list[str]:
    """Gibt sortierte Liste eindeutiger laufender Prozess-Namen zurück."""
    if not _PSUTIL_AVAILABLE:
        return []

    names: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name") or ""
            if name:
                names.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(names, key=str.lower)


def get_system_stats() -> dict[str, Any]:
    """
    Gibt CPU%, RAM% und Festplatten-Auslastung zurück.
    Returns: {"cpu_percent": float, "ram_percent": float, "ram_used_gb": float, ...}
    """
    try:
        _psutil_guard()

        # CPU (kurzes interval für einen repräsentativen Wert)
        cpu_pct = psutil.cpu_percent(interval=0.5)

        # RAM
        ram = psutil.virtual_memory()

        # Festplatten
        disks: dict[str, Any] = {}
        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks[part.mountpoint] = {
                    "total_gb": round(usage.total / 1_073_741_824, 1),
                    "used_gb": round(usage.used / 1_073_741_824, 1),
                    "free_gb": round(usage.free / 1_073_741_824, 1),
                    "percent": usage.percent,
                }
            except (PermissionError, OSError):
                continue

        return {
            "cpu_percent": cpu_pct,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / 1_073_741_824, 1),
            "ram_total_gb": round(ram.total / 1_073_741_824, 1),
            "disks": disks,
        }

    except Exception as exc:
        return {"error": str(exc)}


def get_full_status() -> dict[str, Any]:
    """Hilfsfunktion: Kombiniert alle Status-Infos für Backend-Antworten."""
    return {
        "battery": get_battery_status(),
        "system": get_system_stats(),
    }
