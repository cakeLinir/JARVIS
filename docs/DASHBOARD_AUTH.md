# JARVIS Dashboard Discord Auth

## Ziel

Das Dashboard verwendet Discord OAuth2 für Login und autorisiert danach gegen `.env`-Allowlisten.

## Warum Discord OAuth2 nötig ist

`JARVIS_ALLOWED_DISCORD_USER_IDS` und `JARVIS_ALLOWED_DISCORD_ROLE_IDS` sind nur Allowlisten. Sie beweisen nicht, wer im Browser sitzt.

Dafür wird Discord OAuth2 genutzt:

1. Browser geht zu `/dashboard/login`.
2. Benutzer klickt „Mit Discord einloggen“.
3. Discord bestätigt die Identität über OAuth2.
4. Backend liest die Discord User-ID.
5. Backend prüft User-ID und optional Rollen gegen `.env`.
6. Backend erzeugt eine lokale Dashboard-Session.

## Benötigte `.env`

```env
JARVIS_DISCORD_OAUTH_CLIENT_ID=DEINE_DISCORD_APP_CLIENT_ID
JARVIS_DISCORD_OAUTH_CLIENT_SECRET=DEIN_DISCORD_APP_CLIENT_SECRET
JARVIS_DISCORD_OAUTH_REDIRECT_URI=http://46.225.14.84:8181/dashboard/auth/discord/callback
JARVIS_DISCORD_GUILD_ID=DEINE_GUILD_ID

JARVIS_ALLOWED_DISCORD_USER_IDS=333006296611684352
JARVIS_ALLOWED_DISCORD_ROLE_IDS=

JARVIS_DASHBOARD_SESSION_IDLE_SECONDS=1800
JARVIS_DASHBOARD_SESSION_TTL_SECONDS=1800
JARVIS_DASHBOARD_COOKIE_SECURE=false
```

## Redirect URL in Discord Developer Portal

Diese Redirect URL muss in der Discord App eingetragen werden:

```text
http://46.225.14.84:8181/dashboard/auth/discord/callback
```

Bei späterem HTTPS-Betrieb entsprechend:

```text
https://DEINE_DOMAIN/dashboard/auth/discord/callback
```

## Scopes

Standard:

```text
identify
```

Wenn `JARVIS_ALLOWED_DISCORD_ROLE_IDS` gesetzt ist, wird zusätzlich benötigt:

```text
guilds.members.read
```

Rollenprüfung funktioniert nur mit:

```env
JARVIS_DISCORD_GUILD_ID
```

## Session

Nach erfolgreichem Login erzeugt das Backend einen zufälligen Session-Token.

Der Token wird nur als HttpOnly-Cookie gespeichert:

```text
jarvis_dashboard_session
```

Serverseitig wird nur diese Session im Speicher gehalten:

```text
discordUserId
roleIds
createdAt
lastActivityAt
expiresAt
```

## 30 Minuten Inaktivität

`JARVIS_DASHBOARD_SESSION_IDLE_SECONDS=1800`

Bei jeder Dashboard-Aktivität wird die Session verlängert. Wenn 30 Minuten keine Aktivität stattfindet:

- Session läuft ab.
- Cookie wird gelöscht, sobald der Browser wieder anfragt.
- Dashboard leitet auf `/dashboard/login`.

## Sicherheit

- Discord Access Tokens werden nicht gespeichert.
- Dashboard-Session ist ein zufälliger lokaler Token.
- Session-Cookie ist `HttpOnly`.
- Cookie ist `SameSite=Strict`.
- Bei HTTP muss `JARVIS_DASHBOARD_COOKIE_SECURE=false` sein.
- Bei HTTPS später auf `true` setzen.

## Wichtiges Restrisiko

HTTP über öffentliche IP ist nicht verschlüsselt. Für produktionsnahen Betrieb muss später HTTPS davor:

- Reverse Proxy
- TLS-Zertifikat
- Firewall-Regeln

## Nicht umgesetzt

- keine Benutzerverwaltung
- keine 2FA
- keine permanente Session-Datenbank
- keine CSRF-Tokens für POST-Aktionen außer OAuth State
- keine HTTPS-Konfiguration
