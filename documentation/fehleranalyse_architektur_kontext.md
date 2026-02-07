# Fehleranalyse & Architektur-Kontext
**Autor:** rahn  
**Datum:** 01.02.2026  
**Version:** 1.0

---

## 🎯 EXECUTIVE SUMMARY

Das AgentSmith Multi-Agent-System zeigt **3 kritische Fehlerkategorien**:
1. **Frontend Build-Fehler** (Tailwind CSS Native Binding)
2. **Backend Runtime-Fehler** (Timeout, Modell-Verfügbarkeit)
3. **Test-Infrastruktur-Fehler** (Playwright Timeouts, Unit-Test Failures)

---

## 📊 ARCHITEKTUR-ÜBERSICHT

### **Systemkomponenten**

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENTSMITH SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   FRONTEND   │◄──►│   BACKEND    │◄──►│  AGENTS      │ │
│  │   (React)    │    │  (FastAPI)   │    │  (CrewAI)    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │         │
│         │                    │                    │         │
│  ┌──────▼──────┐    ┌───────▼────────┐  ┌────────▼──────┐ │
│  │  Vite Build │    │  Model Router  │  │  Memory Agent │ │
│  │  Tailwind   │    │  OpenRouter    │  │  Sandbox      │ │
│  └─────────────┘    └────────────────┘  └───────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### **Technologie-Stack**

| Komponente | Technologie | Zweck |
|------------|-------------|-------|
| **Frontend** | React + Vite + Tailwind CSS | UI Dashboard |
| **Backend** | FastAPI + WebSocket | API & Orchestrierung |
| **Agents** | CrewAI + OpenRouter LLMs | Code-Generierung |
| **Testing** | Playwright + Pytest | UI/Unit Tests |
| **Memory** | JSON-basiert | Lessons Learned |
| **Security** | Custom Sandbox + Validator | Code-Sicherheit |

---

## 🔴 KRITISCHE FEHLER

### **1. FRONTEND BUILD-FEHLER**

**Datei:** `frontend/build_log.txt`

```
Error: Cannot find native binding. npm has a bug related to optional dependencies
(https://github.com/npm/cli/issues/4828). 
Please try `npm i` again after removing both package-lock.json and node_modules directory.
```

**Ursache:**
- Tailwind CSS `@tailwindcss/oxide` native Binding fehlt
- NPM optional dependencies Bug
- Plattform-spezifisches Problem (Windows)

**Auswirkung:**
- Frontend kann nicht gebaut werden
- Keine Produktions-Deployment möglich
- Entwicklungs-Server funktioniert, aber Build schlägt fehl

**Lösung:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

### **2. BACKEND RUNTIME-FEHLER**

#### **2.1 Model Router Timeouts**

**Log-Einträge:**
```json
{"agent": "Reviewer", "action": "Timeout", 
 "content": "Reviewer-Modell openrouter/meta-llama/llama-3.3-70b-instruct:free 
             timeout nach 120s (Versuch 1/3), wechsle zu Fallback..."}
```

**Ursache:**
- OpenRouter Free-Modelle überlastet
- 120s Timeout zu kurz für komplexe Reviews
- Rate-Limiting greift zu aggressiv

**Betroffene Dateien:**
- `model_router.py` - Timeout-Konfiguration
- `model_router_health.py` - Health-Check Logik
- `backend/orchestration_helpers.py` - Fehlerbehandlung

**Lösung:**
- Timeout auf 180s erhöhen
- Besseres Fallback-Modell-Management
- Parallele Modell-Anfragen implementieren

---

#### **2.2 Playwright Test Timeouts**

**Log-Einträge:**
```json
{"agent": "Tester", "action": "Result", 
 "content": "Test fehlgeschlagen nach 3 Versuchen: 
             Page.goto: Timeout 10000ms exceeded.
             Call log: - navigating to 'http://localhost:8000/', 
             waiting until 'domcontentloaded'"}
```

**Ursache:**
- FastAPI Server nicht erreichbar auf Port 8000
- Server startet nicht rechtzeitig vor Tests
- Keine Health-Check vor Test-Ausführung

**Betroffene Dateien:**
- `agents/tester_playwright.py` - Playwright-Tests
- `agents/tester_agent.py` - Test-Orchestrierung
- `backend/orchestration_manager.py` - Test-Koordination

**Lösung:**
- Server-Health-Check vor Tests implementieren
- Timeout auf 30s erhöhen
- Retry-Logik mit exponential backoff

---

### **3. SANDBOX JAVASCRIPT-FEHLER**

