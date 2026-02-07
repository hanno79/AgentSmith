"""
Author: rahn
Datum: 03.02.2026
Version: 1.2
Beschreibung: Spezialisierter Agent fuer gezielte Code-Korrekturen.
              Repariert nur die gemeldeten Fehler, ohne funktionierenden Code zu aendern.
              AENDERUNG 02.02.2026: Signatur-Fix fuer UTDS BatchExecution Kompatibilitaet.
              AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config an LLM uebergeben.
"""

import logging
from crewai import Agent, LLM
from typing import Dict, List, Optional, Any

# AENDERUNG 02.02.2026: Import fuer konsistente project_rules Verarbeitung
# AENDERUNG 02.02.2026: get_model_from_config fuer Single Source of Truth Modellwahl
from agents.agent_utils import combine_project_rules, get_model_from_config

logger = logging.getLogger(__name__)

# =============================================================================
# Fix-Agent Backstory und Prompts
# =============================================================================

FIX_AGENT_BACKSTORY = """
Du bist ein Debugging-Experte, spezialisiert auf gezielte Code-Korrekturen.

DEINE AUFGABE:
- Korrigiere NUR die angegebenen Fehler
- Aendere so wenig wie moeglich am bestehenden Code
- Behalte funktionierenden Code unveraendert
- Stelle sicher dass alle Imports korrekt sind

EINGABE DIE DU ERHAELTST:
- Aktuelle Datei mit Zeilennummern
- Fehlermeldung mit betroffenen Zeilen
- Kontext aus abhaengigen Dateien (falls vorhanden)

AUSGABE-FORMAT:
Du gibst die korrigierte Datei im folgenden Format aus:

### CORRECTION: {dateipfad}
```
[Die korrigierte Version der GESAMTEN Datei]
```

WICHTIGE REGELN:
1. Keine neuen Features hinzufuegen
2. Keine Refactorings durchfuehren
3. Nur den gemeldeten Fehler beheben
4. Imports und Abhaengigkeiten beachten
5. Code-Stil und Formatierung beibehalten
6. Kommentare und Dokumentation erhalten
7. Keine Emojis oder Unicode-Sonderzeichen verwenden
8. ASCII-kompatibel bleiben (a-z, A-Z, 0-9, Standard-Satzzeichen)

FEHLERTYPEN UND LOESUNGEN:
- syntax: Korrigiere die Syntax (fehlende Klammern, Einrueckung, etc.)
- import: Fuege fehlende Imports hinzu oder korrigiere Import-Pfade
- runtime: Behebe Laufzeitfehler (TypeError, AttributeError, etc.)
- test: Korrigiere fehlgeschlagene Tests oder Test-Erwartungen
- truncation: Vervollstaendige abgeschnittenen Code

WENN DU UNSICHER BIST:
- Lieber minimal aendern als zu viel
- Im Zweifel die urspruengliche Struktur beibehalten
- Bei komplexen Fehlern nur den direkten Fehler beheben
"""


