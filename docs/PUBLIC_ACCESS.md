# JARVIS Public Backend Access

## Ziel

Das JARVIS Backend soll auf dem Windows-VPS öffentlich erreichbar sein.

Dein VPS hat aktuell die öffentliche IP:

```text
46.225.14.84
```

Der JARVIS Backend-Port bleibt:

```text
8181
```

Öffentliche Dashboard-URL:

```text
http://46.225.14.84:8181/dashboard
```

## Wichtig

Damit das Backend extern erreichbar ist, muss es auf dem VPS an `0.0.0.0` binden, nicht nur an `127.0.0.1`.

```text
JARVIS_BACKEND_HOST=0.0.0.0
JARVIS_BACKEND_PORT=8181
JARVIS_PUBLIC_BASE_URL=http://46.225.14.84:8181
```

## Konfiguration setzen

Auf dem VPS im Repo-Root:

```powershell
.\scripts\configure-public-backend.ps1
```

Das Skript setzt nur Netzwerkwerte in `backend\.env`:

```text
JARVIS_BACKEND_HOST
JARVIS_BACKEND_PORT
JARVIS_BACKEND_PUBLIC_HOST
JARVIS_BACKEND_PUBLIC_PROTOCOL
JARVIS_PUBLIC_BASE_URL
```

Es gibt keine Secrets aus.

## Backend neu starten

```powershell
.\scripts\backend-restart.ps1 -Build
```

## Prüfen

Lokal auf dem VPS:

```powershell
Invoke-RestMethod http://127.0.0.1:8181/api/health
```

Extern im Browser:

```text
http://46.225.14.84:8181/dashboard
```

## Firewall

Der VPS muss eingehende TCP-Verbindungen auf Port `8181` erlauben.

Beispiel Windows Firewall:

```powershell
New-NetFirewallRule `
  -DisplayName "JARVIS Backend 8181" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8181
```

## Sicherheitswarnung

SICHERHEITSRISIKO: Direkter HTTP-Zugriff über öffentliche IP ist nur für Testbetrieb geeignet.

Für produktiven Betrieb:

- HTTPS aktivieren
- Reverse Proxy verwenden
- Dashboard-Token stark setzen
- Firewall/IP-Restriktionen prüfen
- Rate-Limits ausbauen
- keine Secrets in Logs oder Frontend
