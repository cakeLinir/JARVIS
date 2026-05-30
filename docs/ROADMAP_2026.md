# JARVIS — Entwicklungs-Roadmap

> **Stand:** 30.05.2026  
> **Basis:** Vollständige Analyse von [`cakeLinir/JARVIS`](https://github.com/cakeLinir/JARVIS), [`AnubhavChaturvedi-GitHub/jarvis-ai-assistant`](https://github.com/AnubhavChaturvedi-GitHub/jarvis-ai-assistant), [`dscripka/openWakeWord`](https://github.com/dscripka/openWakeWord)  
> **Ziel:** Evolutionäre Weiterentwicklung des bestehenden MVP zu einem echten persönlichen Assistenten mit TODOs, Schichtlogik, Streaming-Empfehlung und Sprachsteuerung

---

## Architektur-Prinzipien

| **Schicht**                                                         | **Rolle**                                           |
| ------------------------------------------------------------------- | --------------------------------------------------- |
| **Backend ([Fastify](https://fastify.dev)/Node.js)**                | Zentrale Wahrheit, Persistenz, Planungslogik, API   |
| **Desktop-Agent (Python)**                                          | Lokale Ausführung, Voice, Interaktion, Automationen |
| **Dashboard ([React](https://react.dev)/[Vite](https://vite.dev))** | Einsicht, Bearbeitung, Monitoring                   |
| **Discord-Bot (extern)**                                            | Trigger & Fernsteuerung                             |

---

## Übersicht aller Milestones

| **#**                                                            | **Milestone**                     | **Prio**    | **Geschätzte Zeit** |
| ---------------------------------------------------------------- | --------------------------------- | ----------- | ------------------- |
| [`M0`](#m0--code-bereinigung--fundament)                         | Code-Bereinigung & Fundament      | 🔴 KRITISCH | 2–3h                |
| [`M1`](#m1--todo-domäne-backend--sync)                           | TODO-Domäne: Backend + Sync       | 🔴 HOCH     | 4–6h                |
| [`M2`](#m2--schicht-domäne-backend--agent)                       | Schicht-Domäne: Backend + Agent   | 🔴 HOCH     | 3–4h                |
| [`M3`](#m3--streaming-empfehlungs-engine)                        | Streaming-Empfehlungs-Engine      | 🟡 MITTEL   | 1–2h                |
| [`M4`](#m4--intent-parser--sprachsteuerung-für-todos--schichten) | Intent-Parser + Sprachsteuerung   | 🟡 MITTEL   | 5–8h                |
| [`M5`](#m5--automation-erweiterungen)                            | Automation-Erweiterungen          | 🟢 NIEDRIG  | 2–3h                |
| [`M6`](#m6--dashboard-vollausbau)                                | Dashboard-Vollausbau              | 🟡 MITTEL   | 4–6h                |
| [`M7`](#m7--voice-pipeline-vollausbau)                           | Voice-Pipeline Vollausbau         | 🟡 MITTEL   | 6–10h               |
| [`M8`](#m8--stabilisierung--produktionsreife)                    | Stabilisierung & Produktionsreife | 🟢 NIEDRIG  | 3–4h                |
| **Gesamt**                                                       |                                   |             | **~30–46h**         |

### Empfohlene Reihenfolge

```
M0 → M1 → M2 → M3 → M4 (Text) → M6 → M4 (Voice) → M5 → M7 → M8
```

---

## M0 — Code-Bereinigung & Fundament

> **Ziel:** Technische Schulden tilgen, bevor neue Domänen gebaut werden.  
> **Geschätzte Zeit:** 2–3h  
> **Priorität:** 🔴 KRITISCH — Basis für alle weiteren Milestones

### Problem

[`desktop-agent/src/main.py`](../desktop-agent/src/main.py) hat 780 Zeilen und enthält Logik, die in mindestens 4 verschiedene Module gehört. Das macht Erweiterungen fehleranfällig und Tests unmöglich.

### Zu ändernde Dateien

#### Desktop-Agent — Aufteilen von `main.py`

**Neue Dateien anlegen:**

- [`desktop-agent/src/core/logging.py`](../desktop-agent/src/core/logging.py)
  - Noise-Filter-Konstanten (`JARVIS_PROJECT_ANALYSIS_EXCLUDE_DIRS`, `JARVIS_PROJECT_ANALYSIS_EXCLUDE_FILES`)
  - `jarvis_is_noise_path()`, `jarvis_is_todo_noise_path()`
  - `jarvis_normalize_log_text()`, `jarvis_normalize_log_event()`, `jarvis_should_suppress_log()`
  - `configure_console_encoding()`
  - `log()` Funktion

- [`desktop-agent/src/core/config_loader.py`](../desktop-agent/src/core/config_loader.py)
  - `load_json_file()`, `deep_merge()`, `load_config()`
  - Konstanten: `AGENT_DIR`, `JARVIS_ROOT`, `CONFIG_PATH`, `LOCAL_CONFIG_PATH`, `LOG_DIR`

- [`desktop-agent/src/routines/morning.py`](../desktop-agent/src/routines/morning.py)
  - `run_morning_routine()`, `run_todo_review_for_morning()`
  - `send_morning_log_safe()`, `get_todo_status_safe()`
  - `analyze_current_project()`, `arrange_windows()`
  - `open_todo()`, `read_todos()`

- [`desktop-agent/src/handlers/command_handler.py`](../desktop-agent/src/handlers/command_handler.py)
  - `handle_backend_command()`, `complete_backend_command()`

**Bestehende Dateien anpassen:**

- [`desktop-agent/src/main.py`](../desktop-agent/src/main.py) → Schlanker Orchestrator (~80 Zeilen)
  - Imports aus neuen Modulen
  - `main()`, `heartbeat_loop()`, `command_poll_loop()`
  - `stop_event`, Thread-Start, Input-Loop

#### Desktop-Agent — TODO-Module konsolidieren

- [`desktop-agent/src/todo/todo_review.py`](../desktop-agent/src/todo/todo_review.py) + [`desktop-agent/src/todo/todo_review_command.py`](../desktop-agent/src/todo/todo_review_command.py)
  → zusammenführen zu [`desktop-agent/src/todo/review.py`](../desktop-agent/src/todo/review.py)

#### Backend — DB-Vorbereitung

- [`backend/src/services/db.ts`](../backend/src/services/db.ts) neu anlegen
  - SQLite-Initialisierung via [`better-sqlite3`](https://github.com/WiseLibs/better-sqlite3)
  - Schema-Migrations-Mechanismus (Versionstabelle)
  - Exportiert: `getDb()`, `runMigrations()`
- [`backend/package.json`](../backend/package.json) erweitern: `"better-sqlite3"` als Dependency

### Keine neuen Features in M0

Nur Verschieben, Kapseln, Vorbereiten. Jeder Schritt mit manuellem Agent-Start testen.

---

## M1 — TODO-Domäne: Backend + Sync

> **Ziel:** Echte strukturierte TODOs mit vollständigem CRUD. Backend als zentrale Wahrheit, Agent als Sync-Client.  
> **Geschätzte Zeit:** 4–6h  
> **Abhängigkeit:** [M0](#m0--code-bereinigung--fundament) (DB-Layer muss stehen)

### Datenmodell (SQLite — Backend)

```sql
CREATE TABLE todos (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  description   TEXT,
  status        TEXT NOT NULL DEFAULT 'open',     -- open | in_progress | done | cancelled
  priority      TEXT NOT NULL DEFAULT 'normal',   -- low | normal | high | critical
  category      TEXT,                             -- arbeit | haushalt | streaming | privat | custom
  due_date      TEXT,                             -- YYYY-MM-DD
  due_time      TEXT,                             -- HH:MM (optional)
  start_date    TEXT,                             -- YYYY-MM-DD (optional)
  recurrence    TEXT DEFAULT 'none',              -- none | daily | weekly | monthly
  reminder_min  INTEGER,                          -- Minuten vor Fälligkeit
  shift_id      TEXT,                             -- FK → shifts.id (optional)
  source        TEXT DEFAULT 'manual',            -- voice | discord | dashboard | agent | manual
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  completed_at  TEXT,
  history       TEXT DEFAULT '[]'                 -- JSON-Array: [{timestamp, field, old_value, new_value, source}]
);
```

### Backend — neue Dateien

- [`backend/src/services/todo.service.ts`](../backend/src/services/todo.service.ts)
  - `createTodo(data)`, `getTodoById(id)`, `updateTodo(id, data)`
  - `deleteTodo(id)` (soft-delete: status → cancelled)
  - `listTodos(filter)`, `getTodosToday()`
  - `completeTodo(id)` — setzt status=done, completed_at
  - Audit-Event bei jeder Änderung

- [`backend/src/routes/todo.routes.ts`](../backend/src/routes/todo.routes.ts)

| **Methode** | **Pfad**                  | **Auth** | **Beschreibung**                               |
| ----------- | ------------------------- | -------- | ---------------------------------------------- |
| `GET`       | `/api/todos`              | Token    | Liste mit Filtern (status, priority, due_date) |
| `POST`      | `/api/todos`              | Token    | TODO erstellen                                 |
| `GET`       | `/api/todos/today`        | Token    | Heute fällig + überfällig                      |
| `GET`       | `/api/todos/:id`          | Token    | Einzeln                                        |
| `PATCH`     | `/api/todos/:id`          | Token    | Update (Felder einzeln)                        |
| `DELETE`    | `/api/todos/:id`          | Token    | Soft-Delete                                    |
| `POST`      | `/api/todos/:id/complete` | Token    | Als erledigt markieren                         |

- [`backend/src/server.ts`](../backend/src/server.ts) erweitern: `todoRoutes` registrieren

### Desktop-Agent — neue/geänderte Dateien

- [`desktop-agent/src/todo/sync_client.py`](../desktop-agent/src/todo/sync_client.py) _(NEU)_
  - `sync_todos_from_backend(config, log)` — Backend → lokaler Cache
  - `push_todo_to_backend(config, log, todo)` — lokal → Backend
  - `update_todo_on_backend(config, log, todo_id, data)` — PATCH
  - Offline-Flag: bei Verbindungsfehler lokal cachen, bei Reconnect pushen

- [`desktop-agent/src/integrations/backend_client.py`](../desktop-agent/src/integrations/backend_client.py) erweitern
  - `create_todo(config, log, data)` → `POST /api/todos`
  - `update_todo(config, log, todo_id, data)` → `PATCH /api/todos/:id`
  - `get_todos_today(config, log)` → `GET /api/todos/today`
  - `complete_todo(config, log, todo_id)` → `POST /api/todos/:id/complete`

- [`desktop-agent/src/local_api.py`](../desktop-agent/src/local_api.py) erweitern
  - `POST /todos` → ruft `create_todo()` auf
  - `PATCH /todos/:id` → ruft `update_todo()` auf
  - `GET /todos/today` → gibt heutige TODOs zurück

- [`desktop-agent/src/todo/provider.py`](../desktop-agent/src/todo/provider.py) bleibt als lokaler Offline-Cache

### Migration vom alten TODO-System

1. Bestehende Markdown/JSON/SQLite-TODOs werden beim ersten Sync als `source=migration` ins Backend importiert
2. `todo/provider.py` ruft zukünftig primär `sync_client.py` auf
3. Alter lokaler Code bleibt als Fallback erhalten (kein Löschen)

---

## M2 — Schicht-Domäne: Backend + Agent

> **Ziel:** Schichten zuverlässig speichern, Verfügbarkeit und Ruhezeiten ableiten.  
> **Geschätzte Zeit:** 3–4h  
> **Abhängigkeit:** [M0](#m0--code-bereinigung--fundament) (DB-Layer)

### Datenmodell (SQLite — Backend)

```sql
CREATE TABLE shift_types (
  type                 TEXT PRIMARY KEY,
  label                TEXT NOT NULL,
  default_start        TEXT,                -- HH:MM
  default_end          TEXT,                -- HH:MM
  crosses_midnight     INTEGER DEFAULT 0,
  rest_hours_before    INTEGER DEFAULT 8,
  rest_hours_after     INTEGER DEFAULT 8,
  stream_recommendation TEXT,              -- free | conditional | discouraged | blocked
  stream_reason        TEXT
);

CREATE TABLE shifts (
  id               TEXT PRIMARY KEY,
  date             TEXT NOT NULL,           -- YYYY-MM-DD (Startdatum)
  type             TEXT NOT NULL,           -- FK → shift_types.type
  start_time       TEXT,                    -- HH:MM (überschreibt Default)
  end_time         TEXT,                    -- HH:MM
  crosses_midnight INTEGER DEFAULT 0,
  end_date         TEXT,                    -- YYYY-MM-DD wenn crosses_midnight
  notes            TEXT,
  source           TEXT DEFAULT 'manual',
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);
```

### Vordefinierte Schichttypen (Seed-Daten)

| **type**     | **label**      | **Start** | **Ende** | **Über Mitternacht** | **Stream-Empfehlung** |
| ------------ | -------------- | --------- | -------- | -------------------- | --------------------- |
| `tag`        | Tagschicht     | 07:00     | 19:00    | Nein                 | `conditional`         |
| `nacht`      | Nachtschicht   | 19:00     | 07:00    | Ja                   | `discouraged`         |
| `fakt_frueh` | FAKT IST! Früh | 07:00     | 14:30    | Nein                 | `conditional`         |
| `fakt_spaet` | FAKT IST! Spät | 14:30     | 21:30    | Nein                 | `discouraged`         |
| `frei`       | Frei           | —         | —        | Nein                 | `free`                |

### Backend — neue Dateien

- [`backend/src/services/shift.service.ts`](../backend/src/services/shift.service.ts)
  - `createShift(data)`, `getShiftByDate(date)`, `updateShift(id, data)`
  - `listShifts(from, to)` — für Kalenderansicht
  - `getShiftTypes()` — statische Referenz
  - Conflict-Detection: Zwei Schichten pro Tag → 409-Response

- [`backend/src/services/availability.service.ts`](../backend/src/services/availability.service.ts)
  - `getAvailability(date)` → berechnet aus Schicht + benachbarten Schichten
  - Gibt zurück: `streamRecommendation`, `streamWindow`, `recoveryWindow`, `reason`

- [`backend/src/routes/shift.routes.ts`](../backend/src/routes/shift.routes.ts)

| **Methode** | **Pfad**                  | **Auth** | **Beschreibung**                     |
| ----------- | ------------------------- | -------- | ------------------------------------ |
| `GET`       | `/api/shifts`             | Token    | Liste (von/bis-Filter)               |
| `POST`      | `/api/shifts`             | Token    | Schicht eintragen                    |
| `GET`       | `/api/shifts/today`       | Token    | Heutige Schicht                      |
| `GET`       | `/api/shifts/tomorrow`    | Token    | Morgige Schicht                      |
| `GET`       | `/api/shifts/:date`       | Token    | Schicht für Datum (YYYY-MM-DD)       |
| `PATCH`     | `/api/shifts/:id`         | Token    | Update                               |
| `DELETE`    | `/api/shifts/:id`         | Token    | Löschen                              |
| `GET`       | `/api/availability/:date` | Token    | Verfügbarkeit + Streaming-Empfehlung |
| `GET`       | `/api/shift-types`        | Token    | Alle Schichttypen                    |

### Desktop-Agent — neue/geänderte Dateien

- [`desktop-agent/src/shifts/shift_client.py`](../desktop-agent/src/shifts/shift_client.py) _(bestehenden Ordner befüllen!)_
  - `get_shift(config, log, date)` → `GET /api/shifts/:date`
  - `set_shift(config, log, date, type)` → `POST /api/shifts`
  - `get_availability(config, log, date)` → `GET /api/availability/:date`
  - Lokaler Cache: letzte bekannte Schicht in `config.local.json` speichern

- [`desktop-agent/src/scheduler.py`](../desktop-agent/src/scheduler.py) erweitern _(nicht neu schreiben!)_
  - `_get_shift_context(date)` → ruft `shift_client.get_shift()` auf
  - `_should_run()` prüft neues Feld `shiftCondition` in Routine-Config
  - Beispiel-Routine-Config:

```json
{
  "name": "morning_routine",
  "time": "07:00",
  "days": ["mo", "di", "mi", "do", "fr"],
  "shiftTypes": ["tag", "fakt_frueh"],
  "enabled": true
}
```

- [`desktop-agent/src/integrations/backend_client.py`](../desktop-agent/src/integrations/backend_client.py) erweitern
  - `set_shift(config, log, date, type)` → `POST /api/shifts`
  - `get_shift(config, log, date)` → `GET /api/shifts/:date`

---

## M3 — Streaming-Empfehlungs-Engine

> **Ziel:** Intelligente, begründete Streaming-Empfehlung auf Basis von Schicht, Erholung und Tageszeit.  
> **Geschätzte Zeit:** 1–2h  
> **Abhängigkeit:** [M2](#m2--schicht-domäne-backend--agent) (Schicht-Domäne)

### Regelwerk (implementiert in [`availability.service.ts`](../backend/src/services/availability.service.ts))

| **Situation**                        | **Zeitfenster** | **Empfehlung** | **Begründung**                              |
| ------------------------------------ | --------------- | -------------- | ------------------------------------------- |
| Abend VOR Tagschicht (07:00 Start)   | bis 22:00 Uhr   | `conditional`  | Stream ok, aber früh schlafen               |
|                                      | ab 22:00 Uhr    | `discouraged`  | Tagschicht morgen früh — lieber schlafen    |
| Abend VOR Nachtschicht (19:00 Start) | bis 17:00 Uhr   | `conditional`  | Letzter Stream vor der Schicht              |
|                                      | ab 17:00 Uhr    | `blocked`      | Nachtschicht gleich — keine Zeit für Stream |
| Nach Nachtschicht (Ende 07:00)       | bis 13:00 Uhr   | `blocked`      | Erst schlafen nach der Nacht                |
|                                      | 13:00–18:00     | `conditional`  | Nach dem Schlaf: kurzer Stream ok           |
|                                      | ab 18:00 Uhr    | `discouraged`  | Nächste Nachtschicht naht ggf.              |
| Abend VOR FAKT Früh (07:00 Start)    | —               | wie Tagschicht | Identische Regel                            |
| Abend VOR FAKT Spät (14:30 Start)    | bis 12:00 Uhr   | `conditional`  | Morgens ok, Schicht erst Mittag             |
|                                      | 12:00–14:30     | `discouraged`  | Vorbereitung auf Spätschicht                |
|                                      | ab 14:30        | `blocked`      | Schicht läuft                               |
| Nach FAKT Spät (Ende 21:30)          | bis 23:00 Uhr   | `conditional`  | Kurzer entspannter Stream ok                |
|                                      | ab 23:00 Uhr    | `discouraged`  | Langsam ausklingen nach Schicht             |
| Freier Tag                           | ganztägig       | `free`         | Stream jederzeit möglich                    |

### API-Response-Format (`GET /api/availability/:date`)

```json
{
  "date": "2026-05-31",
  "shift": {
    "type": "nacht",
    "label": "Nachtschicht",
    "start": "19:00",
    "end": "07:00",
    "crossesMidnight": true,
    "endDate": "2026-06-01"
  },
  "streamRecommendation": "blocked",
  "streamWindow": null,
  "recoveryWindowStart": null,
  "recoveryWindowEnd": "19:00",
  "reason": "Nachtschicht heute ab 19:00 — Stream nicht empfohlen, Energie sparen",
  "restHoursBefore": 8,
  "restHoursAfter": 8
}
```

### Agent-Integration

- Intent `stream.query` → ruft `GET /api/availability/today` ab
- TTS-Antwort basiert auf `streamRecommendation` + `reason`

---

## M4 — Intent-Parser + Sprachsteuerung für TODOs & Schichten

> **Ziel:** Natürliche deutsche Spracheingaben in strukturierte Backend-Aktionen überführen.  
> **Geschätzte Zeit:** 5–8h  
> **Abhängigkeit:** [M1](#m1--todo-domäne-backend--sync), [M2](#m2--schicht-domäne-backend--agent) (Backend-Domains müssen stehen)  
> **Hinweis:** Erst Text-basiert implementieren, Voice in [M7](#m7--voice-pipeline-vollausbau) dazuschalten

### Neue Datei: [`desktop-agent/src/integrations/intent_router.py`](../desktop-agent/src/integrations/intent_router.py)

Aufgebaut auf bestehendem [`ai_brain.py`](../desktop-agent/src/integrations/ai_brain.py) (OpenAI-Client bereits vorhanden).

#### Intent-Klassen und Slot-Felder

| **Intent**             | **Beispiele**                                                 | **Slots**                                                                          |
| ---------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `todo.create`          | „Erinnere mich morgen an Rechnung bezahlen"                   | `title`, `due_date`, `reminder_min`                                                |
| `todo.create`          | „TODO: Steuererklärung bis Freitag"                           | `title`, `due_date`                                                                |
| `todo.update_priority` | „Mach das wichtig" / „Das ist kritisch"                       | `todo_ref`, `priority`                                                             |
| `todo.reschedule`      | „Verschiebe das auf Sonntag"                                  | `todo_ref`, `due_date`                                                             |
| `todo.complete`        | „Erledigt" / „Das ist fertig" / „Abhaken"                     | `todo_ref`                                                                         |
| `todo.set_reminder`    | „Erinnere mich zwei Stunden vorher"                           | `todo_ref`, `reminder_offset_min`                                                  |
| `todo.query`           | „Was steht heute an?" / „Meine offenen TODOs"                 | `filter`                                                                           |
| `shift.set`            | „Morgen habe ich Tagschicht"                                  | `date`, `type=tag`                                                                 |
| `shift.set`            | „Morgen habe ich Nachtschicht"                                | `date`, `type=nacht`                                                               |
| `shift.set`            | „Morgen ist Fakt Ist früh"                                    | `date`, `type=fakt_frueh`                                                          |
| `shift.set`            | „Morgen ist Fakt Ist spät"                                    | `date`, `type=fakt_spaet`                                                          |
| `shift.set`            | „Morgen habe ich Frei"                                        | `date`, `type=frei`                                                                |
| `shift.query`          | „Was habe ich morgen?" / „Welche Schicht diese Woche?"        | `date`                                                                             |
| `stream.query`         | „Streamen heute Abend sinnvoll?" / „Kann ich heute streamen?" | `date`                                                                             |
| `morning_routine`      | „Guten Morgen Jarvis"                                         | —                                                                                  |
| `app.open`             | „Öffne Discord" / „Starte OBS"                                | `app_name`                                                                         |
| `system.stop`          | „Jarvis, beenden" / „Jarvis, stopp"                           | —                                                                                  |
| `unknown`              | alles andere                                                  | → [`ai_brain.py`](../desktop-agent/src/integrations/ai_brain.py) für freie Antwort |

### Datums-Parsing (deutsch)

```python
RELATIVE_DATES = {
    "heute":           lambda: today(),
    "morgen":          lambda: today() + 1,
    "übermorgen":      lambda: today() + 2,
    "nächsten montag": lambda: next_weekday(0),
    "nächsten dienstag": lambda: next_weekday(1),
    # ... alle Wochentage
    "sonntag":         lambda: next_weekday(6),
}
# Absolut: "am 3. Juni", "3.6.", "03.06.2026"
```

#### Mehrdeutigkeits-Behandlung

- `todo_ref` ohne konkreten Bezug → JARVIS fragt nach:  
  `"Welche Aufgabe meinst du? [1] Rechnung bezahlen [2] Einkaufen [3] Arzt anrufen"`
- Intent-Konfidenz < 0.75 → immer mit Bestätigung:  
  `"Soll ich [Aktion] ausführen?"`
- Widersprüchliche Schicht für gleichen Tag →  
  `"Du hast für morgen bereits Tagschicht eingetragen. Überschreiben?"`

### Geänderte Dateien

- [`desktop-agent/src/voice/phrases.py`](../desktop-agent/src/voice/phrases.py) erweitern:

```python
SHIFT_PHRASES = {
    "tagschicht":      "tag",
    "nachtschicht":    "nacht",
    "fakt ist früh":   "fakt_frueh",
    "fakt früh":       "fakt_frueh",
    "fakt ist spät":   "fakt_spaet",
    "fakt spät":       "fakt_spaet",
    "frei":            "frei",
    "freier tag":      "frei",
    "freizeit":        "frei",
}

TODO_CREATION_TRIGGERS = [
    "erinnere mich", "erinnere mich an", "nicht vergessen",
    "todo:", "aufgabe:", "merk dir:", "auf die liste",
]
```

- [`desktop-agent/src/handlers/command_handler.py`](../desktop-agent/src/handlers/command_handler.py) erweitern:
  - Neuer Command-Typ `voice_intent` → ruft `intent_router.route()` auf
  - Mapping Intent → Backend-Action

---

## M5 — Automation-Erweiterungen

> **Ziel:** Nützliche Features aus [`AnubhavChaturvedi-GitHub/jarvis-ai-assistant`](https://github.com/AnubhavChaturvedi-GitHub/jarvis-ai-assistant) portieren.  
> **Geschätzte Zeit:** 2–3h  
> **Abhängigkeit:** keine (eigenständig)

### Neue Dateien im Agent

- [`desktop-agent/src/execution/system_control.py`](../desktop-agent/src/execution/system_control.py) _(NEU)_
  - Basis: `Features/set_get_volume.py` + `Features/set_br.py` + `Features/br_persentage.py`
  - `set_volume(level: int)`, `get_volume() -> int`
  - `set_brightness(level: int)`, `get_brightness() -> int`

- [`desktop-agent/src/execution/system_info.py`](../desktop-agent/src/execution/system_info.py) erweitern
  - Basis: `Automation/Battery.py` + `Features/check_running_app.py`
  - `get_battery_status() -> dict` (percent, plugged)
  - `is_app_running(name: str) -> bool`

- [`desktop-agent/src/execution/media_control.py`](../desktop-agent/src/execution/media_control.py) _(NEU)_
  - Basis: `Automation/Play_Music_YT.py` + `Automation/playmusic_Sfy.py`
  - `play_on_youtube(query: str)` — öffnet Browser mit Suche
  - `play_on_spotify(query: str)` — öffnet Spotify mit Suche
  - Allowlist-Pflicht: nur auf freigegebenen Plattformen

- [`desktop-agent/src/execution/audio_check.py`](../desktop-agent/src/execution/audio_check.py) _(NEU)_
  - Basis: `Features/mike_health.py` + `Features/speaker_health.py`
  - `check_microphone() -> dict` (status, device)
  - `check_speaker() -> dict` (status, device)

- [`desktop-agent/src/execution/web_tools.py`](../desktop-agent/src/execution/web_tools.py) _(NEU)_
  - Basis: `Automation/Web_Open.py` + `Automation/Web_Data.py`
  - `open_url(url: str)` (mit Allowlist-Check)
  - `fetch_page_title(url: str) -> str`

### Geänderte Dateien

- [`desktop-agent/src/handlers/command_handler.py`](../desktop-agent/src/handlers/command_handler.py) erweitern:
  - Neue Command-Typen: `set_volume`, `play_music`, `system_info`, `audio_check`
- [`desktop-agent/src/local_api.py`](../desktop-agent/src/local_api.py) erweitern:
  - `POST /actions/volume`, `GET /actions/system-info`

### Was NICHT portiert wird

| **Feature**                         | **Grund**                           |
| ----------------------------------- | ----------------------------------- |
| `Whatsapp_automation/`              | PyWhatKit zu fragil, nicht relevant |
| `NetHyTechSTT/`                     | Eigene STT bereits vorhanden        |
| `Automation/tab_automation.py`      | Selenium-abhängig, instabil         |
| `Automation/scrool_system.py`       | Kein Use-Case                       |
| Root-Files (`co_brain.py`, `ui.py`) | Monolithisch, nicht übertragbar     |

---

## M6 — Dashboard-Vollausbau

> **Ziel:** Dashboard zeigt alle neuen Domänen — TODOs, Schichten, Streaming-Empfehlung, Routinen.  
> **Geschätzte Zeit:** 4–6h  
> **Abhängigkeit:** [M1](#m1--todo-domäne-backend--sync), [M2](#m2--schicht-domäne-backend--agent), [M3](#m3--streaming-empfehlungs-engine) (Backend-APIs müssen stehen)

### Neue React-Seiten/Komponenten

- [`dashboard/src/pages/TodoPage.tsx`](../dashboard/src/pages/TodoPage.tsx)
  - Liste aller TODOs mit Filtern (Status, Priorität, Fälligkeit)
  - Inline-Status-Toggle, Prioritäts-Badge
  - Neues-TODO-Modal
  - Schnell-Actions: „Erledigt", „Verschieben", „Priorität ändern"

- [`dashboard/src/pages/ShiftCalendarPage.tsx`](../dashboard/src/pages/ShiftCalendarPage.tsx)
  - Wochenansicht mit Schichtfarben
  - Schicht-Eintragen-Modal (Typ + optionale Zeiten)
  - Streaming-Ampel pro Tag (Farbe = Empfehlung)

- [`dashboard/src/components/AvailabilityWidget.tsx`](../dashboard/src/components/AvailabilityWidget.tsx)
  - Auf der Startseite: Heute + Morgen
  - Schicht-Typ + Icon + Streaming-Ampel
  - Bei `blocked`: roter Badge — bei `free`: grüner Badge

- [`dashboard/src/pages/RoutinesPage.tsx`](../dashboard/src/pages/RoutinesPage.tsx)
  - Übersicht aller konfigurierten Routinen
  - Nächster Trigger (Datum + Uhrzeit)
  - Schichtbedingungen anzeigen

### Geänderte Dateien

- [`backend/src/routes/dashboard.routes.ts`](../backend/src/routes/dashboard.routes.ts) — Overview-Endpoint erweitern:
  - TODO-Count (offen, heute fällig, überfällig)
  - Heutige + morgige Schicht
  - Aktuelle Streaming-Empfehlung

- [`dashboard/src/pages/OverviewPage.tsx`](../dashboard/src/pages/OverviewPage.tsx) _(bestehend)_ — neue Widgets einbauen

---

## M7 — Voice-Pipeline Vollausbau

> **Ziel:** JARVIS hört permanent zu. Wake-Word → STT → Intent → Aktion → TTS.  
> **Geschätzte Zeit:** 6–10h  
> **Abhängigkeit:** [M4](#m4--intent-parser--sprachsteuerung-für-todos--schichten) (Intent-Router muss stehen)

### Vollständige Pipeline

```
[Mikrofon]
    │  kontinuierlicher Audio-Stream
    ▼
[wake_word.py — openWakeWord "hey_jarvis"]
    │  Aktivierung erkannt
    ▼
[stt_service.py — Whisper / OpenAI STT]
    │  Transkript: "erinnere mich morgen an Rechnung bezahlen"
    ▼
[intent_router.py — OpenAI Function Calling]
    │  Intent: todo.create | slots: {title, due_date}
    ▼
[command_handler.py — Backend-API-Aufruf]
    │  TODO erstellt, Response
    ▼
[tts_service.py — Sprach-Ausgabe]
    "Aufgabe angelegt: Rechnung bezahlen, fällig morgen."
```

### Geänderte Dateien

- [`desktop-agent/src/voice/wake_word.py`](../desktop-agent/src/voice/wake_word.py) _(bereits vorhanden, vollständig aktivieren)_
  - [openWakeWord](https://github.com/dscripka/openWakeWord) `hey_jarvis`-Modell laden
  - Aktivierungs-Callback → STT starten
  - Konfigurierbare Schwelle (`threshold`) aus `config.json`
  - [Silero VAD](https://github.com/snakers4/silero-vad) aktivieren: `vad_threshold: 0.5`

- [`desktop-agent/src/voice/stt_service.py`](../desktop-agent/src/voice/stt_service.py) erweitern
  - Segment-Aufnahme nach Wake-Word (bis Stille, max. 8 Sekunden)
  - [Whisper](https://github.com/openai/whisper)-Transkription (lokal oder [OpenAI STT API](https://platform.openai.com/docs/guides/speech-to-text))

- [`desktop-agent/src/voice/tts_service.py`](../desktop-agent/src/voice/tts_service.py) erweitern
  - TTS-Antworten für alle Intent-Typen
  - Fehlerfall: „Ich habe das nicht verstanden, bitte wiederholen."

- [`desktop-agent/src/voice/controller.py`](../desktop-agent/src/voice/controller.py) erweitern
  - Vollständige Pipeline verdrahten
  - Hintergrund-Listener-Thread

- [`desktop-agent/src/main.py`](../desktop-agent/src/main.py) erweitern
  - Voice-Controller-Start in `main()` einbauen
  - Config-Flag `voice.enabled` respektieren

### Config-Erweiterung (`config.json`)

```json
{
  "voice": {
    "enabled": true,
    "wakeWordEnabled": true,
    "wakeWordThreshold": 0.5,
    "vadEnabled": true,
    "vadThreshold": 0.5,
    "sttProvider": "openai",
    "ttsProvider": "openai",
    "maxRecordSeconds": 8,
    "wakeWords": ["hey jarvis", "jarvis"]
  }
}
```

### Fehlerbehandlung

| **Fehlerfall**           | **Verhalten**                                                                      |
| ------------------------ | ---------------------------------------------------------------------------------- |
| Keine Erkennung          | Stille nach Wake-Word → „Ich habe dich nicht gehört, bitte wiederholen."           |
| Unbekannter Intent       | → [`ai_brain.py`](../desktop-agent/src/integrations/ai_brain.py) für freie Antwort |
| Backend nicht erreichbar | Fehlermeldung per TTS: „Backend nicht verfügbar, Befehl gespeichert."              |
| Mikrofon-Fehler          | Log + `voice.enabled: false` im laufenden Betrieb                                  |

---

## M8 — Stabilisierung & Produktionsreife

> **Ziel:** Tests, Dokumentation, Fehlerbehandlung, Produktions-Readiness.  
> **Geschätzte Zeit:** 3–4h  
> **Abhängigkeit:** [M1](#m1--todo-domäne-backend--sync)–[M7](#m7--voice-pipeline-vollausbau)

### Technisch

- [ ] SQLite-Migrationen versionieren (Tabelle `schema_migrations`)
- [ ] [`requirements.txt`](../desktop-agent/requirements.txt) aufräumen — nur produktive Dependencies
- [ ] `requirements-dev.txt` anlegen — pytest, pytest-asyncio, etc.
- [ ] Backend-Tests: [Fastify](https://fastify.dev/docs/latest/Reference/Testing/) `inject()` für TODO- und Shift-Routes
- [ ] Agent-Tests: pytest für [`intent_router.py`](../desktop-agent/src/integrations/intent_router.py) (Fixture-Daten)
- [ ] Offline-Fallback vollständig dokumentieren

### Edge Cases & Absicherung

| **Edge Case**                   | **Lösung**                                                    |
| ------------------------------- | ------------------------------------------------------------- |
| Zwei Schichten für gleichen Tag | Backend: 409 Conflict → Agent fragt nach                      |
| Nachtschicht endet am Folgetag  | `crosses_midnight: true` + `end_date` im Schema               |
| TODO ohne Datum + Voice-Abbruch | Lokal als Draft speichern, beim nächsten Start fragen         |
| Planänderung nach Eintrag       | PATCH-Endpoint + Scheduler liest Schicht kurz vor Trigger neu |
| Intent-Konfidenz zu niedrig     | Immer mit Bestätigung, kein blindes Ausführen                 |
| Wake-Word False Positive        | Threshold tunen, VAD aktivieren, Whitelist für Umgebungen     |

### Discord-Bot _(externes Repo — als Tickets dokumentieren)_

- [ ] Issue erstellen: `/todo add <title>` Command
- [ ] Issue erstellen: `/shift set <date> <type>` Command
- [ ] Issue erstellen: `/stream? [date]` Command — gibt Empfehlung zurück
- [ ] Issue erstellen: `/todo list` Command — zeigt heutige TODOs

### Realistischer Zeitplan (mit konsequenter KI-Nutzung)

| **Phase**                 | **Milestones**                                                                    | **Aufwand/Tag** | **Dauer** | **Gesamt**  |
| ------------------------- | --------------------------------------------------------------------------------- | --------------- | --------- | ----------- |
| Phase 1: Fundament        | [M0](#m0--code-bereinigung--fundament), [M1](#m1--todo-domäne-backend--sync)      | 1–2h            | ~5 Tage   | ~6–9h       |
| Phase 2: Schicht + Stream | [M2](#m2--schicht-domäne-backend--agent), [M3](#m3--streaming-empfehlungs-engine) | 1–2h            | ~3 Tage   | ~4–6h       |
| Phase 3: Intelligenz      | [M4](#m4--intent-parser--sprachsteuerung-für-todos--schichten)                    | 1–2h            | ~5 Tage   | ~5–8h       |
| Phase 4: Ausbau           | [M5](#m5--automation-erweiterungen), [M6](#m6--dashboard-vollausbau)              | 1–2h            | ~4 Tage   | ~6–9h       |
| Phase 5: Voice            | [M7](#m7--voice-pipeline-vollausbau), [M8](#m8--stabilisierung--produktionsreife) | 1–2h            | ~6 Tage   | ~9–14h      |
| **Gesamt**                | M0–M8                                                                             | ~1,5h           | ~23 Tage  | **~30–46h** |

> Mit intensiver Arbeit (3–4h/Tag + KI-Unterstützung) in **2–3 Wochen** vollständig erreichbar.

---

_Roadmap Version 1.0 — [cakeLinir/JARVIS](https://github.com/cakeLinir/JARVIS) — 30.05.2026_
