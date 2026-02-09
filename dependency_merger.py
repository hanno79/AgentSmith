"""
Author: rahn
Datum: 08.02.2026
Version: 1.0
Beschreibung: Generischer Dependency-Merge fuer Template-basierte Projekte.
              Verhindert dass der DevLoop-Coder Template-Dependencies ueberschreibt.
              Unterstuetzt package.json (JS/TS) und requirements.txt (Python).
"""
# AENDERUNG 08.02.2026: Fix 24A — Dependency-Datei Merge
# ROOT-CAUSE-FIX: Coder generiert eigene package.json die Template-Dependencies loescht
# Symptom: Template hat next:15.1.0, sqlite3:5.1.7 — Coder ueberschreibt mit next:14.2.0 OHNE sqlite3
# Loesung: Merge statt Overwrite — Template-Deps als Minimum-Basis, Coder kann nur HINZUFUEGEN

import json
import os
import re
import logging

logger = logging.getLogger(__name__)


def merge_dependency_file(existing_path: str, new_content: str, tech_blueprint: dict) -> str:
    """
    Dispatcher: Erkennt Dateityp anhand des Pfades und ruft den passenden Merger.

    Args:
        existing_path: Absoluter Pfad zur existierenden Dependency-Datei auf Disk
        new_content: Vom Coder generierter neuer Inhalt der Datei
        tech_blueprint: Blueprint mit _pinned_versions und _source_template

    Returns:
        Gemergter Inhalt als String. Bei Fehler: new_content unveraendert.
    """
    basename = os.path.basename(existing_path).lower()
    pinned_versions = tech_blueprint.get("_pinned_versions", {})

    try:
        if basename == "package.json":
            return _merge_package_json(existing_path, new_content, pinned_versions)
        elif basename == "requirements.txt":
            return _merge_requirements_txt(existing_path, new_content, pinned_versions)
        else:
            # Unbekannter Dateityp — Coder-Version unveraendert zurueck
            return new_content
    except Exception as e:
        logger.warning("Dependency-Merge fehlgeschlagen fuer %s: %s — verwende Coder-Version", basename, e)
        return new_content


def _merge_package_json(existing_path: str, new_content: str, pinned_versions: dict) -> str:
    """
    Merged existierende package.json mit Coder-generierter Version.

    Merge-Regeln:
    - dependencies: Union beider. Versions-Prioritaet: pinned > existierend > neu
    - devDependencies: Analog
    - scripts: Union (existierende behalten, neue hinzufuegen)
    - name, version, private: Existierende Werte behalten
    """
    # Existierende package.json von Disk lesen
    if not os.path.exists(existing_path):
        return new_content

    with open(existing_path, "r", encoding="utf-8") as f:
        existing_raw = f.read()

    try:
        existing_pkg = json.loads(existing_raw)
    except json.JSONDecodeError:
        logger.warning("Existierende package.json ist kein gueltiges JSON — verwende Coder-Version")
        return new_content

    try:
        new_pkg = json.loads(new_content)
    except json.JSONDecodeError:
        logger.warning("Coder-package.json ist kein gueltiges JSON — behalte existierende")
        return existing_raw

    # Basis: Existierende package.json (Template-Version)
    merged = dict(existing_pkg)

    # Dependencies mergen
    merged["dependencies"] = _merge_deps(
        existing_pkg.get("dependencies", {}),
        new_pkg.get("dependencies", {}),
        pinned_versions
    )

    # devDependencies mergen
    existing_dev = existing_pkg.get("devDependencies", {})
    new_dev = new_pkg.get("devDependencies", {})
    if existing_dev or new_dev:
        merged["devDependencies"] = _merge_deps(existing_dev, new_dev, pinned_versions)

    # Scripts mergen (existierende behalten, neue hinzufuegen)
    existing_scripts = existing_pkg.get("scripts", {})
    new_scripts = new_pkg.get("scripts", {})
    if new_scripts:
        merged_scripts = dict(existing_scripts)
        for key, val in new_scripts.items():
            if key not in merged_scripts:
                merged_scripts[key] = val
        merged["scripts"] = merged_scripts

    result = json.dumps(merged, indent=2, ensure_ascii=False)
    logger.info("package.json gemergt: %d existierende + %d neue Dependencies",
                len(existing_pkg.get("dependencies", {})),
                len(new_pkg.get("dependencies", {})))
    return result


