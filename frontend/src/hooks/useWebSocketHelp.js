/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.1
 * Beschreibung: Help-Request Management fuer WebSocket HELP_NEEDED Events.
 *               Extrahiert aus useWebSocket.js (Regel 1: Max 500 Zeilen)
 *
 * AENDERUNG 02.02.2026: Eindeutige ID fuer Help-Requests
 * Date.now() durch generateHelpRequestId() ersetzt (crypto.randomUUID oder Fallback),
 * damit schnelle HELP_NEEDED-Events keine ID-Kollisionen verursachen.
 */

import { useState, useCallback } from 'react';

/**
 * Erzeugt eine eindeutige ID fuer Help-Requests.
 * Nutzt crypto.randomUUID() wenn verfuegbar, sonst Timestamp + Zufallsstring.
 * @returns {string} Eindeutige ID
 */
function generateHelpRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Hook fuer HELP_NEEDED Event Management.
 * @returns {Object} { helpRequests, handleHelpNeeded, dismissHelpRequest, clearHelpRequests }
 */
export const useWebSocketHelp = () => {
  const [helpRequests, setHelpRequests] = useState([]);

  /**
   * Handler fuer HELP_NEEDED Events.
   */
  const handleHelpNeeded = useCallback((data, setActiveAgents, setAgentData) => {
    try {
      if (data.message == null || data.message === undefined) {
        console.warn('[HELP_NEEDED] Keine message – Agent:', data.agent);
        return;
      }
      const payload = JSON.parse(data.message);
      const agentKey = data.agent?.toLowerCase().replace(/[\s-]/g, '');

      // Agent-Status auf "Blocked" setzen
      if (agentKey) {
        setActiveAgents(prev => ({
          ...prev,
          [agentKey]: {
            ...prev[agentKey],
            status: 'Blocked',
            helpNeeded: {
              reason: payload.reason,
              actionRequired: payload.action_required,
              context: payload.context,
              timestamp: new Date().toISOString()
            }
          }
        }));

        // AgentData aktualisieren mit HELP_NEEDED Info
        setAgentData(prev => ({
          ...prev,
          [agentKey]: {
            ...prev[agentKey],
            blocked: true,
            blockedReason: payload.reason,
            blockedAction: payload.action_required,
            blockedContext: payload.context
          }
        }));
      }

      // Zu globaler Help-Request Liste hinzufuegen
      setHelpRequests(prev => [...prev, {
        id: generateHelpRequestId(),
        agent: data.agent,
        reason: payload.reason,
        actionRequired: payload.action_required,
        context: payload.context || {},
        timestamp: new Date().toISOString()
      }]);

      // Browser-Notification (falls erlaubt)
      try {
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          new Notification(`${data.agent} benoetigt Hilfe`, {
            body: payload.reason,
            icon: '/favicon.ico',
            tag: 'help-needed-' + data.agent
          });
        }
      } catch (notifError) {
        console.warn('Notification fehlgeschlagen:', notifError);
      }

      console.warn('[HELP_NEEDED]', data.agent, payload.reason);
    } catch (e) {
      console.warn('HELP_NEEDED Event parsen fehlgeschlagen:', e);
    }
  }, []);

  /**
   * Entfernt einen einzelnen Help-Request.
   */
  const dismissHelpRequest = useCallback((requestId) => {
    setHelpRequests(prev => prev.filter(r => r.id !== requestId));
  }, []);

  /**
   * Loescht alle Help-Requests.
   */
  const clearHelpRequests = useCallback(() => {
    setHelpRequests([]);
  }, []);

  return {
    helpRequests,
    handleHelpNeeded,
    dismissHelpRequest,
    clearHelpRequests
  };
};

export default useWebSocketHelp;
