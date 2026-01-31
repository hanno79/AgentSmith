/**
 * Author: rahn
 * Datum: 30.01.2026
 * Version: 2.2
 * Beschreibung: Custom Hook für WebSocket-Verbindung zum Backend.
 *               Verarbeitet Echtzeit-Nachrichten von den Agenten.
 *               ÄNDERUNG 24.01.2026: DBDesignerOutput Event Handler hinzugefügt.
 *               ÄNDERUNG 24.01.2026: SecurityOutput Event Handler hinzugefügt.
 *               ÄNDERUNG 24.01.2026: SecurityRescanOutput Event Handler für Code-Scan hinzugefügt.
 *               ÄNDERUNG 25.01.2026: TokenMetrics Event Handler für Live-Metriken.
 *               ÄNDERUNG 25.01.2026: WorkerStatus Event Handler für parallele Worker-Anzeige.
 *               ÄNDERUNG 28.01.2026: Reconnection-Logik mit Exponential Backoff.
 *               ÄNDERUNG 28.01.2026: Heartbeat-Mechanismus fuer Verbindungsstabilitaet.
 *               ÄNDERUNG 29.01.2026: Host-Fallback fuer localhost -> 127.0.0.1.
 *               ÄNDERUNG 30.01.2026: HELP_NEEDED Event Handler gemäß Kommunikationsprotokoll.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * WebSocket Hook für Echtzeit-Kommunikation mit dem Backend.
 * Unterstützt automatische Reconnection bei Verbindungsverlust.
 *
 * @param {Function} setLogs - Setter für Log-Nachrichten
 * @param {Object} activeAgents - Aktueller Status aller Agenten
 * @param {Function} setActiveAgents - Setter für Agenten-Status
 * @param {Function} setAgentData - Setter für strukturierte Agenten-Daten
 * @param {Function} setStatus - Setter für globalen Status
 * @returns {Object} { ws, isConnected, reconnectAttempts }
 */