**Log-Einträge:**
```json
{"agent": "Sandbox", "action": "Result", 
 "content": "❌ JavaScript-Syntaxfehler: 
             C:\\Users\\rahn\\AppData\\Local\\Temp\\tmpbz1_rg72.js:1"}
```

**Ursache:**
- Generierter JavaScript-Code hat Syntaxfehler
- Sandbox validiert Code, aber Fehler nicht spezifisch genug
- Temp-Datei wird sofort gelöscht (Debugging schwierig)

**Betroffene Dateien:**
- `sandbox_runner.py` - Code-Validierung
- `agents/coder_agent.py` - Code-Generierung

**Lösung:**
- Detailliertere Fehlermeldungen (Zeile + Kontext)
- Temp-Dateien bei Fehler behalten für Debugging
- AST-basierte Validierung vor Sandbox-Ausführung

---

## 🏗️ ARCHITEKTUR-DETAILS

### **Agent-System**

**Verfügbare Agenten:**

| Agent | Rolle | Modell | Aufgabe |
|-------|-------|--------|---------|
| **Coder** | Code-Generierung | Llama 3.3 70B / Gemma 3 27B | Erstellt Source Code |
| **Reviewer** | Code-Review | Llama 3.3 70B / Gemma 3 27B | Prüft Code-Qualität |
| **Tester** | Testing | Playwright + Pytest | UI/Unit Tests |
| **Security** | Sicherheit | Gemma 3 27B | Security-Scans |
| **Designer** | UI/UX | Llama 3.3 70B | Design-Konzepte |
| **Researcher** | Recherche | Exa Search API | Technologie-Recherche |
| **TechStack Architect** | Architektur | Llama 3.3 70B | Tech-Stack Entscheidungen |
| **DB Designer** | Datenbank | Llama 3.3 70B | Schema-Design |
| **Memory** | Lernen | Lokal (JSON) | Lessons Learned |
| **Orchestrator** | Koordination | Meta-Orchestrator | Workflow-Steuerung |

**Worker-Pool-System:**
- Jeder Agent hat 1-3 Worker
- Worker-Status: `idle`, `working`, `error`
- Task-Queue pro Office
- Parallele Ausführung möglich

---

### **Error-Handling-System**

**Komponenten:**
- `exceptions.py` - Exception-Hierarchie (12 Exception-Typen)
- `backend/error_analyzer.py` - Fehleranalyse & Priorisierung
- `backend/error_extractors.py` - Pattern-Matching für Fehler
- `backend/error_utils.py` - Hilfsfunktionen
- `backend/error_models.py` - Datenmodelle

**Fehler-Priorisierung:**
```python
ERROR_PRIORITY_MAP = {
    "syntax": 0,        # Höchste Priorität
    "truncation": 1,
    "import": 2,
    "runtime": 3,
    "test": 4,
    "review": 5,
    "unknown": 6        # Niedrigste Priorität
}
```

**Dependency-Analyse:**
- Import-Fehler haben keine Dependencies
- Runtime-Fehler hängen von Import-Fehlern ab
- Automatische Sortierung nach Abhängigkeiten

---

### **Model Router**

**Funktionen:**
- Health-Checks für Modelle
- Automatisches Fallback bei Fehlern
- Rate-Limit-Management
- Permanente Unavailability-Markierung

**Fehler-Kategorien:**
1. **Permanent Unavailable** - "free period ended", 404
2. **Rate Limited** - Temporäre Überlastung
3. **Server Error** - 500/502/503/504
4. **Timeout** - Keine Antwort innerhalb Timeout

**Fallback-Strategie:**
```
Llama 3.3 70B (free) → Gemma 3 27B (free) → Claude Haiku 4.5 (paid)
```

---

## 🔍 FEHLER-PATTERNS AUS LOGS

### **Pattern 1: Modell-Timeout → Fallback → Erfolg**

```
1. Reviewer startet mit Llama 3.3 70B
2. Timeout nach 120s
3. Modell wird rate-limited (30s Pause)
4. Fallback auf Gemma 3 27B
5. Erfolgreiche Ausführung
```

**Häufigkeit:** ~40% der Reviewer-Tasks
**Auswirkung:** +2-3 Minuten Verzögerung

---

### **Pattern 2: Playwright Test-Fehler Loop**

```
1. Tester startet Playwright
2. Versucht http://localhost:8000/ zu öffnen
3. Timeout nach 10s
4. Retry (3x)
5. Alle Retries fehlgeschlagen
6. Test als ERROR markiert
```

**Häufigkeit:** 100% bei FastAPI-Projekten
**Ursache:** Server nicht gestartet oder nicht erreichbar

