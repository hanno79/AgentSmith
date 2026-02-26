/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Next.js Konfiguration mit Webpack-Einstellungen fuer better-sqlite3
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Webpack fuer better-sqlite3 serverseitig konfigurieren
  webpack: (config, { isServer }) => {
    if (isServer) {
      // better-sqlite3 als externe Abhaengigkeit behandeln (native Node.js Modul)
      config.externals = [...(config.externals || []), 'better-sqlite3'];
    }
    return config;
  },
};

export default nextConfig;
