# JARVIS Architektur

## Komponenten

### 1. Windows-VPS Backend

- Fastify API
- Authentifizierung für Agent, Bot und Dashboard
- Command-Queue
- OpenAI Chat-/Realtime-Service
- Dev-News-Aggregation
- Dashboard-API
- zentrale Policy-Entscheidungen

### 2. Nextcord Bot Bridge

- läuft auf dem VPS neben oder innerhalb des vorhandenen Nextcord-Bots
- ruft ausschließlich das JARVIS-Backend auf
- erzeugt Commands statt direkt lokale Programme zu starten
- nutzt Discord-Slash-Commands, keine Selfbot-Automation

### 3. Webdashboard

- wird vom Backend unter `/dashboard` ausgeliefert
- fragt Status, Commands, Agent-Heartbeat und Morning-Log ab
- kann die Morning-Routine nach expliziter Bestätigung anfordern

### 4. Lokaler Windows-Agent

- startet nach Windows-Login
- pollt Backend-Commands
- startet Programme
- liest TODOs
- analysiert Projekte lokal
- ordnet Fenster an
- stellt eine lokale API für den späteren Voice-Client bereit

### 5. Voice-Client

- späterer Electron/Tauri/WebRTC-Client
- Wake-Word lokal
- OpenAI Realtime Audio nach Aktivierung
- ruft lokale Agent-API für Windows-Aktionen auf

## Realtime-Datenfluss

```text
User sagt Wake-Word
→ Voice-Client aktiviert Session
→ Backend erstellt OpenAI Realtime Client Secret
→ Voice-Client verbindet sich per WebRTC
→ Modell antwortet per Audio
→ Tool-Call löst lokale Agent-API aus
→ Agent führt Windows-Aktion aus
→ Ergebnis geht zurück in die Session
```
