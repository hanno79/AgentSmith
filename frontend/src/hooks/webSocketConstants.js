/**
 * Author: rahn
 * Datum: 03.02.2026
 * Version: 1.2
 * Beschreibung: Konstanten fuer WebSocket-Kommunikation.
 *               Extrahiert aus useWebSocket.js (Regel 1: Max 500 Zeilen)
 *
 *               AENDERUNG 01.02.2026 v1.1: UTDS Events hinzugefuegt
 *               AENDERUNG 03.02.2026 v1.2: AGENT_TO_DATA_KEY Mapping fuer Worker-Status-Reset
 */

// Reconnection-Konfiguration
// ÄNDERUNG 22.02.2026: Fix 63d — Höhere Reconnect-Limits nach Docker-Migration
// Ursache: Backend wird bei Deployments mehrfach neu gestartet → Frontend erschoepfte
//             10 Versuche → gab auf ohne je wieder zu verbinden (ohne Browser-Reload)
// Loesung: 50 Versuche + 60s Max-Delay + Reset-statt-Aufgeben in useWebSocket.js
export const MAX_RECONNECT_ATTEMPTS = 50;
export const HEARTBEAT_INTERVAL = 30000;  // 30 Sekunden
export const BASE_RECONNECT_DELAY = 1000;  // 1 Sekunde
export const MAX_RECONNECT_DELAY = 60000;  // 60 Sekunden (war 30s)

// Events die anzeigen dass ein Agent arbeitet
// AENDERUNG 02.02.2026: 'Heartbeat' ENTFERNT - Heartbeats duerfen Status nicht aendern
// Heartbeats sind nur fuer Fortschritts-Informationen, nicht fuer Status-Aenderungen
export const WORKING_EVENTS = [
  'Status', 'Iteration', 'searching', 'RescanStart',
  'Analysis', 'generating', 'processing', 'testing',
  'reviewing', 'designing', 'InstallStart', 'InstallProgress',
  // AENDERUNG 01.02.2026: UTDS Events
  'DerivationStart', 'BatchExecutionStart',
  // AENDERUNG 07.02.2026: Fix-Agent Events (Fix 14)
  'FixStart'
];

// Events die anzeigen dass ein Agent fertig ist
export const COMPLETION_EVENTS = [
  'CodeOutput', 'ResearchOutput', 'DesignerOutput',
  'ReviewOutput', 'UITestResult', 'SecurityOutput',
  'SecurityRescanOutput', 'TechStackOutput', 'DBDesignerOutput',
  'InstallComplete', 'InstallError', 'InstallSkipped',
  // AENDERUNG 01.02.2026: UTDS Events
  'DerivationComplete', 'BatchExecutionComplete',
  // AENDERUNG 03.02.2026: Planner Event hinzugefuegt
  'PlannerOutput',
  // AENDERUNG 07.02.2026: Fix-Agent Events (Fix 14)
  'FixOutput'
];

// Mapping von Office-Namen zu AgentData-Keys
// AENDERUNG 02.02.2026: Planner Office hinzugefuegt
export const OFFICE_KEY_MAP = {
  'coder': 'coder',
  'tester': 'tester',
  'designer': 'designer',
  'db_designer': 'dbdesigner',
  'security': 'security',
  'researcher': 'researcher',
  'reviewer': 'reviewer',
  'techstack_architect': 'techstack',
  'planner': 'planner',
  // AENDERUNG 01.02.2026: UTDS
  'utds': 'utds',
  // AENDERUNG 07.02.2026: Fix-Agent Office (Fix 14)
  'fix': 'fix'
};

// AENDERUNG 03.02.2026: Mapping von Agent-Namen (lowercase) zu agentData Keys
// Verwendet fuer Worker-Status-Reset bei COMPLETION_EVENTS
// Bug Fix: Glow-Effekt stoppt nicht wenn Agent fertig ist
export const AGENT_TO_DATA_KEY = {
  'coder': 'coder',
  'tester': 'tester',
  'designer': 'designer',
  'reviewer': 'reviewer',
  'researcher': 'researcher',
  'security': 'security',
  'techarchitect': 'techstack',
  'dbdesigner': 'dbdesigner',
  'documentationmanager': 'documentationmanager',
  'planner': 'planner',
  'orchestrator': 'orchestrator',
  // AENDERUNG 07.02.2026: Fix-Agent (Fix 14)
  'fix': 'fix'
};

// Berechnet den Reconnection-Delay mit Exponential Backoff + Jitter
export const getReconnectDelay = (attemptCount) => {
  const baseDelay = Math.min(
    BASE_RECONNECT_DELAY * Math.pow(2, attemptCount),
    MAX_RECONNECT_DELAY
  );
  // Jitter: +/- 20% um Thundering Herd zu vermeiden
  const jitter = baseDelay * 0.4 * (Math.random() - 0.5);
  return Math.round(baseDelay + jitter);
};
