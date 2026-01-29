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

## Problemanalyse (29.01.2026)
- Es fehlen Tests für die neuen Discovery-Endpunkte.
- Externe LLM-Aufrufe und Dateischreibvorgänge müssen für Tests gemockt werden.
- Dedup-Logik benötigt einen reproduzierbaren Testfall mit Agenten-Array.

## Aufgabenplanung (29.01.2026)
- [x] Relevante Discovery-Endpunkte und Hilfsfunktionen prüfen
- [x] Tests für save_discovery_briefing erstellen (Session-Update, Pfad, Status)
- [x] Tests für generate_discovery_questions inkl. Dedup-Case erstellen
- [x] Tests für _generate_agent_questions mit gemocktem LLM-Call ergänzen
- [x] Überprüfungsbereich aktualisieren

## Überprüfungsbereich (29.01.2026)
- [x] Tests decken Status-Codes und JSON-Shape ab
- [x] Dedup-Case liefert agents-Array und Zusammenführungen
- [x] Dateischreiben und Env-Keys sauber gemockt
