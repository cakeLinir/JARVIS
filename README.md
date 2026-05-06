# JARVIS

Persönlicher Windows-Desktop-Assistent mit Windows-VPS-Backend, Nextcord-Bot-Integration, Webdashboard und lokalem Windows-Agent.

## Zielarchitektur

```text
Windows-VPS
  ├─ Backend API
  ├─ Webdashboard
  ├─ OpenAI Realtime Client-Secret-Service
  ├─ Dev-News-Aggregation
  └─ Nextcord-Bot-Bridge

Lokaler Windows-PC
  ├─ Python Desktop-Agent
  ├─ lokale Agent-API auf 127.0.0.1
  ├─ Programmstart/Fenstersteuerung
  └─ später: Voice-Client mit Wake-Word + WebRTC Realtime Audio
```

## Backend starten

```powershell
cd backend
copy .env.example .env
# .env ausfüllen
npm install
npm run build
npm start
```

Healthcheck:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
```

Dashboard:

```text
http://localhost:8080/dashboard
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
..\scripts\install-local-agent-task.ps1 -JarvisRoot "C:\Pfad\zu\JARVIS"
```

## Bot-Bridge starten

```powershell
cd bot-bridge
copy .env.example .env
# .env ausfüllen
py -3 -m pip install -r requirements.txt
py -3 src/bridge.py
```

## Wichtige Endpunkte

| Bereich | Methode | Pfad |
|---|---:|---|
| Health | GET | `/api/health` |
| Dashboard | GET | `/dashboard` |
| Dashboard Overview | GET | `/api/dashboard/overview` |
| Realtime Secret | POST | `/api/realtime/client-secret` |
| OpenAI Chat | POST | `/api/openai/chat` |
| Dev-News | GET | `/api/news/dev` |
| Agent Status | POST/GET | `/api/agent/status` |
| Morning Log | POST/GET | `/api/agent/morning-log` |
| Commands | POST/GET | `/api/commands/*` |

## Sicherheit

- Echte `.env`-Dateien werden nicht committed.
- Tokens gehören nicht in Code.
- OpenAI-Key bleibt nur auf dem VPS.
- Lokale Windows-Aktionen laufen nur über den Desktop-Agent.
- Discord wird über Slash-Commands/Backend-Commands eingebunden, nicht als Selfbot.
- Wake-Word und Voice-Client bleiben lokal; Audio wird erst nach Aktivierung gestreamt.
