/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.3
 * Beschreibung: Konstanten für Discovery-Phasen und Agentenfarben.
 */
// ÄNDERUNG 29.01.2026: Discovery-Konstanten ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: ALL_AGENTS Liste für Team-Bearbeitung hinzugefügt
// ÄNDERUNG 29.01.2026 v1.2: AGENT_FEEDBACK Phase für Feedback-Schleifen
// ÄNDERUNG 29.01.2026 v1.3: DB-Designer und TechStack hinzugefügt (Sync mit Backend)

export const PHASES = {
  VISION: 'vision',
  TEAM_SETUP: 'team_setup',
  DYNAMIC_QUESTIONS: 'dynamic_questions',
  AGENT_FEEDBACK: 'agent_feedback',  // NEU: Feedback nach Agent-Runde
  GUIDED_QA: 'guided_qa',
  SUMMARY: 'summary',
  BRIEFING: 'briefing'
};

export const AGENT_COLORS = {
  Analyst: 'blue',
  'Data Researcher': 'green',
  Coder: 'yellow',
  Tester: 'purple',
  Designer: 'cyan',
  Planner: 'red',
  Security: 'orange',
  'DB-Designer': 'indigo',
  TechStack: 'teal'
};

// ÄNDERUNG 29.01.2026: Statische Tailwind-Klassen für Agent-Farben
export const AGENT_COLOR_CLASSES = {
  Analyst: 'bg-blue-400',
  'Data Researcher': 'bg-green-400',
  Coder: 'bg-yellow-400',
  Tester: 'bg-purple-400',
  Designer: 'bg-cyan-400',
  Planner: 'bg-red-400',
  Security: 'bg-orange-400',
  'DB-Designer': 'bg-indigo-400',
  TechStack: 'bg-teal-400'
};

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
