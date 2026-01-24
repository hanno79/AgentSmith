# -*- coding: utf-8 -*-
"""
AgentSmith Exception Hierarchy
Standardisierte Exceptions für konsistente Fehlerbehandlung.
"""

from typing import Optional, Any


class AgentSmithError(Exception):
    """
    Basis-Exception für alle AgentSmith-Fehler.
    Alle benutzerdefinierten Exceptions sollten von dieser Klasse erben.
    """

    def __init__(self, message: str, details: Optional[Any] = None):
        """
        Args:
            message: Beschreibende Fehlermeldung
            details: Optionale zusätzliche Details (z.B. Kontext, Daten)
        """
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ==================== Agent Exceptions ====================

class AgentExecutionError(AgentSmithError):
    """
    Wird ausgelöst, wenn ein Agent bei der Ausführung fehlschlägt.
    """

    def __init__(
        self,
        agent_name: str,
        message: str,
        original_error: Optional[Exception] = None
    ):
        """
        Args:
            agent_name: Name des fehlgeschlagenen Agenten
            message: Beschreibung des Fehlers
            original_error: Die ursprüngliche Exception (falls vorhanden)
        """
        self.agent_name = agent_name
        self.original_error = original_error
        full_message = f"[{agent_name}] {message}"
        super().__init__(full_message, details=str(original_error) if original_error else None)


