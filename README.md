# JARVIS — Persönlicher KI-Desktop-Assistent

[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](backend/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](desktop-agent/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](dashboard/)
[![Fastify](https://img.shields.io/badge/Fastify-5-000000?logo=fastify&logoColor=white)](backend/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](backend/src/services/db.ts)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> **JARVIS** ist ein verteiltes, persönliches Assistenzsystem für den Windows-Desktop.  
> VPS-Backend · lokaler Python-Agent · React-Dashboard · Voice-Pipeline · Discord-Integration

---

## Inhalt

- [Features](#features)
- [Systemarchitektur](#systemarchitektur)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Konfiguration](#konfiguration)
- [API-Endpunkte](#api-endpunkte)
- [Projektstruktur](#projektstruktur)
- [Sicherheit](#sicherheit)
- [Tests](#tests)
- [Lizenz](#lizenz)

---

## Features

### 🗣️ Voice-Pipeline
- Wake-Word-Erkennung via **openWakeWord** (`hey_jarvis`, ONNX-Modell, offline)
- **Faster-Whisper** STT (lokal, Deutsch, ~1.5 GB Modell) oder OpenAI Whisper API
- **Intent-Router** mit Claude AI (Function Calling) — erkennt Absichten aus natürlichem Deutsch
- **Edge-TTS** / Windows SAPI für Sprachausgabe
- Vollständige Pipeline: `Wake-Word → STT → Intent → Aktion → TTS`

### 📋 TODO-Verwaltung
- SQLite-Backend mit vollständigem CRUD
- Priorisierung (1–5), Fälligkeitsdaten, Erinnerungen, Kategorien
- **Wiederholungen** (täglich/wöchentlich/monatlich) mit automatischer Folgeinstanz nach Abschluss
- Offline-Fallback: `pending_queue.json` bei Backend-Ausfall, automatischer Sync beim Reconnect
- Voice-Befehle: „Erinnere mich morgen an Rechnung bezahlen"

### 🔄 Schichtplanung
- Schichttypen: **Tagschicht** (07–19), **Nachtschicht** (19–07+1), **FAKT IST! Früh** (07–14:30), **FAKT IST! Spät** (14:30–21:30), **Frei**
- Conflict-Check: 409 bei doppeltem Datum
- Nachtschicht: automatische `end_date = start_date + 1` Berechnung
- Kalender-Ansicht im Dashboard (Wochensicht)

### 📡 Streaming-Empfehlung
- Ampel-System: `free` 🟢 / `conditional` 🟡 / `discouraged` 🟠 / `blocked` 🔴
- Zeitabhängig (currentHour) und schichtabhängig
- Beispielregel: Nachtschicht heute → vor 12 Uhr `conditional`, ab 17 Uhr `blocked`
- REST-Endpunkt: `GET /api/availability/:date?current_hour=14`

### 🌅 Morning Routine
- Automatischer App-Start (OBS, Discord, Spotify, WhatsApp, VS Code)
- TODOs vorlesen via TTS
- TODO-Review: KI-gestützte Priorisierung und Neuformatierung
- Fensteranordnung via pywin32
- Backend-Report mit Zusammenfassung

### 🤖 Intent-Router (Claude AI)
- 11 vordefinierte Intents: `todo.create`, `shift.set`, `stream.query`, `app.open`, ...
- Konfidenz-Schwellenwert: < 0.75 → Rückfrage statt blinder Ausführung
- Offline-sicher: bei unbekanntem Intent Fallback auf AI-Brain

### 📊 Web-Dashboard
- Echtzeit-Status: Agent-Heartbeat, TODO-Statistiken, Schicht heute/morgen
- Availability-Widget: Streaming-Ampel für heute und morgen
- TODO-Verwaltung mit Filter, Inline-Aktionen, Erstellungs-Modal
- Schichtkalender (Wochensicht) mit Edit-Modal
- Auth: HMAC-SHA256 signierte Session-Cookies, Discord OAuth

### 🔧 Automation
- System-Steuerung: Lautstärke (pycaw), Helligkeit (WMI)
- Prozess-Info: Akku, CPU/RAM, laufende Apps (psutil)
- Audio-Diagnose: Mikrofon/Lautsprecher-Check (sounddevice)
- Media-Control: YouTube/Spotify-Suche im Browser (Allowlist-gesichert)

---

## Systemarchitektur

```
┌────────────────────────────────────────────────────────────┐
│                      Windows VPS                           │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Fastify Backend (:8181)                  │   │
│  │                                                     │   │
│  │  Auth  ·  TODOs  ·  Schichten  ·  Availability     │   │
│  │  Dashboard  ·  Commands  ·  Agent-State             │   │
│  │  Claude API  ·  News  ·  Streaming Advice           │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │ HTTPS (Caddy Reverse Proxy)      │
│  ┌───────────────────────▼─────────────────────────────┐   │
│  │         React Dashboard (Static via Caddy)          │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬─────────────────────────────────┘
                           │ Bearer Token (HTTPS)
┌──────────────────────────▼─────────────────────────────────┐
│                   Lokaler Windows-PC                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Python Desktop-Agent                    │  │
│  │                                                      │  │
│  │  Voice-Pipeline  ·  Intent-Router  ·  Heartbeat     │  │
│  │  Morning Routine  ·  App-Launcher  ·  System-Ctrl   │  │
│  │  TODO-Sync  ·  Shift-Cache  ·  Local API (:8765)   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │ Bot-Bridge Token
┌──────────────────────────▼─────────────────────────────────┐
│          Discord-Bot (externes Repo)                        │
│          github.com/cakeLinir/discord_bot_hundekuchenlive   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Schicht | Technologie | Zweck |
|---|---|---|
| **Backend** | Fastify 5, TypeScript, Node.js | REST-API, Auth, Commands |
| **Datenbank** | SQLite (better-sqlite3) | TODOs, Schichten, Migrationen |
| **Validierung** | Zod | Schema-Validierung aller Requests |
| **Frontend** | React 19, Vite, TypeScript | Dashboard-UI |
| **Agent** | Python 3.11+ | Lokale Ausführung, Voice-Pipeline |
| **Wake-Word** | openWakeWord (ONNX) | hey_jarvis, offline |
| **STT** | faster-whisper | Lokale Spracherkennung, Deutsch |
| **TTS** | edge-tts / Windows SAPI | Sprachausgabe |
| **AI** | Anthropic Claude (Tool Use) | Intent-Router, AI-Brain |
| **Audio** | sounddevice, pyaudio | Mikrofon-Stream |
| **System** | psutil, pycaw, pywin32 | Automation, Windows-APIs |
| **Reverse Proxy** | Caddy | HTTPS, Static Serving |
| **Auth** | HMAC-SHA256, Discord OAuth | Signed Cookies, Token-Auth |

---

JARVIS_BACKEND_HOST=0.0.0.0
JARVIS_BACKEND_PORT=8181
```

## Quick Start

### Voraussetzungen

- **VPS**: Linux, Node.js 22+, Caddy
- **Lokal**: Windows 10/11, Python 3.11+, Microsoft C++ Build Tools
- **Accounts**: Anthropic API-Key (für Intent-Router)

### 1. Backend (VPS)

## Backend starten

````bash
```powershell
cd backend
cp .env.example .env
# .env mit echten Werten füllen (siehe Konfiguration)
npm install
npm run build
npm start
````

**Health-Check:**

````bash
curl http://localhost:8181/api/health
Healthcheck:

```powershell
Invoke-RestMethod http://localhost:8181/api/health
````

### 2. Dashboard (VPS — Build)

Dashboard:

````bash
cd dashboard
npm install
npm run build
# dist/ wird von Caddy als Static Files ausgeliefert
```text
http://localhost:8181/dashboard
````

### 3. Desktop-Agent (Windows)

```powershell
cd desktop-agent
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Konfiguration
copy config.local.example.json config.local.json
# config.local.json mit backendUrl, agentToken etc. füllen

py -3 src/main.py
```

**Voice-Modus aktivieren** (`config.local.json`):

```json
{
  "voice": {
    "enabled": true,
    "wakeWordEnabled": true,
    "sttProvider": "faster-whisper",
    "ttsProvider": "edge"
  }
}
```

### 4. Autostart (Windows Task Scheduler)

```powershell
.\scripts\install-local-agent-task.ps1 -JarvisRoot "C:\Path\To\JARVIS"
```

---

## Konfiguration

### Backend (`backend/.env`)

| Variable                             | Beschreibung                              | Pflicht |
| ------------------------------------ | ----------------------------------------- | ------- |
| `ANTHROPIC_API_KEY`                  | Claude API-Key                            | ✅      |
| `JARVIS_AGENT_TOKEN`                 | Token für Desktop-Agent                   | ✅      |
| `JARVIS_BOT_BRIDGE_TOKEN`            | Token für Discord-Bot                     | ✅      |
| `JARVIS_DASHBOARD_TOKEN`             | Token für Dashboard-Direktzugriff         | ✅      |
| `JARVIS_BACKEND_PORT`                | Server-Port (default: `8181`)             | —       |
| `JARVIS_ALLOWED_DISCORD_USER_IDS`    | Erlaubte Discord-User-IDs (kommagetrennt) | —       |
| `JARVIS_DISCORD_OAUTH_CLIENT_ID`     | Discord OAuth Client-ID                   | —       |
| `JARVIS_DISCORD_OAUTH_CLIENT_SECRET` | Discord OAuth Secret                      | —       |
| `OPENAI_API_KEY`                     | OpenAI API-Key (optional)                 | —       |

Alle Werte: [backend/.env.example](backend/.env.example)

### Desktop-Agent (`desktop-agent/config.local.json`)

| Feld                | Beschreibung                               |
| ------------------- | ------------------------------------------ |
| `backendUrl`        | URL des VPS-Backends                       |
| `agentToken`        | Gleicher Wert wie `JARVIS_AGENT_TOKEN`     |
| `anthropicApiKey`   | Claude API-Key (lokal für Intent-Router)   |
| `voice.enabled`     | Voice-Pipeline aktivieren                  |
| `voice.sttProvider` | `"faster-whisper"` (lokal) oder `"openai"` |
| `apps.*`            | App-Pfade für Morning Routine              |
| `todo.markdownPath` | Pfad zur TODO-Markdown-Datei               |

Template: [desktop-agent/config.local.example.json](desktop-agent/config.local.example.json)

---

## API-Endpunkte

### Öffentlich

Der Discord-Bot wird nicht in diesem Repository als `bot-bridge/` gepflegt.

| Methode | Pfad            | Beschreibung             |
| ------- | --------------- | ------------------------ |
| `GET`   | `/api/health`   | System-Gesundheitsstatus |
| `GET`   | `/api/news/dev` | Dev-News-Aggregation     |

Verwendetes Repo:

### Agent (Bearer Token)

| Methode | Pfad                         | Beschreibung             |
| ------- | ---------------------------- | ------------------------ |
| `POST`  | `/api/agent/status`          | Heartbeat senden         |
| `GET`   | `/api/agent/status`          | Letzten Status abrufen   |
| `POST`  | `/api/agent/morning-log`     | Morning-Routine-Report   |
| `GET`   | `/api/commands/next`         | Nächsten Command abrufen |
| `POST`  | `/api/commands/:id/complete` | Command abschließen      |

### TODOs (Alle Jarvis-Token)

| Methode  | Pfad                      | Beschreibung                           |
| -------- | ------------------------- | -------------------------------------- |
| `GET`    | `/api/todos`              | Liste (Filter: status, category, date) |
| `POST`   | `/api/todos`              | TODO erstellen (→ 201)                 |
| `GET`    | `/api/todos/today`        | Heute fällige TODOs                    |
| `GET`    | `/api/todos/:id`          | TODO abrufen                           |
| `PATCH`  | `/api/todos/:id`          | TODO aktualisieren                     |
| `DELETE` | `/api/todos/:id`          | TODO soft-löschen (cancelled)          |
| `POST`   | `/api/todos/:id/complete` | Als erledigt markieren + Recurrence    |

### Schichten

| Methode  | Pfad                      | Beschreibung                             |
| -------- | ------------------------- | ---------------------------------------- |
| `GET`    | `/api/shifts`             | Liste (?from=&to=)                       |
| `POST`   | `/api/shifts`             | Schicht anlegen (→ 409 bei Konflikt)     |
| `GET`    | `/api/shifts/today`       | Heutige Schicht                          |
| `GET`    | `/api/shifts/tomorrow`    | Morgige Schicht                          |
| `GET`    | `/api/shifts/:date`       | Schicht für Datum (YYYY-MM-DD)           |
| `PATCH`  | `/api/shifts/:id`         | Schicht aktualisieren                    |
| `DELETE` | `/api/shifts/:id`         | Schicht löschen                          |
| `GET`    | `/api/availability/:date` | Streaming-Verfügbarkeit (?current_hour=) |
| `GET`    | `/api/shift-types`        | Alle Schichttypen mit Regelwerk          |

### Streaming Advice (Legacy)

| Methode | Pfad                             | Beschreibung                |
| ------- | -------------------------------- | --------------------------- |
| `GET`   | `/api/streaming/advice/today`    | Streaming-Empfehlung heute  |
| `GET`   | `/api/streaming/advice/tomorrow` | Streaming-Empfehlung morgen |
| `GET`   | `/api/streaming/advice?date=`    | Streaming-Empfehlung Datum  |

### Dashboard

| Methode | Pfad                                      | Beschreibung               |
| ------- | ----------------------------------------- | -------------------------- |
| `GET`   | `/api/dashboard/overview`                 | Vollständiger Systemstatus |
| `POST`  | `/api/dashboard/commands/morning-routine` | Morning Routine auslösen   |
| `GET`   | `/dashboard`                              | Web-Dashboard (HTML)       |

---

## Projektstruktur

````
JARVIS/
├── backend/                    # Fastify TypeScript Backend
│   ├── src/
│   │   ├── config/config.ts    # Zentrales Config-System
│   │   ├── routes/             # REST-Endpunkte
│   │   ├── services/           # Business-Logik + SQLite
│   │   │   ├── db.ts           # Versionierte Migrationen
│   │   │   ├── todo.service.ts # TODO-CRUD
│   │   │   ├── shift.service.ts
│   │   │   └── availability.service.ts
│   │   ├── security/auth.ts    # HMAC + Discord OAuth
│   │   └── types/              # Shared TypeScript-Typen
│   ├── .env.example
│   └── package.json
│
├── dashboard/                  # React 19 + Vite Frontend
│   └── src/
│       ├── pages/              # TodoPage, ShiftsPage, StreamingPage
│       ├── components/         # AvailabilityWidget, Panel, DataTable, ...
│       ├── api/                # Fetch-Wrapper für alle Endpunkte
│       └── types/              # Todo, Shift, Availability-Typen
│
├── desktop-agent/              # Python Windows-Agent
│   ├── src/
│   │   ├── core/               # Config, Logging
│   │   ├── execution/          # App-Launcher, System-Control, Media
│   │   ├── handlers/           # Backend-Commands, Text-Input
│   │   ├── integrations/       # AI-Brain, Intent-Router, Backend-Client
│   │   ├── routines/           # Morning Routine
│   │   ├── shifts/             # Schicht-Client, Parser
│   │   ├── todo/               # TODO-Provider, Sync, Review
│   │   ├── voice/              # Wake-Word, STT, TTS, Controller
│   │   └── main.py             # Orchestrator
│   ├── tests/                  # pytest Unit-Tests
│   ├── config.local.example.json
│   └── requirements.txt
│
├── deploy/caddy/Caddyfile      # Reverse-Proxy-Konfiguration
├── scripts/                    # Setup- und Deploy-Skripte
└── docs/                       # ROADMAP, Offline-Fallback, Discord-Bot
```text
https://github.com/cakeLinir/discord_bot_hundekuchenlive.git
````

---

## Sicherheit

| Thema              | Implementierung                                  |
| ------------------ | ------------------------------------------------ |
| **Tokens**         | Mindestens 16 Zeichen, Placeholder-Erkennung     |
| **Dashboard-Auth** | HMAC-SHA256 signierte Session-Cookies            |
| **Discord OAuth**  | State-Parameter, Cookie-Prüfung                  |
| **Agent-Token**    | Timing-safe Vergleich (`timingSafeEqual`)        |
| **App-Start**      | Allowlist für URI-Schemas und Executable-Pfade   |
| **URL-Öffnen**     | Domain-Allowlist (youtube.com, open.spotify.com) |
| **Secrets**        | Nie in Code oder `.gitignore`d-Dateien           |
| **Logging**        | Token-Maskierung in Log-Ausgaben                 |
| **Voice**          | Audio bleibt lokal, kein Stream ans Backend      |

> **Hinweis:** Echte Tokens und API-Keys gehören in `backend/.env` (VPS) bzw. `desktop-agent/config.local.json` (lokal) — beide sind gitignored.

## Wichtige Endpunkte

---

| Bereich            |  Methode | Pfad                          | Auth                   |
| ------------------ | -------: | ----------------------------- | ---------------------- |
| Health             |      GET | `/api/health`                 | nein                   |
| Dashboard          |      GET | `/dashboard`                  | Token im UI            |
| Dashboard Overview |      GET | `/api/dashboard/overview`     | Jarvis Token           |
| Realtime Secret    |     POST | `/api/realtime/client-secret` | Agent                  |
| OpenAI Chat        |     POST | `/api/openai/chat`            | Jarvis Token           |
| Dev-News           |      GET | `/api/news/dev`               | nein                   |
| Agent Status       | POST/GET | `/api/agent/status`           | Agent/Jarvis Token     |
| Morning Log        | POST/GET | `/api/agent/morning-log`      | Agent/Jarvis Token     |
| Commands           | POST/GET | `/api/commands/*`             | Bot/Agent/Jarvis Token |

## Tests

### Backend

```bash
cd backend
npm test
```

### Desktop-Agent

````bash
cd desktop-agent
pip install -r requirements-dev.txt
pytest tests/ -v
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
````

Tests für Date-Parser (alle deutschen Datumsformate), Shift-Phrasen (SHIFT_PHRASES Vollständigkeit) und Intent-Router (Mocking).

---

## Verwandte Projekte

| Projekt                                                                                 | Beschreibung                                          |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [discord_bot_hundekuchenlive](https://github.com/cakeLinir/discord_bot_hundekuchenlive) | Discord-Bot mit `/todo`, `/shift`, `/stream` Commands |

---

## Lizenz

MIT — Details in [LICENSE](LICENSE).
