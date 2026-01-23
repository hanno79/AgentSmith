# 🧠 Multi-Agenten Proof-of-Concept (PoC)

**Version:** v3.0  
**Stand:** 8. Januar 2026  
**Autor:** HR Dart / ChatGPT-5  
**Ablage:** /multi_agent_poc  

---

## 🚀 Projektziel
Ziel des Projekts ist der Aufbau eines **modularen, erweiterbaren Multi-Agenten-Systems**,  
das Softwareentwicklungs- und Analyseaufgaben automatisiert durchführen kann –  
vom Planen über die Codierung bis hin zu Review, Testing und Memory-Lernen.

Langfristig soll daraus ein **autonomes KI-Unternehmen** entstehen,  
das eigenständig Aufgaben im Bereich Softwareentwicklung, GIS, Forschung  
oder Datenanalyse bearbeitet.

---

## 🏗️ Architekturübersicht

### 🔸 Meta-Orchestrator (Projektleiter)
- Erkennt automatisch, **welche Agenten aktiviert werden müssen**
- Analysiert das Ziel („User Goal“) und plant den Workflow
- Übergibt strukturierte Aufgaben (Tasks) an die Crew
- Version aktuell: **MetaOrchestratorV2**

### 🔸 Orchestrator
- Leitet operative Kommunikation zwischen Agents
- Nimmt Pläne des Meta-Orchestrators entgegen
- Startet und überwacht die Task-Sequenzen

### 🔸 Coder-Agent
- Erstellt **funktionierenden Code** auf Basis der Beschreibung
- Erkennt Sprache (Python, HTML, CSS, JS) automatisch
- Gibt nur reinen Code zurück (keine Erklärungen)
- Nutzt Lessons aus dem Memory (z. B. UTF-8 Encoding-Regel)

### 🔸 Designer-Agent
- Verantwortlich für visuelles Design, Farben, Layouts
- Liefert Designkonzepte oder direktes CSS
- Optional, wird durch Meta-Orchestrator aktiviert

### 🔸 Reviewer-Agent
- Überprüft Code auf Syntax, Semantik, PEP8- oder HTML-Regeln
- Erkennt Encoding-Probleme (UTF-8) oder logische Fehler
- Gibt „OK“ oder Korrekturvorschläge an den Orchestrator zurück

### 🔸 Tester-Agent (Playwright-basiert)
- Führt **echte UI-Tests** mit Playwright aus:
  - Klicktests für Buttons, Formulare, Navigation
  - Responsivitätsprüfung
  - Validierung aller Links & Statuscodes
- Speichert Screenshots in `/projects/.../screenshots`
- Erkennt, ob neue Durchläufe notwendig sind

### 🔸 Memory-Agent
- Persistiert Wissen über vergangene Durchläufe:
  - Fehler, Reviews, Sandbox-Ausgaben
  - erfolgreiche Designs oder Coding-Patterns
- Führt globale und projektbezogene Memorys (`memory.json`)  
- Liefert Lessons an Coder/Reviewer zurück, um Wiederholungsfehler zu vermeiden

### 🔸 Sandbox
- Führt generierten Code isoliert aus
- Erlaubt Tests, ohne das System zu gefährden
- Erkennt Syntaxfehler, falsches Encoding oder Laufzeitfehler
- Ergebnisse werden ebenfalls im Memory gespeichert

---

## 🧩 Daten- & Verzeichnisstruktur

multi_agent_poc/
│
├── main.py # Hauptsteuerung
├── config.yaml # Modellkonfiguration (OpenRouter etc.)
├── sandbox_runner.py # Sicheres Test-Framework
│
├── agents/
│ ├── init.py
│ ├── coder_agent.py
│ ├── designer_agent.py
│ ├── reviewer_agent.py
│ ├── tester_agent.py
│ ├── memory_agent.py
│ ├── orchestrator_agent.py
│ └── meta_orchestrator_agent.py
│
├── projects/
│ └── project_YYYYMMDD_HHMMSS/
│ ├── project_YYYYMMDD_HHMMSS.html
│ └── screenshots/
│
└── memory/
├── memory.json
└── project_memory.json

multi_agent_poc/
│
├── main.py # Hauptsteuerung
├── config.yaml # Modellkonfiguration (OpenRouter etc.)
├── sandbox_runner.py # Sicheres Test-Framework
│
├── agents/
│ ├── init.py
│ ├── coder_agent.py
│ ├── designer_agent.py
│ ├── reviewer_agent.py
│ ├── tester_agent.py
│ ├── memory_agent.py
│ ├── orchestrator_agent.py
│ └── meta_orchestrator_agent.py
│
├── projects/
│ └── project_YYYYMMDD_HHMMSS/
│ ├── project_YYYYMMDD_HHMMSS.html
│ └── screenshots/
│
└── memory/
├── memory.json
└── project_memory.json