# JARVIS Dashboard Session Fix

## Patch 015

Patch 015 ersetzt die fragile In-Memory-Dashboard-Session durch ein signiertes Session-Cookie.

## Problem

Wenn nach erfolgreichem Discord OAuth sofort wieder `/dashboard/login` erscheint, wurde entweder:

- das Session-Cookie nicht korrekt erkannt,
- die serverseitige In-Memory-Session nicht gefunden,
- oder der Backend-Prozess/Worker hatte keinen Zugriff auf die gespeicherte Session.

## Lösung

Die Session steckt jetzt als signiertes Cookie im Browser.

Eigenschaften:

```text
HttpOnly
Secure bei HTTPS
SameSite=Lax
Max-Age=1800
HMAC-SHA256 Signatur
```

Der Cookie-Inhalt enthält:

```text
discordUserId
username
globalName
roleIds
createdAt
lastActivityAt
expiresAt
nonce
```

Der Cookie wird mit `JARVIS_DASHBOARD_TOKEN` signiert.

## Inaktivität

Bei jedem Dashboard-Request wird `lastActivityAt` aktualisiert und `expiresAt` um 30 Minuten verlängert.

Nach 30 Minuten ohne Request:

- Cookie gilt als abgelaufen.
- Backend löscht ihn beim nächsten Request.
- Dashboard leitet auf `/dashboard/login`.

## Sicherheit

- Discord Access Token wird weiterhin nicht gespeichert.
- Discord Client Secret wird nicht geloggt.
- Dashboard Session Token wird nicht geloggt.
- Manipulierte Cookies werden verworfen.
- Logout löscht das Cookie im Browser.

## Grenze

Da die Session stateless ist, kann ein einzelnes Cookie serverseitig nicht vor Ablauf widerrufen werden, außer `JARVIS_DASHBOARD_TOKEN` wird rotiert. Für den MVP ist das akzeptabel.
