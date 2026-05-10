# JARVIS Patch 027.1.0 – Project Analyzer Refactor

## Ziel

`desktop-agent/src/integrations/project_analyzer.py` wurde kontrolliert neu aufgebaut.

## Warum

Die vorherigen Pattern-Patches auf den Analyzer waren fehleranfällig. Patch 026.5.1 erzeugte eine `IndentationError`-Situation. Patch 027.1.0 ersetzt den Analyzer deshalb bewusst durch eine klare, kleine Implementierung.

## Enthalten

- saubere Exclude-Listen
- keine Analyse von `.jarvis-patch-backups/`
- keine Analyse von `node_modules/`, `dist/`, `logs/`, `__pycache__/`
- getrennte Sammlung von:
  - Git Status
  - letzten Commits
  - README-Auszug
  - TODO-Dateien
  - TODO/FIXME-Kommentaren
  - Projektstruktur
- feste Ausgabe-Limits
- robuste Fehlerbehandlung
- stabile Rückgabe als Dictionary
- kompatible Funktion `build_human_summary(...)`

## Test

```powershell
py -3 -m py_compile .\desktop-agent\src\main.py .\desktop-agent\src\integrations\project_analyzer.py
.\scripts\test-project-analyzer.ps1
```

## Erwartung

Die Morgenroutine soll weiterhin funktionieren. Die Projektanalyse soll deutlich weniger Rauschen anzeigen und insbesondere keine `.jarvis-patch-backups/`-Struktur mehr ausgeben.

# JARVIS Patch 027.1.1 – Analyzer Smoke-Test Import Fix

## Befund

`py_compile` war erfolgreich, aber `scripts/test-project-analyzer.ps1` schlug fehl:

```text
ModuleNotFoundError: No module named 'integrations'
```

## Ursache

Das temporäre Python-Testskript wird aus `%TEMP%` ausgeführt. Dadurch liegt `desktop-agent/src` nicht automatisch im Python-Importpfad.

## Änderung

Das Testskript übergibt `desktop-agent/src` als zweites Argument an das temporäre Python-Skript und setzt dort:

```python
sys.path.insert(0, agent_src)
```

Zusätzlich prüft der Smoke-Test, ob ausgeschlossene Fragmente wie `.jarvis-patch-backups` noch in Analyzer-Ergebnissen auftauchen.

# JARVIS Patch 027.1.2 – Analyzer Noise Tightening

## Änderung

Die Projektanalyse wurde weiter geschärft:

- `.env` wird nicht mehr in der Struktur ausgegeben.
- `config.local.json` und Backups davon werden nicht mehr ausgegeben.
- `backend/.runtime` und `backend/data` werden aus der Struktur entfernt.
- TODO/FIXME-Erkennung zählt nicht mehr jedes Vorkommen von `todo` in Variablen oder UI-Code.
- Echte TODO/FIXME-Treffer werden nur noch bei klaren Markern gezählt, zum Beispiel `TODO:`, `FIXME:`, `# TODO`, `// TODO`.

## Grund

Nach Patch 027.1.0 war der Analyzer stabil, aber noch zu laut bei Codefeldern wie `todoProvider`, `todoStatus` und `buildTodoOverview`.

# JARVIS Patch 027.1.3 – TODO Marker Strictness

## Änderung

Die TODO/FIXME-Erkennung zählt nur noch explizite Annotationen am Zeilenanfang, zum Beispiel:

```text
TODO:
FIXME:
# TODO
// TODO
```

Nicht mehr gezählt werden normale Variablen oder Kontrollflüsse wie:

```text
todoProvider
buildTodoOverview
if todo:
```

Zusätzlich wird `docs/PROJECT_ANALYZER_REFACTOR.md` als Doku-Rauschen aus der TODO/FIXME-Erkennung ausgeschlossen.

# JARVIS Patch 027.1.4 – Robust TODO Marker Function Replace

## Änderung

`_is_todo_comment_line(...)` wurde robust per Funktionsbereich ersetzt.

Gezählt werden nur noch explizite TODO/FIXME-Annotationen am Zeilenanfang:

```text
TODO:
FIXME:
# TODO
// TODO
```

Nicht mehr gezählt werden:

```text
"todo:"
"fixme:"
if todo:
todoProvider
buildTodoOverview
```

Zusätzlich wird `docs/PROJECT_ANALYZER_REFACTOR.md` aus der TODO/FIXME-Erkennung ausgeschlossen.
