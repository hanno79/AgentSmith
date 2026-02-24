# Projektplan

---

## AKTUELLE AUFGABE: TEST-COVERAGE VERBESSERUNG (14.02.2026)

### Ist-Zustand
- **153 Quell-Module** (31 Root, 81 Backend, 41 Agents)
- **43 Module getestet** (28% Modul-Coverage)
- **46 Test-Dateien** mit ~1.872 Testfaellen
- **Ziel**: 70% Coverage (CLAUDE.md Regel 14)
- **Luecke**: 64 weitere Module brauchen Tests
- **Keine Coverage-Infrastruktur**: Kein pytest.ini, kein .coveragerc, kein pytest-cov

### Nicht-testbare Module (8 Stueck, aus Berechnung ausgeschlossen)
- `__init__.py` (3x) — Leere Init-Dateien
- `main.py` — Entry-Point, Integration
- `check_env.py` — Env-Pruefung, einmalig
- `inspect_crewai.py` — Debug-Tool
- `verify_tool.py` — Manuelles Tool
- `discovery_ui.py` — Rich-Terminal-UI, nicht unit-testbar

**Effektive Basis: 145 Module, Ziel = 102 getestet (70%)**

---

### PHASE 0: Test-Infrastruktur (Voraussetzung)

**Ziel**: Coverage-Messung ermoeglichen, pytest korrekt konfigurieren

- [ ] **0.1** `pytest.ini` erstellen (testpaths, markers, Encoding)
- [ ] **0.2** `.coveragerc` erstellen (Source-Pfade, Ausschluesse, Branch-Coverage)
- [ ] **0.3** `pytest-cov` installieren und testen (`pip install pytest-cov`)
- [ ] **0.4** Baseline-Coverage messen: `pytest --cov=. --cov-report=html tests/`
- [ ] **0.5** conftest.py erweitern mit neuen Fixtures (siehe Fixture-Plan unten)

**Neue Fixtures fuer conftest.py:**
```
sample_tech_blueprint    — Next.js/React Blueprint-Dict fuer DevLoop-Tests
sample_code_dict         — {filename: content} Dict mit 3-5 typischen Dateien
sample_nextjs_project    — Temp-Dir mit package.json + app/page.js + layout.js
mock_config_yaml         — Vollstaendige config.yaml als Dict (alle Agent-Rollen)
sample_feedback          — Reviewer-Feedback mit [DATEI:xxx] Markern
sample_coder_output      — Multi-File Coder-Output mit ### FILENAME: Markern
mock_manager             — MagicMock mit allen DevLoop-Manager-Attributen
```

**Ergebnis Phase 0**: Coverage-Messung funktioniert, Baseline bekannt

---

### PHASE 1: Easy Wins — Pure-Logic Module (24 Module)

**Ziel**: +24 Module, Coverage 28% → 46%
**Aufwand**: ~5-8 Testfunktionen pro Modul, ~150 neue Tests gesamt
**Charakteristik**: Keine externen Abhaengigkeiten, kein Mocking noetig

#### 1A: DevLoop Pure-Logic (5 Module, hoechste Prioritaet)

| # | Modul | Zeilen | Test-Datei | Testbare Funktionen |
|---|-------|--------|------------|---------------------|
| 1 | backend/dev_loop_content_rules.py | 229 | test_dev_loop_content_rules.py | validate_content_rules, _check_esm_compliance, _check_app_router, _check_purple_colors, _check_hydration_safety, _check_date_hydration, extract_filenames_from_feedback |
| 2 | backend/context_compressor.py | 372 | test_context_compressor.py | compress_context, _extract_feedback_files, _find_import_deps, _extract_file_structure, _extract_js_structure, _extract_python_structure, _extract_css_structure |
| 3 | backend/dev_loop_dep_helpers.py | 136 | test_dev_loop_dep_helpers.py | _merge_dependencies, _read_package_json |
| 4 | backend/task_graph.py | ~150 | test_task_graph.py | TaskGraph Klasse, topologische Sortierung, Abhaengigkeitsanalyse |
| 5 | backend/dev_loop_coder_utils.py | 277 | test_dev_loop_coder.py (erweitern) | _get_current_code_dict, _clean_coder_output, _get_affected_files_from_feedback |

