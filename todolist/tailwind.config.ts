/**
 * tailwind.config.ts
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Tailwind-Konfiguration mit custom Farben und Schriftarten
 */

import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Primärfarben gemaess Projektspezifikation
      colors: {
        primary: {
          DEFAULT: "#2b336a",
          light: "#3d4a96",
          dark: "#1a1f40",
          glow: "rgba(43, 51, 106, 0.6)",
        },
        danger: {
          DEFAULT: "#870010",
          light: "#a80014",
          dark: "#5c0009",
          glow: "rgba(135, 0, 16, 0.6)",
        },
        muted: {
          DEFAULT: "#7c7c6b",
          light: "#9a9a87",
          dark: "#5a5a4f",
        },
        // Glassmorphismus-Hintergrundsfarben
        glass: {
          dark: "#080b14",
          mid: "#0d0f20",
          deep: "#120a18",
        },
      },
      // Moderne Schriftarten
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "Fira Code", "monospace"],
      },
      // Backdrop-Filter-Utilities
      backdropBlur: {
        xs: "4px",
        "2xl": "40px",
        "3xl": "60px",
      },
      // Box-Shadow-Erweiterungen fuer Glow-Effekte
      boxShadow: {
        glow: "0 0 20px rgba(43, 51, 106, 0.6)",
        "glow-strong": "0 0 40px rgba(43, 51, 106, 0.8)",
        "glow-red": "0 0 20px rgba(135, 0, 16, 0.6)",
        "glow-green": "0 0 20px rgba(22, 163, 74, 0.6)",
        glass: "0 8px 32px rgba(0, 0, 0, 0.4)",
        "glass-strong": "0 12px 40px rgba(0, 0, 0, 0.6)",
        modal: "0 20px 60px rgba(0, 0, 0, 0.7)",
      },
      // Animationen
      animation: {
        "fade-in": "fadeIn 0.3s ease forwards",
        "glow-pulse": "pulseGlow 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 10px rgba(43, 51, 106, 0.4)" },
          "50%": { boxShadow: "0 0 25px rgba(43, 51, 106, 0.7)" },
        },
      },
    },
  },
  plugins: [],
}

export default config
