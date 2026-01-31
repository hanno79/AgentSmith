# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Agent zur Verwaltung von Docker-Containern fuer generierte Projekte.
              Generiert optimierte Dockerfiles basierend auf dem TechStack.
"""

from crewai import Agent
from typing import Optional, Dict, Any

# =========================================================================
# Agent Backstory und Prompts
# =========================================================================

DOCKER_AGENT_BACKSTORY = """
Du bist ein erfahrener Docker-Experte und DevOps-Spezialist im Entwicklungsbuero.

DEINE KERNAUFGABEN:
1. Generiere optimierte Dockerfiles fuer verschiedene TechStacks
2. Analysiere Projekt-Anforderungen und waehle passende Base-Images
3. Optimiere Container fuer Groesse und Performance
4. Diagnostiziere und behebe Container-Probleme

DEIN WISSEN - BASE IMAGES:
- Python: python:3.11-slim (Klein, produktionsreif)
- Node.js: node:20-alpine (Minimal, schnell)
- Playwright: mcr.microsoft.com/playwright:v1.40.0-jammy (UI-Tests)
- Full-Stack: Python + Node.js kombiniert

DEIN WISSEN - BEST PRACTICES:
1. Immer schlanke Base-Images verwenden (-slim, -alpine)
2. Multi-Stage-Builds fuer Produktion
3. .dockerignore fuer kleinere Build-Contexts
4. Keine Secrets im Dockerfile (ENV fuer Runtime)
5. HEALTHCHECK fuer Produktions-Container
6. Non-root User fuer Security

AUSGABE-FORMAT fuer Dockerfile:
### DOCKERFILE:
```dockerfile
[Dockerfile-Inhalt]
```

REGELN:
1. IMMER vollstaendige, ausfuehrbare Dockerfiles
2. Kommentare in Deutsch
3. Optimiert fuer den spezifischen TechStack
4. Keine unnuetigen Layers (RUN-Befehle kombinieren)
"""

DOCKER_DIAGNOSIS_PROMPT = """
Analysiere diesen Docker-Fehler und gib eine Loesung:

FEHLER:
{error}

PROJEKT-KONTEXT:
- TechStack: {tech_stack}
- Language: {language}
- Projekt-Typ: {project_type}

Gib eine praezise Diagnose und konkrete Loesungsschritte.
"""


# =========================================================================
# Agent Factory
# =========================================================================

def create_docker_agent(
    config: Dict[str, Any],
    router=None,
    project_rules: Optional[Dict[str, Any]] = None
) -> Agent:
    """
    Erstellt den Docker-Agent fuer Container-Management.

    Args:
        config: Globale Konfiguration
        router: Model-Router fuer Fallback-Handling
        project_rules: Optionale Projekt-spezifische Regeln

    Returns:
        Konfigurierter CrewAI Agent
    """
    # Model aus Config oder Fallback
    mode = config.get("mode", "test")
    models = config.get("models", {}).get(mode, {})

    # Docker-Agent nutzt dasselbe Modell wie Coder (Code-Generierung)
    model_config = models.get("coder", {})
    if isinstance(model_config, dict):
        model = model_config.get("primary", "openrouter/meta-llama/llama-3.3-70b-instruct:free")
    else:
        model = model_config

    # Mit Router das aktuelle Modell holen (Fallback-aware)
    if router:
        model = router.get_model("coder")

    backstory = DOCKER_AGENT_BACKSTORY

    # Projekt-spezifische Regeln hinzufuegen
    if project_rules:
        docker_rules = project_rules.get("docker", [])
        if docker_rules:
            backstory += "\n\nPROJEKT-SPEZIFISCHE DOCKER-REGELN:\n"
            backstory += "\n".join(f"- {rule}" for rule in docker_rules)

    return Agent(
        role="Docker Specialist",
        goal="Erstelle optimierte Docker-Konfigurationen fuer Projekte",
        backstory=backstory,
        verbose=False,
        llm=model,
        allow_delegation=False
    )


# =========================================================================
# Dockerfile-Generierung
# =========================================================================

def generate_dockerfile_prompt(
    tech_blueprint: Dict[str, Any],
    project_files: Dict[str, str],
    use_case: str = "development"
) -> str:
    """
    Erstellt einen Prompt fuer Dockerfile-Generierung.

    Args:
        tech_blueprint: TechStack-Blueprint
        project_files: Dict mit Dateinamen -> Inhalt
        use_case: "development" oder "production"

    Returns:
        Prompt-String fuer den Docker-Agent
    """
    language = tech_blueprint.get("language", "python")
    project_type = tech_blueprint.get("project_type", "python_script")
    dependencies = tech_blueprint.get("dependencies", [])
    requires_server = tech_blueprint.get("requires_server", False)
    server_port = tech_blueprint.get("server_port", 5000)

    # Dateien auflisten
    file_list = "\n".join(f"- {name}" for name in project_files.keys())

    prompt = f"""Generiere ein optimiertes Dockerfile fuer dieses Projekt:

