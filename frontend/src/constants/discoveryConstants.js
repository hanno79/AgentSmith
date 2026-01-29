/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.2
 * Beschreibung: Konstanten für Discovery-Phasen und Agentenfarben.
 */
// ÄNDERUNG 29.01.2026: Discovery-Konstanten ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: ALL_AGENTS Liste für Team-Bearbeitung hinzugefügt
// ÄNDERUNG 29.01.2026 v1.2: AGENT_FEEDBACK Phase für Feedback-Schleifen

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
  Security: 'orange'
};

// ÄNDERUNG 29.01.2026: Alle verfügbaren Agenten für Team-Bearbeitung
export const ALL_AGENTS = [
  { id: 'Analyst', name: 'Analyst', description: 'Analysiert Anforderungen und Geschäftsprozesse' },
  { id: 'Data Researcher', name: 'Data Researcher', description: 'Recherchiert Datenquellen und -strukturen' },
  { id: 'Coder', name: 'Coder', description: 'Implementiert die technische Lösung' },
  { id: 'Tester', name: 'Tester', description: 'Prüft Qualität und Funktionalität' },
  { id: 'Designer', name: 'Designer', description: 'Gestaltet UI/UX und visuelle Elemente' },
  { id: 'Planner', name: 'Planner', description: 'Plant Zeitrahmen und Meilensteine' },
  { id: 'Security', name: 'Security', description: 'Prüft Sicherheitsaspekte' }
];
