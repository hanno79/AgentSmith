/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.1
 * Beschreibung: Zentrale Konfiguration - Single Source of Truth für Frontend-Konstanten
 *
 * Alle Default-Werte und Konstanten für das Frontend.
 * Diese Datei sollte die einzige Quelle für solche Werte sein.
 * AENDERUNG 10.02.2026: AGENT_CONFIG + rgb-Feld + Helper fuer zentrale Agent-Farben (Single Source of Truth)
 */

// Zentrale Default-Werte
export const DEFAULTS = {
  MAX_RETRIES: 15,
  RESEARCH_TIMEOUT_MINUTES: 5,
};

// API Base URL mit Environment-Variable Fallback
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// Farb-Definitionen für alle Komponenten
// AENDERUNG 10.02.2026: rgb-Feld fuer CSS Custom Properties hinzugefuegt
export const COLORS = {
  blue: {
    border: 'border-blue-500/40',
    text: 'text-blue-400',
    bg: 'bg-blue-500/10',
    hex: '#3b82f6',
    rgb: '59, 130, 246',
    glow: '0 0 30px rgba(59, 130, 246, 0.8), 0 0 15px rgba(59, 130, 246, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  cyan: {
    border: 'border-cyan-500/40',
    text: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    hex: '#06b6d4',
    rgb: '6, 182, 212',
    glow: '0 0 30px rgba(6, 182, 212, 0.8), 0 0 15px rgba(6, 182, 212, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  purple: {
    border: 'border-purple-500/40',
    text: 'text-purple-400',
    bg: 'bg-purple-500/10',
    hex: '#a855f7',
    rgb: '168, 85, 247',
    glow: '0 0 30px rgba(168, 85, 247, 0.8), 0 0 15px rgba(168, 85, 247, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  pink: {
    border: 'border-pink-500/40',
    text: 'text-pink-400',
    bg: 'bg-pink-500/10',
    hex: '#ec4899',
    rgb: '236, 72, 153',
    glow: '0 0 30px rgba(236, 72, 153, 0.8), 0 0 15px rgba(236, 72, 153, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  yellow: {
    border: 'border-yellow-500/40',
    text: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    hex: '#eab308',
    rgb: '234, 179, 8',
    glow: '0 0 30px rgba(234, 179, 8, 0.8), 0 0 15px rgba(234, 179, 8, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  red: {
    border: 'border-red-500/40',
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    hex: '#ef4444',
    rgb: '239, 68, 68',
    glow: '0 0 30px rgba(239, 68, 68, 0.8), 0 0 15px rgba(239, 68, 68, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  green: {
    border: 'border-green-500/40',
    text: 'text-green-400',
    bg: 'bg-green-500/10',
    hex: '#22c55e',
    rgb: '34, 197, 94',
    glow: '0 0 30px rgba(34, 197, 94, 0.8), 0 0 15px rgba(34, 197, 94, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  orange: {
    border: 'border-orange-500/40',
    text: 'text-orange-400',
    bg: 'bg-orange-500/10',
    hex: '#f97316',
    rgb: '249, 115, 22',
    glow: '0 0 30px rgba(249, 115, 22, 0.8), 0 0 15px rgba(249, 115, 22, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  indigo: {
    border: 'border-indigo-500/40',
    text: 'text-indigo-400',
    bg: 'bg-indigo-500/10',
    hex: '#4f46e5',
    rgb: '79, 70, 229',
    glow: '0 0 30px rgba(79, 70, 229, 0.8), 0 0 15px rgba(79, 70, 229, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  // AENDERUNG 07.02.2026: Amber fuer Fix-Agent (Fix 14)
  amber: {
    border: 'border-amber-500/40',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    hex: '#f59e0b',
    rgb: '245, 158, 11',
    glow: '0 0 30px rgba(245, 158, 11, 0.8), 0 0 15px rgba(245, 158, 11, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
  // ÄNDERUNG 30.01.2026: Platinum/Weiß für Documentation Manager
  platinum: {
    border: 'border-white/30',
    text: 'text-white',
    bg: 'bg-white/10',
    hex: '#ffffff',
    rgb: '255, 255, 255',
    glow: '0 0 30px rgba(255, 255, 255, 0.8), 0 0 15px rgba(255, 255, 255, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  },
};

// Fallback-Farbe wenn ungültiger color-Prop übergeben wird (z. B. in AgentCard)
export const DEFAULT_COLOR = 'blue';

// Helper-Funktion für kombinierte Farb-Klassen (nutzt DEFAULT_COLOR bei ungültigem color)
export const getColorClasses = (color) => {
  const c = COLORS[color] ?? COLORS[DEFAULT_COLOR];
  return `${c.border} ${c.text} ${c.bg}`;
};

// AENDERUNG 10.02.2026: Zentrales Agent → Farbe Mapping (Single Source of Truth)
// Um eine Agent-Farbe zu aendern: NUR hier den colorKey aendern → alles passt sich automatisch an
export const AGENT_CONFIG = {
  coder:          'blue',
  tester:         'orange',
  designer:       'pink',
  reviewer:       'yellow',
  researcher:     'cyan',
  security:       'red',
  techarchitect:  'purple',
  dbdesigner:     'green',
  documentation:  'platinum',
  planner:        'indigo',
  fix:            'khaki',
};

// Helper: Agent-Key → vollstaendiges Farb-Objekt aus COLORS
export const getAgentColor = (agentKey) => {
  const colorKey = AGENT_CONFIG[agentKey];
  return colorKey ? COLORS[colorKey] : COLORS[DEFAULT_COLOR];
};

// Helper: Agent-Key → Farb-Key-String (fuer color-Prop)
export const getAgentColorKey = (agentKey) => {
  return AGENT_CONFIG[agentKey] || DEFAULT_COLOR;
};