---

### **Pattern 3: Security-Scan blockiert Iteration**

```
1. Coder generiert Code
2. Sandbox validiert (OK)
3. Unit-Tests laufen (FAIL)
4. Security-Scan findet 6 Vulnerabilities
5. Iteration blockiert bis Fixes implementiert
```

**Häufigkeit:** ~60% der ersten Iterationen
**Typische Vulnerabilities:**
- Hardcoded Credentials
- SQL Injection Risiko
- Schwache Authentifizierung
- Fehlende Input-Validierung

---

## 📁 DATEI-ORGANISATION

### **Projekt-Struktur**

```
multi_agent_poc/
├── main.py                    # Hauptsteuerung (CLI)
├── config.yaml                # Modell-Konfiguration
├── exceptions.py              # Exception-Hierarchie
├── sandbox_runner.py          # Code-Validierung
├── model_router.py            # LLM-Routing
├── budget_tracker.py          # Kosten-Tracking
│
├── agents/                    # Agent-Implementierungen
│   ├── coder_agent.py
│   ├── reviewer_agent.py
│   ├── tester_agent.py
│   ├── security_agent.py
│   ├── memory_agent.py
│   └── meta_orchestrator_agent.py
│
├── backend/                   # FastAPI Backend
│   ├── api.py                 # Haupt-API
│   ├── orchestration_manager.py
│   ├── error_analyzer.py
│   ├── dev_loop.py
│   └── routers/               # API-Router
│       ├── core.py
│       ├── config.py
│       ├── budget.py
│       └── discovery.py
│
├── frontend/                  # React Frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── MainframeHub.jsx
│   │   ├── BudgetDashboard.jsx
│   │   └── components/
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── tests/                     # Unit-Tests
│   ├── test_error_analyzer.py
│   ├── test_model_router.py
│   └── test_dev_loop.py
│
├── memory/                    # Lessons Learned
│   └── global_memory.json
│
├── projects/                  # Generierte Projekte
│   └── project_YYYYMMDD_HHMMSS/
│
└── documentation/             # Dokumentation
    ├── chatverlauf.md
    └── fehleranalyse_architektur_kontext.md
```

---

## 🔧 LÖSUNGSVORSCHLÄGE

### **Sofortmaßnahmen (Quick Wins)**

1. **Frontend Build fixen:**
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **Model Router Timeout erhöhen:**
   ```python
   # In model_router.py
   DEFAULT_TIMEOUT = 180  # statt 120
   ```

3. **Playwright Health-Check:**
   ```python
   # In agents/tester_playwright.py
   async def wait_for_server(url, timeout=30):
       for _ in range(timeout):
           try:
               response = requests.get(url)
               if response.status_code == 200:
                   return True
           except:
               await asyncio.sleep(1)
       return False
   ```

---

### **Mittelfristige Verbesserungen**

1. **Parallele Modell-Anfragen:**
   - Mehrere Modelle gleichzeitig anfragen
   - Schnellste Antwort verwenden
   - Andere Anfragen abbrechen

2. **Bessere Fehler-Diagnostik:**
   - Sandbox-Temp-Dateien bei Fehler behalten
   - Detaillierte Zeilen-Nummern + Kontext
   - Automatische Fix-Vorschläge

3. **Test-Infrastruktur:**
   - Docker-Container für isolierte Tests
   - Automatischer Server-Start vor Tests
   - Parallele Test-Ausführung

---

## 📈 METRIKEN & MONITORING

**Aus crew_log.jsonl:**
- **Token-Verbrauch:** ~312k-347k Tokens pro Iteration
- **Kosten:** $0.00 (nur Free-Modelle)
- **Durchschnittliche Iteration:** 2-4 Minuten
- **Erfolgsrate:** ~40% beim ersten Versuch
- **Typische Iterationen bis Erfolg:** 3-5

**Bottlenecks:**
1. Modell-Timeouts (40% der Zeit)
2. Test-Ausführung (30% der Zeit)
3. Security-Scans (20% der Zeit)
4. Code-Generierung (10% der Zeit)

---

## ✅ NÄCHSTE SCHRITTE

1. ✅ Frontend Build-Fehler beheben
2. ✅ Model Router Timeout-Konfiguration anpassen
3. ✅ Playwright Health-Check implementieren
4. ⏳ Sandbox-Fehler-Diagnostik verbessern
5. ⏳ Parallele Modell-Anfragen implementieren
6. ⏳ Docker-basierte Test-Umgebung aufsetzen

---

**Ende der Analyse**

