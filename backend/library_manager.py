# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.1
Beschreibung: Library Manager - Zentrale Protokoll- und Archivverwaltung.
              Speichert alle Agent-Kommunikationen und Projektverläufe.
              ÄNDERUNG 29.01.2026: Discovery Briefing wird mit Projekten gespeichert.
              # ÄNDERUNG [31.01.2026]: Archiv-Sanitizing und Token-Summen-Korrektur.
"""

import os
import json
import uuid
import logging
import copy
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LibraryManager:
    """
    Verwaltet das Protokollsystem und Archiv für alle Projekte.
    Speichert jede Agent-Kommunikation für Debugging und Nachvollziehbarkeit.
    """

    def __init__(self, base_dir: str = None):
        """
        Initialisiert den Library Manager.

        Args:
            base_dir: Basisverzeichnis für Library-Daten
        """
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.base_dir = base_dir
        self.library_dir = os.path.join(base_dir, "library")
        self.archive_dir = os.path.join(self.library_dir, "archive")
        self.current_project_file = os.path.join(self.library_dir, "current_project.json")

        # Verzeichnisse erstellen
        os.makedirs(self.library_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

        # Aktuelles Projekt
        self.current_project: Optional[Dict[str, Any]] = None
        self._load_current_project()

    def _load_current_project(self):
        """Lädt das aktuelle Projekt aus der Datei."""
        if os.path.exists(self.current_project_file):
            try:
                with open(self.current_project_file, 'r', encoding='utf-8') as f:
                    self.current_project = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.current_project = None

    def _save_current_project(self):
        """Speichert das aktuelle Projekt in die Datei."""
        if self.current_project:
            try:
                # ÄNDERUNG 28.01.2026: Vorherige Save-Fehler zuruecksetzen bei Erfolg
                if "save_error" in self.current_project:
                    self.current_project["save_error"] = None
                if "save_error_timestamp" in self.current_project:
                    self.current_project["save_error_timestamp"] = None
                with open(self.current_project_file, 'w', encoding='utf-8') as f:
                    json.dump(self.current_project, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Fehler beim Speichern des aktuellen Projekts: {e}")
                # ÄNDERUNG 28.01.2026: Fehler sichtbar machen und weiterreichen
                self.current_project["save_error"] = str(e)
                self.current_project["save_error_timestamp"] = datetime.now().isoformat()
                raise

    def _normalize_briefing_preview(self, briefing: Any) -> str:
        """
        Normalisiert Briefing-Daten zu einem kurzen String-Preview.
        """
        if briefing is None:
            return ""
        if isinstance(briefing, dict):
            try:
                return json.dumps(briefing, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                return str(briefing)
        return str(briefing)

    def start_project(self, name: str, goal: str, briefing: Optional[Dict[str, Any]] = None) -> str:
        """
        Startet ein neues Projekt und erstellt einen Protokoll-Eintrag.

        Args:
            name: Projektname
            goal: Projektziel/Prompt
            briefing: Optional - Discovery Briefing Daten

        Returns:
            Projekt-ID
        """
        project_id = f"proj_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex[:6]}"

        # ÄNDERUNG 29.01.2026: Discovery Briefing wird mit Projekt gespeichert
        # ÄNDERUNG 29.01.2026: Briefing-Preview normalisieren
        briefing_preview = self._normalize_briefing_preview(briefing)[:200]
        self.current_project = {
            "project_id": project_id,
            "name": name,
            "goal": goal,
            "briefing": briefing,
            "briefing_preview": briefing_preview,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "status": "running",
            "iterations": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "agents_involved": [],
            "files_created": [],
            "entries": []
        }

        self._save_current_project()
        return project_id

    def log_entry(
        self,
        from_agent: str,
        to_agent: str,
        entry_type: str,
        content: Any,
        iteration: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Protokolliert einen Eintrag im aktuellen Projekt.

        Args:
            from_agent: Absender-Agent
            to_agent: Empfänger-Agent (oder "System")
            entry_type: Typ des Eintrags (code_submission, feedback, security_scan, etc.)
            content: Inhalt des Eintrags
            iteration: Aktuelle Iteration
            metadata: Zusätzliche Metadaten (model, tokens, duration)

        Returns:
            Entry-ID
        """
        if not self.current_project:
            return ""

        entry_id = f"entry_{len(self.current_project['entries']) + 1:04d}"

        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "type": entry_type,
            "content": self._serialize_content(content),
            "metadata": metadata or {}
        }

        self.current_project["entries"].append(entry)

        # Agent zur Liste hinzufügen
        if from_agent not in self.current_project["agents_involved"]:
            self.current_project["agents_involved"].append(from_agent)

        # Iteration aktualisieren
        if iteration > self.current_project["iterations"]:
            self.current_project["iterations"] = iteration

        # Token-Tracking aus Metadata
        if metadata and "tokens" in metadata:
            self.current_project["total_tokens"] += metadata["tokens"]
        if metadata and "cost" in metadata:
            self.current_project["total_cost"] += metadata["cost"]

        self._save_current_project()
        return entry_id

    def _serialize_content(self, content: Any) -> Any:
        """Serialisiert Inhalte für JSON-Speicherung."""
        if isinstance(content, str):
            # ÄNDERUNG 28.01.2026: Limits erhöht für vollständigere Archivierung
            if len(content) > 50000:
                return {
                    "type": "truncated",
                    "preview": content[:10000],
                    "full_length": len(content)
                }
            return content
        elif isinstance(content, dict):
            return content
        elif isinstance(content, list):
            return content
        else:
            return str(content)

    # ÄNDERUNG [31.01.2026]: Sanitizer für Archive (Pfad/Secret/Stacktrace)
    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]

    def _sanitize_paths(self, text: str) -> str:
        # Windows User-Pfade anonymisieren
        text = re.sub(r"([A-Za-z]:\\Users\\)([^\\]+)(\\[^\s\"']*)", r"\1<USER>\3", text)
        text = re.sub(r"([A-Za-z]:/Users/)([^/]+)(/[^\s\"']*)", r"\1<USER>\3", text)

        def _windows_replacer(match: re.Match) -> str:
            path = match.group(0)
            return path if "<USER>" in path else "<LOCAL_PATH>"

        text = re.sub(r"[A-Za-z]:[\\/][^\s\"']+", _windows_replacer, text)

        # Unix User-Pfade anonymisieren
        text = re.sub(r"(/(?:Users|home)/)([^/]+)(/[^\s\"']*)", r"\1<USER>\3", text)

        def _unix_replacer(match: re.Match) -> str:
            path = match.group(0)
            return path if "<USER>" in path else "<LOCAL_PATH>"

        text = re.sub(r"/(?:Users|home|var|tmp|private|opt|etc|usr|root|Volumes)[^\s\"']+", _unix_replacer, text)
        return text

    def _redact_stack_traces(self, text: str) -> str:
        if "Traceback (most recent call last)" in text:
            trace_id = self._hash_text(text)
            return re.sub(
                r"Traceback \(most recent call last\):[\s\S]*",
                f"[STACK_TRACE_REDACTED:{trace_id}]",
                text
            )

        stack_line_re = re.compile(r"^\s*at .+\(.+:\d+:\d+\)\s*$", re.MULTILINE)
        if stack_line_re.search(text):
            trace_id = self._hash_text(text)
            return stack_line_re.sub(f"[STACK_TRACE_REDACTED:{trace_id}]", text)
        return text

    def _sanitize_text(self, text: str) -> str:
        sanitized = text

        # .env Inhalte redigieren
        sanitized = re.sub(
            r"(### FILENAME: \.env)([\s\S]*?)(?=### FILENAME:|\Z)",
            r"\1\n[ENV_DATEI_REDAKTIERT]\n",
            sanitized
        )

        # Geheimnisse anonymisieren
        sanitized = re.sub(r"(?i)(DART_TOKEN|SECRET_KEY)\s*=\s*([^\r\n]+)", r"\1=<REDACTED_SECRET>", sanitized)
        sanitized = re.sub(
            r"(app\.config\[['\"]SECRET_KEY['\"]\]\s*=\s*)['\"][^'\"]+['\"]",
            r"\1'<REDACTED_SECRET>'",
            sanitized
        )
        sanitized = re.sub(
            r"os\.environ\.get\(['\"]SECRET_KEY['\"],\s*['\"][^'\"]+['\"]\)",
            "os.environ.get('SECRET_KEY')",
            sanitized
        )

        # User-IDs anonymisieren
        sanitized = re.sub(r'("user_id"\s*:\s*")[^"]+(")', r'\1<REDACTED_USER>\2', sanitized)
        sanitized = re.sub(r"(user_id\s*[:=]\s*)([A-Za-z0-9_\-]+)", r"\1<REDACTED_USER>", sanitized)

        sanitized = self._sanitize_paths(sanitized)
        sanitized = self._redact_stack_traces(sanitized)
        return sanitized

    def _sanitize_structure(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized_dict = {}
            for key, item in value.items():
                if key == "files" and isinstance(item, list):
                    item = [entry for entry in item if not (isinstance(entry, str) and entry.strip().endswith(".env"))]
                sanitized_dict[key] = self._sanitize_structure(item)
            return sanitized_dict
        if isinstance(value, list):
            return [self._sanitize_structure(item) for item in value]
        if isinstance(value, str):
            return self._sanitize_text(value)
        return value

    def _recalculate_totals(self, project: Dict[str, Any]) -> None:
        total_tokens = 0
        total_cost = 0.0
        found_metrics = False

        for entry in project.get("entries", []):
            if entry.get("type") == "TokenMetrics":
                content = entry.get("content")
                try:
                    metrics = json.loads(content) if isinstance(content, str) else (content or {})
                except json.JSONDecodeError:
                    metrics = {}
                tokens = metrics.get("total_tokens") or metrics.get("token_count")
                cost = metrics.get("total_cost") or metrics.get("cost")
                if tokens is not None:
                    total_tokens += int(tokens)
                    found_metrics = True
                if cost is not None:
                    total_cost += float(cost)
                    found_metrics = True
            elif entry.get("metadata"):
                tokens = entry["metadata"].get("tokens")
                cost = entry["metadata"].get("cost")
                if tokens is not None:
                    total_tokens += int(tokens)
                    found_metrics = True
                if cost is not None:
                    total_cost += float(cost)
                    found_metrics = True

        if found_metrics:
            project["total_tokens"] = total_tokens
            project["total_cost"] = round(total_cost, 6)
        else:
            project["total_tokens"] = None
            project["total_cost"] = None

    def _prepare_archive_payload(self, project: Dict[str, Any]) -> Dict[str, Any]:
        sanitized_project = copy.deepcopy(project)
        sanitized_project = self._sanitize_structure(sanitized_project)
        self._recalculate_totals(sanitized_project)
        return sanitized_project

    def add_created_file(self, filename: str):
        """Fügt eine erstellte Datei zur Projektliste hinzu."""
        if self.current_project and filename not in self.current_project["files_created"]:
            self.current_project["files_created"].append(filename)
            self._save_current_project()

    def complete_project(self, status: str = "success", allow_error_archives: bool = False):
        """
        Schließt das aktuelle Projekt ab und archiviert es.

        Nur Projekte mit status != "error" werden ins Archiv geschrieben,
        sofern nicht allow_error_archives=True gesetzt ist.

        Args:
            status: Endstatus (success, failed, cancelled, error)
            allow_error_archives: Wenn True, werden auch fehlerhafte Projekte archiviert.
        """
        if not self.current_project:
            return

        self.current_project["completed_at"] = datetime.now().isoformat()
        self.current_project["status"] = status

        archive_file = os.path.join(
            self.archive_dir,
            f"{self.current_project['project_id']}.json"
        )

        # Nur erfolgreiche (nicht error) Projekte archivieren, außer allow_error_archives
        if status == "error" and not allow_error_archives:
            logger.info("Projekt mit status=error wird nicht archiviert (allow_error_archives=False).")
            if os.path.exists(self.current_project_file):
                try:
                    os.remove(self.current_project_file)
                except OSError as e:
                    logger.warning("Aktuelle Projektdatei konnte nicht entfernt werden: %s", e)
            self.current_project = None
            return

        try:
            archive_payload = self._prepare_archive_payload(self.current_project)
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(archive_payload, f, ensure_ascii=False, indent=2)

            if os.path.exists(self.current_project_file):
                os.remove(self.current_project_file)
        except Exception as e:
            logger.error(f"Fehler beim Archivieren des Projekts: {e}")
            # ÄNDERUNG 28.01.2026: Fehler sichtbar machen und weiterreichen
            self.current_project["save_error"] = str(e)
            self.current_project["save_error_timestamp"] = datetime.now().isoformat()
            raise

        # Current project zurücksetzen
        self.current_project = None

    def get_current_project(self) -> Optional[Dict[str, Any]]:
        """Gibt das aktuelle Projekt zurück."""
        return self.current_project

    def get_entries(self, agent_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Gibt Protokoll-Einträge des aktuellen Projekts zurück.

        Args:
            agent_filter: Optional - nur Einträge von diesem Agent
            limit: Maximale Anzahl Einträge

        Returns:
            Liste von Protokoll-Einträgen
        """
        if not self.current_project:
            return []

        entries = self.current_project["entries"]

        if agent_filter:
            entries = [e for e in entries if e["from_agent"] == agent_filter]

        return entries[-limit:]

    def get_archived_projects(self) -> List[Dict[str, Any]]:
        """
        Gibt eine Liste aller archivierten Projekte zurück.

        Returns:
            Liste von Projekt-Metadaten (ohne Einträge)
        """
        projects = []

        for filename in sorted(os.listdir(self.archive_dir), reverse=True):
            if filename.endswith('.json'):
                filepath = os.path.join(self.archive_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        project = json.load(f)
                        # Nur Metadaten, nicht alle Einträge
                        # ÄNDERUNG 29.01.2026: Discovery Briefing kuerzen
                        # Briefing wird auf 200 Zeichen begrenzt zur Payload-Reduktion
                        # ÄNDERUNG 29.01.2026: Briefing-Preview sicher normalisieren
                        briefing_preview = self._normalize_briefing_preview(
                            project.get("briefing_preview", project.get("briefing"))
                        )[:200]
                        projects.append({
                            "project_id": project.get("project_id"),
                            "name": project.get("name"),
                            "goal": project.get("goal", "")[:200],
                            "briefing": briefing_preview,
                            "started_at": project.get("started_at"),
                            "completed_at": project.get("completed_at"),
                            "status": project.get("status"),
                            "iterations": project.get("iterations"),
                            "total_tokens": project.get("total_tokens"),
                            "total_cost": project.get("total_cost"),
                            "agents_involved": project.get("agents_involved", []),
                            "files_created": project.get("files_created", []),
                            "entry_count": len(project.get("entries", []))
                        })
                except (json.JSONDecodeError, IOError):
                    continue

        return projects

    def get_archived_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Lädt ein archiviertes Projekt vollständig.

        Args:
            project_id: Projekt-ID

        Returns:
            Vollständiges Projekt mit allen Einträgen
        """
        filepath = os.path.join(self.archive_dir, f"{project_id}.json")

        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)

        return None

    def search_archives(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Durchsucht alle Archive nach einem Begriff.

        Args:
            query: Suchbegriff
            limit: Maximale Ergebnisse

        Returns:
            Liste von Treffern mit Projekt-ID und Kontext
        """
        results = []
        query_lower = query.lower()

        for filename in os.listdir(self.archive_dir):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(self.archive_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    project = json.load(f)

                # Suche in Name, Goal, Einträgen
                if query_lower in project.get("name", "").lower():
                    results.append({
                        "project_id": project["project_id"],
                        "match_type": "name",
                        "match_text": project["name"],
                        "project_name": project["name"]
                    })
                elif query_lower in project.get("goal", "").lower():
                    results.append({
                        "project_id": project["project_id"],
                        "match_type": "goal",
                        "match_text": project["goal"][:200],
                        "project_name": project["name"]
                    })
                else:
                    # Suche in Einträgen
                    for entry in project.get("entries", []):
                        content = str(entry.get("content", ""))
                        if query_lower in content.lower():
                            results.append({
                                "project_id": project["project_id"],
                                "match_type": "entry",
                                "match_text": content[:200],
                                "project_name": project["name"],
                                "entry_id": entry.get("id")
                            })
                            break  # Nur ein Match pro Projekt

                if len(results) >= limit:
                    break

            except (json.JSONDecodeError, IOError):
                continue

        return results[:limit]


# Singleton-Instanz
_library_manager: Optional[LibraryManager] = None

def get_library_manager() -> LibraryManager:
    """Gibt die Singleton-Instanz des Library Managers zurück."""
    global _library_manager
    if _library_manager is None:
        _library_manager = LibraryManager()
    return _library_manager
