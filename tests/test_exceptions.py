# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Umfassende Tests fuer die Exception-Hierarchie in exceptions.py.
              Testet alle 24 Exception-Klassen auf korrekte Attribute,
              String-Darstellung, Vererbung und Randfaelle.
"""

import os
import sys
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exceptions import (
    AgentSmithError, AgentExecutionError, AgentNotFoundError, AgentTimeoutError,
    SandboxError, SyntaxValidationError,
    SecurityError, PathTraversalError, CommandInjectionError, UnsafeFilenameError,
    ConfigurationError, ConfigKeyMissingError, ConfigValidationError,
    AgentMemoryError, MemoryLoadError, MemorySaveError,
    OrchestrationError, MaxRetriesExceededError, PlanExecutionError,
    APIError, RateLimitError, LLMConnectionError,
    ProjectError, ProjectCreationError, FileOutputError,
)


# ==================== AgentSmithError (Basis) ====================

def test_agentsmith_error_nur_message():
    """Konstruktor mit nur einer Nachricht speichert Attribute korrekt."""
    err = AgentSmithError("Testfehler")
    assert err.message == "Testfehler"
    assert err.details is None
    assert isinstance(err, Exception)

def test_agentsmith_error_mit_details():
    """Konstruktor mit Details speichert beide Attribute und zeigt sie in str()."""
    err = AgentSmithError("Fehler", details="Zusatzinfo")
    assert err.details == "Zusatzinfo"
    assert str(err) == "Fehler | Details: Zusatzinfo"

def test_agentsmith_error_str_ohne_details():
    """String-Darstellung ohne Details zeigt nur die Nachricht."""
    err = AgentSmithError("Einfach")
    assert str(err) == "Einfach"
    assert "Details" not in str(err)

def test_agentsmith_error_details_none_explizit():
    """Explizites None fuer Details erzeugt keinen Details-Suffix."""
    err = AgentSmithError("Test", details=None)
    assert err.details is None
    assert "Details" not in str(err)


# ==================== Agent Exceptions ====================

def test_agent_execution_error_ohne_original():
    """AgentExecutionError ohne original_error speichert Attribute korrekt."""
    err = AgentExecutionError("PlannerAgent", "Planung fehlgeschlagen")
    assert err.agent_name == "PlannerAgent"
    assert err.original_error is None
    assert "[PlannerAgent]" in str(err)
    assert "Planung fehlgeschlagen" in str(err)
    assert isinstance(err, AgentSmithError)

def test_agent_execution_error_mit_original():
    """original_error wird gespeichert und in Details angezeigt."""
    original = ValueError("Ungueltige Eingabe")
    err = AgentExecutionError("CoderAgent", "Abbruch", original)
    assert err.original_error is original
    assert err.details == "Ungueltige Eingabe"
    assert "Details:" in str(err)

def test_agent_not_found_error():
    """AgentNotFoundError speichert agent_name und erzeugt sinnvolle Nachricht."""
    err = AgentNotFoundError("UnbekannterAgent")
    assert err.agent_name == "UnbekannterAgent"
    assert "UnbekannterAgent" in str(err)
    assert "nicht gefunden" in str(err)
    assert isinstance(err, AgentSmithError)

def test_agent_timeout_error():
    """AgentTimeoutError speichert agent_name und timeout_seconds."""
    err = AgentTimeoutError("SlowAgent", 30.0)
    assert err.agent_name == "SlowAgent"
    assert err.timeout_seconds == 30.0
    assert "SlowAgent" in str(err)
    assert "30.0" in str(err)
    assert "Zeitlimit" in str(err)
    assert isinstance(err, AgentSmithError)


# ==================== Sandbox Exceptions ====================

def test_sandbox_error_ohne_zeilennummer():
    """SandboxError ohne Zeilennummer zeigt keine Zeilen-Info."""
    err = SandboxError("python", "Import nicht erlaubt")
    assert err.code_type == "python"
    assert err.line_number is None
    assert "python" in str(err)
    assert "Zeile" not in str(err)
    assert isinstance(err, AgentSmithError)

def test_sandbox_error_mit_zeilennummer():
    """SandboxError mit Zeilennummer zeigt Zeilen-Info in der Nachricht."""
    err = SandboxError("javascript", "eval verboten", line_number=42)
    assert err.line_number == 42
    assert "Zeile 42" in str(err)

def test_syntax_validation_error():
    """SyntaxValidationError fuegt Syntaxfehler-Prefix hinzu."""
    err = SyntaxValidationError("python", "unerwartetes Zeichen", line_number=10)
    assert err.code_type == "python"
    assert err.line_number == 10
    assert "Syntaxfehler" in str(err)
    assert "Zeile 10" in str(err)
    assert isinstance(err, SandboxError)

def test_syntax_validation_error_ohne_zeile():
    """SyntaxValidationError funktioniert auch ohne Zeilennummer."""
    err = SyntaxValidationError("css", "Unbekannte Eigenschaft")
    assert err.line_number is None
    assert "Zeile" not in str(err)


# ==================== Security Exceptions ====================

def test_security_error_ohne_threat_type():
    """SecurityError ohne threat_type erzeugt Nachricht ohne Typ-Prefix."""
    err = SecurityError("Zugriff verweigert")
    assert err.threat_type is None
    assert "Sicherheitswarnung" in str(err)
    assert isinstance(err, AgentSmithError)

def test_security_error_mit_threat_type():
    """SecurityError mit threat_type zeigt Typ als Prefix."""
    err = SecurityError("Verdaechtig", threat_type="xss")
    assert err.threat_type == "xss"
    assert "[xss]" in str(err)

def test_path_traversal_error_ohne_resolved():
    """PathTraversalError ohne resolved_path speichert Attribute korrekt."""
    err = PathTraversalError("../../etc/passwd")
    assert err.filename == "../../etc/passwd"
    assert err.resolved_path is None
    assert err.threat_type == "path_traversal"
    assert "../../etc/passwd" in str(err)
    assert isinstance(err, SecurityError)

def test_path_traversal_error_mit_resolved():
    """PathTraversalError mit resolved_path zeigt aufgeloesten Pfad."""
    err = PathTraversalError("../secret", resolved_path="/etc/secret")
    assert err.resolved_path == "/etc/secret"
    assert "/etc/secret" in str(err)

def test_command_injection_error_ohne_char():
    """CommandInjectionError ohne dangerous_char speichert Attribute."""
    err = CommandInjectionError("ls; rm -rf /")
    assert err.command == "ls; rm -rf /"
    assert err.dangerous_char is None
    assert err.threat_type == "command_injection"
    assert isinstance(err, SecurityError)

def test_command_injection_error_mit_char():
    """CommandInjectionError mit dangerous_char zeigt Zeichen in Nachricht."""
    err = CommandInjectionError("test; drop table", dangerous_char=";")
    assert err.dangerous_char == ";"
    assert ";" in str(err)

def test_command_injection_langer_befehl():
    """Befehle laenger als 100 Zeichen werden in der Nachricht abgeschnitten."""
    langer_befehl = "x" * 200
    err = CommandInjectionError(langer_befehl)
    assert err.command == langer_befehl
    assert langer_befehl not in str(err)  # Nachricht kuerzt auf 100 Zeichen

def test_unsafe_filename_error():
    """UnsafeFilenameError speichert filename, reason und setzt threat_type."""
    err = UnsafeFilenameError("test<>.txt", "Enthaelt Sonderzeichen")
    assert err.filename == "test<>.txt"
    assert err.reason == "Enthaelt Sonderzeichen"
    assert err.threat_type == "unsafe_filename"
    assert "test<>.txt" in str(err)
    assert isinstance(err, SecurityError)


# ==================== Configuration Exceptions ====================

def test_configuration_error_ohne_key():
    """ConfigurationError ohne config_key erzeugt einfache Nachricht."""
    err = ConfigurationError("Datei nicht lesbar")
    assert err.config_key is None
    assert str(err) == "Datei nicht lesbar"
    assert isinstance(err, AgentSmithError)

def test_configuration_error_mit_key():
    """ConfigurationError mit config_key zeigt Key als Prefix."""
    err = ConfigurationError("Wert fehlt", config_key="api_key")
    assert err.config_key == "api_key"
    assert "[config.api_key]" in str(err)

def test_config_key_missing_error():
    """ConfigKeyMissingError setzt key als config_key."""
    err = ConfigKeyMissingError("database_url")
    assert err.config_key == "database_url"
    assert "database_url" in str(err)
    assert "fehlt" in str(err)
    assert isinstance(err, ConfigurationError)

def test_config_validation_error():
    """ConfigValidationError speichert key, value und expected."""
    err = ConfigValidationError("max_retries", -5, "positive Ganzzahl")
    assert err.config_key == "max_retries"
    assert err.value == -5
    assert err.expected == "positive Ganzzahl"
    assert "[config.max_retries]" in str(err)
    assert "-5" in str(err)
    assert isinstance(err, ConfigurationError)


# ==================== Memory Exceptions ====================

def test_agent_memory_error_ohne_path():
    """AgentMemoryError ohne memory_path speichert None als details."""
    err = AgentMemoryError("Speicher voll")
    assert err.memory_path is None
    assert err.details is None
    assert "Memory-Fehler" in str(err)
    assert isinstance(err, AgentSmithError)

def test_agent_memory_error_mit_path():
    """AgentMemoryError mit memory_path speichert Pfad als Details."""
    err = AgentMemoryError("Zugriff verweigert", memory_path="/tmp/mem.json")
    assert err.memory_path == "/tmp/mem.json"
    assert err.details == "/tmp/mem.json"
    assert "Details:" in str(err)

def test_memory_load_error_ohne_original():
    """MemoryLoadError ohne original_error funktioniert korrekt."""
    err = MemoryLoadError("/data/mem.json")
    assert err.memory_path == "/data/mem.json"
    assert err.original_error is None
    assert "laden" in str(err)
    assert isinstance(err, AgentMemoryError)

def test_memory_load_error_mit_original():
    """MemoryLoadError mit original_error speichert diesen."""
    original = FileNotFoundError("Datei fehlt")
    err = MemoryLoadError("/data/mem.json", original_error=original)
    assert err.original_error is original
    assert err.memory_path == "/data/mem.json"

def test_memory_save_error_ohne_original():
    """MemorySaveError ohne original_error funktioniert korrekt."""
    err = MemorySaveError("/data/mem.json")
    assert err.memory_path == "/data/mem.json"
    assert err.original_error is None
    assert "speichern" in str(err)
    assert isinstance(err, AgentMemoryError)

def test_memory_save_error_mit_original():
    """MemorySaveError mit original_error speichert diesen."""
    original = PermissionError("Keine Berechtigung")
    err = MemorySaveError("/data/mem.json", original_error=original)
    assert err.original_error is original


# ==================== Orchestration Exceptions ====================

def test_orchestration_error():
    """OrchestrationError reicht Nachricht durch an AgentSmithError."""
    err = OrchestrationError("Pipeline abgebrochen")
    assert err.message == "Pipeline abgebrochen"
    assert str(err) == "Pipeline abgebrochen"
    assert isinstance(err, AgentSmithError)

def test_max_retries_exceeded_ohne_feedback():
    """MaxRetriesExceededError ohne last_feedback speichert None."""
    err = MaxRetriesExceededError(5)
    assert err.max_retries == 5
    assert err.last_feedback is None
    assert "5" in str(err)
    assert "Wiederholungen" in str(err)
    assert isinstance(err, OrchestrationError)

def test_max_retries_exceeded_mit_feedback():
    """MaxRetriesExceededError mit last_feedback speichert als Details."""
    err = MaxRetriesExceededError(3, last_feedback="Syntax-Fehler")
    assert err.last_feedback == "Syntax-Fehler"
    assert err.details == "Syntax-Fehler"
    assert "Details: Syntax-Fehler" in str(err)

def test_plan_execution_error():
    """PlanExecutionError speichert plan, failed_at korrekt."""
    plan = ["schritt1", "schritt2", "schritt3"]
    err = PlanExecutionError(plan, "schritt2", "Abhaengigkeit fehlt")
    assert err.plan == plan
    assert err.failed_at == "schritt2"
    assert "schritt2" in str(err)
    assert "fehlgeschlagen" in str(err)
    assert isinstance(err, OrchestrationError)


# ==================== API Exceptions ====================

def test_api_error():
    """APIError reicht Nachricht durch an AgentSmithError."""
    err = APIError("Server nicht erreichbar")
    assert err.message == "Server nicht erreichbar"
    assert str(err) == "Server nicht erreichbar"
    assert isinstance(err, AgentSmithError)

def test_rate_limit_error_ohne_retry():
    """RateLimitError ohne retry_after speichert None."""
    err = RateLimitError()
    assert err.retry_after is None
    assert "Rate-Limit" in str(err)
    assert "Sekunden" not in str(err)
    assert isinstance(err, APIError)

def test_rate_limit_error_mit_retry():
    """RateLimitError mit retry_after zeigt Wartezeit in Nachricht."""
    err = RateLimitError(retry_after=60)
    assert err.retry_after == 60
    assert "60" in str(err)
    assert "Sekunden" in str(err)

def test_llm_connection_error_ohne_original():
    """LLMConnectionError ohne original_error speichert None."""
    err = LLMConnectionError("OpenAI")
    assert err.provider == "OpenAI"
    assert err.original_error is None
    assert err.details is None
    assert "OpenAI" in str(err)
    assert isinstance(err, APIError)

def test_llm_connection_error_mit_original():
    """LLMConnectionError mit original_error speichert Details."""
    original = ConnectionError("Timeout")
    err = LLMConnectionError("Anthropic", original_error=original)
    assert err.original_error is original
    assert err.details == "Timeout"
    assert "Details:" in str(err)


# ==================== Project Exceptions ====================

def test_project_error():
    """ProjectError reicht Nachricht durch an AgentSmithError."""
    err = ProjectError("Projekt ungueltig")
    assert err.message == "Projekt ungueltig"
    assert str(err) == "Projekt ungueltig"
    assert isinstance(err, AgentSmithError)

def test_project_creation_error_ohne_original():
    """ProjectCreationError ohne original_error speichert None."""
    err = ProjectCreationError("/tmp/neues_projekt")
    assert err.project_path == "/tmp/neues_projekt"
    assert err.original_error is None
    assert err.details is None
    assert "/tmp/neues_projekt" in str(err)
    assert isinstance(err, ProjectError)

def test_project_creation_error_mit_original():
    """ProjectCreationError mit original_error speichert Details."""
    original = OSError("Kein Speicherplatz")
    err = ProjectCreationError("/tmp/proj", original_error=original)
    assert err.original_error is original
    assert err.details == "Kein Speicherplatz"

def test_file_output_error_ohne_original():
    """FileOutputError ohne original_error speichert None."""
    err = FileOutputError("/tmp/output.txt")
    assert err.file_path == "/tmp/output.txt"
    assert err.original_error is None
    assert err.details is None
    assert "/tmp/output.txt" in str(err)
    assert isinstance(err, ProjectError)

def test_file_output_error_mit_original():
    """FileOutputError mit original_error speichert Details."""
    original = PermissionError("Schreibzugriff verweigert")
    err = FileOutputError("/tmp/out.txt", original_error=original)
    assert err.original_error is original
    assert err.details == "Schreibzugriff verweigert"


# ==================== Uebergreifende Hierarchie-Tests ====================

# Alle Exception-Instanzen fuer parametrisierte Tests
ALLE_EXCEPTIONS = [
    AgentSmithError("Test"),
    AgentExecutionError("a", "m"),
    AgentNotFoundError("a"),
    AgentTimeoutError("a", 10),
    SandboxError("py", "m"),
    SyntaxValidationError("py", "m"),
    SecurityError("m"),
    PathTraversalError("f"),
    CommandInjectionError("c"),
    UnsafeFilenameError("f", "r"),
    ConfigurationError("m"),
    ConfigKeyMissingError("k"),
    ConfigValidationError("k", "v", "e"),
    AgentMemoryError("m"),
    MemoryLoadError("/p"),
    MemorySaveError("/p"),
    OrchestrationError("m"),
    MaxRetriesExceededError(1),
    PlanExecutionError([], "s", "m"),
    APIError("m"),
    RateLimitError(),
    LLMConnectionError("p"),
    ProjectError("m"),
    ProjectCreationError("/p"),
    FileOutputError("/p"),
]


@pytest.mark.parametrize("exc", ALLE_EXCEPTIONS, ids=lambda e: type(e).__name__)
def test_alle_erben_von_agentsmith_error(exc):
    """Jede Exception erbt von AgentSmithError."""
    assert isinstance(exc, AgentSmithError), (
        f"Erwartet: isinstance von AgentSmithError, "
        f"Erhalten: {type(exc).__name__} erbt nicht korrekt"
    )


@pytest.mark.parametrize("exc", ALLE_EXCEPTIONS, ids=lambda e: type(e).__name__)
def test_str_immer_nicht_leer(exc):
    """str() liefert fuer jede Exception einen nicht-leeren String."""
    assert len(str(exc)) > 0, (
        f"Erwartet: Nicht-leerer String, "
        f"Erhalten: Leerer String fuer {type(exc).__name__}"
    )


def test_hierarchie_fangbar_mit_except():
    """Abgeleitete Exceptions sind mit Eltern-except-Block fangbar."""
    with pytest.raises(AgentSmithError):
        raise RateLimitError(retry_after=30)
    with pytest.raises(SecurityError):
        raise PathTraversalError("../etc/passwd")
    with pytest.raises(OrchestrationError):
        raise MaxRetriesExceededError(10)
    with pytest.raises(APIError):
        raise LLMConnectionError("OpenAI")
    with pytest.raises(ProjectError):
        raise FileOutputError("/tmp/x")
    with pytest.raises(ConfigurationError):
        raise ConfigKeyMissingError("api_key")
    with pytest.raises(SandboxError):
        raise SyntaxValidationError("py", "fehler")
    with pytest.raises(AgentMemoryError):
        raise MemoryLoadError("/tmp/mem.json")
