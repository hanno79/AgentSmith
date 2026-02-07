# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 03.02.2026
Version: 1.5
Beschreibung: Coder Agent - Generiert Production-Ready Code basierend auf Projektanforderungen.
              AENDERUNG 31.01.2026: Single-File Modus fuer File-by-File Generierung (Anti-Truncation).
              AENDERUNG 01.02.2026: Dependency-Versionen fuer requirements.txt.
              AENDERUNG 02.02.2026: Anti-Pattern Constraints hinzugefuegt (zirkulaere Imports etc.)
              AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config an LLM uebergeben (Root Cause fuer Truncation!)
"""

import logging
from typing import Any, Dict, List, Optional
from crewai import Agent, LLM

logger = logging.getLogger(__name__)

# ÄNDERUNG 24.01.2026: Zentrale Hilfsfunktion verwenden (Single Source of Truth)
from agents.agent_utils import get_model_from_config, combine_project_rules

# AENDERUNG 01.02.2026: Dependency-Versionen fuer requirements.txt
try:
    from backend.dev_loop_helpers import get_python_dependency_versions
except ImportError:
    # Fallback wenn Import fehlschlaegt (z.B. bei direktem Agent-Test)
    def get_python_dependency_versions():
        return ""


def create_coder(config: Dict[str, Any], project_rules: Dict[str, List[str]], router=None) -> Agent:
    """
    Erstellt den Coder-Agenten, der auf Basis des Plans und Feedbacks
    funktionierenden, sauberen Code schreibt.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln
        router: Optional ModelRouter für Fallback bei Rate Limits

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    # AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config/Router holen
    if router:
        model_name = router.get_model("coder")
        max_tokens = router.get_token_limit("coder", default=8192)
    else:
        model_name = get_model_from_config(config, "coder")
        max_tokens = config.get("token_limits", {}).get("coder", 8192)

    # AENDERUNG 03.02.2026: Fix 11 - LLM-Objekt mit max_tokens erstellen
    # Das ist die ROOT CAUSE fuer Truncation: Ohne explizites max_tokens
    # verwendet das Modell sein Default (oft nur 2K-4K bei Free-Modellen)
    llm = LLM(
        model=model_name,
        max_tokens=max_tokens
    )
    logger.info(f"[Coder] LLM erstellt: {model_name} mit max_tokens={max_tokens}")

    combined_rules = combine_project_rules(project_rules, "coder")

    return Agent(
        role="Senior Full-Stack Developer",
        goal=(
            "Schreibe sauberen, effizienten und vor allem SOFORT AUSFÜHRBAREN Code. "
            "Stelle sicher, dass alle notwendigen Dateien (Backend, Frontend, Config, Setup-Scripte) vorhanden sind. "
            "Erstelle immer eine `run.bat` (für Windows), die alle Dienste startet und ggf. den Browser öffnet."
        ),
        backstory=(
            "Du bist ein pragmatischer Senior Developer. Dein Ziel ist 'Production-Ready Code'. "
            "Du denkst nicht nur an die Logik, sondern auch an die Deployment-Fähigkeit. "
            "Wenn du ein Web-Projekt baust, sorge dafür, dass Backend und Frontend harmonieren. "
            "Nutze das Format ### FILENAME: Pfad/Datei.ext für JEDE Datei.\n\n"
            "## WICHTIG - KEINE EMOJIS IM CODE\n"
            "- Verwende KEINE Emojis (z.B. Checkmarks, Kreuze, Ordner-Icons) in Python/SQL/Batch-Dateien\n"
            "- Verwende KEINE Unicode-Sonderzeichen in Kommentaren\n"
            "- Halte Code ASCII-kompatibel (nur a-z, A-Z, 0-9, Standard-Satzzeichen)\n"
            "- Ausnahme: UTF-8 Strings fuer Benutzer-sichtbare Texte in der UI\n\n"
            "## PROJEKTSTRUKTUR (automatisch erstellt)\n"
            "Lege Dateien IMMER in den entsprechenden Ordnern ab:\n"
            "- tests/   -> Unit-Tests (test_*.py mit pytest)\n"
            "- docs/    -> Dokumentation (ausser README.md im Root)\n"
            "- src/     -> Quellcode bei groesseren Projekten\n"
            "- assets/  -> Statische Ressourcen (Bilder, CSS, etc.)\n\n"
            "## ANTI-PATTERN REGELN (KRITISCH!)\n"
            "Diese Fehler fuehren zu Docker-Fehlern und muessen VERMIEDEN werden:\n\n"
            "1. ZIRKULAERE IMPORTS VERMEIDEN:\n"
            "   - NIEMALS: from src.routes import X in src/__init__.py UND from src import Y in routes.py\n"
            "   - STATTDESSEN: Importiere Module, nicht Objekte (import src.routes statt from src.routes import)\n"
            "   - ODER: Lazy Imports innerhalb von Funktionen wenn noetig\n"
            "   - __init__.py sollte MINIMAL sein - nur __all__ definieren, keine App-Logik\n\n"
            "2. IMPORT-REIHENFOLGE:\n"
            "   - Definiere Objekte BEVOR du sie importierst\n"
            "   - In Flask: db = SQLAlchemy() VOR route-Imports\n"
            "   - In src/__init__.py: Erst db/app erstellen, DANN routes importieren\n\n"
            "3. VOLLSTAENDIGER CODE:\n"
            "   - NIEMALS Code abschneiden oder mit '...' abkuerzen\n"
            "   - Jede Funktion MUSS vollstaendig sein (inkl. return)\n"
            "   - Jede Klasse MUSS alle Methoden enthalten\n"
            "   - Jeder Block MUSS geschlossen werden (if/for/def/class)\n\n"
            "4. REQUIREMENTS.TXT:\n"
            "   - NUR existierende PyPI-Pakete verwenden\n"
            "   - KEINE erfundenen Pakete (z.B. 'bootstrap' existiert nicht als Python-Paket)\n"
            "   - Bei Unsicherheit: >= statt == verwenden\n\n"
            f"{combined_rules}"
        ),
        llm=llm,  # AENDERUNG 03.02.2026: LLM-Objekt statt String
        verbose=True
    )


