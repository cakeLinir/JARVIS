# JARVIS Backend Prozessverwaltung auf Windows-VPS

## Ziel

Das JARVIS Backend läuft auf dem Windows-VPS lokal auf:

```text
http://127.0.0.1:8181
```

Caddy stellt es öffentlich über HTTPS bereit:

```text
https://jarvis.hundekuchenlive.de
```

## Manuelle Prozessverwaltung

| Skript | Zweck |
|---|---|
| `scripts/backend-start.ps1` | Backend starten |
| `scripts/backend-stop.ps1` | Backend stoppen |
| `scripts/backend-restart.ps1` | Backend neu starten |
| `scripts/backend-status.ps1` | PID und Health prüfen |
| `scripts/backend-health.ps1` | `/api/health` prüfen |

## Scheduled Task Autostart

Patch 016 ergänzt einen Scheduled Task für den Windows-VPS.

### Installieren

Standard: Start bei Benutzer-Login.

```powershell
cd C:\Bots\JARVIS
.\scripts\install-backend-task.ps1
```

Start bei Systemstart:

```powershell
.\scripts\install-backend-task.ps1 -AtStartup
```

Expliziter Benutzer:

```powershell
.\scripts\install-backend-task.ps1 -AtLogon -User "Administrator"
```

### Status prüfen

```powershell
.\scripts\backend-task-status.ps1
```

### Entfernen

```powershell
.\scripts\uninstall-backend-task.ps1
```

### Manuell starten

```powershell
Start-ScheduledTask -TaskPath "\JARVIS\" -TaskName "JARVIS Backend"
```

## Logs

Backend-Logs:

```text
logs/backend/
```

PID-Datei:

```text
backend/.runtime/jarvis-backend.pid
```

## Sicherheitsregeln

- Backend bindet mit Caddy-Setup nur auf `127.0.0.1`.
- Öffentlich läuft Zugriff über HTTPS/Caddy.
- Skripte geben keine `.env`-Werte aus.
- Scheduled Task ruft nur `scripts/backend-start.ps1` auf.
- Keine Secrets im Task selbst.

## Watchdog

Zusätzlich zum Autostart kann ein Watchdog installiert werden:

```powershell
.\scripts\install-backend-watchdog-task.ps1
```

Der Watchdog prüft regelmäßig den lokalen Health-Endpunkt:

```text
http://127.0.0.1:8181/api/health
```

Bei Fehlern ruft er auf:

```powershell
.\scripts\backend-restart.ps1
```

Details: `docs/BACKEND_WATCHDOG.md`
