# JARVIS VPS Pull Workflow

## Ziel

Dieses Dokument beschreibt den Ablauf nach lokalem Commit/Push über GitHub Desktop.

## Voraussetzungen auf dem VPS

- Git installiert
- Node.js installiert
- npm installiert
- PowerShell
- Repository auf dem VPS ausgecheckt
- `backend/.env` auf dem VPS vorhanden
- Port `8181` verfügbar oder JARVIS-Backend läuft bereits dort

## Erstinstallation auf dem VPS

```powershell
cd C:\Pfad\zum\JARVIS
copy backend\.env.example backend\.env
notepad backend\.env
```

Danach echte Werte setzen:

```text
OPENAI_API_KEY
JARVIS_AGENT_TOKEN
JARVIS_BOT_BRIDGE_TOKEN
JARVIS_DASHBOARD_TOKEN
JARVIS_ALLOWED_DISCORD_USER_IDS
JARVIS_BACKEND_PORT=8181
```

## Update nach GitHub Desktop Push

```powershell
cd C:\Pfad\zum\JARVIS
.\scripts\vps-update-backend.ps1
```

Das Skript prüft:

- Git-Status
- Branch
- Pull von Remote
- `backend/package.json`
- `npm install`
- `npm run build`

## Danach Backend starten

Manuell im Backend-Ordner:

```powershell
cd backend
npm start
```

Wenn später ein Windows-Service oder Scheduled Task eingerichtet ist, wird dieser separat dokumentiert.

## Preflight nach Update

```powershell
.\scripts\preflight-vps.ps1
```

## Fehlerfälle

### Working tree ist dirty

Wenn lokale Änderungen auf dem VPS existieren, stoppt `vps-update-backend.ps1` standardmäßig.

Nur bewusst überschreiben oder fortsetzen:

```powershell
.\scripts\vps-update-backend.ps1 -AllowDirty
```

### Backend-Port belegt

`preflight-vps.ps1` warnt, wenn Port `8181` belegt ist. Das ist okay, wenn bereits JARVIS läuft. Wenn ein anderer Prozess den Port belegt, muss der Konflikt manuell gelöst werden.

### `.env` fehlt

`backend/.env` wird nie committed. Sie muss auf dem VPS manuell angelegt werden.
