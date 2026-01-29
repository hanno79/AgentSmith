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

## Problemanalyse (29.01.2026 - Fixes)
- Dead Code und fail-open Stellen im Dev-Loop und Security-Handling.
- Fehlende Fehler-Logs in Budget/Config/Discovery und Regex-Parsing.
- Unsichere Dependency-Installation ermöglicht Command-Injection.
- Race-Conditions in Session-Logs und Worker-Reset.
- Tailwind-Klassen dynamisch generiert und State-Fehler im UI.

## Aufgabenplanung (29.01.2026 - Fixes)
- [x] `dev_loop_steps.py` Dead Code entfernen und Exceptions loggen
- [x] `library_manager.py` Briefing-Normalisierung robust machen
- [x] `orchestration_helpers.py` Rate-Limit-Prädikat bereinigen + Regex-Fehlerbehandlung
- [x] Router-Fixes: Budget-Validierung, Config-Logging, Discovery-Logging, External-Bureau-Validierung
- [x] Security/Worker/Session: fail-closed, reset await, atomare Logs
- [x] Frontend: Tailwind-Static-Mapping und State-Resets
- [x] Überprüfungsbereich aktualisieren

## Überprüfungsbereich (29.01.2026 - Fixes)
- [x] Keine stillen Exceptions in Budget/Config/Discovery/Regex
- [x] Dependency-Installation validiert und ohne Shell-Ausführung
- [x] Session-Logs atomar, Worker-Reset wartet auf Cancellation
- [x] Security-Scan fail-closed mit klarer UI-Log-Meldung
- [x] Tailwind-Classes statisch, Session-Resume robust, UI-State reset

## Problemanalyse (29.01.2026 - Pydantic Validator)
- Pydantic V2 bricht beim Import des Budget-Routers wegen veralteter Validator-Signatur.
- Uvicorn startet nicht, weil `field`/`config` nicht mehr verfügbar sind.

## Aufgabenplanung (29.01.2026 - Pydantic Validator)
- [x] Budget-Validator auf Pydantic V2 `field_validator` umstellen
- [ ] Prüfung: Lints/Start optional

## Überprüfungsbereich (29.01.2026 - Pydantic Validator)
- [x] Validator nutzt `info` statt `field`
- [x] Import-Fehler beim Start behoben
