"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: Spezialisierter Agent fuer gezielte Code-Korrekturen.
              Repariert nur die gemeldeten Fehler, ohne funktionierenden Code zu aendern.
"""

from crewai import Agent
from typing import Dict, List, Optional, Any

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
    project_rules: str = "",
    router=None,
    target_file: str = "",
    error_info: Optional[Dict[str, Any]] = None
) -> Agent:
    """
    Erstellt einen spezialisierten Fix-Agent fuer eine Datei.

    Args:
        config: Konfiguration mit Modell-Einstellungen
        project_rules: Projektspezifische Regeln
        router: Optional - Model Router fuer dynamische Modellwahl
        target_file: Der Pfad der zu korrigierenden Datei
        error_info: Optional - Informationen ueber den Fehler

    Returns:
        CrewAI Agent konfiguriert fuer Code-Korrekturen
    """
    # Modell bestimmen
    if router:
        llm = router.get_llm_for_agent("fix")
    else:
        llm = config.get("default_model", "gpt-4o-mini")

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

    if project_rules:
        backstory += f"\n\nPROJEKTREGELN:\n{project_rules}"

    return Agent(
        role="Code-Korrektur-Spezialist",
        goal=f"Korrigiere den Fehler in {target_file} mit minimalen Aenderungen",
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
        llm=config.get("default_model", "gpt-4o-mini"),
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
