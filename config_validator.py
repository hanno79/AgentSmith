# -*- coding: utf-8 -*-
"""
Config Validator: Pydantic-basierte Validierung der config.yaml
Stellt sicher, dass alle erforderlichen Felder vorhanden und korrekt typisiert sind.
"""

import os
import yaml
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from exceptions import ConfigurationError, ConfigKeyMissingError, ConfigValidationError


class ModelConfig(BaseModel):
    """Konfiguration für Modelle pro Agent."""
    meta_orchestrator: str = Field(default="gpt-4", description="Modell für Meta-Orchestrator")
    orchestrator: str = Field(default="gpt-4", description="Modell für Orchestrator")
    coder: str = Field(default="gpt-4", description="Modell für Coder")
    reviewer: str = Field(default="gpt-4", description="Modell für Reviewer")
    designer: str = Field(default="gpt-4", description="Modell für Designer")
    researcher: str = Field(default="gpt-4", description="Modell für Researcher")
    database_designer: str = Field(default="gpt-4", description="Modell für Database Designer")
    techstack_architect: str = Field(default="gpt-4", description="Modell für TechStack Architect")
    security: str = Field(default="gpt-4", description="Modell für Security Agent")
    tester: Optional[str] = Field(default=None, description="Modell für Tester (optional)")


class TemplateRules(BaseModel):
    """Regeln für ein Projekt-Template."""
    global_: List[str] = Field(default_factory=list, alias="global", description="Globale Regeln")
    coder: List[str] = Field(default_factory=list, description="Coder-spezifische Regeln")
    reviewer: List[str] = Field(default_factory=list, description="Reviewer-spezifische Regeln")
    designer: List[str] = Field(default_factory=list, description="Designer-spezifische Regeln")
    security: List[str] = Field(default_factory=list, description="Security-spezifische Regeln")
    orchestrator: List[str] = Field(default_factory=list, description="Orchestrator-spezifische Regeln")
    techstack_architect: List[str] = Field(default_factory=list, description="TechStack-Architect Regeln")
    database_designer: List[str] = Field(default_factory=list, description="Database-Designer Regeln")
    researcher: List[str] = Field(default_factory=list, description="Researcher-spezifische Regeln")

    model_config = {"populate_by_name": True}


class AppConfig(BaseModel):
    """Hauptkonfiguration für AgentSmith."""

    # API-Einstellungen
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="Basis-URL für OpenAI-kompatible API"
    )
    openai_api_key: str = Field(
        default="${OPENAI_API_KEY}",
        description="API-Schlüssel (kann Umgebungsvariable referenzieren)"
    )

    # Betriebsmodus
    mode: str = Field(
        default="test",
        description="Betriebsmodus: 'test' oder 'production'"
    )
    project_type: str = Field(
        default="webapp",
        description="Standard-Projekttyp: 'cli', 'webapp', oder 'ml'"
    )
    include_designer: bool = Field(
        default=True,
        description="Designer-Agent einbeziehen"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximale Wiederholungen für Self-Healing Loop"
    )
    security_max_retries: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximale Wiederholungen für Security-kritische Operationen"
    )

    # Modelle
    models: Dict[str, ModelConfig] = Field(
        default_factory=lambda: {"test": ModelConfig(), "production": ModelConfig()},
        description="Modellkonfigurationen pro Modus"
    )

    # Templates
    templates: Dict[str, TemplateRules] = Field(
        default_factory=dict,
        description="Projekt-Templates mit Regeln"
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validiert, dass mode 'test' oder 'production' ist."""
        valid_modes = ["test", "production"]
        if v not in valid_modes:
            raise ValueError(f"mode muss einer von {valid_modes} sein, nicht '{v}'")
        return v

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, v: str) -> str:
        """Validiert den Standard-Projekttyp."""
        valid_types = ["cli", "webapp", "ml", "static_html", "python_cli", "flask_app", "fastapi_app", "nodejs_app"]
        if v not in valid_types:
            raise ValueError(f"project_type muss einer von {valid_types} sein, nicht '{v}'")
        return v

    @model_validator(mode="after")
    def validate_models_for_mode(self) -> "AppConfig":
        """Stellt sicher, dass Modelle für den aktuellen Modus konfiguriert sind."""
        if self.mode not in self.models:
            raise ValueError(f"Keine Modellkonfiguration für Modus '{self.mode}' gefunden")
        return self

    def get_model(self, agent_name: str) -> str:
        """
        Gibt das konfigurierte Modell für einen Agenten zurück.

        Args:
            agent_name: Name des Agenten (z.B. 'coder', 'reviewer')

        Returns:
            Modellname als String
        """
        mode_config = self.models.get(self.mode)
        if mode_config is None:
            raise ConfigKeyMissingError(f"models.{self.mode}")

        model = getattr(mode_config, agent_name, None)
        if model is None:
            raise ConfigKeyMissingError(f"models.{self.mode}.{agent_name}")

        return model

    def get_rules_for_type(self, project_type: str) -> Dict[str, List[str]]:
        """
        Gibt die Regeln für einen Projekttyp zurück.

        Args:
            project_type: Projekttyp (z.B. 'webapp', 'cli')

        Returns:
            Dictionary mit Regeln pro Rolle
        """
        template = self.templates.get(project_type, TemplateRules())
        return {
            "global": template.global_,
            "coder": template.coder,
            "reviewer": template.reviewer,
            "designer": template.designer,
            "security": template.security,
            "orchestrator": template.orchestrator,
        }

    def resolve_env_vars(self) -> "AppConfig":
        """
        Löst Umgebungsvariablen in Konfigurationswerten auf.
        Format: ${VAR_NAME}
        """
        import re

        def resolve(value: str) -> str:
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)
            for var_name in matches:
                env_value = os.environ.get(var_name, "")
                value = value.replace(f"${{{var_name}}}", env_value)
            return value

        # API Key auflösen
        self.openai_api_key = resolve(self.openai_api_key)
        self.openai_api_base = resolve(self.openai_api_base)

        return self


def load_and_validate_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Lädt und validiert die Konfigurationsdatei.

    Args:
        config_path: Pfad zur config.yaml

    Returns:
        Validierte AppConfig-Instanz

    Raises:
        ConfigurationError: Bei Validierungsfehlern
        FileNotFoundError: Wenn die Datei nicht existiert
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"YAML-Parsing fehlgeschlagen: {e}")

    if raw_config is None:
        raw_config = {}

    try:
        config = AppConfig(**raw_config)
        return config.resolve_env_vars()
    except Exception as e:
        raise ConfigurationError(f"Validierung fehlgeschlagen: {e}")


def validate_config_dict(config_dict: Dict[str, Any]) -> AppConfig:
    """
    Validiert ein Konfigurations-Dictionary.

    Args:
        config_dict: Dictionary mit Konfigurationswerten

    Returns:
        Validierte AppConfig-Instanz
    """
    try:
        return AppConfig(**config_dict)
    except Exception as e:
        raise ConfigurationError(f"Validierung fehlgeschlagen: {e}")


# Convenience-Funktion für Abwärtskompatibilität
def get_validated_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Lädt und validiert die Konfiguration, gibt aber ein Dictionary zurück.
    Für Abwärtskompatibilität mit bestehendem Code.

    Args:
        config_path: Pfad zur config.yaml

    Returns:
        Validiertes Konfigurations-Dictionary
    """
    config = load_and_validate_config(config_path)
    return config.model_dump(by_alias=True)
