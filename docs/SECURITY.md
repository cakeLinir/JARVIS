# JARVIS Sicherheit und Konfiguration

## Ziel

Dieses Dokument beschreibt die Sicherheitsregeln für den aktuellen MVP-Stand. Es enthält keine Secrets und keine lokalen Pfade.

## Secrets

Secrets dürfen nicht ins Repository.

Nicht committen:

```text
backend/.env
desktop-agent/config.local.json
.env
.env.local
bot/.env
bot/.env.local
```

## Backend-Konfigurationsstatus

Das Backend prüft beim Start, ob sicherheitsrelevante Konfiguration gesetzt ist.

Geprüft werden:

- `JARVIS_AGENT_TOKEN`
- `JARVIS_BOT_BRIDGE_TOKEN`
- `JARVIS_DASHBOARD_TOKEN`
- `OPENAI_API_KEY`
- erlaubte Discord-User- oder Rollen-IDs
- Backend Host und Port

Der Dashboard-Status darf nur anzeigen, ob Werte konfiguriert sind. Der tatsächliche Secret-Wert darf niemals im Dashboard, in Logs oder in API-Antworten ausgegeben werden.

## Authentifizierung

Alle schreibenden oder sensiblen Backend-Endpunkte verwenden Bearer-Tokens.

| Client | Token |
|---|---|
| Desktop-Agent | `JARVIS_AGENT_TOKEN` |
| Discord-Bot | `JARVIS_BOT_BRIDGE_TOKEN` |
| Dashboard | `JARVIS_DASHBOARD_TOKEN` |

## Lokale Aktionen

Lokale Windows-Aktionen dürfen ausschließlich vom Desktop-Agent ausgeführt werden.

Das Backend speichert und routet Commands. Es führt selbst keine Windows-Aktion aus.

## Nicht erlaubt

- Keine Platzhalter-Tokens produktiv verwenden.
- Keine Secrets loggen.
- Keine Secrets im Dashboard anzeigen.
- Keine unbekannten Programme starten.
- Keine Selfbots.
- Keine lokalen Aktionen direkt vom Discord-Bot.
- Keine lokalen Aktionen direkt vom Backend.
