# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 07.02.2026
Version: 1.0
Beschreibung: Dependency-Helper fuer TechStack-Phase.
              Extrahiert aus orchestration_phases.py (Regel 1: Max 500 Zeilen)
              Enthaelt: Dependency-Sanitizing, Template-Anwendung, Pflicht-Dependencies
"""

import json
import logging
from typing import Callable

logger = logging.getLogger(__name__)

# AENDERUNG 02.02.2026: Blacklist fuer ungueltige Python-Pakete (Frontend-only)
# Diese Pakete werden vom LLM manchmal faelschlicherweise als Python-Dependencies empfohlen
INVALID_PYTHON_PACKAGES = {
    # CSS-Frameworks (nur per CDN oder npm)
    "bootstrap", "tailwindcss", "bulma", "foundation", "materialize",
    "semantic-ui", "pure-css", "skeleton", "milligram",
    # JS-Frameworks (nur npm)
    "react", "vue", "angular", "svelte", "ember", "backbone",
    # JS-Bibliotheken (nur npm)
    "jquery", "lodash", "axios", "moment", "d3", "chart.js", "three.js",
    # CSS-in-JS (nur npm)
    "styled-components", "emotion", "tailwind",
}


def ensure_required_dependencies(deps: list, language: str, project_type: str, ui_log_callback: Callable) -> list:
    """
    AENDERUNG 07.02.2026: Fuegt fehlende Pflicht-Dependencies hinzu basierend auf Framework.
    Symptom: react-dom fehlte in package.json -> Next.js App startet nicht.
    Ursache: LLM vergisst haeufig Co-Dependencies (react-dom, postcss, autoprefixer).
    Loesung: Automatische Ergaenzung nach Blueprint-Parsing.
    """
    if not deps or language.lower() not in ("javascript", "typescript"):
        return deps
    # AENDERUNG 07.02.2026: Set statt Liste, nach jedem Append aktualisieren
    # ROOT-CAUSE-FIX: deps_lower war stale nach Append -> react-dom wurde doppelt eingefuegt
    deps_lower = {d.lower() for d in deps}
    added = []
    # React braucht zwingend react-dom
    if "react" in deps_lower and "react-dom" not in deps_lower:
        deps.append("react-dom")
        deps_lower.add("react-dom")
        added.append("react-dom")
    # Next.js braucht react + react-dom
    if "next" in deps_lower:
        if "react" not in deps_lower:
            deps.append("react")
            deps_lower.add("react")
            added.append("react")
        if "react-dom" not in deps_lower:
            deps.append("react-dom")
            deps_lower.add("react-dom")
            added.append("react-dom")
    # Tailwind braucht postcss + autoprefixer
    if "tailwindcss" in deps_lower:
        if "postcss" not in deps_lower:
            deps.append("postcss")
            deps_lower.add("postcss")
            added.append("postcss")
        if "autoprefixer" not in deps_lower:
            deps.append("autoprefixer")
            deps_lower.add("autoprefixer")
            added.append("autoprefixer")
    # AENDERUNG 07.02.2026: Shadcn/UI Ecosystem Dependencies
    # ROOT-CAUSE-FIX: Coder importiert lucide-react, clsx, tailwind-merge im Code
    # aber deklariert sie nicht in package.json -> Compile-Fehler zur Laufzeit
    has_radix = any("@radix-ui" in d.lower() or "shadcn" in d.lower() for d in deps)
    if has_radix:
        for pkg in ["lucide-react", "clsx", "tailwind-merge"]:
            if pkg.lower() not in deps_lower:
                deps.append(pkg)
                deps_lower.add(pkg.lower())
                added.append(pkg)
    # AENDERUNG 07.02.2026: sqlite3 braucht sqlite-Wrapper fuer Promise-API
    # ROOT-CAUSE-FIX: Coder importiert 'sqlite' (Promise-Wrapper) aber deklariert nur 'sqlite3'
    if "sqlite3" in deps_lower and "sqlite" not in deps_lower:
        deps.append("sqlite")
        deps_lower.add("sqlite")
        added.append("sqlite")
    # AENDERUNG 07.02.2026: Ungueltige Package-Namen entfernen
    # ROOT-CAUSE-FIX: 'shadcn/ui' existiert nicht auf npm, Coder generiert es trotzdem
    invalid_packages = {"shadcn/ui", "shadcn"}
    removed = [d for d in deps if d.lower() in invalid_packages]
    if removed:
        deps[:] = [d for d in deps if d.lower() not in invalid_packages]
        ui_log_callback("TechArchitect", "Info",
            f"Ungueltige Packages entfernt: {', '.join(removed)}")
    # AENDERUNG 07.02.2026: @next/jest existiert nicht auf npm
    # ROOT-CAUSE-FIX: Coder generiert @next/jest als devDependency -> npm install schlaegt fehl
    # Loesung: Entferne @next/jest (next/jest wird direkt ueber require('next/jest') genutzt)
    next_jest_removed = [d for d in deps if d.lower() == "@next/jest"]
    if next_jest_removed:
        deps[:] = [d for d in deps if d.lower() != "@next/jest"]
        ui_log_callback("TechArchitect", "Info",
            "Entfernt @next/jest (existiert nicht auf npm, verwende next/jest)")
    if added:
        ui_log_callback("TechArchitect", "Info",
            f"Pflicht-Dependencies automatisch ergaenzt: {', '.join(added)}")
    return deps


def sanitize_python_dependencies(deps: list, language: str, ui_log_callback: Callable) -> list:
    """
    Entfernt ungueltige Python-Pakete aus der Dependencies-Liste.

    Args:
        deps: Liste der Dependencies vom TechArchitect
        language: Sprache des Projekts (python, javascript, etc.)
        ui_log_callback: Callback fuer Logging

    Returns:
        Bereinigte Liste ohne ungueltige Pakete
    """
    if language != "python" or not deps:
        return deps

    sanitized = []
    removed = []

    for dep in deps:
        dep_lower = dep.lower().strip()
        if dep_lower in INVALID_PYTHON_PACKAGES:
            removed.append(dep)
        else:
            sanitized.append(dep)

    if removed:
        ui_log_callback("TechArchitect", "Warning",
            f"Ungueltige Python-Pakete entfernt (Frontend-only): {', '.join(removed)}")

    return sanitized


def apply_template_if_selected(
    parsed_output: dict,
    project_path: str,
    ui_log_callback: Callable
) -> dict:
    """
    AENDERUNG 07.02.2026: Template-Integration in TechStack-Phase.
    Wenn der Agent ein Template gewaehlt hat (selected_template != null),
    wird der Blueprint aus dem Template gebaut und File-Templates kopiert.
    Sonst wird der Output unveraendert zurueckgegeben.

    Args:
        parsed_output: JSON-Output des TechStack-Agents
        project_path: Ziel-Projektverzeichnis
        ui_log_callback: UI-Log Callback

    Returns:
        Fertiger tech_blueprint (Template-basiert oder Original)
    """
    selected_template_id = parsed_output.get("selected_template")
    if not selected_template_id:
        # Kein Template gewaehlt — Agent hat custom Blueprint geliefert
        # Pruefe ob Blueprint im "blueprint" Feld steckt (Custom-Format)
        if "blueprint" in parsed_output and "project_type" in parsed_output.get("blueprint", {}):
            return parsed_output["blueprint"]
        return parsed_output

    try:
        from techstack_templates.template_loader import (
            get_template_by_id, build_blueprint_from_template, copy_file_templates
        )

        template = get_template_by_id(selected_template_id)
        if not template:
            ui_log_callback("TechArchitect", "Warning",
                f"Template '{selected_template_id}' nicht gefunden, verwende Agent-Output als Fallback")
            return parsed_output.get("blueprint", parsed_output)

        # Blueprint aus Template + Customizations bauen
        customizations = parsed_output.get("customizations", {})
        customizations["additional_dependencies"] = parsed_output.get("additional_dependencies", {})
        if parsed_output.get("reasoning"):
            customizations["reasoning"] = parsed_output["reasoning"]

        tech_blueprint = build_blueprint_from_template(template, customizations)

        # File-Templates ins Projekt kopieren
        copied = copy_file_templates(template, project_path)
        if copied:
            ui_log_callback("TechArchitect", "Info",
                f"Template '{selected_template_id}': {len(copied)} Basis-Dateien kopiert ({', '.join(copied[:5])})")

        ui_log_callback("TechArchitect", "Info",
            f"Template '{selected_template_id}' angewendet: {template.get('display_name', '')}")

        return tech_blueprint

    except ImportError:
        ui_log_callback("TechArchitect", "Warning",
            "techstack_templates Modul nicht verfuegbar, verwende Agent-Output")
        return parsed_output.get("blueprint", parsed_output)
    except Exception as e:
        ui_log_callback("TechArchitect", "Warning",
            f"Template-Anwendung fehlgeschlagen ({e}), verwende Agent-Output als Fallback")
        return parsed_output.get("blueprint", parsed_output)
