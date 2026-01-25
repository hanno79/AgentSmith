/**
 * Author: rahn
 * Datum: 25.01.2026
 * Version: 1.5
 * Beschreibung: Custom Hook für WebSocket-Verbindung zum Backend.
 *               Verarbeitet Echtzeit-Nachrichten von den Agenten.
 *               ÄNDERUNG 24.01.2026: DBDesignerOutput Event Handler hinzugefügt.
 *               ÄNDERUNG 24.01.2026: SecurityOutput Event Handler hinzugefügt.
 *               ÄNDERUNG 24.01.2026: SecurityRescanOutput Event Handler für Code-Scan hinzugefügt.
 *               ÄNDERUNG 25.01.2026: TokenMetrics Event Handler für Live-Metriken.
 *               ÄNDERUNG 25.01.2026: WorkerStatus Event Handler für parallele Worker-Anzeige.
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
          setAgentData(prev => ({
            ...prev,
            techstack: {
              blueprint: payload.blueprint || {},
              model: payload.model || '',
              decisions: payload.decisions || [],
              dependencies: payload.dependencies || [],
              reasoning: payload.reasoning || '',
              timestamp: data.timestamp
            }
          }));
        } catch (e) {
          console.warn('TechStackOutput parsen fehlgeschlagen:', e);
        }
      }

      // ÄNDERUNG 24.01.2026: ReviewOutput Event für Reviewer Office (erweitert mit humanSummary)
      if (data.event === 'ReviewOutput' && data.agent === 'Reviewer') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            reviewer: {
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

      // ÄNDERUNG 24.01.2026: DBDesignerOutput Event für DB Designer Office
      if (data.event === 'DBDesignerOutput' && data.agent === 'DBDesigner') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            dbdesigner: {
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

      // ÄNDERUNG 24.01.2026: SecurityOutput Event für Security Office (Initial-Scan)
      if (data.event === 'SecurityOutput' && data.agent === 'Security') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            security: {
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

      // ÄNDERUNG 24.01.2026: SecurityRescanOutput Event für Security Office (Code-Scan)
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

      // ÄNDERUNG 24.01.2026: DesignerOutput Event für Designer Office
      if (data.event === 'DesignerOutput' && data.agent === 'Designer') {
        try {
          const payload = JSON.parse(data.message);
          setAgentData(prev => ({
            ...prev,
            designer: {
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

      // ÄNDERUNG 25.01.2026: TokenMetrics Event für Live-Metriken im CoderOffice
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

      // ÄNDERUNG 25.01.2026: WorkerStatus Event für parallele Worker-Anzeige
      if (data.event === 'WorkerStatus') {
        try {
          const payload = JSON.parse(data.message);
          const office = payload.office;

          // Mapping von Office-Namen zu agentData Keys
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
    };

    return () => ws.current?.close();
  }, []);

  return ws;
};

export default useWebSocket;
