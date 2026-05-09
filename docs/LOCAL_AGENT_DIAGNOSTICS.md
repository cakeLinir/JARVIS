# JARVIS Local Agent Diagnostics

## Problem

PowerShell kann `run-local-agent.ps1` blockieren, wenn die lokale Execution Policy nur signierte Skripte erlaubt.

Fehlerbeispiel:

```text
Die Datei ist nicht digital signiert.
```

## Lösung ohne Policy-Änderung

Patch 024 ergänzt:

```text
scripts/run-local-agent.cmd
```

Start:

```powershell
.\scripts\run-local-agent.cmd
```

`.cmd` ist nicht von PowerShell-Skriptsignaturen betroffen.

## Diagnose

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-local-agent-vps.ps1
```

Prüft:

- Backend URL aus `desktop-agent/config.local.json`
- DNS
- TCP Port 443/80
- `/api/health`
- `/api/agent/status` mit Agent Token

## Erwarteter Zielwert

```text
BackendUrl: https://jarvis.hundekuchenlive.de
```

Wenn dort noch `127.0.0.1` oder `http://46.225.14.84:8181` steht, lokale Agent-Konfiguration erneut setzen:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-local-agent-vps.ps1 -ReadTokenFromBackendEnv
```