#### 1B: Infrastruktur Pure-Logic (8 Module)

| # | Modul | Zeilen | Test-Datei | Testbare Funktionen |
|---|-------|--------|------------|---------------------|
| 6 | config_validator.py | ~200 | test_config_validator.py | validate_config, validate_models_section, validate_agent_roles |
| 7 | dependency_merger.py | ~180 | test_dependency_merger.py | merge_dependencies, resolve_version_conflicts |
| 8 | model_router_error_history.py | ~150 | test_model_router.py (erweitern) | ErrorHistory Klasse, add_error, get_recent_errors |
| 9 | model_router_health.py | ~150 | test_model_router.py (erweitern) | HealthTracker, mark_healthy, mark_unhealthy |
| 10 | backend/heartbeat_utils.py | ~80 | test_heartbeat_utils.py | run_with_heartbeat (mock Timer) |
| 11 | backend/orchestration_readme.py | ~120 | test_orchestration_readme.py | generate_readme, _format_section |
| 12 | backend/orchestration_worker_status.py | ~100 | test_orchestration_worker_status.py | WorkerStatus Klasse, update_status |
| 13 | backend/session_utils.py | ~80 | test_session_utils.py | generate_session_id, validate_session |

#### 1C: Datenmodelle und Konstanten (6 Module)

| # | Modul | Zeilen | Test-Datei | Testbare Funktionen |
|---|-------|--------|------------|---------------------|
| 14 | discovery_models.py | ~100 | test_discovery_models.py | DiscoveryState, DiscoveryResult Dataclasses |
| 15 | discovery_questions.py | 261 | test_discovery_questions.py | QuestionBank static methods, get_questions_for_phase |
| 16 | backend/agent_message.py | ~80 | test_agent_message.py | AgentMessage Dataclass, Serialisierung |
| 17 | backend/app_state.py | ~100 | test_app_state.py | AppState Singleton, get/set Methoden |
| 18 | agents/tester_types.py | ~60 | test_tester_types.py | UITestResult, TestStrategy Dataclasses |
| 19 | agents/memory_types.py | ~80 | test_memory_types.py | MemoryEntry, LessonLearned Dataclasses |

#### 1D: Agent-Utils und Defaults (5 Module)

| # | Modul | Zeilen | Test-Datei | Testbare Funktionen |
|---|-------|--------|------------|---------------------|
| 20 | agents/agent_utils.py | ~100 | test_agent_utils.py | combine_project_rules, format_backstory |
| 21 | agents/dependency_constants.py | ~80 | test_dependency_constants.py | FRAMEWORK_DEPS Mapping, DB_REQUIRED_PACKAGES |
| 22 | agents/planner_defaults.py | ~200 | test_planner_defaults.py | PROTECTED_CONFIGS, get_default_plan, _get_template_files |
| 23 | agents/memory_features.py | ~120 | test_memory_features.py | extract_features, categorize_lesson |
| 24 | agents/memory_learning.py | ~150 | test_memory_learning.py | learn_from_error, consolidate_lessons |

**Ergebnis Phase 1**: 67/145 Module getestet = **46% Coverage**

---

### PHASE 2: Medium — Module mit Mocking (29 Module)

**Ziel**: +29 Module, Coverage 46% → 66%
**Aufwand**: ~8-12 Tests pro Modul, ~260 neue Tests gesamt
**Charakteristik**: unittest.mock noetig fuer LLM, File-I/O, subprocess, Docker

