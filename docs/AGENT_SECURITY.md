# JARVIS Agent Security

## Ziel

Der lokale Windows-Agent führt nur lokale Aktionen aus, die explizit in der lokalen Konfiguration erlaubt sind.

## Patch 004

Dieser Patch härtet den Desktop-Agent in folgenden Bereichen:

- zentrale Prüfung von Platzhalterwerten
- klare Meldungen mit `KONFIGURATION_ERFORDERLICH`
- lokale API startet nur mit echtem Token
- lokale API bindet nur auf `127.0.0.1` oder `localhost`
- URI-Start nur für erlaubte Schemes
- `command`-Startmodus ist standardmäßig blockiert
- strukturierte JSONL-Agent-Logs
- Backend-Completion kann `errorCode` senden

## Nicht erlaubt

- unbekannte Commands
- Placeholder-Pfade
- Placeholder-Tokens
- lokale API ohne Token
- lokale API auf externem Interface
- beliebige Shell-Kommandos

## Lokale Konfiguration

Echte Werte gehören in:

```text
desktop-agent/config.local.json
```

Nicht committen:

```text
desktop-agent/config.local.json
backend/.env
.env
.env.local
```

## Logs

Der Agent schreibt:

```text
logs/desktop-agent.log
logs/desktop-agent.jsonl
```

Logs dürfen keine Secrets enthalten.