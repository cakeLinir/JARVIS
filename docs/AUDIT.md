# JARVIS Audit-Log

## Ziel

Das Audit-Log macht nachvollziehbar, welcher Client welchen Command angefordert, geclaimt oder abgeschlossen hat.

## MVP-Speicher

Der aktuelle MVP schreibt Audit-Events als JSON Lines in:

```text
backend/data/audit-log.jsonl
```

Dieser Speicher ist bewusst einfach gehalten. Für produktionsnahen Betrieb soll er später durch SQLite oder PostgreSQL ersetzt werden.

## Event-Felder

```text
id
timestamp
component
action
result
commandId
correlationId
actor.type
actor.id
errorCode
message
details
```

## Wichtige Regeln

- Keine Secrets im Audit-Log.
- Keine Tokens im Audit-Log.
- Keine OpenAI-Rohprompts im Audit-Log.
- Keine sensiblen Rohdaten im Audit-Log.
- Command-ID und Correlation-ID müssen reichen, um Backend-, Agent- und Bot-Ereignisse zusammenzuführen.

## Aktuelle Events

| Action | Bedeutung |
|---|---|
| `command.create` | Backend hat einen Command angenommen oder abgelehnt. |
| `command.claim` | Agent hat einen Command übernommen. |
| `command.complete` | Agent hat einen Command abgeschlossen, abgelehnt oder als fehlgeschlagen gemeldet. |
| `command.claim_expired` | Ein geclaimter Command wurde wegen Timeout erneut freigegeben. |

## Bekannte Grenzen

- JSONL ist kein transaktionaler Speicher.
- Keine Rotation implementiert.
- Keine manipulationssichere Signatur implementiert.
- Keine Benutzeroberfläche außer Dashboard-Rohansicht implementiert.

## Nächster Ausbau

1. SQLite-Tabelle `audit_events`.
2. strukturierte Query-Endpunkte.
3. Dashboard-Filter nach Command-ID und Correlation-ID.
4. Log-Rotation und Retention.
5. optional Hash-Verkettung gegen nachträgliche Manipulation.
