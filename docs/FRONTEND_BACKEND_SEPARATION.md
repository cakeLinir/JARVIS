# JARVIS Frontend/Backend Separation

## Ziel

Patch 019 trennt Auslieferung und API sauber:

```text
Caddy serviert dashboard/dist
Backend liefert API/Auth/OAuth
```

## Routing

```text
https://jarvis.hundekuchenlive.de/
https://jarvis.hundekuchenlive.de/dashboard
  -> dashboard/dist/index.html

https://jarvis.hundekuchenlive.de/api/*
  -> http://127.0.0.1:8181

https://jarvis.hundekuchenlive.de/dashboard/auth/*
  -> http://127.0.0.1:8181

https://jarvis.hundekuchenlive.de/dashboard/logout
  -> http://127.0.0.1:8181
```

## Build + Deployment

```powershell
cd C:\Bots\JARVIS
.\scripts\dashboard-build.ps1
.\scripts\caddy-install-jarvis-config.ps1 -Reload
```

Oder kombiniert:

```powershell
.\scripts\deploy-dashboard.ps1 -ReloadCaddy
```

## Backend

Backend bleibt lokal:

```env
JARVIS_BACKEND_HOST=127.0.0.1
JARVIS_BACKEND_PORT=8181
JARVIS_PUBLIC_BASE_URL=https://jarvis.hundekuchenlive.de
JARVIS_DISCORD_OAUTH_REDIRECT_URI=https://jarvis.hundekuchenlive.de/dashboard/auth/discord/callback
JARVIS_DASHBOARD_COOKIE_SECURE=true
```

## Healthcheck

```powershell
.\scripts\caddy-health.ps1
```

Prüft:

```text
lokales Backend
öffentliche API
Dashboard Frontend
Discord OAuth Start
```

## Sicherheitsregeln

- Dashboard enthält keine Secrets.
- Dashboard speichert keinen Token.
- API-Auth bleibt serverseitig.
- Caddy proxyt nur API/Auth/Logout ans Backend.
- Backend-Port 8181 muss nicht öffentlich sein.
