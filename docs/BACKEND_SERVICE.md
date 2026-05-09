# JARVIS Backend Prozessverwaltung auf Windows-VPS

## Ziel

Patch 011 ergänzt einfache Prozessverwaltung für das JARVIS Backend auf einem Windows-VPS.

Es wird noch kein Windows-Service eingerichtet. Die Skripte starten und stoppen den Backend-Prozess kontrolliert über Node.js.

## Skripte

| Skript | Zweck |
|---|---|
| `scripts/backend-start.ps1` | Backend starten |
| `scripts/backend-stop.ps1` | Backend stoppen |
| `scripts/backend-restart.ps1` | Backend neu starten |
| `scripts/backend-status.ps1` | PID und Health prüfen |
| `scripts/backend-health.ps1` | `/api/health` prüfen |

## Start

```powershell
cd C:\Pfad\zum\JARVIS
.\scripts\backend-start.ps1
```

Mit Build vor Start:

```powershell
.\scripts\backend-start.ps1 -Build
```

## Stop

```powershell
.\scripts\backend-stop.ps1
```

Falls nötig:

```powershell
.\scripts\backend-stop.ps1 -Force
```

## Restart

```powershell
.\scripts\backend-restart.ps1 -Build
```

## Status

```powershell
.\scripts\backend-status.ps1
```

## Logs

Logs werden geschrieben nach:

```text
logs/backend/
```

PID-Datei:

```text
backend/.runtime/jarvis-backend.pid
```

Diese Dateien werden nicht committed.

## Healthcheck

```powershell
.\scripts\backend-health.ps1
```

Standard-URL:

```text
http://127.0.0.1:8181/api/health
```

## Voraussetzungen

- Node.js im PATH
- npm im PATH
- `backend/.env` mit echten Werten
- `npm run build` erfolgreich
- Port `8181` verfügbar

## Sicherheitsregeln

- Die Skripte schreiben keine Secrets.
- Die Skripte geben keine `.env`-Werte aus.
- Backend läuft auf Port `8181`.
- Externer Zugriff muss über Firewall/Reverse Proxy/HTTPS separat abgesichert werden.
- Diese Skripte ersetzen noch keinen gehärteten Windows-Service.

## Späterer Ausbau

Mögliche nächste Schritte:

- Windows Scheduled Task für Backend-Autostart
- NSSM-Service oder nativer Windows-Service-Wrapper
- Log-Rotation
- Health-basiertes Restart-Skript
- Reverse Proxy mit HTTPS
