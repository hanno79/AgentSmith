/**
 * next.config.mjs
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Next.js Konfiguration fuer better-sqlite3
 */

const nextConfig = {
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals.push("better-sqlite3")
    }
    return config
  },
}

export default nextConfig