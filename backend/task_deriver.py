"""
Author: rahn
Datum: 01.02.2026
Version: 1.1
Beschreibung: LLM-basierter Task-Ableiter fuer das Universal Task Derivation System (UTDS).
              Zerlegt Feedback aus verschiedenen Quellen in einzelne, ausfuehrbare Tasks.
              AENDERUNG 05.02.2026 v1.1: Erweiterte Patterns fuer alle Issue-Typen.
"""

import json
import logging
import os
import re
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from backend.task_models import (
    DerivedTask, TaskCategory, TaskPriority, TargetAgent, TaskStatus,
    TaskDerivationResult, sort_tasks_by_priority
)

logger = logging.getLogger(__name__)


# AENDERUNG 06.02.2026: Vorhandene Projekt-Dateien fuer UTDS-Prompt
# Verhindert dass LLM Dateipfade erfindet
_IGNORED_DIRS = {"node_modules", ".git", "__pycache__", ".next", "dist", "build", ".cache", "screenshots"}


def _get_existing_project_files(context: Dict[str, Any]) -> List[str]:
    """Extrahiert vorhandene Projekt-Dateien aus current_code oder Festplatte."""
    current_code = context.get("current_code")
    if isinstance(current_code, dict) and current_code:
        return list(current_code.keys())[:30]
    # Fallback: Dateien vom Projektverzeichnis lesen
    blueprint = context.get("tech_blueprint", {})
    project_path = blueprint.get("project_path", "")
    if project_path and Path(project_path).is_dir():
        files = []
        for root, dirs, filenames in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), project_path).replace("\\", "/")
                files.append(rel)
                if len(files) >= 30:
                    return files
        return files
    return []


# AENDERUNG 01.02.2026: LLM-Prompt Template fuer Task-Ableitung
TASK_DERIVER_PROMPT = """Analysiere das folgende Feedback und extrahiere einzelne, ausfuehrbare Tasks.

FEEDBACK ({source}):
{feedback}

KONTEXT:
- Betroffene Dateien: {affected_files}
- Vorhandene Projekt-Dateien: {existing_files}
- Tech-Stack: {tech_stack}
- Projekt-Typ: {project_type}
- Aktueller Code vorhanden: {has_code}
{database_schema_section}

AUSGABE-FORMAT (strikt JSON):
```json
{{
  "tasks": [
    {{
      "title": "Kurze Beschreibung (max 60 Zeichen)",
      "description": "Detaillierte Anweisung fuer den Agenten mit konkreten Schritten",
      "category": "code|test|security|docs|config|refactor",
      "priority": "critical|high|medium|low",
      "target_agent": "coder|tester|security|docs|fix",
      "affected_files": ["datei1.py", "datei2.py"],
      "dependencies": [],
      "source_issue": "Exakter Text des urspruenglichen Problems"
    }}
  ]
}}
```

REGELN:
1. Jeder Task muss EINE konkrete, abgeschlossene Aktion sein
2. KEIN Buendeln mehrerer Probleme in einem Task
3. Abhaengigkeiten zwischen Tasks explizit angeben (Task-Index, z.B. ["TASK-001"])
4. Security-Issues IMMER als "critical" priorisieren
5. Test-fehlende Tasks als "high" priorisieren
6. Syntax-Fehler und Import-Fehler als "critical" priorisieren
7. Dokumentations-Aufgaben als "low" priorisieren (ausser explizit angefordert)
8. WICHTIG: affected_files MUESSEN zum Tech-Stack passen! Kein .py fuer JavaScript-Projekte, kein .js fuer Python-Projekte!
9. WICHTIG: affected_files MUESSEN aus der Liste 'Vorhandene Projekt-Dateien' stammen! Erfinde KEINE Dateipfade!

KATEGORISIERUNG:
- "code": Code-Aenderungen, Bugfixes, Implementierungen
- "test": Unit-Tests, Integration-Tests, Test-Coverage
- "security": Vulnerabilities, SQL-Injection, XSS, etc.
- "docs": Dokumentation, Kommentare, README
- "config": Konfiguration, Dependencies, Setup
- "refactor": Code-Verbesserungen ohne Funktionsaenderung

AGENT-ZUWEISUNG:
- "coder": Fuer Code-Generierung und Bugfixes
- "fix": Fuer gezielte Korrekturen in existierenden Dateien
- "tester": Fuer Test-Erstellung und Test-Fixes
- "security": Fuer Security-Review und -Fixes
- "docs": Fuer Dokumentations-Aufgaben

Gib NUR den JSON-Block aus, keine zusaetzlichen Erklaerungen.
"""


