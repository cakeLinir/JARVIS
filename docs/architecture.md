# JARVIS Architektur

## Verifizierter Zielzustand

JARVIS besteht aus drei getrennten Laufzeitbereichen:

1. **VPS-Backend**
   - Fastify API
   - OpenAI-Service
   - Realtime Client-Secret-Service
   - Dev-News-Aggregation
   - Command-Routing
   - Dashboard-MVP
   - Authentifizierung für Agent, Bot und Dashboard

2. **Lokaler Windows-Agent**
   - lokale Programmausführung
   - lokale Fenstersteuerung
   - lokale TODO-/Projektanalyse
   - lokale Agent-API auf `127.0.0.1`
   - später Voice/Wake-Word/STT/TTS

3. **Discord-Bot**
   - bleibt im separaten Repository `cakeLinir/discord_bot_hundekuchenlive`
   - erzeugt Backend-Commands
   - führt keine Windows-Aktionen selbst aus

## Port-Entscheidung

Das JARVIS-Backend verwendet Port `8181`.

Port `8080` wird nicht als Standard verwendet, weil er auf dem VPS bereits durch andere Software belegt ist.

## Sicherheitsprinzip

Das Backend fordert lokale Aktionen nur an. Die Ausführung erfolgt ausschließlich über den lokalen Windows-Agent.

```text
Discord/Dashboard/Voice
  -> Backend Command
  -> Agent claimt Command
  -> Agent validiert lokal
  -> Agent führt erlaubte Aktion aus
  -> Agent meldet Ergebnis zurück
```

## Nicht erlaubt

- Keine Selfbots.
- Keine Secrets im Repository.
- Keine OpenAI-Keys im Agent oder Dashboard.
- Keine lokalen Windows-Aktionen direkt vom Backend.
- Keine Ausführung unbekannter Programme.
- Keine erfundenen Pfade.
- Keine dauerhafte Audioübertragung ohne Aktivierung.

## MVP-Komponenten

| Komponente | Status |
|---|---|
| Backend Health | vorhanden |
| Agent Status | vorhanden |
| Morning Log | vorhanden |
| Command Queue | vorhanden |
| Dashboard-MVP | vorhanden |
| Dev-News | vorhanden |
| OpenAI Chat/Realtime Secret | vorhanden |
| Windows-Agent Textmodus | vorhanden |
| Voice/Wake-Word | später |
| Multi-Monitor-Fensterlogik | auszubauen |
| Audit-Log | auszubauen |
| Persistenz SQLite/PostgreSQL | auszubauen |
