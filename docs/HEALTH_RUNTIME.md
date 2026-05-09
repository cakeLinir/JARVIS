# JARVIS Health & Runtime Status

## Ziel

Patch 008 ergänzt Runtime-Status für Backend, Dashboard und lokalen Agent.

## Backend

Das Backend bewertet den letzten Agent-Status als:

| State | Bedeutung |
|---|---|
| `unknown` | Noch kein Agent-Status empfangen |
| `online` | Agent hat kürzlich Status gesendet |
| `stale` | Agent-Status ist älter als Stale-Timeout |
| `offline` | Agent-Status ist älter als Offline-Timeout oder Agent meldete offline |
| `stopped` | Agent meldete gestoppt |
| `interrupted` | Agent meldete Abbruch durch Benutzer |

Standardwerte:

```text
JARVIS_AGENT_STALE_AFTER_SECONDS=45
JARVIS_AGENT_OFFLINE_AFTER_SECONDS=180
```

Diese Werte werden aktuell direkt aus `process.env` gelesen, ohne Secrets zu berühren.

## Agent Heartbeat

Der Desktop-Agent sendet periodisch `online` an `/api/agent/status`.

Konfiguration in `desktop-agent/config.local.json`:

```json
{
  "runtime": {
    "heartbeatIntervalSeconds": 30
  }
}
```

Der Wert wird begrenzt:

```text
Minimum: 10 Sekunden
Maximum: 300 Sekunden
```

## Lokale Agent-API

`GET /health` liefert ab Patch 008:

```text
runtime
configuration
voice
todo
```

Lokale Pfade und Secrets werden nicht ausgegeben.

## Dashboard

Das Dashboard zeigt einen neuen Abschnitt `Runtime`.

`GET /api/dashboard/overview` enthält zusätzlich:

```text
runtime
overview.runtimeState
```

## Sicherheitsregeln

- Lokale API bindet nur auf `127.0.0.1` oder `localhost`.
- Lokale API startet nur mit echtem Token.
- `/actions/stop` verlangt `confirm: "STOP"`.
- `/actions/morning` verlangt `confirm: "START"`.
- Health-Ausgaben enthalten keine Tokens.
- Health-Ausgaben enthalten keine lokalen Pfade.
