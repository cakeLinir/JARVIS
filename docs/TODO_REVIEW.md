# JARVIS TODO Review & Deferred Day Planning

## Ziel

Patch 027.3.1 führt einen sicheren TODO-Review-Baustein ein, der TODOs nicht nur vorschlagen, sondern bei explizitem Apply-Schritt auch `data/todo.md` überarbeiten darf.

## Sicherheitsregel

JARVIS darf die TODO-Datei überarbeiten, aber nur mit Backup.

Vor jedem Überschreiben wird eine Sicherung erstellt:

```text
data/backups/todo.md.backup-YYYYMMDD-HHMMSS
```

Zusätzlich kann ein Apply-Log geschrieben werden:

```text
data/todo.apply-log.json
```

## Dateien

### `data/todo.review.json`

Enthält Review-Vorschläge:

- Originaltext
- vorgeschlagene Formulierung
- Priorität
- empfohlenes Zeitfenster
- Status `proposed`

### `data/todo.schedule.json`

Enthält geplante Einträge für später am Tag:

- Titel
- Zeitraum
- Status `pending`
- `requiresConfirmation: true`

### `data/todo.apply-log.json`

Enthält technische Informationen zum Überschreiben:

- Backup-Pfad
- Hash vor Änderung
- Hash nach Änderung
- Anzahl geschriebener Einträge

## Apply-Modus

Nur Review/Schedule erzeugen:

```powershell
.\scripts\test-todo-review.ps1
```

Review/Schedule erzeugen und `data/todo.md` nach Backup überarbeiten:

```powershell
.\scripts\test-todo-review.ps1 -ApplyToTodo
```

## Keine automatische Ausführung

Auch wenn JARVIS `data/todo.md` überarbeiten darf, werden geplante TODOs nicht automatisch gestartet.

```json
{
  "applyAllowed": true,
  "applyRequiresBackup": true,
  "autoStart": false,
  "requiresUserConfirmation": true
}
```

## OpenAI

OpenAI wird in diesem Patch nicht verwendet.

Grund:

- Erst Datenmodell stabilisieren.
- Erst sichere Apply-/Backup-Mechanik bauen.
- Danach KI-gestützte Umformulierung ergänzen.

# JARVIS Patch 027.3.2 – Checkbox + Encoding Fix

## Befund

Patch 027.3.1 konnte TODOs überarbeiten, aber bereits vorhandene oder escaped Checkboxen wurden teilweise als Text übernommen:

```text
\[x] JARVIS Backend starten
\[ ] Agent testen
```

Außerdem zeigte Windows PowerShell bei UTF-8 ohne BOM Umlaute als Mojibake an.

## Änderung

- Escaped Checkboxen wie `\[x]` und `\[ ]` werden erkannt.
- Verschachtelte Checkbox-Reste werden aus dem Task-Text entfernt.
- Erledigte Einträge werden nicht erneut als offene TODOs geschrieben.
- `data/todo.md` wird beim Apply mit `utf-8-sig` geschrieben.
- JSON-Dateien werden ASCII-escaped geschrieben, um Mojibake bei Raw-Reads zu vermeiden.

## Reparatur vorhandener Datei

Nach Anwendung:

```powershell
.\scripts\test-todo-review.ps1 -ApplyToTodo
```

Dadurch wird die aktuell beschädigte `data/todo.md` erneut gesichert und sauber neu geschrieben.

# Patch 027.3.3 – Agent TODO Review Command

## Ziel

Die TODO-Review-/Apply-Logik ist jetzt als Agent-interne Command-Schicht verfügbar.

## Neue Dateien

```text
desktop-agent/src/todo/todo_review_command.py
scripts/agent-todo-review.ps1
scripts/test-agent-todo-review-command.ps1
```

## Verhalten

Ohne Apply:

```powershell
.\scripts\agent-todo-review.ps1
```

Mit Apply:

```powershell
.\scripts\agent-todo-review.ps1 -ApplyToTodo
```

## Sicherheit

Auch der Agent-Command überschreibt `data/todo.md` nur über die bestehende Backup-Mechanik aus `todo_review.py`.

## Technische Funktion

Für spätere Integration in `main.py` oder die lokale Agent-API steht bereit:

```python
from todo.todo_review_command import run_agent_todo_review
```

Diese Funktion liefert ein strukturiertes Ergebnis mit `ok`, Pfaden und Summary.

# Patch 027.3.4 – Morning Routine TODO Review Integration

## Ziel

Die Morning Routine erzeugt automatisch einen TODO Review und eine Schedule-Datei.

Standard:

```json
{
  "todoReview": {
    "enabled": true,
    "applyDuringMorningRoutine": false
  }
}
```

## Verhalten

Bei `guten morgen jarvis`:

```text
TODO Review startet ohne Apply.
TODO Review abgeschlossen: openItems=..., scheduledItems=..., applied=False
```

## Sicherheit

`applyDuringMorningRoutine` ist standardmäßig `false`.

Damit wird `data/todo.md` während der Morning Routine nicht automatisch überschrieben.

Explizites Apply bleibt weiterhin über den Agent-Command möglich:

```powershell
.\scripts\agent-todo-review.ps1 -ApplyToTodo
```

## Konfiguration

In `desktop-agent/config.json`, `desktop-agent/config.local.example.json` und, falls vorhanden, `desktop-agent/config.local.json` wird ergänzt:

```json
"todoReview": {
  "enabled": true,
  "applyDuringMorningRoutine": false
}
```
