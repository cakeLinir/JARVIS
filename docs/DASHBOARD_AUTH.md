# JARVIS Dashboard Auth & VPS Binding

## Ziel

Patch 012 macht zwei Dinge:

1. Das Backend kann auf dem VPS extern erreichbar gebunden werden.
2. Das Dashboard selbst ist nicht mehr öffentlich lesbar, sondern verlangt Login.

## VPS Binding

Empfohlene Backend-Konfiguration auf dem VPS:

```env
JARVIS_BACKEND_HOST=0.0.0.0
JARVIS_BACKEND_PORT=8181
JARVIS_PUBLIC_HOST=46.225.14.84
JARVIS_PUBLIC_BASE_URL=http://46.225.14.84:8181
```

`0.0.0.0` bedeutet: Node/Fastify lauscht auf allen Interfaces. Das ist auf Servern üblich.

Optional kann direkt auf die öffentliche IP gebunden werden:

```env
JARVIS_BACKEND_HOST=46.225.14.84
```

Das funktioniert nur, wenn Windows diese IP tatsächlich als Interface-Adresse führt.

## Dashboard Login

Dashboard-URL:

```text
http://46.225.14.84:8181/dashboard
```

Ohne gültige Session wird auf diese Seite umgeleitet:

```text
/dashboard/login
```

Login erfolgt mit:

```env
JARVIS_DASHBOARD_TOKEN
```

Nach erfolgreichem Login setzt das Backend ein HttpOnly-Cookie:

```text
jarvis_dashboard_session
```

## API-Schutz

Dashboard-APIs nutzen `requireDashboardAuth`.

Geschützt sind unter anderem:

```text
/api/dashboard/overview
/api/dashboard/commands/morning-routine
```

Der normale Bearer-Token-Zugriff mit `Authorization: Bearer <JARVIS_DASHBOARD_TOKEN>` bleibt für Skripte möglich.

## Cookie-Sicherheit

Bei HTTP:

```env
JARVIS_DASHBOARD_COOKIE_SECURE=false
```

Bei HTTPS später:

```env
JARVIS_DASHBOARD_COOKIE_SECURE=true
```

## Wichtige Sicherheitsgrenze

HTTP über öffentliche IP schützt das Token nicht vor Netzwerkmitschnitt. Für produktionsnahen Betrieb muss später HTTPS davor:

- Reverse Proxy
- TLS-Zertifikat
- Firewall-Regeln

## Firewall

Auf dem VPS muss Port `8181` eingehend erlaubt sein, falls Dashboard/API extern erreichbar sein sollen.

## Nicht umgesetzt

- Kein HTTPS
- Kein Reverse Proxy
- Keine Benutzerverwaltung
- Keine Rollen im Dashboard
- Keine CSRF-Tokens
- Keine 2FA