def _merge_deps(existing: dict, new: dict, pinned: dict) -> dict:
    """
    Merged zwei Dependency-Dicts mit Versions-Prioritaet: pinned > existierend > neu.

    Entfernt ^ und ~ Prefixe (konsistent mit Fix 16 Version-Normalisierung).
    """
    merged = {}

    # Alle Packages aus beiden Quellen sammeln
    all_packages = set(list(existing.keys()) + list(new.keys()))

    for pkg in sorted(all_packages):
        if pkg in pinned:
            # Hoechste Prioritaet: Gepinnte Version aus Template
            merged[pkg] = str(pinned[pkg]).lstrip("^~")
        elif pkg in existing:
            # Zweite Prioritaet: Existierende Version (Template)
            merged[pkg] = str(existing[pkg]).lstrip("^~")
        else:
            # Dritte Prioritaet: Coder-Version (neue Dependency)
            merged[pkg] = str(new[pkg]).lstrip("^~")

    return merged


def _merge_requirements_txt(existing_path: str, new_content: str, pinned_versions: dict) -> str:
    """
    Merged existierende requirements.txt mit Coder-generierter Version.

    Merge-Regeln:
    - Union aller Packages
    - Versions-Prioritaet: pinned > existierend > neu
    - Alphabetisch sortiert
    """
    if not os.path.exists(existing_path):
        return new_content

    with open(existing_path, "r", encoding="utf-8") as f:
        existing_raw = f.read()

    existing_deps = _parse_requirements(existing_raw)
    new_deps = _parse_requirements(new_content)

    # Alle Packages sammeln
    all_packages = set(list(existing_deps.keys()) + list(new_deps.keys()))
    merged_lines = []

    for pkg in sorted(all_packages):
        # Pinned-Versions sind fuer Python als Keys normalisiert (lowercase, - statt _)
        pkg_normalized = pkg.lower().replace("_", "-")
        pinned_key = None
        for pkey in pinned_versions:
            if pkey.lower().replace("_", "-") == pkg_normalized:
                pinned_key = pkey
                break

        if pinned_key:
            merged_lines.append(f"{pkg}=={pinned_versions[pinned_key]}")
        elif pkg in existing_deps and existing_deps[pkg]:
            merged_lines.append(f"{pkg}=={existing_deps[pkg]}")
        elif pkg in new_deps and new_deps[pkg]:
            merged_lines.append(f"{pkg}=={new_deps[pkg]}")
        else:
            merged_lines.append(pkg)

    result = "\n".join(merged_lines) + "\n"
    logger.info("requirements.txt gemergt: %d existierende + %d neue Packages",
                len(existing_deps), len(new_deps))
    return result


def _parse_requirements(content: str) -> dict:
    """
    Parst requirements.txt in ein Dict {package_name: version_or_None}.

    Unterstuetzt: flask==2.3.0, flask>=2.3.0, flask~=2.3.0, flask (ohne Version)
    Ignoriert: Kommentare (#), Leerzeilen, -r includes, --extra-index-url
    """
    deps = {}
    for line in content.splitlines():
        line = line.strip()
        # Kommentare und leere Zeilen ueberspringen
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # Version extrahieren (==, >=, ~=, <=)
        match = re.match(r'^([a-zA-Z0-9_-]+(?:\[[a-zA-Z0-9_,-]+\])?)\s*(?:[><=~!]+\s*(.+))?$', line)
        if match:
            pkg_name = match.group(1).strip()
            version = match.group(2).strip() if match.group(2) else None
            deps[pkg_name] = version

    return deps
