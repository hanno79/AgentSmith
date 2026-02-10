/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.4
 * Beschreibung: Konstanten für Discovery-Phasen und Agentenfarben.
 */
// ÄNDERUNG 29.01.2026: Discovery-Konstanten ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: ALL_AGENTS Liste für Team-Bearbeitung hinzugefügt
// ÄNDERUNG 29.01.2026 v1.2: AGENT_FEEDBACK Phase für Feedback-Schleifen
// ÄNDERUNG 29.01.2026 v1.3: DB-Designer und TechStack hinzugefügt (Sync mit Backend)
// AENDERUNG 10.02.2026 v1.4: Farben aus config.js AGENT_CONFIG ableiten (Single Source of Truth)

import { AGENT_CONFIG } from './config';

export const PHASES = {
  VISION: 'vision',
  TEAM_SETUP: 'team_setup',
  DYNAMIC_QUESTIONS: 'dynamic_questions',
  AGENT_FEEDBACK: 'agent_feedback',  // NEU: Feedback nach Agent-Runde
  GUIDED_QA: 'guided_qa',
  SUMMARY: 'summary',
  BRIEFING: 'briefing'
};

// Discovery Agent-Name → config.js Agent-Key Mapping
const DISCOVERY_TO_CONFIG = {
  Analyst:           'researcher',
  'Data Researcher': 'researcher',
  Coder:             'coder',
  Tester:            'tester',
  Designer:          'designer',
  Planner:           'planner',
  Security:          'security',
  'DB-Designer':     'dbdesigner',
  TechStack:         'techarchitect',
};

// AENDERUNG 10.02.2026: Farb-Keys aus AGENT_CONFIG ableiten
export const AGENT_COLORS = Object.fromEntries(
  Object.entries(DISCOVERY_TO_CONFIG).map(([name, key]) => [name, AGENT_CONFIG[key]])
);

// Statische BG-Klassen (Tailwind braucht vollstaendige Klassennamen fuer Purge)
const BG_CLASS_MAP = {
  blue: 'bg-blue-400',
  cyan: 'bg-cyan-400',
  purple: 'bg-purple-400',
  pink: 'bg-pink-400',
  yellow: 'bg-yellow-400',
  red: 'bg-red-400',
  green: 'bg-green-400',
  orange: 'bg-orange-400',
  indigo: 'bg-indigo-400',
  amber: 'bg-amber-400',
  platinum: 'bg-white',
};

export const AGENT_COLOR_CLASSES = Object.fromEntries(
  Object.entries(AGENT_COLORS).map(([name, colorKey]) => [name, BG_CLASS_MAP[colorKey] || 'bg-gray-400'])
);

// ÄNDERUNG 29.01.2026 v1.3: Alle verfügbaren Agenten synchronisiert mit Backend
export const ALL_AGENTS = [
  { id: 'Analyst', name: 'Analyst', description: 'Analysiert Anforderungen und Geschäftsprozesse' },
  { id: 'Coder', name: 'Coder', description: 'Implementiert die technische Lösung' },
  { id: 'Designer', name: 'Designer', description: 'Gestaltet UI/UX und visuelle Elemente' },
  { id: 'DB-Designer', name: 'DB-Designer', description: 'Plant Datenbankstruktur und Schema' },
  { id: 'Tester', name: 'Tester', description: 'Prüft Qualität und Funktionalität' },
  { id: 'Data Researcher', name: 'Data Researcher', description: 'Recherchiert externe Datenquellen' },
  { id: 'TechStack', name: 'TechStack', description: 'Berät bei Technologie-Auswahl' },
  { id: 'Planner', name: 'Planner', description: 'Plant Zeitrahmen und Meilensteine' },
  { id: 'Security', name: 'Security', description: 'Prüft Sicherheitsaspekte' }
];
