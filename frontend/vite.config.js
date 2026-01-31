/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.1
 * Beschreibung: Vite-Konfiguration für das Frontend.
 * # ÄNDERUNG [31.01.2026]: Vitest-Konfiguration ergänzt.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  test: {
    environment: 'jsdom',
  },
})
