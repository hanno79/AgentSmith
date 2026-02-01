/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 2.4
 * Beschreibung: Custom Hook fuer WebSocket-Verbindung zum Backend.
 *               Verarbeitet Echtzeit-Nachrichten von den Agenten.
 *               ÄNDERUNG 01.02.2026 v2.3: Refaktoriert in Module (Regel 1: Max 500 Zeilen)
 *               - webSocketConstants.js: Konstanten und Event-Arrays
 *               - webSocketEventHandlers.js: Agent-spezifische Handler
 *               - useWebSocketHelp.js: Help-Request Management
 *               AENDERUNG 01.02.2026 v2.4: UTDS Event Routing hinzugefuegt
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// Importiere extrahierte Module
import {
  MAX_RECONNECT_ATTEMPTS,
  HEARTBEAT_INTERVAL,
  WORKING_EVENTS,
  COMPLETION_EVENTS,
  getReconnectDelay
} from './webSocketConstants';

import {
  handleHeartbeat,
  handleCoderEvent,
  handleResearcherEvent,
  handleTesterEvent,
  handleTechArchitectEvent,
  handleReviewerEvent,
  handleDBDesignerEvent,
  handleSecurityEvent,
  handleDesignerEvent,
  handleWorkerStatus,
  // AENDERUNG 01.02.2026: UTDS Event Handler
  handleUTDSEvent
} from './webSocketEventHandlers';

import { useWebSocketHelp } from './useWebSocketHelp';

/**
 * WebSocket Hook fuer Echtzeit-Kommunikation mit dem Backend.
 * Unterstuetzt automatische Reconnection bei Verbindungsverlust.
 *
 * @param {Function} setLogs - Setter fuer Log-Nachrichten
 * @param {Object} activeAgents - Aktueller Status aller Agenten
 * @param {Function} setActiveAgents - Setter fuer Agenten-Status
 * @param {Function} setAgentData - Setter fuer strukturierte Agenten-Daten
 * @param {Function} setStatus - Setter fuer globalen Status
 * @returns {Object} { ws, isConnected, reconnectAttempts, helpRequests, dismissHelpRequest, clearHelpRequests }
 */
