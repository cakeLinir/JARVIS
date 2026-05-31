"""
JARVIS Voice-Pipeline Diagnose — schneller Pre-Flight-Check.
Ausführen: python check_voice.py

Testet alle Abhängigkeiten der Voice-Pipeline und gibt klare Fehlermeldungen aus.
Kein Backend nötig, kein API-Aufruf.
"""

from __future__ import annotations

import sys
import os

# UTF-8 für Windows-Terminal erzwingen (verhindert cp1252-UnicodeEncodeError)
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# src/ zum Suchpfad hinzufügen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

PASS  = "[OK]  "
FAIL  = "[FAIL]"
WARN  = "[WARN]"
INFO  = "[INFO]"

results: list[tuple[str, str]] = []

def check(label: str, fn):
    try:
        msg = fn()
        results.append((PASS, f"{label}: {msg or 'OK'}"))
        return True
    except Exception as exc:
        results.append((FAIL, f"{label}: {exc}"))
        return False

print("\n── JARVIS Voice-Pipeline Diagnose ─────────────────────────────\n")

# 1. Python-Version
check("Python", lambda: f"{sys.version.split()[0]} (mind. 3.11 empfohlen)")

# 2. numpy
check("numpy", lambda: __import__("numpy").__version__)

# 3. sounddevice + Audio-Gerät
def check_sounddevice():
    import sounddevice as sd
    devices = sd.query_devices()
    default_in = sd.query_devices(kind="input")
    return f"{sd.__version__} — Mikrofon: {default_in['name']}"
check("sounddevice", check_sounddevice)

# 4. pyaudio
check("pyaudio", lambda: __import__("pyaudio").__version__)

# 5. openWakeWord
def check_openwakeword():
    import openwakeword
    import openwakeword.model
    version = getattr(openwakeword, "__version__", "installiert (Version nicht lesbar)")
    return version
oww_ok = check("openWakeWord", check_openwakeword)

# 6. openWakeWord Modell hey_jarvis
if oww_ok:
    def check_oww_model():
        from openwakeword.model import Model
        m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        return f"Modell geladen: {list(m.models.keys())}"
    check("hey_jarvis Modell", check_oww_model)

# 7. onnxruntime
check("onnxruntime", lambda: __import__("onnxruntime").__version__)

# 8. faster-whisper
def check_whisper():
    from faster_whisper import WhisperModel
    return "faster-whisper verfügbar (Modell noch nicht geladen)"
fw_ok = check("faster-whisper", check_whisper)

# 9. faster-whisper Modell-Cache-Status
if fw_ok:
    def check_whisper_model():
        import os
        from pathlib import Path
        # Typischer Cache-Pfad für faster-whisper
        cache_paths = [
            Path.home() / ".cache" / "huggingface" / "hub",
            Path(os.getenv("HF_HOME", "")) / "hub" if os.getenv("HF_HOME") else None,
        ]
        for p in cache_paths:
            if p and p.exists():
                models = [d.name for d in p.iterdir() if "whisper" in d.name.lower()]
                if models:
                    return f"Cache gefunden: {', '.join(models)}"
        return "Kein Cache — beim ersten Befehl wird ~1.5 GB heruntergeladen"
    check("Whisper-Modell-Cache", check_whisper_model)

# 10. edge-tts
def check_edge_tts():
    import edge_tts
    return f"edge-tts verfügbar (benötigt Internet)"
edge_ok = check("edge-tts", check_edge_tts)

# 11. SAPI (Windows TTS-Fallback)
def check_sapi():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    sp = win32com.client.Dispatch("SAPI.SpVoice")
    voices = [sp.GetVoices().Item(i).GetDescription() for i in range(sp.GetVoices().Count)]
    pythoncom.CoUninitialize()
    de_voices = [v for v in voices if "de" in v.lower() or "german" in v.lower() or "deutsch" in v.lower()]
    return f"SAPI OK | DE-Stimmen: {de_voices or 'keine gefunden (englische Stimme als Fallback)'}"
check("Windows SAPI", check_sapi)

# 12. Anthropic SDK (für Intent-Router)
check("anthropic SDK", lambda: __import__("anthropic").__version__)

# 13. Config prüfen
def check_config():
    from core.config_loader import load_config
    import sys as _sys
    # load_config ruft sys.exit auf wenn Config fehlt — das wollen wir nicht
    from pathlib import Path
    cfg_path = Path(__file__).parent / "config.json"
    lcfg_path = Path(__file__).parent / "config.local.json"
    if not cfg_path.exists():
        raise FileNotFoundError("config.json fehlt!")
    voice_enabled = False
    import json
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    if lcfg_path.exists():
        local = json.loads(lcfg_path.read_text(encoding="utf-8-sig"))
        # Deep merge voice section
        if "voice" in local:
            cfg["voice"] = {**cfg.get("voice", {}), **local["voice"]}
    voice_enabled = cfg.get("voice", {}).get("enabled", False)
    api_key = cfg.get("anthropicApiKey", "")
    key_ok = bool(api_key) and "CHANGE_ME" not in api_key.upper() and len(api_key) > 16
    return (
        f"voice.enabled={voice_enabled} | "
        f"anthropicApiKey={'OK' if key_ok else 'FEHLT oder Placeholder'}"
    )
check("Config", check_config)

# ── Ergebnis ─────────────────────────────────────────────────────────────────

print()
for icon, msg in results:
    print(f"  {icon}  {msg}")

passed  = sum(1 for icon, _ in results if icon == PASS)
failed  = sum(1 for icon, _ in results if icon == FAIL)
total   = len(results)

print(f"\n── Ergebnis: {passed}/{total} Checks bestanden", "──────────────────\n")

if failed == 0:
    print("  🎉 Alle Checks bestanden — Voice-Pipeline sollte funktionieren.\n")
else:
    print(f"  ⚠️  {failed} Probleme gefunden — bitte oben beheben, dann neu prüfen.\n")
    print("  Häufige Fixes:")
    print("    pip install openwakeword onnxruntime sounddevice pyaudio faster-whisper edge-tts")
    print("    pip install anthropic pywin32\n")