#### 2A: DevLoop Kern-Module (10 Module, hoechste Prioritaet)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 25 | backend/dev_loop_sandbox.py | 517 | content_validator, docker_executor | _is_harmless_warning_only (pure), _run_content_validators (mock validators) |
| 26 | backend/dev_loop_smoke_test.py | 332 | playwright, subprocess | _extract_compile_errors (pure), SmokeTestResult (dataclass) |
| 27 | backend/dev_loop_parallel_patch.py | 485 | LLM, dev_loop_coder | should_use_parallel_patch, _extract_imports, group_files_by_dependency (alle pure) |
| 28 | backend/dev_loop_review.py | 357 | crewai.Task, agent_factory | _compress_review_code (mock code_dict), Prompt-Aufbau |
| 29 | backend/dev_loop_security.py | 181 | security_agent | extract_vulnerabilities, build_feedback |
| 30 | backend/dev_loop_external_review.py | ~200 | coderabbit_specialist | run_external_review Ablauf (mock CLI) |
| 31 | backend/dev_loop_coder_prompt.py | 724 | config.yaml | _truncate_prompt_if_needed, _build_coder_prompt (String-Assembly) |
| 32 | backend/orchestration_budget.py | ~200 | budget_tracker | check_budget, calculate_remaining |
| 33 | backend/orchestration_phases.py | ~250 | agent_factory | phase_plan, phase_code, phase_review Ablauf |
| 34 | backend/dev_loop_task_derivation.py | ~200 | task_deriver | DevLoopTaskDerivation Wrapper |

#### 2B: Datenbank-Module (3 Module)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 35 | model_stats_db.py | 307 | - (SQLite in-memory) | Singleton, record_call, get_stats, get_model_ranking |
| 36 | backend/feature_tracking_db.py | ~250 | - (SQLite in-memory) | create_feature, update_status, get_features, scheduling_score |
| 37 | backend/session_manager.py | 502 | - (Dict-basiert) | create_session, get_session, list_sessions, cleanup |

#### 2C: Budget-System (3 Module)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 38 | budget_alerts.py | 161 | requests.post | check_thresholds, format_alert |
| 39 | budget_config.py | ~100 | - | load_config, get_tier_limits |
| 40 | budget_tracker.py | 323 | budget_persistence | track_usage, get_remaining, is_over_budget |

#### 2D: Agent Pure-Functions (3 Module)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 41 | agents/fix_agent.py | 421 | crewai.Agent | build_fix_prompt (pure), extract_corrected_content (pure), _add_line_numbers (pure) |
| 42 | agents/tester_agent.py | 342 | tester_playwright | summarize_ui_result (pure), _get_ui_test_strategy (pure) |
| 43 | agents/external_bureau_manager.py | ~200 | context7, reftools | run_bureau, _merge_results |

#### 2E: Docker und Infrastruktur (4 Module)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 44 | backend/docker_project_container.py | 454 | subprocess | DockerProjectContainer Klasse, _to_docker_path, is_running |
| 45 | backend/docker_executor.py | ~200 | subprocess | DockerExecutor, build_command, parse_output |
| 46 | backend/agent_factory.py | ~300 | crewai.Agent | init_agents, get_agent_for_role (mock CrewAI) |
| 47 | backend/middleware.py | ~100 | FastAPI | CORS, Error-Handler (TestClient) |

#### 2F: Discovery und Sonstiges (6 Module)

| # | Modul | Zeilen | Mocking | Testbare Teile |
|---|-------|--------|---------|----------------|
| 48 | discovery_intelligence.py | 140 | memory_agent | analyze_requirements, suggest_techstack |
| 49 | discovery_session.py | 492 | Rich console | DiscoverySession Ablauf (mock I/O) |
| 50 | backend/traceability_manager.py | ~150 | - | TraceabilityManager, add_entry, get_trace |
| 51 | backend/traceability_service.py | ~150 | traceability_manager | generate_report, format_trace |
| 52 | agents/memory_core.py | ~200 | file I/O | load_memory, save_memory, merge_entries |
| 53 | agents/memory_encryption.py | ~150 | cryptography | encrypt_data, decrypt_data (mock keys) |

**Ergebnis Phase 2**: 96/145 Module getestet = **66% Coverage**

---

### PHASE 3: Hard — Integration und Agent-Factories (7+ Module)

**Ziel**: +7 Module, Coverage 66% → 71% (Ziel erreicht!)
**Aufwand**: ~5-8 Tests pro Modul, ~50 neue Tests gesamt
**Charakteristik**: Komplexes Mocking, Agent-Stubs, Manager-State

