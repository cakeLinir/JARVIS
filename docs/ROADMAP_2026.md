# JARVIS Development Roadmap

**Projekt:** JARVIS - Persönlicher Windows-Desktop-Assistent  
**Repository:** https://github.com/cakeLinir/JARVIS  
**Ziel-Architektur:** Windows VPS Backend + Lokaler Desktop-Agent + Discord Integration  
**Letzte Aktualisierung:** 28.05.2026

---

## Übersicht: Projekt-Status

| Komponente | Status | Fortschritt |
|------------|--------|-------------|
| Backend (VPS) | 🟡 MVP | 60% |
| Desktop-Agent | 🟡 MVP | 45% |
| Dashboard | 🟡 MVP | 55% |
| Discord-Bot Integration | 🔴 Fehlt | 10% |
| Voice-System | 🔴 Fehlt | 5% |
| AI/LLM Integration | 🟡 Partial | 40% |

**Legende:**  
🔴 Kritisch / Nicht begonnen  
🟡 In Arbeit / MVP  
🟢 Stabil / Produktionsreif

---

## Phase 1: Kritische Fixes (Woche 1)

> **Ziel:** System stabilisieren, bevor neue Features hinzugefügt werden

### Tag 1-2: Backend Hotfixes

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 1.1 | Fix OpenAI Chat Route | `backend/src/routes/openai.routes.ts:42` | Response-Daten hinzufügen | 🔴 KRITISCH |
| 1.2 | Fix Realtime Secret Route | `backend/src/routes/realtime.routes.ts:34` | Secret-Daten zurückgeben | 🔴 KRITISCH |
| 1.3 | Config JSON Syntax fix | `desktop-agent/config.local.example.json:22` | Fehlendes Komma nach `localApi` | 🔴 KRITISCH |
| 1.4 | Error Handling verbessern | `backend/src/services/openai.service.ts` | Retry-Logik für API-Fehler | 🟡 Medium |
| 1.5 | Logging erweitern | `backend/src/server.ts` | Strukturierte Logs für Debugging | 🟢 Low |

**Definition of Done:**
- [ ] Alle Routes geben korrekte JSON-Responses zurück
- [ ] Backend startet ohne Fehler
- [ ] API-Tests mit curl/Postman erfolgreich

### Tag 3-4: Discord-Bot Integration

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 2.1 | JARVIS API Client erstellen | `discord_bot_hundekuchenlive/bot/services/jarvis_client.py` | HTTP-Client für Backend-Calls | 🔴 KRITISCH |
| 2.2 | Bot-Bridge Token integrieren | `discord_bot_hundekuchenlive/bot/core/config.py` | `JARVIS_BOT_BRIDGE_TOKEN` laden | 🔴 KRITISCH |
| 2.3 | Jarvis Cog erstellen | `discord_bot_hundekuchenlive/bot/cogs/jarvis.py` | Neue Cog-Datei | 🔴 KRITISCH |
| 2.4 | Command: !jarvis morgen | `bot/cogs/jarvis.py` | Morning Routine trigger | 🟡 Medium |
| 2.5 | Command: !jarvis status | `bot/cogs/jarvis.py` | Agent-Status abfragen | 🟡 Medium |

**Definition of Done:**
- [ ] Discord-Bot kann Backend erreichen
- [ ] Commands werden im Audit-Log registriert
- [ ] Fehler werden sichtbar geloggt

### Tag 5-7: Code Review & Stabilisierung

| # | Task | Beschreibung | Priorität |
|---|------|--------------|-----------|
| 3.1 | VPS Deployment testen | Backend auf 46.225.14.84:8181 prüfen | 🔴 KRITISCH |
| 3.2 | Agent-Verbindung testen | Desktop-Agent mit Backend verbinden | 🔴 KRITISCH |
| 3.3 | Dashboard-Auth testen | Discord OAuth Flow | 🟡 Medium |
| 3.4 | End-to-End Test | Discord → Backend → Agent | 🟡 Medium |
| 3.5 | Dokumentation aktualisieren | README.md mit aktuellen Endpoints | 🟢 Low |

---

## Phase 2: Voice MVP (Woche 2-3)

> **Ziel:** Erste Sprachinteraktion ermöglichen

### Woche 2: TTS & WebRTC Setup

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 4.1 | TTS Service implementieren | `desktop-agent/src/voice/tts_service.py` | pyttsx3 Wrapper | 🔴 KRITISCH |
| 4.2 | TTS Integration in main | `desktop-agent/src/main.py` | Speak-Callback für Commands | 🔴 KRITISCH |
| 4.3 | WebSocket Client für Realtime | `desktop-agent/voice-client/websocket_client.py` | Verbindung zu Backend | 🔴 KRITISCH |
| 4.4 | Audio Input/Output Handler | `desktop-agent/voice-client/audio_handler.py` | Mikrofon & Lautsprecher | 🟡 Medium |
| 4.5 | Voice-Status in local_api | `desktop-agent/src/local_api.py` | /health erweitern | 🟢 Low |

**Optional (falls zeitlich möglich):**
- [ ] Ephemeral Token Caching im Backend
- [ ] Voice-Config (Stimme, Sprache) über config.json

### Woche 3: STT & Wake Word

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 5.1 | STT Provider wählen | Research: Whisper vs. Azure vs. Google | 🟡 Medium |
| 5.2 | STT Service implementieren | `desktop-agent/src/voice/stt_service.py` | Speech-to-Text | 🟡 Medium |
| 5.3 | Wake-Word Detection | `desktop-agent/src/voice/wake_word.py` | "Jarvis" erkennen | 🟡 Medium |
| 5.4 | Voice Loop Integration | `desktop-agent/src/main.py` | STT → Command → TTS | 🟡 Medium |
| 5.5 | Voice--only Mode | Config-Flag für Headless-Modus | 🟢 Low |

