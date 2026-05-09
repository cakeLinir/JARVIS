# JARVIS Local Agent mit VPS verbinden

## Ziel

Das Dashboard zeigt aktuell:

```text
Runtime: unknown
Agent: unknown
TODO: unknown
```

Das ist korrekt, solange der lokale Windows-Agent keinen Status an das VPS-Backend sendet.

## Ziel-Backend

```text
https://jarvis.hundekuchenlive.de
```

Der Agent sendet an:

```text
https://jarvis.hundekuchenlive.de/api/agent/status
```

## Lokale Agent-Konfiguration setzen

Auf dem lokalen PC, nicht auf dem VPS:

```powershell
cd C:\Users\hunde\Desktop\JARVIS
.\scripts\configure-local-agent-vps.ps1 -ReadTokenFromBackendEnv
```

Alternativ Token bewusst übergeben:

```powershell
.\scripts\configure-local-agent-vps.ps1 -AgentToken "DEIN_AGENT_TOKEN"
```

Das Skript schreibt in:

```text
desktop-agent/config.local.json
```

und legt vorher ein Backup an.

## Verbindung testen

```powershell
.\scripts\test-local-agent-vps-connection.ps1
```

Erwartung:

```text
[OK] Agent-Status erfolgreich an VPS gesendet.
```

Danach sollte das Dashboard nicht mehr `unknown` anzeigen, spätestens nach Klick auf:

```text
Status laden
```

## Agent starten

```powershell
.\scripts\run-local-agent.ps1
```

oder direkt:

```powershell
cd desktop-agent
py -3 src/main.py
```

## Sicherheit

- `config.local.json` darf nicht committed werden.
- Agent Token wird nicht ausgegeben.
- Agent Token bleibt lokal.
- Backend bleibt über HTTPS erreichbar.
- Caddy proxyt `/api/*` ans Backend.