# AENDERUNG 31.01.2026: Single-File Modus fuer File-by-File Generierung

SINGLE_FILE_BACKSTORY = """
Du generierst NUR EINE einzige Datei auf einmal.
Halte den Code kompakt und fokussiert.
ERSTELLE KEINE anderen Dateien!

REGELN:
- Gib NUR den Code fuer die angeforderte Datei aus
- Maximale Laenge: 200 Zeilen
- Keine Emojis oder Unicode-Sonderzeichen im Code
- Format: ### FILENAME: {requested_file}
- Danach der vollstaendige, ausfuehrbare Code

KONTEXT-NUTZUNG:
- Nutze die bereits erstellten Dateien als Referenz
- Importiere aus bestehenden Modulen korrekt
- Halte die API-Kompatibilitaet zu existierenden Dateien

ANTI-PATTERN (KRITISCH - Diese Fehler vermeiden!):
1. ZIRKULAERE IMPORTS:
   - In __init__.py: KEINE Importe aus Submodulen die wiederum aus __init__ importieren
   - Fuer Flask: db = SQLAlchemy() in __init__.py BEVOR routes importiert werden
   - Lazy Import Pattern: Importiere innerhalb von Funktionen wenn noetig

2. VOLLSTAENDIGKEIT:
   - Code NIEMALS abschneiden oder mit ... abkuerzen
   - Jede Funktion mit return/pass beenden
   - Alle Bloecke (if/for/def/class) schliessen

3. REQUIREMENTS.TXT:
   - NUR echte PyPI-Pakete (keine erfundenen Namen)
   - pytest wenn tests/ existiert
"""