const useWebSocket = (setLogs, activeAgents, setActiveAgents, setAgentData, setStatus) => {
  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef(null);
  const heartbeatTimer = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const activeAgentsRef = useRef(activeAgents);
  const hasConnectedOnce = useRef(false);
  const wsHostRef = useRef(window.location.hostname);
  const triedHostFallbackRef = useRef(false);

  // Help-Request Management Hook
  const {
    helpRequests,
    handleHelpNeeded,
    dismissHelpRequest,
    clearHelpRequests
  } = useWebSocketHelp();

  // Sync activeAgents zu Ref
  useEffect(() => {
    activeAgentsRef.current = activeAgents;
  }, [activeAgents]);

  // Message Handler
  const handleMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);

      // Log-Array auf max 1000 Eintraege limitieren
      setLogs((prev) => {
        const newLogs = [...prev, data];
        return newLogs.length > 1000 ? newLogs.slice(-1000) : newLogs;
      });

      const agentKey = data.agent?.toLowerCase();

      // Agent-Status aktualisieren (Working/Idle)
      if (agentKey && activeAgentsRef.current[agentKey]) {
        if (WORKING_EVENTS.includes(data.event)) {
          setActiveAgents(prev => ({
            ...prev,
            [agentKey]: {
              status: 'Working',
              lastUpdate: data.message
            }
          }));
        } else if (COMPLETION_EVENTS.includes(data.event)) {
          setActiveAgents(prev => ({
            ...prev,
            [agentKey]: {
              status: 'Idle',
              lastUpdate: data.message
            }
          }));
        }
      }

      // Event-spezifische Handler aufrufen
      if (data.event === 'Heartbeat') {
        handleHeartbeat(data, setActiveAgents, setAgentData);
      }

      if ((data.event === 'CodeOutput' || data.event === 'CoderTasksOutput' ||
           data.event === 'ModelSwitch' || data.event === 'TokenMetrics') &&
          data.agent === 'Coder') {
        handleCoderEvent(data, setAgentData);
      }

      if (data.event === 'ResearchOutput' && data.agent === 'Researcher') {
        handleResearcherEvent(data, setAgentData);
      }

      if (data.event === 'UITestResult' && data.agent === 'Tester') {
        handleTesterEvent(data, setAgentData);
      }

      if (data.event === 'TechStackOutput' && data.agent === 'TechArchitect') {
        handleTechArchitectEvent(data, setAgentData);
      }

      if (data.event === 'ReviewOutput' && data.agent === 'Reviewer') {
        handleReviewerEvent(data, setAgentData);
      }

      if (data.event === 'DBDesignerOutput' && data.agent === 'DBDesigner') {
        handleDBDesignerEvent(data, setAgentData);
      }

      if ((data.event === 'SecurityOutput' || data.event === 'SecurityRescanOutput') &&
          data.agent === 'Security') {
        handleSecurityEvent(data, setAgentData);
      }

      if (data.event === 'DesignerOutput' && data.agent === 'Designer') {
        handleDesignerEvent(data, setAgentData);
      }

      if (data.event === 'WorkerStatus') {
        handleWorkerStatus(data, setAgentData);
      }

      // AENDERUNG 01.02.2026: UTDS (Universal Task Derivation System) Events
      if (data.agent === 'UTDS' && [
        'DerivationStart', 'TasksDerived', 'BatchExecutionStart',
        'BatchExecutionComplete', 'DerivationComplete'
      ].includes(data.event)) {
        handleUTDSEvent(data, setAgentData);
      }

      if (data.event === 'HELP_NEEDED') {
        handleHelpNeeded(data, setActiveAgents, setAgentData);
      }

      // Globalen Status aktualisieren
      if (data.agent === 'System' && data.event === 'Success') setStatus('Success');
      if (data.agent === 'System' && data.event === 'Failure') setStatus('Error');

      // Agent-Status zuruecksetzen bei System Completion
      if (data.agent === 'System' && (data.event === 'Success' || data.event === 'Failure')) {
        setActiveAgents(prev => {
          const reset = {};
          Object.keys(prev).forEach(key => {
            reset[key] = { status: 'Idle', lastUpdate: '' };
          });
          return reset;
        });
      }

    } catch (e) {
      console.warn('WebSocket Message parsen fehlgeschlagen:', e);
    }
  }, [setActiveAgents, setAgentData, setLogs, setStatus, handleHelpNeeded]);

  // WebSocket-Verbindung herstellen
  const connect = useCallback(() => {
    // Vorherige Verbindung bereinigen
    if (ws.current) {
      ws.current.onclose = null;
      ws.current.onerror = null;
      ws.current.onmessage = null;
      ws.current.onopen = null;
      if (ws.current.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
    }

    try {
      console.log(`[WebSocket] Verbindungsversuch ${reconnectAttempts.current + 1}...`);
      ws.current = new WebSocket(`ws://${wsHostRef.current}:8000/ws`);

      ws.current.onopen = () => {
        console.log('[WebSocket] Verbindung hergestellt');
        setIsConnected(true);
        reconnectAttempts.current = 0;

        // Heartbeat starten
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
        }
        heartbeatTimer.current = setInterval(() => {
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, HEARTBEAT_INTERVAL);

        // System-Log nur bei ERSTER Verbindung oder nach Reconnection
        if (!hasConnectedOnce.current || reconnectAttempts.current > 0) {
          setLogs(prev => [...prev, {
            agent: 'System',
            event: 'Connected',
            message: hasConnectedOnce.current
              ? 'WebSocket-Verbindung wiederhergestellt'
              : 'WebSocket-Verbindung hergestellt',
            timestamp: new Date().toISOString()
          }]);
          hasConnectedOnce.current = true;
        }
      };

      ws.current.onmessage = handleMessage;

      ws.current.onerror = (error) => {
        console.warn('[WebSocket] Fehler:', error);
        setIsConnected(false);
      };

      ws.current.onclose = (event) => {
        console.log(`[WebSocket] Verbindung geschlossen (Code: ${event.code})`);
        setIsConnected(false);

        // Heartbeat stoppen
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }

        // Host-Fallback fuer localhost
        if (
          event.code !== 1000 &&
          !triedHostFallbackRef.current &&
          wsHostRef.current === 'localhost'
        ) {
          triedHostFallbackRef.current = true;
          wsHostRef.current = '127.0.0.1';
          console.warn('[WebSocket] Fallback Host aktiviert: 127.0.0.1');
          reconnectAttempts.current = 0;
          connect();
          return;
        }

        // Reconnection mit Exponential Backoff
        if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = getReconnectDelay(reconnectAttempts.current);
          console.log(`[WebSocket] Reconnect in ${delay}ms (Versuch ${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);

          if (reconnectAttempts.current > 0) {
            setLogs(prev => [...prev, {
              agent: 'System',
              event: 'Reconnecting',
              message: `Verbindung verloren - Reconnect in ${Math.round(delay / 1000)}s...`,
              timestamp: new Date().toISOString()
            }]);
          }

          reconnectTimeout.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error('[WebSocket] Maximale Reconnection-Versuche erreicht');
          setLogs(prev => [...prev, {
            agent: 'System',
            event: 'Error',
            message: 'WebSocket-Verbindung konnte nicht wiederhergestellt werden. Bitte Seite neu laden.',
            timestamp: new Date().toISOString()
          }]);
        }
      };

    } catch (error) {
      console.error('[WebSocket] Verbindungsfehler:', error);
      setIsConnected(false);
    }
  }, [handleMessage, setLogs]);

  // Initialer Verbindungsaufbau
  useEffect(() => {
    connect();

    // Cleanup bei Unmount
    return () => {
      console.log('[WebSocket] Cleanup');
      if (heartbeatTimer.current) {
        clearInterval(heartbeatTimer.current);
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close(1000, 'Component unmounting');
      }
    };
  }, [connect]);

  return {
    ws,
    isConnected,
    reconnectAttempts: reconnectAttempts.current,
    helpRequests,
    dismissHelpRequest,
    clearHelpRequests
  };
};

export default useWebSocket;
