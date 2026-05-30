# JARVIS — Offline-Fallback-Verhalten

Dieses Dokument beschreibt, was passiert wenn das Backend (VPS) nicht erreichbar ist,
und wie der Desktop-Agent beim Reconnect synchronisiert.

---

## 1. Was passiert wenn das Backend nicht erreichbar ist?

### TODO-Erstellung (Voice / Textbefehl)

| Schritt | Verhalten |
|---|---|
| `POST /api/todos` schlägt fehl | Agent schreibt TODO in `desktop-agent/.runtime/pending_queue.json` |
| TTS-Antwort | „Backend nicht erreichbar. Aufgabe wurde lokal gespeichert." |
| Lokaler Fallback | Falls konfiguriert: TODO in `config.todo.markdownPath` anhängen |

**Format `pending_queue.json`:**
```json
[
  {
    "action": "create",
    "payload": { "title": "Rechnung bezahlen", "dueDate": "2026-06-05" },
    "queuedAt": "2026-06-01T10:23:00"
  }
]
```

### Schicht-Abfrage

| Schicht-Abfrage | Verhalten |
|---|---|
| `GET /api/shifts/:date` schlägt fehl | Cache aus `desktop-agent/.runtime/cache/shifts.json` laden |
| Max. Cache-Einträge | 7 Einträge (letzte 7 abgerufene Schichten) |
| Cache-Miss | Gibt `None` zurück; Agent loggt WARN |
| TTS-Antwort | „Schicht aus lokalem Cache geladen." |

**Cache-Pfad:** `desktop-agent/.runtime/cache/shifts.json`

### TODO-Abfrage (heute fällig)

| Abfrage | Verhalten |
|---|---|
| `GET /api/todos/today` schlägt fehl | Cache aus `desktop-agent/.runtime/cache/todos_today.json` |
| Cache-Alter | Wird bei jedem erfolgreichen Sync überschrieben (kein TTL) |
| Cache-Miss | Leere Liste → TTS: „Keine TODOs im Cache gefunden." |

### Voice-Intent (Spracheingabe offline)

```
Nutzer: "Erinnere mich morgen an Rechnung bezahlen"
→ Intent-Router: todo.create erkannt
→ Backend-Call schlägt fehl
→ pending_queue.json: { "action": "create", ... }
→ TTS: "Backend offline. Aufgabe lokal gespeichert."
```

### Schicht-Eintrag offline

```
Nutzer: "Morgen habe ich Tagschicht"
→ Intent-Router: shift.set erkannt
→ Backend-Call schlägt fehl
→ pending_queue.json: { "action": "update", "endpoint": "/api/shifts", ... }
→ TTS: "Schicht konnte nicht eingetragen werden. Im Cache vorgemerkt."
```

---

## 2. Reconnect: automatische Synchronisation

### Trigger

Der Sync-Vorgang wird ausgelöst wenn:
1. `sync_todos_from_backend()` erfolgreich eine Antwort erhält
2. Agent-Heartbeat nach erfolgloser Phase wieder antwortet
3. Manuell über Local API: `POST /actions/sync` *(geplant)*

### Ablauf `_flush_pending_queue()`

```
pending_queue.json laden
  ↓
Für jeden Eintrag:
  action=create → POST /api/todos
  action=update → PATCH /api/todos/:id
  action=complete → POST /api/todos/:id/complete
  action=shift   → POST /api/shifts
  ↓
Erfolgreiche Einträge: aus Queue entfernen
Fehlgeschlagene: in Queue behalten (Retry beim nächsten Sync)
  ↓
pending_queue.json überschreiben
```

### Conflict-Handling

| Szenario | Verhalten |
|---|---|
| TODO wurde auf Backend erstellt (z.B. via Dashboard) während Agent offline war | Kein Conflict — TODO-IDs sind UUIDs, keine Überschneidung |
| Schicht für selbes Datum bereits vorhanden (409) | Queue-Eintrag wird verworfen + geloggt: WARN shift_conflict |
| TODO-ID nicht mehr vorhanden (404) | Queue-Eintrag wird verworfen + geloggt: WARN todo_not_found |
| Netzwerk-Fehler beim Flush | Eintrag bleibt in Queue, Retry beim nächsten Sync |

### Logging

```
[INFO]  Pending-Queue flushen: 3 Einträge.
[OK]    Pending-Queue: 2 Einträge gesendet, 1 verbleibend.
[WARN]  Queue-Flush Fehler (shift): shift_conflict — Eintrag verworfen.
```

---

## 3. Konfiguration

```json
{
  "runtime": {
    "heartbeatIntervalSeconds": 30
  }
}
```

Die `pending_queue.json` und Caches liegen unter:
```
desktop-agent/
  .runtime/
    pending_queue.json       ← Offline-Queue
    cache/
      todos_today.json       ← TODO-Cache
      shifts.json            ← Schicht-Cache (max. 7 Einträge)
```

---

## 4. Bekannte Einschränkungen

- **Voice-Commands offline**: Spracheingaben werden in der Queue gespeichert, aber die TTS-Antwort bestätigt nur die lokale Speicherung — keine Garantie der Ausführung.
- **Schicht-Cache**: Nur die letzten 7 abgerufenen Schichten sind offline verfügbar. Schichten die nie abgerufen wurden, sind nicht cached.
- **TODO-Cache-Alter**: Der Cache wird nicht nach Zeit invalidiert — nach längerem Offline kann er veraltet sein.