| # | Modul | Zeilen | Strategie |
|---|-------|--------|-----------|
| 54 | agents/coder_agent.py | 269 | Stub crewai.Agent, verify init-Parameter |
| 55 | agents/reviewer_agent.py | 82 | Stub crewai.Agent, verify init-Parameter |
| 56 | agents/designer_agent.py | 51 | Stub crewai.Agent, verify init-Parameter |
| 57 | backend/dev_loop_coder.py | 313 | Mock LLM-Response, test Output-Parsing |
| 58 | backend/api.py | ~400 | FastAPI TestClient, mock Endpoints |
| 59 | agents/dependency_agent.py | ~250 | Mock subprocess (npm), test Paket-Logik |
| 60 | agents/dependency_installer.py | ~200 | Mock subprocess, test install_packages |

**Ergebnis Phase 3**: 103/145 Module getestet = **71% Coverage** (ZIEL ERREICHT)

---

### PHASE 4: Bonus — Richtung 80% (Optional, spaeter)

Fuer spaetere Erweiterung, falls gewuenscht:

| Modul | Herausforderung |
|-------|----------------|
| backend/dev_loop_core.py (585 Zeilen!) | Refactoring noetig (Regel 1), dann Integration-Test |
| backend/orchestration_manager.py (841!) | Refactoring DRINGEND noetig, dann testen |
| backend/file_by_file_loop.py (956!) | Refactoring KRITISCH noetig |
| backend/dev_loop_run_helpers.py (541!) | Leicht ueber Limit, Refactoring sinnvoll |
| backend/parallel_file_generator.py | Threading + Async, schwer zu testen |

**ACHTUNG**: 4 Module verletzen Regel 1 (>500 Zeilen):
- `file_by_file_loop.py` (956 Zeilen) — DOPPELT ueber Limit!
- `orchestration_manager.py` (841 Zeilen) — 68% ueber Limit!
- `dev_loop_coder_prompt.py` (724 Zeilen) — 45% ueber Limit!
- `dev_loop_core.py` (585 Zeilen) — 17% ueber Limit!

Diese muessen VOR dem Testen refactored werden.

---

### ZUSAMMENFASSUNG

| Phase | Module | Kumulativ | Coverage | Neue Tests | Aufwand |
|-------|--------|-----------|----------|------------|---------|
| 0: Infrastruktur | 0 | 43/145 | 28% | 0 | 1 Stunde |
| 1: Easy Wins | +24 | 67/145 | 46% | ~150 | 1-2 Tage |
| 2: Medium | +29 | 96/145 | 66% | ~260 | 3-4 Tage |
| 3: Hard | +7 | 103/145 | 71% | ~50 | 1-2 Tage |
| **Gesamt** | **+60** | **103/145** | **71%** | **~460** | **~7-9 Tage** |

---

### PRIORITAETEN-REIHENFOLGE INNERHALB PHASEN

**Hoechste Prioritaet** (Module die wir in Fix 1-56 am meisten geaendert haben):
1. dev_loop_content_rules.py — Fix 38, 39
2. context_compressor.py — Fix 41, 41b, 42c
3. dev_loop_sandbox.py — Fix 43, 51
4. dev_loop_smoke_test.py — Fix 43, 45
5. dev_loop_parallel_patch.py — Fix 48, 53, 53b
6. dev_loop_coder_prompt.py — Fix 40d, 40e, 41, 44
7. dev_loop_helpers.py — Fix 35b, 36, 56a (erweitern!)
8. content_validator.py — Fix 56b (erweitern!)

---

### UEBERPRUEFUNGSBEREICH

- [ ] Phase 0 abgeschlossen (Infrastruktur steht)
- [ ] Phase 1 abgeschlossen (46% Coverage erreicht)
- [ ] Phase 2 abgeschlossen (66% Coverage erreicht)
- [ ] Phase 3 abgeschlossen (71% Coverage erreicht, Ziel erfuellt)
- [ ] Alle Test-Dateien haben Author-Header (Regel 8)
- [ ] Alle Tests haben deutsche Docstrings (Regel 4)
- [ ] Coverage-Report als HTML generierbar
- [ ] Keine Test-Datei ueber 500 Zeilen (Regel 1)

---

## FRUEHERE PROBLEMANALYSEN

