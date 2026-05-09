# JARVIS Patch 020 – VPS Recovery & HTTPS Config

## Zweck

Patch 020 korrigiert zwei Betriebsprobleme:

1. Watchdog Scheduled Task Installation auf Windows/PowerShell-Versionen, bei denen `$trigger.Repetition.Interval` nicht setzbar ist.
2. Rücksetzung der `.env` auf HTTPS/Caddy-Betrieb nach versehentlichem `configure-public-backend.ps1`.

## Watchdog Task

```powershell
.\scripts\install-backend-watchdog-task.ps1
```

nutzt jetzt direkt:

```powershell
New-ScheduledTaskTrigger -RepetitionInterval
```

statt nachträglich `Repetition.Interval` zu setzen.

## HTTPS/Caddy Backend-Konfiguration

```powershell
.\scripts\configure-https-backend.ps1
```

setzt in `backend\.env`:

```env
JARVIS_BACKEND_HOST=127.0.0.1
JARVIS_BACKEND_PORT=8181
JARVIS_PUBLIC_HOST=jarvis.hundekuchenlive.de
JARVIS_PUBLIC_BASE_URL=https://jarvis.hundekuchenlive.de
JARVIS_DISCORD_OAUTH_REDIRECT_URI=https://jarvis.hundekuchenlive.de/dashboard/auth/discord/callback
JARVIS_DASHBOARD_COOKIE_SECURE=true
JARVIS_DASHBOARD_SESSION_IDLE_SECONDS=1800
JARVIS_DASHBOARD_SESSION_TTL_SECONDS=1800
```

Danach Backend neu starten.

## Dashboard Source Check

```powershell
.\scripts\vps-dashboard-source-check.ps1
```

prüft, ob `dashboard/package.json` und optional `dashboard/dist/index.html` vorhanden sind.

Wenn `dashboard/package.json` fehlt, wurde Patch 018 nicht auf diesen Repo-Stand angewendet oder nicht auf den VPS gepullt.
