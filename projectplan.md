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

## Problemanalyse (31.01.2026)
- UI-Test-Resultate inkonsistent mit Rückgabeschema.
- Anzeigeprüfung auf macOS falsch behandelt.
- Dependency-Installation läuft fälschlich beim Import in Produktion.
- Agent-Blocking speichert fehlende Snapshots nicht.
- Modell-IDs und Budget-Kalkulation inkonsistent.
- App.jsx zu groß, UI-Logik nicht modularisiert.
- Frontend-Fehlerbehandlung, Logs und Guards fehlen.
- Archiv-Ausgaben enthalten Pfade/Secrets und Summenfehler.

## Aufgabenplanung (31.01.2026)
- [ ] Tester-Agent: Rückgabeschema, macOS-Display-Check
- [ ] Backend: Dependency-Check, Session-Blocking, Budget-IDs
- [ ] Frontend: App-Splitting, Fixes, Tests
- [ ] Archive/Secrets: Sanitizing + Generator + Tests
- [ ] Überprüfungsbereich aktualisieren

## Überprüfungsbereich (31.01.2026)
- [ ] UI-Test-Resultate korrekt gemappt
- [ ] macOS als GUI-Plattform behandelt
- [ ] Keine Auto-Installationen beim Import
- [ ] Agent-Blocking immer gespeichert
- [ ] Modell-IDs/Budget-Kalkulation korrekt
- [ ] App.jsx < 500 Zeilen, UI modularisiert
- [ ] Frontend-Guards/Logs/Conditions korrigiert
- [ ] Archive ohne Pfade/Secrets, Summen korrekt

## Problemanalyse (31.01.2026 - Truncation Fix)
- Free-Tier-Modelle haben niedrige Output-Token-Limits (4-8K Tokens)
- Code wird abgeschnitten (Truncation), Syntax-Fehler entstehen
- Modellwechsel-Logik wird bei Truncation nicht getriggert
- Modelle zyklieren zurück zum Primary bei persistenten Fehlern (Ping-Pong)
- Fehlende Task-Decomposition führt zu "alles auf einmal" Generierung

## Aufgabenplanung (31.01.2026 - Truncation Fix)
- [x] Fix 1: Truncation als Sandbox-Fehler propagieren (dev_loop_steps.py, dev_loop.py)
- [x] Fix 2: Model-Rotation Bug beheben - Trennung rate-limited vs. versucht (model_router.py)
- [x] Fix 3: Planner Agent erstellen (agents/planner_agent.py)
- [x] Fix 3: Coder Single-File Template (agents/coder_agent.py)
- [x] Fix 3: File-by-File Loop (backend/file_by_file_loop.py)
- [x] Fix 3: DevLoop Integration für File-by-File Modus (backend/dev_loop.py)

## Überprüfungsbereich (31.01.2026 - Truncation Fix)
- [x] Truncation wird als Fehler erkannt und triggert Modellwechsel
- [x] Modelle werden nicht mehr vorzeitig zurückgesetzt bei rate-limited Zustand
- [x] Planner Agent erstellt File-by-File Implementierungsplan
- [x] Coder kann einzelne Dateien generieren statt alle auf einmal
- [x] File-by-File Modus aktiviert bei Desktop-Apps und komplexen Projekten
- [x] Dart AI Feature-Ableitung Konzept umgesetzt (max. 1 Ergebnis pro Task)

## Problemanalyse (31.01.2026 - Dart AI Vollständige Implementation)
- Dart AI Konzept war nur zu 50% umgesetzt (Planner vorhanden)
- Analyst Agent fehlte (Anforderungs-Clustering aus Discovery-Briefing)
- Konzepter Agent fehlte (Feature-Extraktion mit Traceability)
- Traceability Manager fehlte (REQ -> FEAT -> TASK -> Datei)
- Memory und Documentation Service hatten keine Feature-Derivation Integration
- Quality Gate hatte keine Validierung für neue Agenten-Outputs

## Aufgabenplanung (31.01.2026 - Dart AI Vollständige Implementation)
- [x] Phase 1: Agent Factory - Planner/Analyst/Konzepter registrieren
- [x] Phase 1: Session Manager - Neue Agents in Snapshots
- [x] Phase 2: Analyst Agent erstellen (agents/analyst_agent.py)
- [x] Phase 2: Konzepter Agent erstellen (agents/konzepter_agent.py)
- [x] Phase 3: Traceability Manager erstellen (backend/traceability_manager.py)
- [x] Phase 4: Memory Agent erweitern (record_feature_derivation, record_file_by_file_session)
- [x] Phase 4: Documentation Service erweitern (collect_anforderungen, collect_features, etc.)
- [x] Phase 5: Quality Gate erweitern (validate_anforderungen, validate_features, etc.)
- [x] Phase 6: File-by-File Loop Integration (Traceability, Documentation, Memory Hooks)

## Überprüfungsbereich (31.01.2026 - Dart AI Vollständige Implementation)
- [x] Analyst Agent analysiert Discovery-Briefing und erstellt REQ-Katalog
- [x] Konzepter Agent extrahiert Features mit REQ-Traceability
- [x] Traceability Manager verfolgt REQ -> FEAT -> TASK -> Datei
- [x] Memory Agent speichert Feature-Derivation Sessions
- [x] Documentation Service generiert Traceability Report
- [x] Quality Gate validiert alle Dart AI Agent-Outputs
- [x] File-by-File Loop integriert alle Komponenten automatisch

## Problemanalyse (31.01.2026 - AsyncIO Bug Fix)
- File-by-File Modus funktionierte nicht wegen AsyncIO-Fehler
- DevLoop laeuft in Worker-Thread, nicht im Main-Thread
- asyncio.get_event_loop() findet keinen Event-Loop in Worker-Threads

## Aufgabenplanung (31.01.2026 - AsyncIO Bug Fix)
- [x] AsyncIO-Bug in dev_loop.py identifizieren (Zeile 63)
- [x] asyncio.new_event_loop() statt get_event_loop() verwenden
- [x] Event-Loop nach Verwendung schliessen

## Überprüfungsbereich (31.01.2026 - AsyncIO Bug Fix)
- [x] File-by-File Modus startet ohne Fallback-Warnung
- [x] Planner erstellt Datei-Plan
- [x] Coder generiert einzelne Dateien nacheinander

## Verifikation (31.01.2026 - 17:07 Uhr)
**Test-Run:** PyQt5 Todo-Liste mit Glassmorphism UI

| Datei | Zeilen | Status |
|-------|--------|--------|
| src/config.py | 195 | OK |
| requirements.txt | 9 | OK |
| src/database.py | 231 | OK |
| src/main.py | 212 | OK |
| run.bat | 38 | OK |
| tests/test_database.py | 149 | OK |
| **Gesamt** | **834** | **6/6** |

**Integrationen:**
- Documentation: "File-by-File Ergebnisse dokumentiert"
- Traceability: "Matrix aktualisiert: 6 Dateien"
- Memory: "File-by-File Session gespeichert: 6/6 erfolgreich"
- DevLoop: "Alle 6 Dateien erfolgreich erstellt"
