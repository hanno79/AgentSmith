# -*- coding: utf-8 -*-
# Author: rahn
# Datum: 31.01.2026
# Version: 1.0
# Beschreibung: Basis-Dockerfile fuer Playwright UI-Tests mit Browsern

# Microsoft Playwright Image mit vorinstallierten Browsern
FROM mcr.microsoft.com/playwright:v1.40.0-jammy

# Arbeitsverzeichnis setzen
WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# npm aktualisieren und Playwright installieren
RUN npm install -g npm@latest && \
    npm install -g playwright@1.40.0

# Python Playwright fuer Python-Projekte
RUN pip3 install --no-cache-dir playwright pytest pytest-playwright

# Umgebungsvariablen
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NODE_ENV=test \
    CI=true

# Projekt-Dependencies werden zur Laufzeit installiert

# Default-Befehl: Playwright-Version anzeigen
CMD ["npx", "playwright", "--version"]
