# JARVIS Backend Watchdog & Log-Rotation

## Ziel

Patch 017.1 ergänzt einen Watchdog für den Windows-VPS.

Der Watchdog prüft:

```text
http://127.0.0.1:8181/api/health
```

Wenn das Backend nicht gesund ist, ruft er auf:

```powershell
.\scripts\backend-restart.ps1
```

## Manuell testen

```powershell
cd C:\Bots\JARVIS
.\scripts\backend-watchdog.ps1
```

## Scheduled Task installieren

```powershell
.\scripts\install-backend-watchdog-task.ps1
```

Standardintervall:

```text
5 Minuten
```

Anderes Intervall:

```powershell
.\scripts\install-backend-watchdog-task.ps1 -EveryMinutes 2
```

## Scheduled Task entfernen

```powershell
.\scripts\uninstall-backend-watchdog-task.ps1
```

## Logs

```text
logs/backend-watchdog/watchdog.log
```

## Log-Cleanup

Nur anzeigen:

```powershell
.\scripts\backend-log-cleanup.ps1 -WhatIfOnly
```

Tatsächlich löschen:

```powershell
.\scripts\backend-log-cleanup.ps1
```

Standard:

```text
KeepDays=14
```

## Sicherheitsregeln

- Watchdog prüft nur lokalen Health-Endpunkt.
- Watchdog gibt keine Secrets aus.
- Watchdog führt keine Agent-Commands aus.
- Watchdog startet nur Backend-Prozessverwaltung.