PROJEKT-DETAILS:
- Sprache: {language}
- Projekt-Typ: {project_type}
- Einsatzzweck: {use_case}
- Benoetigt Server: {requires_server}
- Server-Port: {server_port}

DEPENDENCIES:
{', '.join(dependencies) if dependencies else 'Keine spezifischen'}

PROJEKT-DATEIEN:
{file_list}

ANFORDERUNGEN:
1. Waehle das passende Base-Image
2. Installiere alle Dependencies
3. Kopiere Projekt-Dateien
4. Setze korrekten WORKDIR und CMD
5. Expose den Server-Port wenn noetig
6. Fuer {use_case}: {"Multi-Stage-Build" if use_case == "production" else "Einfaches Setup"}

AUSGABE-FORMAT:
### DOCKERFILE:
```dockerfile
[Dein Dockerfile hier]
```
"""
    return prompt


def extract_dockerfile(agent_output: str) -> Optional[str]:
    """
    Extrahiert das Dockerfile aus der Agent-Ausgabe.

    Args:
        agent_output: Ausgabe des Docker-Agents

    Returns:
        Dockerfile-Inhalt oder None
    """
    import re

    # Pattern fuer Code-Block
    patterns = [
        r'```dockerfile\n(.*?)```',
        r'### DOCKERFILE:\n```\n(.*?)```',
        r'### DOCKERFILE:\n```dockerfile\n(.*?)```',
    ]

    for pattern in patterns:
        match = re.search(pattern, agent_output, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: Wenn kein Pattern matched, aber FROM vorhanden
    if "FROM " in agent_output:
        lines = agent_output.split("\n")
        dockerfile_lines = []
        in_dockerfile = False

        for line in lines:
            if line.startswith("FROM "):
                in_dockerfile = True
            if in_dockerfile:
                # Stoppe bei offensichtlichem Ende
                if line.startswith("###") or line.startswith("ERKLAERUNG"):
                    break
                dockerfile_lines.append(line)

        if dockerfile_lines:
            return "\n".join(dockerfile_lines).strip()

    return None


# =========================================================================
# Dockerfile-Templates (Fallback wenn Agent nicht verfuegbar)
# =========================================================================

DOCKERFILE_TEMPLATES = {
    "python": '''# Python Development Container
FROM python:3.11-slim

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    sqlite3 \\
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Projekt-Code
COPY . .

# Standard-Port
EXPOSE 5000

# Start-Befehl
CMD ["python", "src/app.py"]
''',

    "nodejs": '''# Node.js Development Container
FROM node:20-alpine

WORKDIR /app

# Dependencies installieren
COPY package*.json ./
RUN npm install --silent

# Projekt-Code
COPY . .

# Standard-Port
EXPOSE 3000

# Start-Befehl
CMD ["npm", "start"]
''',

    "flask": '''# Flask Web Application Container
FROM python:3.11-slim

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    sqlite3 \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Projekt-Code
COPY . .

# Umgebungsvariablen
ENV FLASK_APP=src/app.py
ENV FLASK_ENV=development

# Port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD curl -f http://localhost:5000/health || exit 1

# Start-Befehl
CMD ["flask", "run", "--host=0.0.0.0"]
''',

    "fastapi": '''# FastAPI Web Application Container
FROM python:3.11-slim

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    sqlite3 \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Projekt-Code
COPY . .

# Port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Start-Befehl
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
'''
}


def get_dockerfile_template(tech_blueprint: Dict[str, Any]) -> str:
    """
    Gibt ein passendes Dockerfile-Template zurueck.

    Args:
        tech_blueprint: TechStack-Blueprint

    Returns:
        Dockerfile-Template als String
    """
    project_type = tech_blueprint.get("project_type", "").lower()
    language = tech_blueprint.get("language", "python").lower()

    # Spezifische Templates
    if "flask" in project_type:
        return DOCKERFILE_TEMPLATES["flask"]
    elif "fastapi" in project_type:
        return DOCKERFILE_TEMPLATES["fastapi"]
    elif language == "python":
        return DOCKERFILE_TEMPLATES["python"]
    elif language in ("javascript", "nodejs", "typescript"):
        return DOCKERFILE_TEMPLATES["nodejs"]

    # Default: Python
    return DOCKERFILE_TEMPLATES["python"]
