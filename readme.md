# 🤖 Multi-Agent Proof of Concept (CrewAI)

Dieses Projekt ist ein **lokaler Proof of Concept für ein Multi-Agenten-System** auf Basis von [CrewAI](https://github.com/joaomdmoura/crewAI).  
Es zeigt, wie ein Orchestrator-Agent Aufgaben an spezialisierte Subagenten (Coder, Reviewer, Designer) delegiert,  
Code automatisch ausführt, Feedbackschleifen verarbeitet und alles protokolliert.

---

## 📁 Projektstruktur

multi_agent_poc/
│
├── config.yaml # Zentrale Konfigurationsdatei
├── main.py # Startpunkt des Systems
├── sandbox_runner.py # Sichere Codeausführung + Paket-Handling
├── logger_utils.py # Logging-System
│
└── agents/
├── orchestrator_agent.py
├── coder_agent.py
├── reviewer_agent.py
└── designer_agent.py

---

## ⚙️ Voraussetzungen

- **Python** ≥ 3.9 (empfohlen: 3.10 oder 3.11)
- **Virtuelle Umgebung** (`venv`)
- CrewAI & OpenAI-kompatible API (z. B. [OpenRouter](https://openrouter.ai))

---

## 🧩 Installation

1. Repository-Ordner anlegen:
   ```bash
   mkdir multi_agent_poc
   cd multi_agent_poc

python -m venv venv

venv\Scripts\activate         # Windows

pip install crewai openai pyyaml termcolor

export OPENAI_API_KEY="DEIN_OPENROUTER_KEY"
export OPENAI_API_BASE="https://openrouter.ai/api/v1"

setx OPENAI_API_KEY "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
"
setx OPENAI_API_BASE "https://openrouter.ai/api/v1"
