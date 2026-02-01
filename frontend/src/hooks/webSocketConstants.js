/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.1
 * Beschreibung: Konstanten fuer WebSocket-Kommunikation.
 *               Extrahiert aus useWebSocket.js (Regel 1: Max 500 Zeilen)
 *
 *               AENDERUNG 01.02.2026 v1.1: UTDS Events hinzugefuegt
 */

// Reconnection-Konfiguration
export const MAX_RECONNECT_ATTEMPTS = 10;
export const HEARTBEAT_INTERVAL = 30000;  // 30 Sekunden
export const BASE_RECONNECT_DELAY = 1000;  // 1 Sekunde
export const MAX_RECONNECT_DELAY = 30000;  // 30 Sekunden

// Events die anzeigen dass ein Agent arbeitet
export const WORKING_EVENTS = [
  'Status', 'Iteration', 'searching', 'RescanStart',
  'Analysis', 'generating', 'processing', 'testing',
  'reviewing', 'designing', 'InstallStart', 'InstallProgress',
  'Heartbeat',
  // AENDERUNG 01.02.2026: UTDS Events
  'DerivationStart', 'BatchExecutionStart'
];

// Events die anzeigen dass ein Agent fertig ist
export const COMPLETION_EVENTS = [
  'CodeOutput', 'ResearchOutput', 'DesignerOutput',
  'ReviewOutput', 'UITestResult', 'SecurityOutput',
  'SecurityRescanOutput', 'TechStackOutput', 'DBDesignerOutput',
  'InstallComplete', 'InstallError', 'InstallSkipped',
  // AENDERUNG 01.02.2026: UTDS Events
  'DerivationComplete', 'BatchExecutionComplete'
];

// Mapping von Office-Namen zu AgentData-Keys
export const OFFICE_KEY_MAP = {
  'coder': 'coder',
  'tester': 'tester',
  'designer': 'designer',
  'db_designer': 'dbdesigner',
  'security': 'security',
  'researcher': 'researcher',
  'reviewer': 'reviewer',
  'techstack_architect': 'techstack',
  // AENDERUNG 01.02.2026: UTDS
  'utds': 'utds'
};

// Berechnet den Reconnection-Delay mit Exponential Backoff + Jitter
export const getReconnectDelay = (attemptCount) => {
  const baseDelay = Math.min(
    BASE_RECONNECT_DELAY * Math.pow(2, attemptCount),
    MAX_RECONNECT_DELAY
  );
  // Jitter: +/- 20% um Thundering Herd zu vermeiden
  const jitter = baseDelay * 0.2 * (Math.random() - 0.5);
  return Math.round(baseDelay + jitter);
};