def create_single_file_coder(
    config: Dict[str, Any],
    project_rules: Dict[str, List[str]],
    router=None,
    target_file: str = "",
    file_description: str = ""
) -> Agent:
    """
    Erstellt einen Coder-Agenten der NUR EINE Datei generiert.

    Dies loest das Truncation-Problem bei Free-Tier-Modellen, da jede
    Datei einzeln generiert wird statt alle auf einmal.

    Args:
        config: Anwendungskonfiguration
        project_rules: Projekt-Regeln
        router: Optional ModelRouter
        target_file: Pfad der zu erstellenden Datei
        file_description: Beschreibung der Datei

    Returns:
        Konfigurierte CrewAI Agent-Instanz fuer Single-File Generierung
    """
    # AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config/Router holen
    if router:
        model_name = router.get_model("coder")
        max_tokens = router.get_token_limit("coder", default=8192)
    else:
        model_name = get_model_from_config(config, "coder")
        max_tokens = config.get("token_limits", {}).get("coder", 8192)

    # AENDERUNG 03.02.2026: Fix 11 - LLM-Objekt mit max_tokens erstellen
    llm = LLM(
        model=model_name,
        max_tokens=max_tokens
    )
    logger.info(f"[SingleFileCoder] LLM erstellt: {model_name} mit max_tokens={max_tokens}")

    combined_rules = combine_project_rules(project_rules, "coder")

    goal = f"Erstelle NUR die Datei: {target_file}"
    if file_description:
        goal += f" - {file_description}"

    backstory = SINGLE_FILE_BACKSTORY.format(requested_file=target_file)
    backstory += f"\n\n{combined_rules}"

    return Agent(
        role="Single-File Developer",
        goal=goal,
        backstory=backstory,
        llm=llm,  # AENDERUNG 03.02.2026: LLM-Objekt statt String
        verbose=True
    )


def build_single_file_prompt(
    target_file: str,
    file_description: str,
    blueprint: Dict[str, Any],
    existing_files: Dict[str, str],
    user_goal: str
) -> str:
    """
    Baut den Prompt fuer eine einzelne Datei.

    Args:
        target_file: Pfad der zu erstellenden Datei
        file_description: Was die Datei enthalten soll
        blueprint: TechStack-Blueprint
        existing_files: Dict mit bereits erstellten Dateien (path -> content)
        user_goal: Urspruengliches Benutzer-Ziel

    Returns:
        Vollstaendiger Prompt fuer den Coder
    """
    prompt = f"""Erstelle NUR die Datei: {target_file}

BESCHREIBUNG:
{file_description}

BENUTZER-ZIEL:
{user_goal}

TECHNISCHER KONTEXT:
- Projekt-Typ: {blueprint.get('project_type', 'unknown')}
- Sprache: {blueprint.get('language', 'unknown')}
- App-Typ: {blueprint.get('app_type', 'webapp')}
"""

    if existing_files:
        prompt += "\n\nBEREITS ERSTELLTE DATEIEN (als Referenz):\n"
        for filepath, content in existing_files.items():
            # Zeige nur die ersten 50 Zeilen jeder Datei als Kontext
            lines = content.split('\n')[:50]
            truncated = '\n'.join(lines)
            if len(content.split('\n')) > 50:
                truncated += "\n... (gekuerzt)"
            prompt += f"\n--- {filepath} ---\n{truncated}\n"

    # AENDERUNG 01.02.2026: Spezialbehandlung fuer requirements.txt
    # Verhindert dass LLM veraltete/falsche Versionen generiert (z.B. greenlet==2.0.7)
    if target_file.endswith("requirements.txt"):
        dep_versions = get_python_dependency_versions()
        if dep_versions:
            prompt += f"\n\nPACKAGES: {dep_versions}\n"
            prompt += "WICHTIG: Verwende NUR diese Versionen! Erfinde KEINE eigenen Versionsnummern!\n"
            prompt += "Falls ein Paket nicht in der Liste ist, nutze >= statt == (z.B. requests>=2.0)\n"

    prompt += f"""

WICHTIG:
- Gib NUR den Code fuer {target_file} aus
- Format: ### FILENAME: {target_file}
- Danach der vollstaendige Code
- Keine anderen Dateien erstellen!
- Maximal 200 Zeilen
- Keine Emojis im Code
"""

    return prompt
