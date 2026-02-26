/**
 * Author: rahn
 * Datum: 25.02.2026
 * Version: 1.0
 * Beschreibung: Tailwind CSS Konfiguration mit Glassmorphismus-Utilities und Sora-Schriftart
 */
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Projektspezifische Primaerfarben
      colors: {
        primaer: {
          blau: '#2b336a',
          rot: '#870010',
          grau: '#7c7c6b',
          hintergrund: '#0a0b14',
        },
      },
      // Sora-Schriftart als Standard
      fontFamily: {
        sora: ['Sora', 'sans-serif'],
        sans: ['Sora', 'sans-serif'],
      },
      // Animations-Keyframes
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-out',
        slideUp: 'slideUp 0.4s ease-out',
      },
      // Hintergrundfarbe
      backgroundColor: {
        app: '#0a0b14',
      },
    },
  },
  plugins: [],
}

export default config
