# JARVIS Operations CLI

## Ziel

Patch 021 reduziert Script-Sprawl durch einen zentralen Einstiegspunkt:

```powershell
.\scripts\jarvis.ps1 <area> <action>
```

Die bestehenden Skripte bleiben als Low-Level-Bausteine erhalten.

## Wichtig

Nicht mehr direkt verwenden, außer bewusst im Testbetrieb:

```powershell
.\scripts\configure-public-backend.ps1
```

Dieses Skript verlangt jetzt absichtlich:

```powershell
-AllowInsecurePublicHttp
```

Für produktiven Caddy/HTTPS-Betrieb:

```powershell
.\scripts\jarvis.ps1 config https
```

## Häufige Befehle

### Backend

```powershell
.\scripts\jarvis.ps1 backend start -Build
.\scripts\jarvis.ps1 backend stop
.\scripts\jarvis.ps1 backend restart -Build
.\scripts\jarvis.ps1 backend status
.\scripts\jarvis.ps1 backend health
```

### Dashboard

```powershell
.\scripts\jarvis.ps1 dashboard check
.\scripts\jarvis.ps1 dashboard build
.\scripts\jarvis.ps1 dashboard deploy -ReloadCaddy
```

### Caddy

```powershell
.\scripts\jarvis.ps1 caddy install -ReloadCaddy
.\scripts\jarvis.ps1 caddy health
```

### HTTPS-Konfiguration

```powershell
.\scripts\jarvis.ps1 config https
```

### Watchdog

```powershell
.\scripts\jarvis.ps1 watchdog run
.\scripts\jarvis.ps1 watchdog install -EveryMinutes 5
.\scripts\jarvis.ps1 watchdog uninstall
```

### Backend Scheduled Task

```powershell
.\scripts\jarvis.ps1 task install
.\scripts\jarvis.ps1 task status
.\scripts\jarvis.ps1 task uninstall
```

### Preflight

```powershell
.\scripts\jarvis.ps1 preflight local
.\scripts\jarvis.ps1 preflight vps
```

## Script-Kategorien

### Primärer Einstiegspunkt

```text
scripts/jarvis.ps1
```

### Backend Runtime

```text
backend-start.ps1
backend-stop.ps1
backend-restart.ps1
backend-status.ps1
backend-health.ps1
```

### Backend Autostart

```text
install-backend-task.ps1
uninstall-backend-task.ps1
backend-task-status.ps1
```

### Watchdog / Logs

```text
backend-watchdog.ps1
install-backend-watchdog-task.ps1
uninstall-backend-watchdog-task.ps1
backend-log-cleanup.ps1
```

### Dashboard / Caddy

```text
dashboard-build.ps1
deploy-dashboard.ps1
caddy-install-jarvis-config.ps1
caddy-health.ps1
```

### Konfiguration

```text
configure-https-backend.ps1
configure-public-backend.ps1
```

### Preflight / VPS

```text
preflight-local.ps1
preflight-vps.ps1
vps-check-layout.ps1
vps-dashboard-source-check.ps1
vps-update-backend.ps1
```

## Sicherheitsregeln

- HTTPS/Caddy ist der Standardpfad.
- Public HTTP ist blockiert, außer mit explizitem `-AllowInsecurePublicHttp`.
- Keine Secrets werden ausgegeben.
- Low-Level-Skripte bleiben erhalten, aber operative Nutzung läuft über `jarvis.ps1`.

## Local Agent

```powershell
.\scripts\jarvis.ps1 agent start
.\scripts\jarvis.ps1 agent status
.\scripts\jarvis.ps1 agent diagnose
.\scripts\jarvis.ps1 agent config
.\scripts\jarvis.ps1 agent install-task
.\scripts\jarvis.ps1 agent uninstall-task
```

Details:

```text
docs/LOCAL_AGENT_OPERATIONS.md
```

## Patch 025.3 Hinweis

`jarvis.ps1` wurde als zentraler CLI-Einstiegspunkt neu aufgebaut, weil PowerShell beim Weiterreichen von Arrays an Subskripte `-RepoRoot` als Wert statt als Parameternamen übergeben hatte.

Zusätzlich gibt es:

```powershell
.\scripts\jarvis.ps1 agent stop
```

Damit kann ein bereits laufender lokaler Agent beendet werden, bevor ein neuer gestartet wird.

## Patch 025.6 Hinweis

`agent stop` nutzt jetzt zusätzlich den Besitzer des lokalen Agent-Ports:

```text
127.0.0.1:8765
```

Wenn ein Prozess Port `8765` besitzt, aber nicht eindeutig nach JARVIS Agent aussieht, wird er nicht automatisch beendet. Erzwingen:

```powershell
.\scripts\stop-local-agent.ps1 -ForceByPort
```
