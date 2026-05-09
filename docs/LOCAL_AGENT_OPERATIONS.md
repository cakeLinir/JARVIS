# JARVIS Local Agent Operations

## Ziel

Patch 025.1 macht den lokalen Agent-Betrieb robuster.

PowerShell blockiert `.ps1`-Skripte je nach Execution Policy, wenn sie nicht signiert sind. Deshalb ist der offizielle Startweg für den lokalen Agent:

```powershell
.\scripts\run-local-agent.cmd
```

## Start

```powershell
cd C:\Users\hunde\Desktop\JARVIS
.\scripts\run-local-agent.cmd
```

oder über die zentrale CLI:

```powershell
.\scripts\jarvis.ps1 agent start
```

## Diagnose

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\diagnose-local-agent-vps.ps1
```

oder:

```powershell
.\scripts\jarvis.ps1 agent diagnose
```

## Status der lokalen Agent-API

Wenn der Agent läuft:

```powershell
.\scripts\local-agent-status.ps1
```

oder:

```powershell
.\scripts\jarvis.ps1 agent status
```

Prüft:

```text
http://127.0.0.1:8765/health
```

## Agent-Konfiguration auf VPS setzen

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-local-agent-vps.ps1 -BackendUrl "https://jarvis.hundekuchenlive.de" -AgentName "jarvis-desktop-agent"
```

oder:

```powershell
.\scripts\jarvis.ps1 agent config
```

## Autostart installieren

```powershell
.\scripts\install-local-agent-task.ps1
```

oder:

```powershell
.\scripts\jarvis.ps1 agent install-task
```

Standard ist Start bei Benutzer-Login.

## Autostart entfernen

```powershell
.\scripts\uninstall-local-agent-task.ps1
```

oder:

```powershell
.\scripts\jarvis.ps1 agent uninstall-task
```

## Sicherheitsregeln

- Agent startet lokale Desktop-Automation nur auf dem lokalen PC.
- Agent kommuniziert mit dem Backend über HTTPS.
- Agent Token wird nicht ausgegeben.
- `desktop-agent/config.local.json` darf nicht committed werden.
- Kein PowerShell-Policy-Bypass für den normalen Start nötig, wenn `.cmd` genutzt wird.
