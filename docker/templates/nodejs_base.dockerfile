# -*- coding: utf-8 -*-
# Author: rahn
# Datum: 31.01.2026
# Version: 1.0
# Beschreibung: Basis-Dockerfile fuer Node.js-Projekte (Express, React, Vue)

FROM node:20-alpine

# Arbeitsverzeichnis setzen
WORKDIR /app

# System-Dependencies (fuer native npm Module)
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    sqlite \
    curl

# npm aktualisieren
RUN npm install -g npm@latest

# Umgebungsvariablen
ENV NODE_ENV=development \
    NPM_CONFIG_LOGLEVEL=warn \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

# Standard-Ports fuer Web-Apps (Express: 3000, Vite: 5173)
EXPOSE 3000 5173

# Projekt-Dependencies werden zur Laufzeit installiert via:
# docker run -v ./project:/app nodejs-base npm install

# Healthcheck fuer Web-Apps
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || curl -f http://localhost:5173/ || exit 1

# Default-Befehl: Node-Version anzeigen
CMD ["node", "--version"]
