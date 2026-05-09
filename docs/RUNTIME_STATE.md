# JARVIS Runtime State

## Ziel

Runtime-State darf Git-Pull und Deployment nicht blockieren.

## Änderung ab Patch 011.1

Backend-Runtime-Dateien werden nicht mehr unter `backend/data/`, sondern unter folgendem Pfad geschrieben:

```text
backend/.runtime/data/
```

Betroffen:

```text
commands.json
audit-log.jsonl
```

## Grund

`backend/data/commands.json` wurde im frühen MVP als Command-Store genutzt. Auf dem VPS wird diese Datei zur Laufzeit verändert. Wenn sie von Git getrackt ist, blockiert `git pull` mit Meldungen wie:

```text
M backend/data/commands.json
Working tree ist nicht sauber.
```

## Regel

Runtime-Dateien gehören nicht ins Repository.

## Einmalige Bereinigung, falls Datei noch getrackt ist

Lokal im Entwicklungs-Repo:

```powershell
git rm --cached backend/data/commands.json
git rm --cached backend/data/audit-log.jsonl
```

Nur aus dem Git-Index entfernen, nicht zwingend lokal löschen.

Danach committen und pushen.

## VPS Sofortmaßnahme bei blockiertem Pull

Wenn auf dem VPS `backend/data/commands.json` als geändert angezeigt wird:

```powershell
Copy-Item backend\data\commands.json backend\data\commands.vps.backup.json -ErrorAction SilentlyContinue
git restore backend/data/commands.json
```

Dann erneut:

```powershell
.\scripts\vps-update-backend.ps1
```

Nach Patch 011.1 schreibt das Backend neue Runtime-Daten nach `backend/.runtime/data/`.

## Sicherheit

- Runtime-Dateien enthalten keine Secrets.
- Runtime-Dateien können Command-Metadaten enthalten.
- Runtime-Dateien werden nicht committed.
- Logs und JSONL-Dateien bleiben lokal/runtime-only.
