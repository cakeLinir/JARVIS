# JARVIS Dashboard Frontend

## Ziel

Ab Patch 018 wird das Dashboard als eigenes Frontend-Projekt entwickelt.

```text
dashboard/
```

Das Backend bleibt für API, Auth, Discord OAuth, Commands und Agent-State zuständig.

## Stack

```text
Vite
React
TypeScript
CSS
```

## Start lokal

```powershell
cd C:\Bots\JARVIS\dashboard
npm install
npm run dev
```

Vite läuft lokal auf:

```text
http://127.0.0.1:5173
```

## Build

```powershell
cd C:\Bots\JARVIS
.\scripts\dashboard-build.ps1
```

oder:

```powershell
cd dashboard
npm install
npm run build
```

Output:

```text
dashboard/dist
```

## Auth

Das Frontend speichert keine Tokens.

Auth läuft über:

```text
HttpOnly Cookie
```

API Requests nutzen:

```ts
credentials: "include"
```

Login-Link:

```text
/dashboard/auth/discord/start
```

Logout:

```text
/dashboard/logout
```

## API

Das Frontend nutzt aktuell:

```text
GET  /api/dashboard/overview
POST /api/dashboard/commands/morning-routine
POST /dashboard/logout
```

## Caddy-Ziel in späterem Patch

Später soll Caddy `dashboard/dist` direkt ausliefern:

```caddy
handle /api/* {
    reverse_proxy 127.0.0.1:8181
}

handle /dashboard/auth/* {
    reverse_proxy 127.0.0.1:8181
}

handle /dashboard/logout {
    reverse_proxy 127.0.0.1:8181
}

handle {
    root * C:\Bots\JARVIS\dashboard\dist
    try_files {path} /index.html
    file_server
}
```

## Sicherheitsregeln

- Kein Token im Frontend.
- Kein Local Storage für Session.
- Keine Secrets im Build.
- Backend prüft alle API-Zugriffe.
- Dashboard ist nur eine UI, keine Autoritätsquelle.

## Deployment über Caddy

Ab Patch 019 serviert Caddy `dashboard/dist` direkt.

Details:

```text
docs/FRONTEND_BACKEND_SEPARATION.md
```
