# JARVIS

Persönlicher Windows-Desktop-Assistent mit Windows-VPS-Backend, bestehender Discord-Bot-Integration, Webdashboard und lokalem Windows-Agent.

## Zielarchitektur

```text
Windows-VPS
  ├─ backend/
  │   ├─ Fastify API
  │   ├─ Dashboard-MVP
  │   ├─ OpenAI-Service
  │   ├─ Realtime Client-Secret-Service
  │   ├─ Dev-News-Aggregation
  │   ├─ Command-Routing
  │   └─ Agent-/Bot-/Dashboard-Auth
  │
  └─ Discord-Bot aus separatem Repo:
      cakeLinir/discord_bot_hundekuchenlive

Lokaler Windows-PC
  ├─ desktop-agent/
  │   ├─ Python Desktop-Agent
  │   ├─ lokale Agent-API auf 127.0.0.1
  │   ├─ Programmstart/Fenstersteuerung
  │   ├─ lokale Allowlist/Pfadvalidierung
  │   └─ später: Voice-Client mit Wake-Word + WebRTC Realtime Audio
  │
  └─ lokale Konfiguration:
      desktop-agent/config.local.json
```

## Port-Entscheidung

Das Backend verwendet standardmäßig Port `8181`.

Grund: Port `8080` ist auf dem VPS bereits durch andere Software belegt.

```text
JARVIS_BACKEND_HOST=0.0.0.0
JARVIS_BACKEND_PORT=8181
```

## Lokaler Entwicklungsablauf

Lokaler Repo-Root:

```powershell
cd C:\Users\hunde\Desktop\JARVIS
```

Änderungen werden lokal entwickelt und anschließend über GitHub Desktop ins Repository hochgeladen. Auf dem VPS werden später nur die relevanten Ordner aus dem Repository aktualisiert.

## Backend starten

```powershell
cd backend
copy .env.example .env
# .env mit echten Secrets füllen
npm install
npm run build
npm start
```

Healthcheck:

```powershell
Invoke-RestMethod http://localhost:8181/api/health
```

Dashboard:

```text
http://localhost:8181/dashboard
```

Im Dashboard wird der `JARVIS_DASHBOARD_TOKEN` aus `backend/.env` abgefragt.

## Lokalen Agent starten

```powershell
cd desktop-agent
copy config.local.example.json config.local.json
# config.local.json mit echten lokalen Pfaden und Tokens füllen
py -3 -m pip install -r requirements.txt
py -3 src/main.py
```

## Windows-Autostart installieren

```powershell
PowerShell als Benutzer öffnen:
.\scripts\install-local-agent-task.ps1 -JarvisRoot "C:\Users\hunde\Desktop\JARVIS"
```

## Discord-Bot-Integration

Der Discord-Bot wird nicht in diesem Repository als `bot-bridge/` gepflegt.

Verwendetes Repo:

```text
https://github.com/cakeLinir/discord_bot_hundekuchenlive.git
```

Der Bot kommuniziert über `JARVIS_BOT_BRIDGE_TOKEN` mit dem JARVIS-Backend und erzeugt Backend-Commands. Lokale Windows-Aktionen werden ausschließlich vom lokalen Desktop-Agent ausgeführt.

## Wichtige Endpunkte

| Bereich | Methode | Pfad | Auth |
|---|---:|---|---|
| Health | GET | `/api/health` | nein |
| Dashboard | GET | `/dashboard` | Token im UI |
| Dashboard Overview | GET | `/api/dashboard/overview` | Jarvis Token |
| Realtime Secret | POST | `/api/realtime/client-secret` | Agent |
| OpenAI Chat | POST | `/api/openai/chat` | Jarvis Token |
| Dev-News | GET | `/api/news/dev` | nein |
| Agent Status | POST/GET | `/api/agent/status` | Agent/Jarvis Token |
| Morning Log | POST/GET | `/api/agent/morning-log` | Agent/Jarvis Token |
| Commands | POST/GET | `/api/commands/*` | Bot/Agent/Jarvis Token |

## Sicherheit

- Echte `.env`-Dateien werden nicht committed.
- Tokens gehören nicht in Code.
- OpenAI-Key bleibt nur auf dem VPS.
- Lokale Windows-Aktionen laufen nur über den Desktop-Agent.
- Discord wird über Slash-Commands/Backend-Commands eingebunden, nicht als Selfbot.
- Backend erzeugt nur Commands; der Agent validiert lokal vor der Ausführung.
- Wake-Word und Voice-Client bleiben lokal; Audio wird erst nach Aktivierung gestreamt.
- Unbekannte Pfade, Programme oder Commands werden nicht geraten, sondern abgelehnt und geloggt.

## Nicht committen

```text
backend/.env
desktop-agent/config.local.json
.env
.env.local
```

## Aktueller MVP-Fokus

1. Backend auf Port `8181` stabil starten.
2. Agent-Status und Morning-Log sauber ans Backend senden.
3. Discord-Bot-Commands sicher ins Backend routen.
4. Lokale Programmausführung nur über konfigurierte Allowlist.
5. Dashboard als Kontroll- und Statusfläche stabilisieren.
