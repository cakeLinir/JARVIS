# JARVIS Realtime Voice Architektur

## Ziel

JARVIS soll nach lokalem Wake-Word nahezu in Echtzeit sprechen und hören. Der OpenAI-Key bleibt auf dem VPS. Der lokale Client erhält nur einen kurzlebigen Realtime-Client-Secret vom Backend.

## Datenfluss

```text
Wake-Word lokal
→ lokaler Voice-Client fragt Backend /api/realtime/client-secret an
→ Backend erstellt OpenAI Realtime Client Secret
→ Voice-Client verbindet sich per WebRTC mit OpenAI Realtime
→ Modell ruft Tools auf
→ Voice-Client sendet lokale Aktionen an http://127.0.0.1:8765/actions/*
→ Python-Agent startet Programme / ordnet Fenster / meldet Status
```

## Wichtige Regeln

- Kein permanenter Audio-Upload im Idle-Zustand.
- OpenAI-Key nie im lokalen Client speichern.
- Lokale Aktionen nur über erlaubte Tools und lokale API.
- Riskante Aktionen brauchen Bestätigung.
- Not-Aus: `Jarvis, stopp` oder lokale API `/actions/stop`.

## MVP-Endpunkte

Backend:

- `POST /api/realtime/client-secret`
- `POST /api/openai/chat`
- `GET /api/dashboard/overview`

Lokaler Agent:

- `GET /health`
- `POST /actions/morning`
- `POST /actions/stop`
