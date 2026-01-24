# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Datei-Utilities für Projekt-Suche und Pfad-Operationen.
              Zentrale Funktionen für die Suche nach Projektdateien.
"""

import os
from typing import Optional, List


def find_project_file(project_path: str, extensions: List[str],
                      priority_names: List[str] = None) -> Optional[str]:
    """
    Sucht nach Dateien mit bestimmten Endungen im Projektverzeichnis.

    Args:
        project_path: Projektverzeichnis
        extensions: Liste von Dateiendungen (z.B. ['.html', '.htm'])
        priority_names: Priorisierte Dateinamen (z.B. ['index.html'])

    Returns:
        Pfad zur gefundenen Datei oder None

    Example:
        >>> find_project_file("/project", [".html"], ["index.html"])
        '/project/src/index.html'
    """
    if not project_path or not os.path.exists(project_path):
        return None

    if priority_names:
        # Priorisierte Suche in typischen Ordnern
        search_dirs = [
            project_path,
            os.path.join(project_path, 'src'),
            os.path.join(project_path, 'public'),
            os.path.join(project_path, 'dist'),
            os.path.join(project_path, 'build'),
        ]
        for dir_path in search_dirs:
            if os.path.exists(dir_path):
                for name in priority_names:
                    full_path = os.path.join(dir_path, name)
                    if os.path.exists(full_path):
                        return full_path

    # Fallback: Rekursive Suche
    for root, dirs, files in os.walk(project_path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                return os.path.join(root, f)

    return None


def find_html_file(project_path: str) -> Optional[str]:
    """
    Sucht nach HTML-Dateien im Projektverzeichnis.

    Priorisiert index.html, dann beliebige .html/.htm Dateien.

    Args:
        project_path: Projektverzeichnis

    Returns:
        Pfad zur gefundenen HTML-Datei oder None
    """
    return find_project_file(
        project_path,
        extensions=['.html', '.htm'],
        priority_names=['index.html', 'index.htm']
    )


def find_python_entry(project_path: str) -> Optional[str]:
    """
    Sucht nach Python-Einstiegspunkt im Projektverzeichnis.

    Priorisiert main.py, app.py, dann beliebige .py Dateien.

    Args:
        project_path: Projektverzeichnis

    Returns:
        Pfad zur gefundenen Python-Datei oder None
    """
    return find_project_file(
        project_path,
        extensions=['.py'],
        priority_names=['main.py', 'app.py', 'script.py', '__main__.py']
    )


def find_javascript_entry(project_path: str) -> Optional[str]:
    """
    Sucht nach JavaScript-Einstiegspunkt im Projektverzeichnis.

    Args:
        project_path: Projektverzeichnis

    Returns:
        Pfad zur gefundenen JavaScript-Datei oder None
    """
    return find_project_file(
        project_path,
        extensions=['.js', '.mjs'],
        priority_names=['index.js', 'main.js', 'app.js', 'server.js']
    )