def create_fix_agent(
    config: Dict[str, Any],
    project_rules: Dict[str, Any] = None,
    router=None,
    target_file: str = "",
    error_info: Optional[Dict[str, Any]] = None,
    tech_blueprint: Dict[str, Any] = None
) -> Agent:
    """
    Erstellt einen spezialisierten Fix-Agent fuer eine Datei.

    Args:
        config: Konfiguration mit Modell-Einstellungen
        project_rules: Projektspezifische Regeln (Dict wie bei anderen Agenten)
        router: Optional - Model Router fuer dynamische Modellwahl
        target_file: Der Pfad der zu korrigierenden Datei
        error_info: Optional - Informationen ueber den Fehler
        tech_blueprint: Optional - Tech-Stack-Informationen (language, framework, project_type)

    Returns:
        CrewAI Agent konfiguriert fuer Code-Korrekturen

    AENDERUNG 02.02.2026: Signatur von project_rules: str auf Dict[str, Any] geaendert
                          fuer Konsistenz mit anderen Agenten (coder, tester, reviewer).
                          Dies behebt den UTDS BatchExecution Bug.
    AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config an LLM uebergeben.
    AENDERUNG 06.02.2026: ROOT-CAUSE-FIX tech_blueprint Parameter hinzugefuegt.
                          Symptom: Fix-Agent erzeugt Python-Code (BeispielDatei.py) fuer JS-Projekte
                          Ursache: Agent hatte keine Information ueber den Tech-Stack des Projekts
                          Loesung: tech_blueprint wird an Goal und Backstory angehaengt
    """
    # AENDERUNG 02.02.2026: Modellwahl korrigiert (Single Source of Truth)
    # AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config/Router holen
    if router:
        model_name = router.get_model("fix")
        max_tokens = router.get_token_limit("fix", default=8192)
    else:
        model_name = get_model_from_config(config, "fix", fallback_role="reviewer")
        max_tokens = config.get("token_limits", {}).get("fix", 8192)

    # AENDERUNG 03.02.2026: Fix 11 - LLM-Objekt mit max_tokens erstellen
    llm = LLM(
        model=model_name,
        max_tokens=max_tokens
    )
    logger.info(f"[FixAgent] LLM erstellt: {model_name} mit max_tokens={max_tokens}")

    # Fehlerkontext fuer Backstory aufbereiten
    error_context = ""
    if error_info:
        error_context = f"""

AKTUELLER FEHLER:
- Datei: {error_info.get('file_path', target_file)}
- Fehlertyp: {error_info.get('error_type', 'unbekannt')}
- Zeilen: {error_info.get('line_numbers', [])}
- Fehlermeldung: {error_info.get('error_message', '')}
- Hinweis: {error_info.get('suggested_fix', '')}
"""

    backstory = FIX_AGENT_BACKSTORY + error_context

    # AENDERUNG 06.02.2026: Tech-Stack-Kontext in Backstory einfuegen
    tech_context = ""
    language = "unbekannt"
    if tech_blueprint:
        language = tech_blueprint.get('language', 'unbekannt')
        framework = tech_blueprint.get('framework', 'keins')
        project_type = tech_blueprint.get('project_type', 'unbekannt')
        tech_context = f"""

TECH-STACK DES PROJEKTS (WICHTIG!):
- Programmiersprache: {language}
- Framework: {framework}
- Projekt-Typ: {project_type}
- Du MUSST Code in der Sprache '{language}' generieren!
- NIEMALS Code in einer anderen Sprache erzeugen (z.B. kein Python fuer ein JavaScript-Projekt)!
"""
        backstory += tech_context

    # AENDERUNG 02.02.2026: project_rules Dict korrekt verarbeiten (Fix fuer UTDS BatchExecution)
    if project_rules:
        if isinstance(project_rules, dict):
            # Nutze combine_project_rules fuer konsistente Verarbeitung wie andere Agenten
            rules_text = combine_project_rules(project_rules, "fix")
        else:
            # Fallback fuer String-Eingabe (Rueckwaertskompatibilitaet)
            rules_text = str(project_rules)
        backstory += f"\n\nPROJEKTREGELN:\n{rules_text}"

    # AENDERUNG 06.02.2026: Goal mit Sprache anreichern
    goal_target = target_file if target_file else "den betroffenen Dateien"
    goal_lang = f" (Sprache: {language})" if language != "unbekannt" else ""

    return Agent(
        role="Code-Korrektur-Spezialist",
        goal=f"Korrigiere den Fehler in {goal_target} mit minimalen Aenderungen{goal_lang}",
        backstory=backstory,
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,  # Begrenzte Iterationen fuer schnelle Fixes
    )