class TaskDeriver:
    """
    LLM-basierter Task-Ableiter.

    Analysiert Feedback aus verschiedenen Quellen (Reviewer, Quality Gate,
    Tester, Security) und zerlegt es in einzelne, ausfuehrbare Tasks.
    """

    def __init__(self, model_router=None, config: Dict[str, Any] = None):
        """
        Initialisiert den TaskDeriver.

        Args:
            model_router: ModelRouter fuer LLM-Zugriff
            config: Anwendungskonfiguration
        """
        self.model_router = model_router
        self.config = config or {}
        self._task_counter = 0

    def derive_tasks(
        self,
        feedback: str,
        source: str,
        context: Dict[str, Any] = None
    ) -> TaskDerivationResult:
        """
        Zerlegt Feedback in einzelne Tasks.

        Args:
            feedback: Feedback-Text (Review, QG-Issues, etc.)
            source: Quelle ("reviewer", "quality_gate", "tester", "security", "sandbox")
            context: Zusaetzlicher Kontext (current_code, blueprint, affected_files)

        Returns:
            TaskDerivationResult mit abgeleiteten Tasks
        """
        start_time = time.time()
        context = context or {}

        # Versuche LLM-basierte Ableitung
        tasks = self._derive_with_llm(feedback, source, context)

        # Fallback auf regelbasierte Ableitung
        if not tasks:
            tasks = self._derive_with_rules(feedback, source, context)

        # Tasks priorisieren und IDs vergeben
        tasks = self._assign_task_ids(tasks)
        tasks = sort_tasks_by_priority(tasks)

        # Statistiken berechnen
        result = TaskDerivationResult(
            source=source,
            source_feedback=feedback,
            tasks=tasks,
            total_tasks=len(tasks),
            tasks_by_category=self._count_by_category(tasks),
            tasks_by_priority=self._count_by_priority(tasks),
            tasks_by_agent=self._count_by_agent(tasks),
            derivation_time_seconds=time.time() - start_time
        )

        return result

    def _derive_with_llm(
        self,
        feedback: str,
        source: str,
        context: Dict[str, Any]
    ) -> List[DerivedTask]:
        """
        LLM-basierte Task-Ableitung.

        Args:
            feedback: Feedback-Text
            source: Feedback-Quelle
            context: Kontext-Informationen

        Returns:
            Liste abgeleiteter Tasks
        """
        if not self.model_router:
            return []

        # Prompt zusammenbauen
        # AENDERUNG 06.02.2026: project_type hinzugefuegt fuer Tech-Stack-Bewusstsein
        # ROOT-CAUSE-FIX 06.02.2026 (v2):
        # Symptom: UTDS erfindet Dateipfade wie nextjs_app/package.js
        # Ursache: LLM erhielt KEINE Liste der tatsaechlich vorhandenen Projekt-Dateien
        # Loesung: existing_files aus current_code-Keys oder Festplatte an LLM uebergeben
        existing_files = _get_existing_project_files(context)
        # AENDERUNG 21.02.2026: Fix 59d — Database-Schema als Kontext fuer UTDS
        db_schema = context.get("database_schema", "")
        schema_section = ""
        if db_schema and "Kein Datenbank" not in db_schema:
            schema_section = f"DATENBANK-SCHEMA (EXAKT diese Tabellennamen verwenden!):\n{db_schema[:1500]}"
        prompt = TASK_DERIVER_PROMPT.format(
            source=source,
            feedback=feedback[:4000],  # Truncate fuer Token-Limit
            affected_files=", ".join(context.get("affected_files", ["unbekannt"])),
            existing_files=", ".join(existing_files) if existing_files else "unbekannt",
            tech_stack=context.get("tech_stack", "unbekannt"),
            project_type=context.get("project_type", "unbekannt"),
            has_code="Ja" if context.get("current_code") else "Nein",
            database_schema_section=schema_section
        )

        try:
            # AENDERUNG 07.02.2026: Eigene Modell-Rolle statt meta_orchestrator (Fix 14)
            model = self.model_router.get_model("task_deriver")
            response = model.invoke(prompt)

            # Response parsen
            response_text = response.content if hasattr(response, 'content') else str(response)
            return self._parse_llm_response(response_text, source)

        except Exception as e:
            logger.exception("[TaskDeriver] LLM-Fehler in derive_tasks")
            return []

    def _parse_llm_response(self, response: str, source: str) -> List[DerivedTask]:
        """
        Parst die LLM-Antwort und extrahiert Tasks.

        Args:
            response: LLM-Antwort
            source: Feedback-Quelle

        Returns:
            Liste von DerivedTask-Objekten
        """
        if not response:
            return []

        # JSON-Block extrahieren
        json_patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'\{[\s\S]*"tasks"[\s\S]*\}'
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                json_str = matches[0] if isinstance(matches[0], str) else matches[0]
                try:
                    data = json.loads(json_str)
                    if "tasks" in data and isinstance(data["tasks"], list):
                        return self._convert_to_derived_tasks(data["tasks"], source)
                except json.JSONDecodeError:
                    continue

        # Fallback: Gesamten Output als JSON
        try:
            data = json.loads(response.strip())
            if "tasks" in data:
                return self._convert_to_derived_tasks(data["tasks"], source)
        except json.JSONDecodeError:
            pass

        return []

    def _convert_to_derived_tasks(
        self,
        raw_tasks: List[Dict[str, Any]],
        source: str
    ) -> List[DerivedTask]:
        """
        Konvertiert rohe Task-Dicts zu DerivedTask-Objekten.

        Args:
            raw_tasks: Liste von Task-Dictionaries aus LLM
            source: Feedback-Quelle

        Returns:
            Liste von DerivedTask-Objekten
        """
        tasks = []
        for raw in raw_tasks:
            try:
                task = DerivedTask(
                    id="",  # Wird spaeter vergeben
                    title=raw.get("title", "Unbenannter Task")[:60],
                    description=raw.get("description", ""),
                    category=self._parse_category(raw.get("category", "code")),
                    priority=self._parse_priority(raw.get("priority", "medium")),
                    target_agent=self._parse_agent(raw.get("target_agent", "coder")),
                    affected_files=raw.get("affected_files", []),
                    dependencies=raw.get("dependencies", []),
                    source_issue=raw.get("source_issue", ""),
                    source_type=source,
                    status=TaskStatus.PENDING
                )
                tasks.append(task)
            except Exception as e:
                logger.exception("[TaskDeriver] Task-Konvertierung fehlgeschlagen in _convert_to_derived_tasks")
                continue

        return tasks

    def _derive_with_rules(
        self,
        feedback: str,
        source: str,
        context: Dict[str, Any]
    ) -> List[DerivedTask]:
        """
        Regelbasierte Task-Ableitung als Fallback.
        AENDERUNG 02.02.2026: Duplikat-Erkennung via Hash hinzugefuegt.
        AENDERUNG 05.02.2026: Erweiterte Patterns fuer alle Issue-Typen.

        Args:
            feedback: Feedback-Text
            source: Feedback-Quelle
            context: Kontext-Informationen

        Returns:
            Liste abgeleiteter Tasks (ohne Duplikate)
        """
        tasks = []
        # AENDERUNG 02.02.2026: Duplikat-Tracking via Hash
        seen_issues: Set[str] = set()
        feedback_lower = feedback.lower()

        # Pattern-basierte Erkennung
        patterns = self._get_detection_patterns()

        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            matches = re.findall(pattern, feedback, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                match_text = match if isinstance(match, str) else match[0]

                # AENDERUNG 02.02.2026: Duplikat-Check via Hash
                # Normalisiere den Text fuer bessere Deduplizierung
                normalized_issue = match_text.lower().strip()[:100]
                issue_hash = hashlib.md5(normalized_issue.encode()).hexdigest()[:8]

                if issue_hash in seen_issues:
                    logger.debug(f"[TaskDeriver] Duplikat uebersprungen: {match_text[:50]}...")
                    continue
                seen_issues.add(issue_hash)

                # AENDERUNG 06.02.2026: tech_stack an _extract_files_from_text weiterreichen
                tech_stack = context.get("tech_stack", "") if context else ""
                task = DerivedTask(
                    id="",
                    title=pattern_info["title_template"].format(match=match_text[:30]),
                    description=f"{pattern_info['description']}\n\nOriginal: {match_text}",
                    category=pattern_info["category"],
                    priority=pattern_info["priority"],
                    target_agent=pattern_info["agent"],
                    affected_files=self._extract_files_from_text(match_text, tech_stack),
                    dependencies=[],
                    source_issue=match_text,
                    source_type=source,
                    status=TaskStatus.PENDING
                )
                tasks.append(task)

        # Fallback: Wenn keine Patterns matchen, erstelle generischen Task
        if not tasks and len(feedback.strip()) > 20:
            task = DerivedTask(
                id="",
                title=f"Feedback von {source} bearbeiten",
                description=feedback[:500],
                category=self._infer_category_from_source(source),
                priority=TaskPriority.MEDIUM,
                target_agent=self._infer_agent_from_source(source),
                affected_files=context.get("affected_files", []),
                dependencies=[],
                source_issue=feedback[:200],
                source_type=source,
                status=TaskStatus.PENDING
            )
            tasks.append(task)

        return tasks

    def _get_detection_patterns(self) -> List[Dict[str, Any]]:
        """Liefert erweiterte Pattern-Definitionen fuer regelbasierte Erkennung."""
        return [
            # JavaScript/JSX Syntax-Fehler (CRITICAL)
            {
                "pattern": r"(?:JavaScript[- ]?Syntax(?:Error)?|JSX[- ]?Syntax|unvollstaendig(?:er)?\s*JSX[- ]?Code|parsing[- ]?Fehler)",
                "title_template": "JavaScript/JSX Syntax-Fehler beheben",
                "description": "JavaScript-Syntaxfehler oder unvollstaendigen JSX-Code im Code beheben",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # Python Syntax-Fehler
            {
                "pattern": r"SyntaxError[:\s]+(.+?)(?:\n|$)",
                "title_template": "Syntax-Fehler beheben: {match}",
                "description": "Syntax-Fehler im Python-Code beheben",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # Unvollstaendiger Code / fehlende Klammern/Tags
            {
                "pattern": r"(?:ohne\s*schliessend(?:e)?\s*(?:Klammern?|Tags?|Element)|fehlend(?:e)?\s*(?:schliessend(?:e)?\s*)?(?:Klammern?|Tags?|Element)|unvollstaendig(?:er)?\s*(?:Code|JSX))",
                "title_template": "Unvollstaendigen Code/fehlende Klammern beheben",
                "description": "Fehlende schliessende Klammern, Tags oder JSX-Elemente ergaenzen",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # HTML-Tag-Fehler (falsches schliessendes Tag)
            {
                "pattern": r"(?:falsch(?:es|er|e)?\s*schliessend(?:e)?\s*Tag|</[h1h2h3h4h5h6p]>\s*statt|Tag\s*statt\s*</)",
                "title_template": "HTML-Tag-Fehler beheben",
                "description": "Falsches schliessendes HTML-Tag korrigieren",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # Import-Fehler / ModuleNotFoundError
            {
                "pattern": r"(?:ModuleNotFoundError|ImportError)[:\s]+(.+?)(?:\n|$)",
                "title_template": "Import-Fehler beheben: {match}",
                "description": "Fehlenden Import oder Modul korrigieren",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # ReferenceError / nicht definiert
            {
                "pattern": r"(?:ReferenceError|NotDefined|nicht\s*definiert|ist\s*nicht\s*definiert)",
                "title_template": "ReferenceError beheben",
                "description": "Nicht definierte Variable oder Funktion korrigieren",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.FIX
            },
            # Fehlende Dependencies/Abhaengigkeiten
            {
                "pattern": r"(?:fehlende?\s*(?:Abhaengigkeit|Dependency|Paket|Package)|nicht\s*(?:in\s*package\.json|installiert)|ModuleNotFound)\s*[@\w/-]+",
                "title_template": "Fehlende Dependency hinzufuegen",
                "description": "Fehlende Abhaengigkeit in package.json ergaenzen",
                "category": TaskCategory.CONFIG,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # Fehlende Typdefinitionen
            {
                "pattern": r"(?:fehlende?\s*(?:Typ(?:definition|en)?)|@types/|\.d\.ts?|TypeScript\s*Types?|implizites\s*any)",
                "title_template": "Typdefinitionen hinzufuegen",
                "description": "Fehlende TypeScript-Typdefinitionen installieren",
                "category": TaskCategory.CONFIG,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # Fehlende Verzeichnisse/Dateien
            {
                "pattern": r"(?:Verzeichnis\s*existiert\s*nicht|ENOENT|db/[\./]|mkdir|verzeichnis\s*nicht\s*erstellt)",
                "title_template": "Fehlendes Verzeichnis erstellen",
                "description": "Fehlendes Verzeichnis oder Datei anlegen",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # NameError
            {
                "pattern": r"NameError[:\s]+name '(\w+)' is not defined",
                "title_template": "NameError beheben: {match}",
                "description": "Undefinierte Variable oder Funktion korrigieren",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # TypeError
            {
                "pattern": r"TypeError[:\s]+(.+?)(?:\n|$)",
                "title_template": "TypeError beheben: {match}",
                "description": "Typ-Fehler im Code korrigieren",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # Fehlende Tests
            {
                "pattern": r"(?:keine?\s*(?:unit-?)?tests?|tests?\s*fehlen|missing\s*tests?)",
                "title_template": "Unit-Tests erstellen",
                "description": "Unit-Tests fuer die Kernfunktionalitaet erstellen",
                "category": TaskCategory.TEST,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.TESTER
            },
            # Security: SQL-Injection
            {
                "pattern": r"(?:sql[- ]?injection|unsichere?\s*sql)",
                "title_template": "SQL-Injection beheben",
                "description": "SQL-Injection Vulnerability durch parametrisierte Queries beheben",
                "category": TaskCategory.SECURITY,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.SECURITY
            },
            # Security: XSS
            {
                "pattern": r"(?:xss|cross[- ]?site[- ]?scripting)",
                "title_template": "XSS Vulnerability beheben",
                "description": "Cross-Site-Scripting durch proper Escaping beheben",
                "category": TaskCategory.SECURITY,
                "priority": TaskPriority.CRITICAL,
                "agent": TargetAgent.SECURITY
            },
            # Sandbox/Server konnte nicht gestartet werden
            {
                "pattern": r"(?:Server\s+konnte\s+nicht\s+gestartet\s+werden|Sandbox[- ]?Fehler|Test[- ]?Server[- ]?Start)",
                "title_template": "Server/Start-Problem beheben",
                "description": "Serverstart-Problem oder Sandbox-Fehler beheben",
                "category": TaskCategory.CODE,
                "priority": TaskPriority.HIGH,
                "agent": TargetAgent.FIX
            },
            # Fehlende Dokumentation
            {
                "pattern": r"(?:dokumentation\s*fehlt|keine?\s*(?:doc|doku))",
                "title_template": "Dokumentation hinzufuegen",
                "description": "Fehlende Dokumentation ergaenzen",
                "category": TaskCategory.DOCS,
                "priority": TaskPriority.LOW,
                "agent": TargetAgent.DOCS
            },
        ]

    def _extract_files_from_text(self, text: str, tech_stack: str = "",
                                   existing_files: Optional[List[str]] = None) -> List[str]:
        """
        Extrahiert Dateinamen aus Text, gefiltert nach Tech-Stack und vorhandenen Dateien.

        AENDERUNG 06.02.2026: ROOT-CAUSE-FIX UTDS Sprach-Mismatch + Pfad-Validierung
        Symptom: UTDS erfindet Pfade wie nextjs_app/package.js, Next.js als Dateiname
        Ursache: Keine Laenge-/Existenz-Pruefung, project_type als Prefix
        Loesung: Mindestlaenge, Prefix-Bereinigung, Validierung gegen vorhandene Dateien
        """
        # AENDERUNG 07.02.2026: Extensions fuer alle 12 unterstuetzten Sprachen
        # Laengere Extensions zuerst (jsx vor js, tsx vor ts, json vor js, yaml vor yml)
        file_pattern = r'["\']?([a-zA-Z0-9_/\\.-]+\.(?:py|jsx|json|tsx|js|ts|html|css|yaml|yml|md|java|go|rs|cs|cpp|hpp|kt|kts|rb|swift|php|vue|svelte|dart|scala|ex|xml|gradle|sql|sh|bat|toml))["\']?'
        matches = re.findall(file_pattern, text)

        # Framework-Namen ausfiltern (Next.js, Vue.js, Node.js etc. sind keine Dateien)
        # AENDERUNG 07.02.2026: Erweitert um non-JS Frameworks (Spring.java, Rails.rb etc.)
        _FRAMEWORK_NAMES = {
            "next.js", "vue.js", "node.js", "react.js", "angular.js", "nuxt.js", "svelte.js",
            "express.js", "gatsby.js", "remix.js", "ember.js",
        }
        matches = [m for m in matches
                   if m.lower() not in _FRAMEWORK_NAMES
                   and (len(m) > 4 or "/" in m)]

        # Prefix-Bereinigung: project_type als Verzeichnis entfernen
        cleaned = []
        for m in matches:
            # Entferne project_type-Prefixe wie "nextjs_app/", "nodejs_express/"
            parts = m.replace("\\", "/").split("/")
            if len(parts) > 1 and "_" in parts[0] and parts[0] not in ("node_modules",):
                cleaned.append("/".join(parts[1:]))
            else:
                cleaned.append(m.replace("\\", "/"))
        matches = cleaned

        # Tech-Stack-aware Filterung: Inkompatible Extensions entfernen
        if tech_stack:
            tech_lower = tech_stack.lower()
            filtered = []
            for m in matches:
                ext = "." + m.rsplit(".", 1)[-1].lower() if "." in m else ""
                if ext == ".py" and tech_lower in ("javascript", "typescript"):
                    continue
                if ext in (".js", ".jsx", ".ts", ".tsx") and tech_lower == "python":
                    continue
                filtered.append(m)
            matches = filtered

        # Validierung gegen vorhandene Dateien (wenn verfuegbar)
        if existing_files and matches:
            existing_basenames = {os.path.basename(f) for f in existing_files}
            validated = [m for m in matches if m in existing_files or os.path.basename(m) in existing_basenames]
            if validated:
                matches = validated
            else:
                logger.warning(f"[TaskDeriver] Keine extrahierten Dateien in Projekt gefunden: {matches[:3]}")

        return list(set(matches))[:5]

    def _assign_task_ids(self, tasks: List[DerivedTask]) -> List[DerivedTask]:
        """Weist eindeutige IDs zu."""
        for i, task in enumerate(tasks):
            self._task_counter += 1
            task.id = f"TASK-{self._task_counter:03d}"
        return tasks

    def _parse_category(self, value: str) -> TaskCategory:
        """Parst Kategorie-String zu Enum."""
        mapping = {
            "code": TaskCategory.CODE,
            "test": TaskCategory.TEST,
            "security": TaskCategory.SECURITY,
            "docs": TaskCategory.DOCS,
            "config": TaskCategory.CONFIG,
            "refactor": TaskCategory.REFACTOR,
        }
        return mapping.get(value.lower(), TaskCategory.CODE)

    def _parse_priority(self, value: str) -> TaskPriority:
        """Parst Priority-String zu Enum."""
        mapping = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "medium": TaskPriority.MEDIUM,
            "low": TaskPriority.LOW,
        }
        return mapping.get(value.lower(), TaskPriority.MEDIUM)

    def _parse_agent(self, value: str) -> TargetAgent:
        """Parst Agent-String zu Enum."""
        mapping = {
            "coder": TargetAgent.CODER,
            "tester": TargetAgent.TESTER,
            "security": TargetAgent.SECURITY,
            "docs": TargetAgent.DOCS,
            "reviewer": TargetAgent.REVIEWER,
            "fix": TargetAgent.FIX,
        }
        return mapping.get(value.lower(), TargetAgent.CODER)

    def _infer_category_from_source(self, source: str) -> TaskCategory:
        """Leitet Kategorie aus Quelle ab."""
        source_mapping = {
            "reviewer": TaskCategory.CODE,
            "quality_gate": TaskCategory.CODE,
            "tester": TaskCategory.TEST,
            "security": TaskCategory.SECURITY,
            "sandbox": TaskCategory.CODE,
        }
        return source_mapping.get(source.lower(), TaskCategory.CODE)

    def _infer_agent_from_source(self, source: str) -> TargetAgent:
        """Leitet Ziel-Agent aus Quelle ab."""
        source_mapping = {
            "reviewer": TargetAgent.FIX,
            "quality_gate": TargetAgent.FIX,
            "tester": TargetAgent.TESTER,
            "security": TargetAgent.SECURITY,
            "sandbox": TargetAgent.FIX,
        }
        return source_mapping.get(source.lower(), TargetAgent.CODER)

    def _count_by_category(self, tasks: List[DerivedTask]) -> Dict[str, int]:
        """Zaehlt Tasks nach Kategorie."""
        counts = {}
        for task in tasks:
            key = task.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_priority(self, tasks: List[DerivedTask]) -> Dict[str, int]:
        """Zaehlt Tasks nach Prioritaet."""
        counts = {}
        for task in tasks:
            key = task.priority.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_agent(self, tasks: List[DerivedTask]) -> Dict[str, int]:
        """Zaehlt Tasks nach Ziel-Agent."""
        counts = {}
        for task in tasks:
            key = task.target_agent.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def reset_counter(self):
        """Setzt den Task-Counter zurueck (fuer neue Sessions)."""
        self._task_counter = 0
