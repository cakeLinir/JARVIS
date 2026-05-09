# JARVIS TODO-System

## Ziel

Das TODO-System unterstützt austauschbare lokale Provider, ohne dass Agent, Dashboard oder Backend direkt an ein Dateiformat gekoppelt sind.

## MVP-Provider

Der Desktop-Agent unterstützt ab Patch 005 drei Provider:

| Provider | Zweck | Status |
|---|---|---|
| `markdown` | bestehende `todo.md` weiterverwenden | kompatibel |
| `json` | strukturierter lokaler MVP-Speicher | vorbereitet |
| `sqlite` | produktionsnäherer lokaler MVP-Speicher | vorbereitet |

## Dashboard-Integration

Ab Patch 006 meldet der Agent den TODO-Status im Morning-Log an das Backend. Das Dashboard zeigt diesen Status im Abschnitt `TODO`.

Gemeldet werden:

```text
provider
total
open
dueTodayOrUnscheduled
items
```

Das Backend speichert keine lokalen Pfade und zeigt keine lokalen Pfade im Dashboard an.

## Konfiguration

Die Provider werden in `desktop-agent/config.local.json` oder lokal per nicht committeter Konfiguration gesetzt.

### Markdown

```json
{
  "todo": {
    "provider": "markdown",
    "markdownPath": "C:\\Users\\hunde\\Desktop\\JARVIS\\data\\todo.md"
  }
}
```

### JSON

```json
{
  "todo": {
    "provider": "json",
    "jsonPath": "C:\\Users\\hunde\\Desktop\\JARVIS\\data\\todos.json"
  }
}
```

### SQLite

```json
{
  "todo": {
    "provider": "sqlite",
    "sqlitePath": "C:\\Users\\hunde\\Desktop\\JARVIS\\data\\todos.sqlite3"
  }
}
```

## Datenmodell

Intern werden TODOs auf diese Felder normalisiert:

```text
id
title
status: open | done | cancelled
dueDate: YYYY-MM-DD | null
priority: number
source: markdown | json | sqlite
```

## Sicherheitsregeln

- Keine externen TODO-Provider ohne explizite Entscheidung.
- Keine Tokens oder API-Keys in TODO-Dateien.
- Platzhalterpfade werden als `KONFIGURATION_ERFORDERLICH` geloggt.
- SQLite-Dateien werden lokal erzeugt.
- JSON-Dateien werden lokal erzeugt, wenn sie fehlen.
- Backend und Dashboard erhalten keine lokalen Pfade.

## Bekannte Grenzen

- Dashboard verwaltet TODOs noch nicht direkt.
- Backend synchronisiert TODOs noch nicht.
- SQLite hat noch keine Migrationstabelle.
- Es gibt noch keine Schreibbefehle per Voice oder Discord.
