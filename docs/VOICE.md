# JARVIS Voice-Control Skeleton

## Ziel

Patch 007 bereitet Voice-Control vor, ohne bereits dauerhaft Audio zu verarbeiten.

Der lokale Agent bleibt im Textmodus. Voice-Strukturen werden nur vorbereitet:

- zentrale Wake-Word-Phrasen
- zentrale Not-Aus-Phrasen
- Voice-Status
- Sicherheitsregeln für spätere STT/TTS-Integration

## Aktueller Status

**Voice-Audio ist noch nicht implementiert.**

Der Agent nutzt weiterhin Texteingabe. Die Voice-Module sind bewusst ein Skeleton.

## Not-Aus

Not-Aus-Phrasen werden zentral in `desktop-agent/src/voice/phrases.py` verwaltet.

Standard-Phrasen:

```text
jarvis, stopp
jarvis stopp
jarvis, stop
jarvis stop
jarvis, abbrechen
jarvis abbrechen
jarvis, beenden
jarvis beenden
stopp
abbrechen
```

Die lokale Textschleife prüft Stop-Phrasen vor Wake-Words. Dadurch hat Not-Aus Vorrang.

## Wake-Words

Wake-Words werden aus `voice.wakeWords` gelesen. Falls nicht gesetzt, wird `wakeWords` aus der bestehenden Agent-Konfiguration verwendet. Falls auch dort nichts gesetzt ist, gelten Defaults:

```text
guten morgen jarvis
hallo jarvis
jarvis
```

## Konfiguration

Optional in `desktop-agent/config.local.json`:

```json
{
  "voice": {
    "enabled": false,
    "mode": "text",
    "wakeWordEnabled": false,
    "sttProvider": "disabled",
    "ttsProvider": "disabled",
    "wakeWords": [
      "guten morgen jarvis",
      "hallo jarvis",
      "jarvis"
    ],
    "stopPhrases": [
      "jarvis, stopp",
      "jarvis, abbrechen",
      "jarvis, beenden"
    ]
  }
}
```

## Sicherheitsregeln für spätere Voice-Implementierung

- Keine dauerhafte Audioübertragung ohne Aktivierung.
- Wake-Word-Erkennung bleibt lokal.
- STT startet erst nach Aktivierung.
- Not-Aus muss lokal priorisiert bleiben.
- Modelltext darf keine lokale Aktion direkt ausführen.
- Jede Aktion muss weiter über validierte Commands laufen.
- Sensible Aktionen brauchen Bestätigung.
- Voice-Rohdaten dürfen nicht in Logs geschrieben werden.
- Agent-Logs dürfen keine vollständigen sensiblen Sprachinhalte enthalten.

## Nicht umgesetzt

- Mikrofonzugriff
- Wake-Word-Engine
- STT
- TTS
- WebRTC Realtime Audio
- Audio-Streaming
- Voice-Konfigurations UI
