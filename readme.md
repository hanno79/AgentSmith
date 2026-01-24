# AgentSmith - Multi-Agent Development System

Ein sophistiziertes Multi-Agent-System zur autonomen Code-Generierung mit Self-Healing-Fähigkeiten.

## Überblick

AgentSmith orchestriert spezialisierte KI-Agenten, die zusammenarbeiten, um funktionsfähige Software-Projekte basierend auf natürlichsprachlichen Anforderungen zu erstellen.

### Kern-Features

- **10+ spezialisierte Agenten** - Coder, Reviewer, Designer, Tester, Security, Memory, etc.
- **Self-Healing Loop** - Automatische Fehlerkorrektur durch iteratives Feedback (max 5 Versuche)
- **Sichere Code-Validierung** - AST-basiertes Parsing ohne Code-Ausführung
- **Persistentes Lernen** - Memory-System speichert Fehler-Patterns für zukünftige Projekte
- **Visual Regression Testing** - Playwright-basierte UI-Tests mit Screenshot-Vergleich
- **Security Scanning** - OWASP Top 10 Vulnerability-Checks

## Schnellstart

### 1. Installation

```bash
# Repository klonen
git clone <repo-url>
cd multi_agent_poc

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate  # Windows
# oder: source venv/bin/activate  # Linux/Mac

# Dependencies installieren
pip install -r requirements.txt

# Playwright Browser installieren
playwright install chromium
```

### 2. Konfiguration

Setze deinen API-Key als Umgebungsvariable:

```bash
# Windows
set OPENAI_API_KEY=your-api-key

# Linux/Mac
export OPENAI_API_KEY=your-api-key
```

Passe `config.yaml` an deine Bedürfnisse an:

```yaml
mode: test  # oder "production" für Premium-Modelle
project_type: webapp
include_designer: true
max_retries: 5
```

### 3. Ausführung

**CLI-Modus:**
```bash
python main.py
```

**Web-UI Modus:**
```bash
# Backend starten
uvicorn backend.api:app --port 8000

# Frontend starten (in separatem Terminal)
cd frontend
npm install
npm run dev
```

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Meta-Orchestrator                        │
│            (Analysiert Prompt, erstellt Plan)               │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│    Researcher    │ │ TechStack Arch.  │ │ Database Designer│
│   (Web Search)   │ │  (JSON Blueprint)│ │   (Schema/ERD)   │
└──────────────────┘ └──────────────────┘ └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Development Loop                         │
│  ┌────────┐    ┌─────────┐    ┌────────┐    ┌──────────┐   │
│  │ Coder  │ ─► │ Sandbox │ ─► │ Tester │ ─► │ Reviewer │   │
│  └────────┘    └─────────┘    └────────┘    └──────────┘   │
│       ▲                                           │        │
│       └───────────── Feedback Loop ───────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Post-Success                            │
│  ┌──────────────┐    ┌────────────┐    ┌────────────────┐  │
│  │ Security Scan│ ─► │   Memory   │ ─► │ Orchestrator   │  │
│  │ (OWASP Top10)│    │  (Lessons) │    │  (README.md)   │  │
│  └──────────────┘    └────────────┘    └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Agenten

| Agent | Beschreibung |
|-------|--------------|
| **Meta-Orchestrator** | Analysiert User-Prompts via Regex, erstellt dynamischen Ausführungsplan |
| **TechStack Architect** | Entscheidet Tech-Stack, generiert JSON Blueprint |
| **Database Designer** | Erstellt normalisierte Schemas (3NF+) mit Mermaid ERD |
| **Designer** | UI/UX Konzepte mit CSS-Variablen und Flat Design |
| **Coder** | Generiert Production-Ready Code im `### FILENAME:` Format |
| **Reviewer** | 5-Punkte-Validierung, striktes ❌-Blocking |
| **Tester** | Playwright UI-Tests mit Visual Regression |
| **Security Agent** | OWASP Top 10 Vulnerability-Scanning |
| **Researcher** | Web-Recherche via DuckDuckGo |
| **Memory Agent** | Persistiert Lessons Learned für zukünftige Projekte |

## Projektstruktur

```
multi_agent_poc/
├── agents/                    # 10+ spezialisierte Python-Agenten
│   ├── meta_orchestrator_agent.py
│   ├── coder_agent.py
│   ├── reviewer_agent.py
│   └── ...
├── backend/                   # FastAPI + WebSocket Server
│   ├── api.py
│   └── orchestration_manager.py
├── frontend/                  # React + Vite + Tailwind Dashboard
│   └── src/App.jsx
├── tests/                     # pytest Test-Suite
│   ├── test_meta_orchestrator.py
│   ├── test_sandbox_runner.py
│   └── test_memory_agent.py
├── main.py                    # CLI Entry Point
├── config.yaml               # Zentrale Konfiguration
├── config_validator.py       # Pydantic-basierte Validierung
├── exceptions.py             # Standardisierte Exceptions
├── sandbox_runner.py         # Sichere Code-Validierung (AST)
├── logger_utils.py           # JSONL Event-Logging
├── memory/                   # Persistente Lernhistorie
└── projects/                 # Generierte Projekte
```

## Konfiguration

### config.yaml Struktur

```yaml
# API-Einstellungen
openai_api_base: "https://openrouter.ai/api/v1"
openai_api_key: "${OPENAI_API_KEY}"

# Betriebsmodus
mode: "test"  # test = kostenlose Modelle, production = Premium
project_type: "webapp"
include_designer: true
max_retries: 5

# Modelle pro Modus
models:
  test:
    coder: "qwen/qwen3-coder:free"
    reviewer: "meta-llama/llama-3.3-70b-instruct:free"
    # ...
  production:
    coder: "anthropic/claude-opus-4.5"
    reviewer: "openai/gpt-4-turbo"
    # ...

# Projekt-Templates mit Regeln
templates:
  webapp:
    global:
      - "UTF-8 Encoding verwenden"
    coder:
      - "Erstelle immer requirements.txt"
    security:
      - "Keine hardcoded API-Keys"
```

## Tests ausführen

```bash
# Alle Tests
python -m pytest tests/ -v

# Mit Coverage
python -m pytest tests/ --cov=. --cov-report=html
```

## API-Endpunkte (Backend)

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/run` | POST | Startet Agent-Task |
| `/ws` | WebSocket | Real-Time Log-Streaming |
| `/status` | GET | System-Status |

## Lizenz

MIT License

## Beitragende

- AgentSmith Team
