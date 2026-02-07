/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Konstanten für External Bureau UI.
 *               Extrahiert aus ExternalBureauOffice.jsx (Regel 1: Max 500 Zeilen)
 */

// Matrix-Design Farben
export const MATRIX_GREEN = '#0df259';
export const MATRIX_GREEN_DIM = 'rgba(13, 242, 89, 0.5)';
export const MATRIX_BG = '#0a0a0a';
export const MATRIX_BG_LIGHT = '#111';
export const MATRIX_BORDER = 'rgba(13, 242, 89, 0.3)';

// Status-Farben
export const STATUS_COLORS = {
  'DORMANT': '#555',
  'READY': MATRIX_GREEN,
  'COMPILING': '#ffcc00',
  'ERROR': '#ff3333',
  'RATE_LIMITED': '#ff9900'
};

// Kategorie-Icons
export const CATEGORY_ICONS = {
  'combat': 'shield',
  'intelligence': 'search',
  'creative': 'palette'
};

// Severity-Farben für Findings
export const SEVERITY_COLORS = {
  'CRITICAL': '#ff0000',
  'HIGH': '#ff6600',
  'MEDIUM': '#ffcc00',
  'LOW': '#00ccff',
  'INFO': '#888'
};

// API Base URL – aus Umgebungsvariable, Fallback nur für Entwicklung
// AENDERUNG 02.02.2026: Vite verwendet import.meta.env statt process.env
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
