# JARVIS HTTPS mit Caddy

## Ziel

JARVIS wird öffentlich über diese Subdomain bereitgestellt:

```text
https://jarvis.hundekuchenlive.de
```

Caddy übernimmt HTTPS und leitet intern auf das JARVIS Backend weiter:

```text
https://jarvis.hundekuchenlive.de -> http://127.0.0.1:8181
```

## Bereits erledigt

DNS:

```text
Typ: A
Name: jarvis
Ziel: 46.225.14.84
```

Discord Redirect URI:

```text
https://jarvis.hundekuchenlive.de/dashboard/auth/discord/callback
```

## Empfohlene Backend `.env`

Auf dem VPS in `backend\.env`:

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

## Caddy konfigurieren

```powershell
cd C:\Pfad\zum\JARVIS
.\scripts\caddy-install-jarvis-config.ps1 -Reload
```

Optional mit E-Mail:

```powershell
.\scripts\caddy-install-jarvis-config.ps1 -Email "admin@hundekuchenlive.de" -Reload
```

## Healthcheck

```powershell
.\scripts\caddy-health.ps1
```

Prüft:

```text
http://127.0.0.1:8181/api/health
https://jarvis.hundekuchenlive.de/api/health
https://jarvis.hundekuchenlive.de/dashboard/login
```

## Firewall

Öffentlich erlauben:

```text
TCP 80
TCP 443
```

Nach außen schließen:

```text
TCP 8181
```

Port `8181` soll nur lokal auf dem VPS erreichbar sein, wenn Caddy davor sitzt.

## Sicherheit

- Öffentlich nur HTTPS.
- Backend nur lokal auf `127.0.0.1:8181`.
- Cookies mit `Secure=true`.
- Dashboard-Login über Discord OAuth.
- Keine Secrets im Caddyfile.