def build_fix_prompt(
    file_path: str,
    current_content: str,
    error_type: str,
    error_message: str,
    line_numbers: List[int],
    context_files: Optional[Dict[str, str]] = None,
    suggested_fix: str = ""
) -> str:
    """
    Baut einen gezielten Fix-Prompt fuer den Agent.

    Args:
        file_path: Pfad der zu korrigierenden Datei
        current_content: Aktueller Inhalt der Datei
        error_type: Art des Fehlers (syntax, import, runtime, test, truncation)
        error_message: Die vollstaendige Fehlermeldung
        line_numbers: Betroffene Zeilennummern
        context_files: Optional - Relevante andere Dateien als Kontext
        suggested_fix: Optional - Vorgeschlagene Korrektur

    Returns:
        Formatierter Prompt fuer den Fix-Agent
    """
    # Dateiinhalt mit Zeilennummern versehen
    numbered_content = _add_line_numbers(current_content)

    # Zeilen hervorheben falls angegeben
    if line_numbers:
        highlighted_lines = ", ".join(str(n) for n in line_numbers)
        line_hint = f"\n\nBETROFFENE ZEILEN: {highlighted_lines}"
    else:
        line_hint = ""

    # Kontext aus anderen Dateien
    context_section = ""
    if context_files:
        context_section = "\n\nKONTEXT AUS ANDEREN DATEIEN:\n"
        for ctx_path, ctx_content in context_files.items():
            # Nur erste 50 Zeilen als Kontext
            ctx_lines = ctx_content.split('\n')[:50]
            ctx_preview = '\n'.join(ctx_lines)
            context_section += f"\n--- {ctx_path} (erste 50 Zeilen) ---\n{ctx_preview}\n"

    # Fix-Hinweis
    fix_hint = ""
    if suggested_fix:
        fix_hint = f"\n\nHINWEIS ZUR KORREKTUR:\n{suggested_fix}"

    prompt = f"""KORREKTUR-AUFGABE

ZIELDATEI: {file_path}
FEHLERTYP: {error_type}
{line_hint}

FEHLERMELDUNG:
{error_message}
{fix_hint}

AKTUELLER DATEIINHALT (mit Zeilennummern):
```
{numbered_content}
```
{context_section}

ANWEISUNGEN:
1. Analysiere den Fehler anhand der Fehlermeldung und der betroffenen Zeilen
2. Identifiziere die minimale Aenderung zur Behebung
3. Korrigiere NUR den Fehler - keine anderen Aenderungen
4. Gib die korrigierte Datei im folgenden Format aus:

### CORRECTION: {file_path}
```
[Die VOLLSTAENDIGE korrigierte Datei]
```

WICHTIG:
- Gib die gesamte Datei aus, nicht nur die geaenderten Zeilen
- Behalte alle existierenden Kommentare und Formatierung
- Aendere keine funktionierenden Teile des Codes
"""

    return prompt


def extract_corrected_content(agent_output: str, expected_path: str) -> Optional[str]:
    """
    Extrahiert den korrigierten Dateiinhalt aus der Agent-Ausgabe.

    Args:
        agent_output: Die vollstaendige Ausgabe des Fix-Agents
        expected_path: Der erwartete Dateipfad

    Returns:
        Der extrahierte Dateiinhalt oder None wenn nicht gefunden
    """
    import re

    if not agent_output:
        return None

    # Pattern fuer ### CORRECTION: pfad
    pattern = r'###\s*CORRECTION:\s*([^\n]+)\s*\n```[^\n]*\n(.*?)```'
    matches = re.findall(pattern, agent_output, re.DOTALL | re.IGNORECASE)

    for path, content in matches:
        path = path.strip()
        # Pruefen ob Pfad uebereinstimmt
        if path == expected_path or path.endswith(expected_path) or expected_path.endswith(path):
            return content.strip()

    # Fallback: Versuche einfaches Code-Block-Pattern
    code_pattern = r'```(?:python|javascript|typescript|jsx|tsx)?\n(.*?)```'
    code_matches = re.findall(code_pattern, agent_output, re.DOTALL)

    if code_matches:
        # Nimm den laengsten Code-Block (wahrscheinlich die vollstaendige Datei)
        return max(code_matches, key=len).strip()

    return None