## 🔴 AKTUELLE PROBLEMANALYSE (01.02.2026)

### **Kritische Fehler identifiziert:**

1. **Frontend Build-Fehler**
   - Tailwind CSS `@tailwindcss/oxide` native binding fehlt
   - NPM optional dependencies Bug
   - Build schlägt fehl, Dev-Server funktioniert

2. **Backend Runtime-Fehler**
   - Model Router Timeouts (120s zu kurz)
   - Playwright Test-Timeouts (Server nicht erreichbar)
   - Sandbox JavaScript-Fehler (unspezifische Meldungen)

3. **Test-Infrastruktur-Probleme**
   - 100% Fehlerrate bei FastAPI Playwright-Tests
   - Fehlender Health-Check vor Test-Ausführung
   - Unit-Tests schlagen fehl wegen fehlender Dependencies

4. **Architektur-Erkenntnisse**
   - 40% der Reviewer-Tasks laufen in Timeout
   - 60% der ersten Iterationen haben Security-Vulnerabilities
   - Durchschnittlich 3-5 Iterationen bis Erfolg

### **Dokumentation erstellt:**
- ✅ `documentation/fehleranalyse_architektur_kontext.md` (vollständige Analyse)
- ✅ `documentation/fehler_quick_reference.md` (Quick Reference)

---

## FRÜHERE PROBLEMANALYSEN

### Problemanalyse (Legacy)
- Fehlerbehandlung beim Speichern von Projekten verschluckt Exceptions.
- Agent-Name-Mapping passt nicht zu Session-Keys.
- `library/current_project.json` darf nicht versioniert werden.
- npm-Status/Health-Score ist inkonsistent bei Fehlern.

## 🎯 AUFGABENPLANUNG (01.02.2026)

### **Phase 1: Sofortmaßnahmen (Heute)**
- [x] Fehleranalyse durchführen
- [x] Architektur-Dokumentation erstellen
- [x] Quick Reference Guide erstellen
- [ ] Frontend Build-Fehler beheben
- [ ] Model Router Timeout erhöhen (120s → 180s)
- [ ] Playwright Health-Check implementieren

### **Phase 2: Stabilisierung (Diese Woche)**
- [ ] Sandbox-Fehler-Diagnostik verbessern (Zeilen-Nummern + Kontext)
- [ ] Test-Infrastruktur robuster machen
- [ ] Error-Handling in Model Router optimieren
- [ ] Logging-System verbessern

### **Phase 3: Optimierung (Nächste Woche)**
- [ ] Parallele Modell-Anfragen implementieren
- [ ] Docker-basierte Test-Umgebung aufsetzen
- [ ] Automatische Retry-Strategien
- [ ] Performance-Monitoring Dashboard

---

## FRÜHERE AUFGABENPLANUNGEN

### Aufgabenplanung (Legacy)
- [x] Relevante Stellen in den Backend-Dateien prüfen
- [x] Fehlerbehandlung in `library_manager.py` anpassen
- [x] Agent-Mapping in `orchestration_manager.py` ergänzen
- [x] `.gitignore` anpassen und npm-Health-Score-Logik fixen
- [x] Prüfung: Lints/Tests optional

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
(Hinweis: Diese Tasks sind dem aktuellen PR zugeordnet bzw. fuer einen zukuenftigen Work-Stream/PR vorgesehen; Kästchen auf [x] setzen sobald im PR enthalten.)

## Überprüfungsbereich (31.01.2026)
(Abgleich mit den Unterabschnitten „Truncation Fix“, „Dart AI“, „AsyncIO“ weiter unten.)
- [ ] UI-Test-Resultate korrekt gemappt
- [ ] macOS als GUI-Plattform behandelt
- [ ] Keine Auto-Installationen beim Import
- [ ] Agent-Blocking immer gespeichert
- [ ] Modell-IDs/Budget-Kalkulation korrekt
- [ ] App.jsx < 500 Zeilen, UI modularisiert
- [ ] Frontend-Guards/Logs/Conditions korrigiert
- [ ] Archive ohne Pfade/Secrets, Summen korrekt
(Top-Level-Review ausstehend bis Unterabschnitte verifiziert.)

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
