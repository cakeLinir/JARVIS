# JARVIS Deployment-Strategie

## Ziel

JARVIS wird lokal unter `C:\Users\hunde\Desktop\JARVIS` entwickelt, über GitHub Desktop ins Repository gepusht und auf dem Windows-VPS per Git aktualisiert.

## Grundprinzip

- Lokaler PC: Entwicklung, Windows-Agent, lokale Pfade, Voice/Wake-Word, App-Start, Fenstersteuerung.
- VPS: Backend, Dashboard, OpenAI-Service, Dev-News, Command-Routing, Agent-Status, Audit/Runtime.
- Discord-Bot: bleibt im separaten Repository `discord_bot_hundekuchenlive`.

## Ordnerrollen

| Pfad | Zielsystem | Zweck |
|---|---|---|
| `backend/` | VPS | Fastify API, Dashboard-MVP, Command-Routing, OpenAI-Service |
| `desktop-agent/` | lokaler PC | lokaler Windows-Agent |
| `scripts/` | lokal + VPS | Preflight, Autostart, VPS-Hilfsskripte |
| `docs/` | lokal + VPS | Architektur-/Betriebsdoku |
| `data/` | lokal | Beispiel-/MVP-TODOs, keine produktive Persistenz |
| `.jarvis-patch-backups/` | lokal | Patch-Backups, nicht committen |
| `logs/` | lokal | Runtime-Logs, nicht committen |

## Dateien, die niemals committed werden

```text
backend/.env
desktop-agent/config.local.json
.env
.env.local
*.sqlite3
*.db
*.log
*.jsonl
.jarvis-patch-backups/
```

## VPS-Backend-Workflow

1. Lokal entwickeln.
2. Lokal prüfen:

```powershell
.\scripts\preflight-local.ps1 -CheckLocalApi
```

3. Mit GitHub Desktop committen und pushen.
4. Auf dem VPS im Repo-Root:

```powershell
.\scripts\vps-update-backend.ps1
```

5. VPS prüfen:

```powershell
.\scripts\preflight-vps.ps1
```

6. Backend-Service/Prozess neu starten.

## Port

Der Backend-Port ist projektweit `8181`.

Grund: `8080` ist auf dem VPS bereits durch andere Software belegt.

## Discord-Bot

Der Discord-Bot wird nicht in dieses Repo integriert. Er bleibt im bestehenden Bot-Repo und spricht per HTTP mit dem JARVIS-Backend.

## Nicht umsetzen

- Keine Secrets ins Repository.
- Keine lokalen Windows-Pfade in produktive Doku als Fakt übernehmen.
- Kein Selfbot.
- Keine direkte lokale Windows-Aktion vom VPS.
- Keine Agent-Aktion ohne lokale Agent-Allowlist.