const useWebSocket = (setLogs, activeAgents, setActiveAgents, setAgentData, setStatus) => {
  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef(null);
  const heartbeatTimer = useRef(null);  // ÄNDERUNG 28.01.2026: Heartbeat-Timer
  const [isConnected, setIsConnected] = useState(false);
  // ÄNDERUNG 30.01.2026: State fuer HELP_NEEDED Events
  const [helpRequests, setHelpRequests] = useState([]);
  // ÄNDERUNG 28.01.2026: Ref für activeAgents um zirkuläre Dependencies zu vermeiden
  const activeAgentsRef = useRef(activeAgents);
  const hasConnectedOnce = useRef(false);
  // ÄNDERUNG 29.01.2026: Host-Fallback fuer stabile WS-Verbindung
  const wsHostRef = useRef(window.location.hostname);
  const triedHostFallbackRef = useRef(false);

  // ÄNDERUNG 28.01.2026: Sync-Effect für activeAgentsRef
  useEffect(() => {
    activeAgentsRef.current = activeAgents;
  }, [activeAgents]);

  // Maximale Reconnection-Versuche
  const MAX_RECONNECT_ATTEMPTS = 10;
  // ÄNDERUNG 28.01.2026: Heartbeat-Intervall (30 Sekunden)
  const HEARTBEAT_INTERVAL = 30000;
  // Basis-Delay in Millisekunden (wird exponentiell erhöht)
  const BASE_RECONNECT_DELAY = 1000;
  // Maximaler Delay in Millisekunden
  const MAX_RECONNECT_DELAY = 30000;

  // Berechnet den Reconnection-Delay mit Exponential Backoff + Jitter
  const getReconnectDelay = useCallback(() => {
    const baseDelay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
      MAX_RECONNECT_DELAY
    );
    // Jitter: +/- 20% um Thundering Herd zu vermeiden
    const jitter = baseDelay * 0.2 * (Math.random() - 0.5);
    return Math.round(baseDelay + jitter);
  }, []);

  // Message Handler (ausgelagert für Klarheit)
  const handleMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      // ÄNDERUNG 28.01.2026: Log-Array auf max 1000 Einträge limitieren (Performance)
      setLogs((prev) => {
        const newLogs = [...prev, data];
        return newLogs.length > 1000 ? newLogs.slice(-1000) : newLogs;
      });

      // Agenten-Status aktualisieren
      const agentKey = data.agent?.toLowerCase();

      // ÄNDERUNG 28.01.2026: Echte Arbeits-Events vs. Completion-Events unterscheiden
      // ÄNDERUNG 29.01.2026: Heartbeat für stabile WebSocket-Verbindung bei langen Operationen
      const workingEvents = [
        'Status', 'Iteration', 'searching', 'RescanStart',
        'Analysis', 'generating', 'processing', 'testing',
        'reviewing', 'designing', 'InstallStart', 'InstallProgress',
        'Heartbeat'
      ];

      const completionEvents = [
        'CodeOutput', 'ResearchOutput', 'DesignerOutput',
        'ReviewOutput', 'UITestResult', 'SecurityOutput',
        'SecurityRescanOutput', 'TechStackOutput', 'DBDesignerOutput',
        'InstallComplete', 'InstallError', 'InstallSkipped'
      ];

      // ÄNDERUNG 28.01.2026: Ref verwenden statt State (vermeidet zirkuläre Dependencies)
      if (agentKey && activeAgentsRef.current[agentKey]) {
        if (workingEvents.includes(data.event)) {
          // Agent arbeitet - Status auf "Working" setzen (fuer Glow-Effekt)
          setActiveAgents(prev => ({
            ...prev,
            [agentKey]: {
              status: 'Working',
              lastUpdate: data.message
            }
          }));
        } else if (completionEvents.includes(data.event)) {
          // Agent ist fertig - sofort auf Idle setzen
          setActiveAgents(prev => ({
            ...prev,
            [agentKey]: {
              status: 'Idle',
              lastUpdate: data.message
            }
          }));
        }
      }

      // ÄNDERUNG 29.01.2026: Heartbeat-Event Handler für Fortschrittsanzeige
      if (data.event === 'Heartbeat') {
        try {
          const payload = JSON.parse(data.message);
          const agentKey = data.agent?.toLowerCase();

          if (agentKey) {
            // Agent-Status auf "Working" halten mit Fortschrittsinfo
            setActiveAgents(prev => ({
              ...prev,
              [agentKey]: {
                status: 'Working',
                lastUpdate: `${payload.task} (${payload.elapsed_seconds}s)`
              }
            }));

            // Heartbeat-Daten in AgentData speichern
            setAgentData(prev => ({
              ...prev,
              [agentKey]: {
                ...prev[agentKey],
                heartbeat: {
                  elapsedSeconds: payload.elapsed_seconds,
                  heartbeatCount: payload.heartbeat_count,
                  task: payload.task
                }
              }
            }));
          }
        } catch (e) {
          console.warn('Heartbeat parsen fehlgeschlagen:', e);
        }
      }

      // Strukturierte Events für Agent Offices parsen
      if (data.event === 'CodeOutput' && data.agent === 'Coder') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            coder: {
              ...prev.coder,
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

      // ÄNDERUNG 25.01.2026: CoderTasksOutput Event für granulare Security-Tasks
      if (data.event === 'CoderTasksOutput' && data.agent === 'Coder') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            coder: {
              ...prev.coder,
              tasks: payload.tasks || [],
              taskCount: payload.count || 0
            }
          }));
        } catch (e) {
          console.warn('CoderTasksOutput parsen fehlgeschlagen:', e);
        }
      }

      // ÄNDERUNG 25.01.2026: ModelSwitch Event für Modellwechsel ("Kollegen fragen")
      if (data.event === 'ModelSwitch' && data.agent === 'Coder') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            coder: {
              ...prev.coder,
              currentModel: payload.new_model,
              previousModel: payload.old_model,
              modelsUsed: payload.models_used || [],
              modelSwitchReason: payload.reason,
              failedAttempts: payload.failed_attempts || 0
            }
          }));
        } catch (e) {
          console.warn('ModelSwitch parsen fehlgeschlagen:', e);
        }
      }

      // ResearchOutput Event für Researcher Office
      if (data.event === 'ResearchOutput' && data.agent === 'Researcher') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            researcher: {
              ...prev.researcher,
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

      // UITestResult Event für Tester Office
      if (data.event === 'UITestResult' && data.agent === 'Tester') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            tester: {
              ...prev.tester,
              defects: payload.issues || payload.defects || [],
              coverage: payload.coverage || [],
              stability: payload.stability || prev.tester.stability,
              risk: payload.risk || prev.tester.risk,
              screenshot: payload.screenshot || null,
              model: payload.model || ''
            }
          }));
        } catch (e) {
          console.warn('UITestResult parsen fehlgeschlagen:', e);
        }
      }

      // TechStackOutput Event für TechStack-Architect Office
      if (data.event === 'TechStackOutput' && data.agent === 'TechArchitect') {
        try {
          const payload = JSON.parse(data.message);
          const blueprint = payload.blueprint || {};
          setAgentData(prev => ({
            ...prev,
            techstack: {
              ...prev.techstack,
              blueprint: blueprint,
              model: payload.model || '',
              decisions: payload.decisions || [],
              dependencies: blueprint.dependencies || payload.dependencies || [],
              reasoning: blueprint.reasoning || '',
              timestamp: data.timestamp
            }
          }));
        } catch (e) {
          console.warn('TechStackOutput parsen fehlgeschlagen:', e);
        }
      }

      // ReviewOutput Event für Reviewer Office
      if (data.event === 'ReviewOutput' && data.agent === 'Reviewer') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            reviewer: {
              ...prev.reviewer,
              verdict: payload.verdict || '',
              isApproved: payload.isApproved || false,
              humanSummary: payload.humanSummary || '',
              feedback: payload.feedback || '',
              model: payload.model || '',
              iteration: payload.iteration || 0,
              maxIterations: payload.maxIterations || 3,
              sandboxStatus: payload.sandboxStatus || '',
              sandboxResult: payload.sandboxResult || '',
              testSummary: payload.testSummary || '',
              reviewOutput: payload.reviewOutput || ''
            }
          }));
        } catch (e) {
          console.warn('ReviewOutput parsen fehlgeschlagen:', e);
        }
      }

      // DBDesignerOutput Event für DB Designer Office
      if (data.event === 'DBDesignerOutput' && data.agent === 'DBDesigner') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            dbdesigner: {
              ...prev.dbdesigner,
              schema: payload.schema || '',
              model: payload.model || '',
              status: payload.status || '',
              tables: payload.tables || [],
              timestamp: payload.timestamp || ''
            }
          }));
        } catch (e) {
          console.warn('DBDesignerOutput parsen fehlgeschlagen:', e);
        }
      }

      // SecurityOutput Event für Security Office (Initial-Scan)
      if (data.event === 'SecurityOutput' && data.agent === 'Security') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            security: {
              ...prev.security,
              vulnerabilities: payload.vulnerabilities || [],
              overallStatus: payload.overall_status || '',
              scanResult: payload.scan_result || '',
              model: payload.model || '',
              scannedFiles: payload.scanned_files || 0,
              scanType: 'requirement_scan',
              blocking: false,
              iteration: 0,
              timestamp: payload.timestamp || ''
            }
          }));
        } catch (e) {
          console.warn('SecurityOutput parsen fehlgeschlagen:', e);
        }
      }

      // SecurityRescanOutput Event für Security Office (Code-Scan)
      if (data.event === 'SecurityRescanOutput' && data.agent === 'Security') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            security: {
              ...prev.security,
              vulnerabilities: payload.vulnerabilities || [],
              overallStatus: payload.overall_status || '',
              scanType: payload.scan_type || 'code_scan',
              iteration: payload.iteration || 0,
              blocking: payload.blocking || false,
              model: payload.model || '',
              timestamp: payload.timestamp || ''
            }
          }));
        } catch (e) {
          console.warn('SecurityRescanOutput parsen fehlgeschlagen:', e);
        }
      }

      // ÄNDERUNG 30.01.2026: HELP_NEEDED Event Handler gemäß Kommunikationsprotokoll
      if (data.event === 'HELP_NEEDED') {
        try {
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
            id: Date.now(),
            agent: data.agent,
            reason: payload.reason,
            actionRequired: payload.action_required,
            context: payload.context || {},
            timestamp: new Date().toISOString()
          }]);

          // Browser-Notification (falls erlaubt)
          if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification(`${data.agent} benötigt Hilfe`, {
              body: payload.reason,
              icon: '/favicon.ico',
              tag: 'help-needed-' + data.agent
            });
          }

          console.warn('[HELP_NEEDED]', data.agent, payload.reason);
        } catch (e) {
          console.warn('HELP_NEEDED Event parsen fehlgeschlagen:', e);
        }
      }

      // DesignerOutput Event für Designer Office
      if (data.event === 'DesignerOutput' && data.agent === 'Designer') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            designer: {
              ...prev.designer,
              colorPalette: payload.colorPalette || [],
              typography: payload.typography || [],
              atomicAssets: payload.atomicAssets || [],
              qualityScore: payload.qualityScore || null,
              iterationInfo: payload.iterationInfo || null,
              viewport: payload.viewport || null,
              previewUrl: payload.previewUrl || '',
              concept: payload.concept || '',
              model: payload.model || '',
              timestamp: payload.timestamp || ''
            }
          }));
        } catch (e) {
          console.warn('DesignerOutput parsen fehlgeschlagen:', e);
        }
      }

      // TokenMetrics Event für Live-Metriken im CoderOffice
      if (data.event === 'TokenMetrics') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            coder: {
              ...prev.coder,
              totalTokens: payload.total_tokens || 0,
              totalCost: payload.total_cost || 0
            }
          }));
        } catch (e) {
          console.warn('TokenMetrics parsen fehlgeschlagen:', e);
        }
      }

      // WorkerStatus Event für parallele Worker-Anzeige
      if (data.event === 'WorkerStatus') {
        try {
          const payload = JSON.parse(data.message);
          const office = payload.office;

          const officeKeyMap = {
            'coder': 'coder',
            'tester': 'tester',
            'designer': 'designer',
            'db_designer': 'dbdesigner',
            'security': 'security',
            'researcher': 'researcher',
            'reviewer': 'reviewer',
            'techstack_architect': 'techstack'
          };

          const agentKey = officeKeyMap[office];
          if (agentKey) {
            setAgentData(prev => ({
              ...prev,
              [agentKey]: {
                ...prev[agentKey],
                workers: payload.pool_status?.workers || [],
                activeWorkers: payload.pool_status?.active_workers || 0,
                totalWorkers: payload.pool_status?.total_workers || 0,
                queueSize: payload.pool_status?.queue_size || 0
              }
            }));
          }
        } catch (e) {
          console.warn('WorkerStatus parsen fehlgeschlagen:', e);
        }
      }

      // Globalen Status aktualisieren
      if (data.agent === 'System' && data.event === 'Success') setStatus('Success');
      if (data.agent === 'System' && data.event === 'Failure') setStatus('Error');

      // ÄNDERUNG 28.01.2026: Agent-Status auf "Idle" zurücksetzen bei System Completion
      if (data.agent === 'System' && (data.event === 'Success' || data.event === 'Failure')) {
        setActiveAgents(prev => {
          const reset = {};
          Object.keys(prev).forEach(key => {
            reset[key] = { status: 'Idle', lastUpdate: '' };
          });
          return reset;
        });
      }

      // HINWEIS: Einzelne Agent-Completion wird jetzt oben behandelt (workingEvents/completionEvents)

    } catch (e) {
      console.warn('WebSocket Message parsen fehlgeschlagen:', e);
    }
  // ÄNDERUNG 28.01.2026: activeAgents aus Dependencies entfernt (verwende Ref stattdessen)
  }, [setActiveAgents, setAgentData, setLogs, setStatus]);

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

        // ÄNDERUNG 28.01.2026: Heartbeat starten fuer Keep-Alive
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
        }
        heartbeatTimer.current = setInterval(() => {
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, HEARTBEAT_INTERVAL);

        // ÄNDERUNG 28.01.2026: System-Log nur bei ERSTER Verbindung oder nach Reconnection
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

        // ÄNDERUNG 28.01.2026: Heartbeat stoppen bei Verbindungsverlust
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }

        // ÄNDERUNG 29.01.2026: Host-Fallback fuer localhost falls Verbindung fehlschlaegt
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

        // Nur reconnecten wenn nicht absichtlich geschlossen
        if (event.code !== 1000 && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = getReconnectDelay();
          console.log(`[WebSocket] Reconnect in ${delay}ms (Versuch ${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);

          // Reconnection Log (nur wenn nicht sofort beim Start)
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
  }, [handleMessage, getReconnectDelay, setLogs]);

  // Initialer Verbindungsaufbau
  useEffect(() => {
    connect();

    // Cleanup bei Unmount
    return () => {
      console.log('[WebSocket] Cleanup');
      // ÄNDERUNG 28.01.2026: Heartbeat-Timer bereinigen
      if (heartbeatTimer.current) {
        clearInterval(heartbeatTimer.current);
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (ws.current) {
        ws.current.onclose = null; // Verhindert Reconnection bei Cleanup
        ws.current.close(1000, 'Component unmounting');
      }
    };
  }, [connect]);

  // ÄNDERUNG 30.01.2026: Funktion zum Entfernen eines HELP_NEEDED Requests
  const dismissHelpRequest = useCallback((requestId) => {
    setHelpRequests(prev => prev.filter(r => r.id !== requestId));
  }, []);

  // ÄNDERUNG 30.01.2026: Alle Help-Requests leeren
  const clearHelpRequests = useCallback(() => {
    setHelpRequests([]);
  }, []);

  return {
    ws,
    isConnected,
    reconnectAttempts: reconnectAttempts.current,
    // ÄNDERUNG 30.01.2026: HELP_NEEDED Support
    helpRequests,
    dismissHelpRequest,
    clearHelpRequests
  };
};

export default useWebSocket;