class AgentNotFoundError(AgentSmithError):
    """Wird ausgelöst, wenn ein angeforderter Agent nicht existiert."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        super().__init__(f"Agent nicht gefunden: {agent_name}")


class AgentTimeoutError(AgentSmithError):
    """Wird ausgelöst, wenn ein Agent das Zeitlimit überschreitet."""

    def __init__(self, agent_name: str, timeout_seconds: float):
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Agent '{agent_name}' hat das Zeitlimit von {timeout_seconds}s überschritten"
        )


# ==================== Sandbox Exceptions ====================

class SandboxError(AgentSmithError):
    """
    Wird ausgelöst, wenn die Sandbox-Validierung fehlschlägt.
    """

    def __init__(self, code_type: str, message: str, line_number: Optional[int] = None):
        """
        Args:
            code_type: Art des Codes (python, html, js)
            message: Fehlerbeschreibung
            line_number: Zeilennummer des Fehlers (falls bekannt)
        """
        self.code_type = code_type
        self.line_number = line_number
        location = f" in Zeile {line_number}" if line_number else ""
        super().__init__(f"Sandbox-Fehler ({code_type}){location}: {message}")


class SyntaxValidationError(SandboxError):
    """Wird ausgelöst bei Syntax-Fehlern im validierten Code."""

    def __init__(self, code_type: str, message: str, line_number: Optional[int] = None):
        super().__init__(code_type, f"Syntaxfehler: {message}", line_number)


# ==================== Security Exceptions ====================

class SecurityError(AgentSmithError):
    """
    Wird ausgelöst bei Sicherheitsverletzungen.
    Basisklasse für alle sicherheitsbezogenen Exceptions.
    """

    def __init__(self, message: str, threat_type: Optional[str] = None):
        """
        Args:
            message: Beschreibung der Sicherheitsverletzung
            threat_type: Art der Bedrohung (z.B. "path_traversal", "command_injection")
        """
        self.threat_type = threat_type
        prefix = f"[{threat_type}] " if threat_type else ""
        super().__init__(f"Sicherheitswarnung: {prefix}{message}")


class PathTraversalError(SecurityError):
    """Wird ausgelöst bei Path Traversal Versuchen."""

    def __init__(self, filename: str, resolved_path: Optional[str] = None):
        """
        Args:
            filename: Der verdächtige Dateiname
            resolved_path: Der aufgelöste (gefährliche) Pfad
        """
        self.filename = filename
        self.resolved_path = resolved_path
        message = f"Path Traversal erkannt: {filename}"
        if resolved_path:
            message += f" -> {resolved_path}"
        super().__init__(message, threat_type="path_traversal")


class CommandInjectionError(SecurityError):
    """Wird ausgelöst bei Command Injection Versuchen."""

    def __init__(self, command: str, dangerous_char: Optional[str] = None):
        """
        Args:
            command: Der verdächtige Befehl
            dangerous_char: Das gefährliche Zeichen (falls identifiziert)
        """
        self.command = command
        self.dangerous_char = dangerous_char
        message = f"Command Injection erkannt: {command[:100]}"
        if dangerous_char:
            message += f" (enthält '{dangerous_char}')"
        super().__init__(message, threat_type="command_injection")


class UnsafeFilenameError(SecurityError):
    """Wird ausgelöst bei unsicheren Dateinamen."""

    def __init__(self, filename: str, reason: str):
        """
        Args:
            filename: Der unsichere Dateiname
            reason: Grund warum der Dateiname unsicher ist
        """
        self.filename = filename
        self.reason = reason
        super().__init__(f"Unsicherer Dateiname '{filename}': {reason}", threat_type="unsafe_filename")


# ==================== Configuration Exceptions ====================

class ConfigurationError(AgentSmithError):
    """
    Wird ausgelöst bei Konfigurationsfehlern.
    """

    def __init__(self, message: str, config_key: Optional[str] = None):
        """
        Args:
            message: Fehlerbeschreibung
            config_key: Der fehlerhafte Konfigurationsschlüssel
        """
        self.config_key = config_key
        prefix = f"[config.{config_key}] " if config_key else ""
        super().__init__(f"{prefix}{message}")


class ConfigKeyMissingError(ConfigurationError):
    """Wird ausgelöst, wenn ein erforderlicher Konfigurationsschlüssel fehlt."""

    def __init__(self, key: str):
        super().__init__(f"Erforderlicher Schlüssel fehlt: {key}", config_key=key)


class ConfigValidationError(ConfigurationError):
    """Wird ausgelöst, wenn ein Konfigurationswert ungültig ist."""

    def __init__(self, key: str, value: Any, expected: str):
        self.value = value
        self.expected = expected
        super().__init__(
            f"Ungültiger Wert '{value}'. Erwartet: {expected}",
            config_key=key
        )


# ==================== Memory Exceptions ====================

class MemoryError(AgentSmithError):
    """Wird ausgelöst bei Fehlern im Memory-System."""

    def __init__(self, message: str, memory_path: Optional[str] = None):
        self.memory_path = memory_path
        details = memory_path if memory_path else None
        super().__init__(f"Memory-Fehler: {message}", details=details)


class MemoryLoadError(MemoryError):
    """Wird ausgelöst, wenn Memory nicht geladen werden kann."""

    def __init__(self, memory_path: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(f"Kann Memory nicht laden: {original_error}", memory_path)


class MemorySaveError(MemoryError):
    """Wird ausgelöst, wenn Memory nicht gespeichert werden kann."""

    def __init__(self, memory_path: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(f"Kann Memory nicht speichern: {original_error}", memory_path)


# ==================== Orchestration Exceptions ====================

class OrchestrationError(AgentSmithError):
    """Wird ausgelöst bei Fehlern in der Orchestrierung."""
    pass


class MaxRetriesExceededError(OrchestrationError):
    """Wird ausgelöst, wenn die maximale Anzahl an Wiederholungen überschritten wurde."""

    def __init__(self, max_retries: int, last_feedback: Optional[str] = None):
        self.max_retries = max_retries
        self.last_feedback = last_feedback
        super().__init__(
            f"Maximale Wiederholungen ({max_retries}) überschritten",
            details=last_feedback
        )


class PlanExecutionError(OrchestrationError):
    """Wird ausgelöst, wenn der Ausführungsplan fehlschlägt."""

    def __init__(self, plan: list, failed_at: str, message: str):
        self.plan = plan
        self.failed_at = failed_at
        super().__init__(f"Plan fehlgeschlagen bei '{failed_at}': {message}")


# ==================== API Exceptions ====================

class APIError(AgentSmithError):
    """Wird ausgelöst bei API-bezogenen Fehlern."""
    pass


class RateLimitError(APIError):
    """Wird ausgelöst, wenn das API-Rate-Limit erreicht wurde."""

    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "API Rate-Limit erreicht"
        if retry_after:
            message += f". Erneut versuchen in {retry_after} Sekunden"
        super().__init__(message)


class LLMConnectionError(APIError):
    """Wird ausgelöst, wenn die Verbindung zum LLM fehlschlägt."""

    def __init__(self, provider: str, original_error: Optional[Exception] = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(
            f"Verbindung zu {provider} fehlgeschlagen",
            details=str(original_error) if original_error else None
        )


# ==================== File/Project Exceptions ====================

class ProjectError(AgentSmithError):
    """Wird ausgelöst bei Projekt-bezogenen Fehlern."""
    pass


class ProjectCreationError(ProjectError):
    """Wird ausgelöst, wenn ein Projekt nicht erstellt werden kann."""

    def __init__(self, project_path: str, original_error: Optional[Exception] = None):
        self.project_path = project_path
        self.original_error = original_error
        super().__init__(
            f"Projekt konnte nicht erstellt werden: {project_path}",
            details=str(original_error) if original_error else None
        )


class FileOutputError(ProjectError):
    """Wird ausgelöst, wenn Dateien nicht geschrieben werden können."""

    def __init__(self, file_path: str, original_error: Optional[Exception] = None):
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(
            f"Datei konnte nicht geschrieben werden: {file_path}",
            details=str(original_error) if original_error else None
        )
