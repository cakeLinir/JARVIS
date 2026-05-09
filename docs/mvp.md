# JARVIS MVP

## Ziel

Beim Start des lokalen Windows-PCs soll der JARVIS-Agent automatisch starten und lokale Aufgaben sicher ausführen können. Commands kommen vom Dashboard, Discord-Bot oder später vom Voice-Modul.

## MVP-Ablauf

1. Backend läuft auf dem VPS oder lokal auf Port `8181`.
2. Lokaler Agent startet beim Windows-Login.
3. Agent sendet Status an das Backend.
4. Dashboard zeigt Agent-Status und letzte Commands.
5. Discord-Bot kann JARVIS-Commands erzeugen.
6. Agent pollt Commands vom Backend.
7. Agent führt nur lokal erlaubte Aktionen aus.
8. Agent meldet Erfolg, Fehler oder Ablehnung zurück.

## Morning-Routine

Die Morning-Routine soll:

- OBS starten oder minimieren
- Discord öffnen
- Spotify öffnen
- WhatsApp öffnen
- VS Code öffnen
- TODO-Datei öffnen
- offene TODOs lesen
- aktuellen Projektstand analysieren
- Fenster dynamisch anordnen
- Ergebnis ans Backend melden

## Not-Aus

Folgende Befehle müssen priorisiert behandelt werden:

- `Jarvis, stopp`
- `Jarvis, abbrechen`
- `Jarvis, beenden`
- Discord `/jarvis stop confirm_code: STOP`

## Akzeptanzkriterien

1. Backend startet mit `npm run build` und `npm start`.
2. Healthcheck funktioniert auf `http://localhost:8181/api/health`.
3. Agent sendet Status an `/api/agent/status`.
4. Dashboard zeigt Status ohne Secrets.
5. Discord `/jarvis status` liest Backend/Agent-Status.
6. Discord `/jarvis morning` erzeugt nur nach Bestätigung einen Command.
7. Agent claimt und verarbeitet Commands.
8. Unbekannte Apps werden nicht gestartet.
9. Fehlende Pfade werden geloggt.
10. Keine Secrets werden committed.

## Konfiguration erforderlich

- `backend/.env`
- `desktop-agent/config.local.json`
- echte lokale Programmpfade
- echte Tokens
- erlaubte Discord-User- oder Rollen-IDs
