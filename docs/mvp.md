# JARVIS MVP

## Phase 1: stabiler Text-/Command-MVP

Akzeptanzkriterien:

- Backend baut ohne TypeScript-Fehler.
- Python-Agent kompiliert syntaktisch.
- `/api/health` funktioniert.
- `/dashboard` ist erreichbar.
- Dashboard-Overview ist per Token geschützt.
- Command-Queue hängt nicht dauerhaft bei `claimed`, sondern gibt alte Claims nach Timeout frei.
- Dev-News-Route ruft RSS/Atom-Quellen ab und gibt Titel, Kurzfassung, Quelle, Datum und Link zurück.
- Lokaler Agent kann Morning-Routine über Textmodus, Backend-Command oder lokale API starten.

## Phase 2: Voice-MVP

Akzeptanzkriterien:

- Wake-Word läuft lokal.
- OpenAI Realtime Client Secret wird über Backend erzeugt.
- Voice-Client verbindet sich per WebRTC.
- Audio-Antwort wird abgespielt.
- Tool-Call `morning_routine.start` startet lokale Agent-API `/actions/morning`.

## Phase 3: produktiver Desktop-Assistent

Akzeptanzkriterien:

- Windows-Autostart ist eingerichtet.
- Multi-Monitor-Layout ist konfigurierbar.
- Spotify-API kann Playback starten.
- VS-Code-Projektanalyse wird per OpenAI zusammengefasst.
- Dashboard kann App-Pfade und Layouts verwalten.