def _add_line_numbers(content: str) -> str:
    """Fuegt Zeilennummern zum Code hinzu."""
    lines = content.split('\n')
    numbered = []
    for i, line in enumerate(lines, 1):
        numbered.append(f"{i:4d} | {line}")
    return '\n'.join(numbered)


# =============================================================================
# Spezialisierte Fix-Agent Varianten
# =============================================================================

def create_syntax_fix_agent(config: Dict, router=None) -> Agent:
    """Erstellt einen Agent spezialisiert auf Syntax-Fehler."""
    return create_fix_agent(
        config=config,
        router=router,
        error_info={
            "error_type": "syntax",
            "suggested_fix": "Pruefe Einrueckung, Klammern, Doppelpunkte und Anfuehrungszeichen"
        }
    )


def create_import_fix_agent(config: Dict, router=None) -> Agent:
    """Erstellt einen Agent spezialisiert auf Import-Fehler."""
    return create_fix_agent(
        config=config,
        router=router,
        error_info={
            "error_type": "import",
            "suggested_fix": "Pruefe Import-Pfade und Modul-Namen. Stelle sicher dass alle benoetigten Module importiert sind."
        }
    )


def create_truncation_fix_agent(config: Dict, router=None) -> Agent:
    """Erstellt einen Agent spezialisiert auf Truncation-Probleme."""
    # AENDERUNG 02.02.2026: Konsistente Modellwahl wie andere Agenten
    # AENDERUNG 03.02.2026: Fix 11 - max_tokens aus Config/Router holen
    if router:
        model_name = router.get_model("fix")
        max_tokens = router.get_token_limit("fix", default=8192)
    else:
        model_name = get_model_from_config(config, "fix", fallback_role="reviewer")
        max_tokens = config.get("token_limits", {}).get("fix", 8192)

    # AENDERUNG 03.02.2026: Fix 11 - LLM-Objekt mit max_tokens erstellen
    llm = LLM(
        model=model_name,
        max_tokens=max_tokens
    )
    logger.info(f"[TruncationFixAgent] LLM erstellt: {model_name} mit max_tokens={max_tokens}")

    backstory = FIX_AGENT_BACKSTORY + """

TRUNCATION-SPEZIALISIERUNG:
Diese Datei wurde moeglicherweise abgeschnitten (truncated).
Deine Aufgabe ist es, den fehlenden Code zu vervollstaendigen.

ACHTE AUF:
- Fehlende schliessende Klammern
- Unvollstaendige Funktionen
- Abgeschnittene Klassen
- Fehlende return-Statements
- Unvollstaendige if/else Bloecke
"""

    return Agent(
        role="Truncation-Reparatur-Spezialist",
        goal="Vervollstaendige abgeschnittenen Code",
        backstory=backstory,
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )


# =============================================================================
# Integration mit CrewAI Tasks
# =============================================================================

def create_fix_task(
    agent: Agent,
    file_path: str,
    current_content: str,
    error_type: str,
    error_message: str,
    line_numbers: List[int] = None,
    context_files: Dict[str, str] = None
):
    """
    Erstellt einen CrewAI Task fuer die Code-Korrektur.

    Args:
        agent: Der Fix-Agent
        file_path: Pfad der Datei
        current_content: Aktueller Inhalt
        error_type: Fehlertyp
        error_message: Fehlermeldung
        line_numbers: Betroffene Zeilen
        context_files: Kontext-Dateien

    Returns:
        CrewAI Task
    """
    from crewai import Task

    description = build_fix_prompt(
        file_path=file_path,
        current_content=current_content,
        error_type=error_type,
        error_message=error_message,
        line_numbers=line_numbers or [],
        context_files=context_files
    )

    return Task(
        description=description,
        agent=agent,
        expected_output=f"Korrigierte Version von {file_path} im Format ### CORRECTION: {file_path}"
    )
