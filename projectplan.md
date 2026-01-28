# Projektplan

## Problemanalyse
- Fehlerbehandlung beim Speichern von Projekten verschluckt Exceptions.
- Agent-Name-Mapping passt nicht zu Session-Keys.
- `library/current_project.json` darf nicht versioniert werden.
- npm-Status/Health-Score ist inkonsistent bei Fehlern.

## Aufgabenplanung
- [x] Relevante Stellen in den Backend-Dateien prüfen
- [x] Fehlerbehandlung in `library_manager.py` anpassen
- [x] Agent-Mapping in `orchestration_manager.py` ergänzen
- [x] `.gitignore` anpassen und npm-Health-Score-Logik fixen
- [ ] Prüfung: Lints/Tests optional

## Überprüfungsbereich
- [x] Änderungen nachvollziehbar dokumentiert
- [x] Keine stillen Speicherfehler
- [x] Session-Keys korrekt gemappt
- [x] `current_project.json` nicht versioniert
- [x] npm-Health-Score reagiert auf Fehlerzustand
