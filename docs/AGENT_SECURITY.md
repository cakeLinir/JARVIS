# JARVIS Agent Security

## Ziel

Der lokale Windows-Agent fÃ¼hrt nur lokale Aktionen aus, die explizit in der lokalen Konfiguration erlaubt sind.

## Patch 004

Dieser Patch hÃ¤rtet den Desktop-Agent in folgenden Bereichen:

- zentrale PrÃ¼fung von Platzhalterwerten
- klare Meldungen mit `KONFIGURATION_ERFORDERLICH`
- lokale API startet nur mit echtem Token
- lokale API bindet nur auf `127.0.0.1` oder `localhost`
- URI-Start nur fÃ¼r erlaubte Schemes
- `command`-Startmodus ist standardmÃ¤ÃŸig blockiert
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

Echte Werte gehÃ¶ren in:

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

Logs dÃ¼rfen keine Secrets enthalten.