# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 02.02.2026
Version: 1.1
Beschreibung: Zentrale Hilfsfunktionen fuer alle Agenten (Single Source of Truth).

              AENDERUNG 02.02.2026: get_model_for_agent() - Zentrale Wrapper-Funktion
                                    die Router-Logik und Config-Fallback konsolidiert.
"""

from typing import Any, Dict, List, Optional


def get_model_from_config(config: Dict[str, Any], role: str, fallback_role: Optional[str] = None) -> str:
    """
    Hilfsfunktion: Extrahiert Modell aus Config (unterstützt String und Dict-Format).

    Diese Funktion ist die SINGLE SOURCE OF TRUTH für die Modell-Extraktion
    in allen Agent-Dateien. Verwende diese statt lokaler Implementierungen.

    Args:
        config: Anwendungskonfiguration mit 'mode' und 'models' Keys
        role: Name der Agent-Rolle (z.B. 'coder', 'reviewer', 'security')
        fallback_role: Optional - Alternative Rolle falls 'role' nicht gefunden wird

    Returns:
        Model-String für die Verwendung mit CrewAI/LiteLLM

    Raises:
        ValueError: Wenn Config-Keys fehlen oder ungültig sind
        TypeError: Wenn Config-Struktur nicht korrekt ist

    Beispiel:
        >>> config = {"mode": "test", "models": {"test": {"coder": "gpt-4"}}}
        >>> model = get_model_from_config(config, "coder")
        >>> print(model)  # "gpt-4"
    """
    # Prüfe 'mode' Key
    mode = config.get("mode")
    if mode is None:
        raise ValueError("Config key 'mode' fehlt")

    # Prüfe 'models' Key
    models = config.get("models", {})
    if not isinstance(models, dict):
        raise TypeError("Config key 'models' muss ein Dictionary sein")

    # Prüfe Mode-spezifische Models
    mode_models = models.get(mode)
    if mode_models is None or not isinstance(mode_models, dict):
        raise ValueError(f"Config key 'models.{mode}' fehlt oder ist kein Dictionary")

    # Versuche Modell für Rolle zu finden
    model_config = mode_models.get(role)

    # Falls Rolle nicht gefunden, versuche Fallback
    if model_config is None and fallback_role:
        model_config = mode_models.get(fallback_role)

    # Extrahiere Modell-String
    if isinstance(model_config, str):
        return model_config
    elif isinstance(model_config, dict):
        primary = model_config.get("primary")
        if primary is None or not isinstance(primary, str):
            raise ValueError(
                f"Model-Config für Rolle '{role}'"
                + (f" (Fallback: {fallback_role})" if fallback_role else "")
                + " ist ein Dict aber 'primary' Key fehlt oder ist kein String"
            )
        return primary

    # Kein Modell gefunden - werfe Exception statt leerer String
    error_msg = f"Kein Modell gefunden für Rolle '{role}'"
    if fallback_role:
        error_msg += f" oder Fallback-Rolle '{fallback_role}'"
    error_msg += f" im Modus '{mode}'"
    raise ValueError(error_msg)


def combine_project_rules(project_rules: Dict[str, List[str]], role: str) -> str:
    """
    Kombiniert globale und rollenspezifische Regeln zu einem String.

    Diese Funktion ist die SINGLE SOURCE OF TRUTH für die Regel-Kombination
    in allen Agent-Dateien.

    Args:
        project_rules: Dictionary mit 'global' und rollenspezifischen Regeln
        role: Name der Agent-Rolle für rollenspezifische Regeln

    Returns:
        Kombinierter Regel-String für den Agent-Backstory

    Beispiel:
        >>> rules = {"global": ["Regel 1"], "coder": ["Coder Regel 1"]}
        >>> combined = combine_project_rules(rules, "coder")
    """
    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get(role, []))

    return f"Globale Regeln:\n{global_rules}\n\n{role.capitalize()}-spezifische Regeln:\n{role_rules}"


def get_model_for_agent(
    config: Dict[str, Any],
    router,
    role: str,
    fallback_role: Optional[str] = None
) -> str:
    """
    Zentrale Wrapper-Funktion fuer Modellauswahl aller Agenten.

    AENDERUNG 02.02.2026: Neue Funktion zur Konsolidierung der duplizierten
    if/else Router-Logik in allen Agenten.

    Diese Funktion ist die SINGLE SOURCE OF TRUTH fuer die Modell-Auswahl
    und vereinheitlicht folgendes Muster das in allen Agenten vorkommt:

        if router:
            model = router.get_model(role)
        else:
            model = get_model_from_config(config, role, fallback_role)

    Args:
        config: Anwendungskonfiguration mit 'mode' und 'models' Keys
        router: ModelRouter-Instanz (kann None sein wenn kein Router verfuegbar)
        role: Name der Agent-Rolle (z.B. 'coder', 'reviewer', 'tester')
        fallback_role: Optional - Alternative Rolle falls 'role' nicht konfiguriert

    Returns:
        Model-String fuer die Verwendung mit CrewAI/LiteLLM

    Beispiel:
        >>> # Mit Router (nutzt automatisches Fallback bei Rate-Limits)
        >>> model = get_model_for_agent(config, router, "coder")

        >>> # Ohne Router (nutzt Config-basiertes Fallback)
        >>> model = get_model_for_agent(config, None, "tester", fallback_role="reviewer")
    """
    if router:
        return router.get_model(role)
    return get_model_from_config(config, role, fallback_role)