**Definition of Done:**
- [ ] "Guten Morgen Jarvis" → TTS-Antwort
- [ ] Wake-Word startet Aufnahme
- [ ] Voice-Status im Dashboard sichtbar

---

## Phase 3: Core Features (Woche 4-6)

> **Ziel:** Referenz-Features von AnubhavChaturvedi implementieren

### Woche 4: System & Automation

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 6.1 | Battery Check | `desktop-agent/src/system/battery.py` | Akku-Status überwachen | 🟡 Medium |
| 6.2 | Volume Control | `desktop-agent/src/system/volume.py` | Lautstärke setzen/lesen | 🟡 Medium |
| 6.3 | Screenshot/Vision | `desktop-agent/src/vision/screenshot.py` | Bildschirm capture | 🟡 Medium |
| 6.4 | System Info | `desktop-agent/src/system/sysinfo.py` | CPU, RAM, IP | 🟡 Medium |
| 6.5 | Backend: Vision Endpoint | `backend/src/routes/vision.routes.ts` | Bild an OpenAI senden | 🟡 Medium |

**Referenz:** `AnubhavChaturvedi-GitHub/jarvis-ai-assistant/Features/`

### Woche 5: Integrationen

| # | Task | Beschreibung | Priorität |
|---|------|--------------|-----------|
| 7.1 | Wetter API | OpenWeatherMap Integration | 🟡 Medium |
| 7.2 | News Aggregation verbessern | AI-Summary statt RSS-Liste | 🟢 Low |
| 7.3 | Zeitgesteuerte Tasks | Cron-ähnliche Jobs im Agent | 🟢 Low |
| 7.4 | WhatsApp Automation | URI-Scheme erweitern | 🟢 Low |
| 7.5 | Spotify Control | Playback-Controls | 🟢 Low |

### Woche 6: Dashboard & UI

| # | Task | Datei | Beschreibung | Priorität |
|---|------|-------|--------------|-----------|
| 8.1 | Voice-UI Komponenten | `dashboard/src/components/VoicePanel.tsx` | Mikrofon-Button, Status | 🟡 Medium |
| 8.2 | Realtime Chat-Interface | `dashboard/src/pages/Chat.tsx` | Text + Voice Chat | 🟡 Medium |
| 8.3 | Command-History | Dashboard-Erweiterung | 🟢 Low |
| 8.4 | System-Stats Anzeige | CPU, RAM, Agent-Status | 🟢 Low |
| 8.5 | Mobile Responsive | CSS Anpassungen | 🟢 Low |

---

## Phase 4: Erweiterte Features (Woche 7-8)

> **Ziel:** Produktionsreife und Polishing

### Woche 7: Sicherheit & Robustheit

| # | Task | Beschreibung | Priorität |
|---|------|--------------|-----------|
| 9.1 | Rate Limiting verbessern | Per-User statt global | 🟡 Medium |
| 9.2 | Secrets Rotation | Token-Refresh Mechanismus | 🟡 Medium |
| 9.3 | Agent Auto-Update | Update-Check im Agent | 🟢 Low |
| 9.4 | Backup & Restore | Config-Backup | 🟢 Low |
| 9.5 | Fehler-Reporting | Sentry oder ähnliches | 🟢 Low |

### Woche 8: Performance & Testing

| # | Task | Beschreibung | Priorität |
|---|------|--------------|-----------|
| 10.1 | Unit Tests Backend | Jest-Tests für Services | 🟢 Low |
| 10.2 | Unit Tests Agent | pytest für Python-Code | 🟢 Low |
| 10.3 | Load Testing | K6 oder Artillery | 🟢 Low |
| 10.4 | Memory Leak Check | Agent-Profiling | 🟢 Low |
| 10.5 | Dokumentation finalisieren | API-Docs, Setup-Guide | 🟢 Low |

---

## Monatliche Meilensteine

| Monat | Meilenstein | Deliverables |
|-------|-------------|--------------|
| **Monat 1** | Stabiles MVP | Backend + Agent + Dashboard laufen stabil, Discord-Basic funktioniert |
| **Monat 2** | Voice-Ready | TTS/STT implementiert, erste Sprachinteraktionen |
| **Monat 3** | Feature-Complete | Alle Referenz-Features implementiert, Dashboard vollständig |
| **Monat 4** | Production | Sicherheit, Tests, Dokumentation, Community-Release |

---

## Tägliche Checkliste (Template)

Verwenden Sie dieses Template für tägliche Stand-ups:

```markdown
## Datum: [YYYY-MM-DD]

### Gestern erledigt:
- [x] Task 1
- [ ] Task 2 (partiell)

### Heute geplant:
- [ ] Priorität 1
- [ ] Priorität 2

### Blocker:
- [Beschreibung]

### Notizen:
- [Wichtige Erkenntnisse]

```
---

### Links & Ressourcen

| Ressource | URL |
| --- | --- |
| Haupt-Repo | https://github.com/cakeLinir/JARVIS |
| Discord-Bot Repo | https://github.com/cakeLinir/discord_bot_hundekuchenlive |
| Referenz-Features | https://github.com/AnubhavChaturvedi-GitHub/jarvis-ai-assistant |
| VPS Dashboard | http://46.225.14.84:8181/dashboard |
| OpenAI Realtime API | https://platform.openai.com/docs/guides/realtime |
| Fastify Docs | https://fastify.dev/docs/latest/ |

---

## Mitwirkende

- Justin Barth - Hauptentwickler