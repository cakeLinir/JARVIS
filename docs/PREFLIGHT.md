# JARVIS Preflight

## Ziel

Patch 009 ergänzt Preflight-Skripte für lokale Entwicklung und VPS-Prüfung.

Die Skripte geben Status aus, ohne Secrets zu drucken.

## Lokaler Preflight

Pfad:

```text
scripts/preflight-local.ps1
```

Ausführen:

```powershell
cd C:\Users\hunde\Desktop\JARVIS
.\scripts\preflight-local.ps1
```

Mit lokaler Agent-API-Prüfung:

```powershell
.\scripts\preflight-local.ps1 -CheckLocalApi
```

Optionen:

```powershell
.\scripts\preflight-local.ps1 -SkipBackendBuild
.\scripts\preflight-local.ps1 -SkipAgentCompile
```

Prüft:

- erwartete Repo-Dateien
- Node/npm/Python
- Backend `.env` Status ohne Secret-Werte
- Port-Konvention `8181`
- Agent `config.json`
- Agent `config.local.json`
- Backend Build
- Python Compile
- optional lokale Agent-API `/health`

## VPS Preflight

Pfad:

```text
scripts/preflight-vps.ps1
```

Ausführen auf dem VPS im Repo-Root:

```powershell
.\scripts\preflight-vps.ps1
```

Mit anderem Port, falls bewusst geändert:

```powershell
.\scripts\preflight-vps.ps1 -ExpectedPort 8181
```

Prüft:

- relevante Backend-Dateien
- `backend\.env`
- Node/npm
- Port-Belegung
- Backend `.env` Status ohne Secret-Werte
- `npm install`
- `npm run build`

## Exit Codes

| Exit Code | Bedeutung |
|---:|---|
| `0` | keine Fehler, keine Warnungen |
| `1` | Warnungen/Konfiguration erforderlich |
| `2` | Fehler |

## Sicherheitsregeln

- Secret-Werte werden nicht ausgegeben.
- `.env` wird nur lokal gelesen.
- Es werden keine Dateien außer durch Patch 009 selbst geändert.
- Preflight führt keine Windows-Aktionen aus.
- Preflight startet kein Backend dauerhaft.
- Preflight startet keinen Agent dauerhaft.

## Patch 011.1: Runtime-Dateien

`backend/data/` enthält Runtime-Dateien wie:

```text
commands.json
audit-log.jsonl
```

Diese Dateien werden nicht committed. Damit der Ordner trotzdem auf dem VPS vorhanden bleibt, wird `backend/data/.gitkeep` verwendet.

Falls `preflight-vps.ps1` den Ordner nicht findet, erstellt es ihn lokal. Danach sollte `.gitkeep` im lokalen Repo committed werden.
