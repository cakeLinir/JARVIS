# JARVIS Patch 026.2 – Project Analysis Filter

## Zweck

Patch 026.2 ergänzt einen zentralen Filter in `desktop-agent/src/main.py`.

## Ziele

- Projektanalyse soll `.jarvis-patch-backups/` nicht mehr ausgeben.
- Projektanalyse soll technische Build-/Dependency-Ordner nicht ausgeben.
- Logausgaben mit bekannten Mojibake-Texten werden normalisiert.
- Deaktivierte Apps werden in der Logausgabe von `ERROR` auf `WARN` normalisiert.
- Rauschende TODO/FIXME-Treffer aus Config-/Doku-Dateien werden in der Logausgabe unterdrückt.

## Hinweis

Dieser Patch filtert primär Ausgabe und Dateidurchläufe. Falls eine interne Zusammenfassungszahl weiterhin zu hoch ist, muss im nächsten Schritt die konkrete Summenbildung im Agent-Code gezielt angepasst werden.

# JARVIS Patch 026.3 – Log Suppression Fix

## Befund

Patch 026.2 hatte den Pfadfilter eingefügt, aber nicht die zentrale Log-Suppression. Dadurch erschienen weiter:

```text
.jarvis-patch-backups/
desktop-agent/config.local.json
docs/TODO_SYSTEM.md
```

## Änderung

Patch 026.3 ergänzt in `desktop-agent/src/main.py`:

- `jarvis_normalize_log_event`
- `jarvis_should_suppress_log`
- Log-Suppression in der zentralen `log(...)`-Funktion
- gezielte Normalisierung von deaktivierten Apps

## Ziel

Diese Zeilen sollen nicht mehr im PROJECT-Log erscheinen:

```text
.jarvis-patch-backups/
desktop-agent/config.local.json
desktop-agent/config.local.example.json
desktop-agent/config.json
docs/TODO_SYSTEM.md
docs/LOCAL_AGENT_VPS_CONNECTION.md
docs/RUNTIME_CLEANUP_ANALYSIS_NOISE.md
```

Deaktiviertes VS Code soll nicht mehr als harter Fehler erscheinen:

```text
[WARN] App übersprungen: vscode | App deaktiviert
```

# JARVIS Patch 026.4 – Log Hook Fix

## Änderung

Die zentrale `log(...)`-Funktion ruft jetzt explizit auf:

```python
level, message = jarvis_normalize_log_event(level, message)
if jarvis_should_suppress_log(level, message):
    return
```

Damit greifen Mojibake-Korrektur, Deaktiviert-App-Normalisierung und PROJECT-Log-Suppression zentral.

# JARVIS Patch 026.5.1 – Project Analyzer Direct Filter Fix

## Befund

Patch 026.5 ist im Apply-Skript gescheitert, bevor Änderungen angewendet wurden.

## Änderung

`desktop-agent/src/integrations/project_analyzer.py` filtert jetzt direkt Pfade aus:

```text
.jarvis-patch-backups/
node_modules/
dashboard/dist/
backend/dist/
logs/
__pycache__/
```

Zusätzlich werden TODO-/FIXME-Treffer aus Config- und TODO-System-Dokumentation herausgefiltert.

## Ziel

Die Morgenroutine soll keine langen Backup-Strukturen und keine Konfigurations-TODO-Rauschtreffer mehr ausgeben.

# JARVIS Patch 026.5.2 – Project Analyzer Restore

## Änderung

`desktop-agent/src/integrations/project_analyzer.py` wurde aus dem Backup vor Patch 026.5.1 wiederhergestellt, weil Patch 026.5.1 eine `IndentationError`-Situation erzeugt hatte.

Die zentrale Log-Normalisierung und PROJECT-Log-Suppression in `desktop-agent/src/main.py` bleibt erhalten.

## Grund

Der Agent selbst war lauffähig, aber die Projektanalyse schlug fehl:

```text
unindent does not match any outer indentation level
```

## Nachprüfung

```powershell
py -3 -m py_compile .\desktop-agent\src\main.py .\desktop-agent\src\integrations\project_analyzer.py
```
