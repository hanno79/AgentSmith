# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 01.02.2026
Version: 1.0
Beschreibung: Konstanten und Hilfs-Funktionen für DependencyAgent.
              Extrahiert aus dependency_agent.py (Regel 1: Max 500 Zeilen)
"""

import os
from pathlib import Path

# Pfad zur Inventar-Datei
INVENTORY_PATH = Path(__file__).parent.parent / "library" / "dependencies.json"

# Bekannte npm-Pakete die NIEMALS via pip installiert werden sollen
NPM_PACKAGES = {
    # React Ecosystem
    "react", "react-dom", "react-router", "react-router-dom", "react-redux",
    "react-query", "react-hook-form", "next", "gatsby", "create-react-app",
    # Vue Ecosystem
    "vue", "vue-router", "vuex", "pinia", "nuxt",
    # Angular
    "angular", "@angular/core", "@angular/cli", "@angular/common",
    # Svelte
    "svelte", "sveltekit", "@sveltejs/kit",
    # Build Tools
    "webpack", "vite", "parcel", "rollup", "esbuild", "turbopack",
    # CSS/Styling
    "tailwindcss", "postcss", "autoprefixer", "sass", "less", "styled-components",
    # UI-Komponentenbibliotheken
    # AENDERUNG 07.02.2026: UI-Libraries hinzugefuegt (shadcn/ui Blockade-Fix)
    "shadcn-ui", "shadcn", "@shadcn/ui",
    "chakra-ui", "antd", "daisyui", "flowbite", "primereact", "primevue",
    # Utility-Libraries (haeufig mit shadcn/UI-Libraries)
    "clsx", "class-variance-authority", "tailwind-merge", "lucide-react",
    "cmdk", "sonner", "vaul",
    # State-Management
    "zustand", "jotai", "recoil", "swr",
    # Validation + Animation
    "zod", "yup", "formik", "framer-motion",
    # Utilities
    "typescript", "eslint", "prettier", "jest", "vitest", "mocha", "chai",
    "axios", "lodash", "moment", "dayjs", "date-fns",
    # Node.js specific
    "express", "fastify", "koa", "nest", "socket.io"
}

# Python Built-in Module die NICHT per pip installiert werden dürfen
PYTHON_BUILTIN_MODULES = {
    # Datenbank
    "sqlite3", "dbm", "shelve", "pickle",
    # System/OS
    "os", "sys", "io", "pathlib", "shutil", "glob", "tempfile",
    "subprocess", "multiprocessing", "threading", "concurrent",
    "asyncio", "queue", "select", "selectors", "signal", "mmap",
    # Datentypen
    "json", "csv", "xml", "html", "configparser",
    "collections", "array", "heapq", "bisect", "copy",
    "types", "typing", "dataclasses", "enum", "abc",
    # Zeit/Datum
    "datetime", "time", "calendar", "zoneinfo",
    # Mathematik
    "math", "cmath", "decimal", "fractions", "random", "statistics", "numbers",
    # Text
    "string", "re", "textwrap", "unicodedata", "difflib",
    # Kryptographie
    "hashlib", "hmac", "secrets", "base64",
    # Netzwerk
    "socket", "ssl", "http", "urllib", "email", "ftplib", "smtplib",
    # Entwicklung
    "unittest", "doctest", "pdb", "timeit", "trace", "traceback",
    "logging", "warnings", "inspect", "dis", "gc", "weakref",
    # Sonstiges
    "argparse", "getopt", "getpass", "gettext", "locale",
    "platform", "ctypes", "struct", "codecs", "pprint", "reprlib",
    "functools", "itertools", "operator", "contextlib", "atexit",
    "uuid", "errno", "builtins", "importlib", "zipfile", "tarfile",
    "gzip", "bz2", "lzma", "zipimport", "pkgutil", "modulefinder"
}

# Bekannte Windows-Installationspfade für Node.js/npm
WINDOWS_NPM_PATHS = [
    r"C:\Program Files\nodejs\npm.cmd",
    r"C:\Program Files (x86)\nodejs\npm.cmd",
    os.path.expandvars(r"%APPDATA%\npm\npm.cmd"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\npm.cmd"),
    os.path.expandvars(r"%ProgramFiles%\nodejs\npm.cmd"),
]


def is_builtin_module(name: str) -> bool:
    """
    Prüft ob ein Paketname ein Python Built-in Modul ist.

    Args:
        name: Paketname (z.B. "sqlite3", "os", "json")

    Returns:
        True wenn es ein Built-in Modul ist
    """
    return name.lower() in PYTHON_BUILTIN_MODULES


def filter_builtin_modules(dependencies: list) -> list:
    """
    Filtert Built-in Module aus einer Dependency-Liste heraus.

    Args:
        dependencies: Liste von Paketnamen

    Returns:
        Liste ohne Built-in Module
    """
    filtered = []
    for dep in dependencies:
        # Extrahiere Paketnamen (ohne Version)
        pkg_name = dep.split("==")[0].split(">=")[0].split("<=")[0].split("<")[0].split(">")[0].strip()
        if not is_builtin_module(pkg_name):
            filtered.append(dep)
    return filtered
