/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Custom Hook für WebSocket-Verbindung zum Backend.
 *               Verarbeitet Echtzeit-Nachrichten von den Agenten.
 */

import { useEffect, useRef } from 'react';

/**
 * WebSocket Hook für Echtzeit-Kommunikation mit dem Backend.
 *
 * @param {Function} setLogs - Setter für Log-Nachrichten
 * @param {Object} activeAgents - Aktueller Status aller Agenten
 * @param {Function} setActiveAgents - Setter für Agenten-Status
 * @param {Function} setAgentData - Setter für strukturierte Agenten-Daten
 * @param {Function} setStatus - Setter für globalen Status
 * @returns {Object} WebSocket-Referenz
 */
const useWebSocket = (setLogs, activeAgents, setActiveAgents, setAgentData, setStatus) => {
  const ws = useRef(null);

  useEffect(() => {
    // WebSocket Setup
    ws.current = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs((prev) => [...prev, data]);

      // Agenten-Status aktualisieren
      const agentKey = data.agent.toLowerCase();
      if (activeAgents[agentKey]) {
        setActiveAgents(prev => ({
          ...prev,
          [agentKey]: {
            status: data.event,
            lastUpdate: data.message
          }
        }));
      }

      // Strukturierte Events für Agent Offices parsen
      if (data.event === 'CodeOutput' && data.agent === 'Coder') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            coder: {
              code: payload.code || '',
              files: payload.files || [],
              iteration: payload.iteration || 0,
              maxIterations: payload.max_iterations || 3,
              model: payload.model || ''
            }
          }));
        } catch (e) {
          console.warn('CodeOutput parsen fehlgeschlagen:', e);
        }
      }

      // ResearchOutput Event für Researcher Office
      if (data.event === 'ResearchOutput' && data.agent === 'Researcher') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            researcher: {
              query: payload.query || '',
              result: payload.result || '',
              status: payload.status || '',
              model: payload.model || '',
              error: payload.error || ''
            }
          }));
        } catch (e) {
          console.warn('ResearchOutput parsen fehlgeschlagen:', e);
        }
      }

      // Globalen Status aktualisieren
      if (data.agent === 'System' && data.event === 'Success') setStatus('Success');
      if (data.agent === 'System' && data.event === 'Failure') setStatus('Error');
    };

    return () => ws.current?.close();
  }, []);

  return ws;
};

export default useWebSocket;
