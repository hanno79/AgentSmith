# -*- coding: utf-8 -*-
# Author: rahn
# Datum: 31.01.2026
# Version: 1.0
# Beschreibung: Basis-Dockerfile fuer Python-Projekte (Flask, FastAPI, CLI)

FROM python:3.11-slim

# Arbeitsverzeichnis setzen
WORKDIR /app

# System-Dependencies installieren (SQLite fuer Datenbank-Projekte)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Pip aktualisieren und grundlegende Tools installieren
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Umgebungsvariablen fuer Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Standard-Port fuer Web-Apps (Flask: 5000, FastAPI: 8000)
EXPOSE 5000 8000

# Projekt-Dependencies werden zur Laufzeit installiert via:
# docker run -v ./project:/app python-base pip install -r requirements.txt

# Healthcheck fuer Web-Apps
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || curl -f http://localhost:8000/health || exit 1

# Default-Befehl: Python-Version anzeigen
CMD ["python", "--version"]
