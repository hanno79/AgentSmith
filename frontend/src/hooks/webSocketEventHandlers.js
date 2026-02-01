/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Event-Handler fuer WebSocket-Nachrichten.
 *               Extrahiert aus useWebSocket.js (Regel 1: Max 500 Zeilen)
 */

import { OFFICE_KEY_MAP } from './webSocketConstants';

/**
 * Handler fuer Heartbeat Events.
 */
export const handleHeartbeat = (data, setActiveAgents, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);
    const agentKey = data.agent?.toLowerCase();

    if (agentKey) {
      setActiveAgents(prev => ({
        ...prev,
        [agentKey]: {
          status: 'Working',
          lastUpdate: `${payload.task} (${payload.elapsed_seconds}s)`
        }
      }));

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
};

/**
 * Handler fuer Coder Events (CodeOutput, CoderTasksOutput, ModelSwitch).
 */
export const handleCoderEvent = (data, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);

    if (data.event === 'CodeOutput') {
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
    } else if (data.event === 'CoderTasksOutput') {
      setAgentData(prev => ({
        ...prev,
        coder: {
          ...prev.coder,
          tasks: payload.tasks || [],
          taskCount: payload.count || 0
        }
      }));
    } else if (data.event === 'ModelSwitch') {
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
    } else if (data.event === 'TokenMetrics') {
      setAgentData(prev => ({
        ...prev,
        coder: {
          ...prev.coder,
          totalTokens: payload.total_tokens || 0,
          totalCost: payload.total_cost || 0
        }
      }));
    }
  } catch (e) {
    console.warn(`${data.event} parsen fehlgeschlagen:`, e);
  }
};

/**
 * Handler fuer Researcher Events.
 */
export const handleResearcherEvent = (data, setAgentData) => {
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
};

/**
 * Handler fuer Tester Events.
 */
export const handleTesterEvent = (data, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);
    setAgentData(prev => ({
      ...prev,
      tester: {
        ...prev.tester,
        defects: payload.issues || payload.defects || [],
        coverage: payload.coverage || [],
        stability: payload.stability || prev.tester?.stability,
        risk: payload.risk || prev.tester?.risk,
        screenshot: payload.screenshot || null,
        model: payload.model || ''
      }
    }));
  } catch (e) {
    console.warn('UITestResult parsen fehlgeschlagen:', e);
  }
};

/**
 * Handler fuer TechStack-Architect Events.
 */
export const handleTechArchitectEvent = (data, setAgentData) => {
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
};

/**
 * Handler fuer Reviewer Events.
 */
export const handleReviewerEvent = (data, setAgentData) => {
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
};

/**
 * Handler fuer DB Designer Events.
 */
export const handleDBDesignerEvent = (data, setAgentData) => {
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
};

/**
 * Handler fuer Security Events (Initial-Scan und Code-Scan).
 */
export const handleSecurityEvent = (data, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);

    if (data.event === 'SecurityOutput') {
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
    } else if (data.event === 'SecurityRescanOutput') {
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
    }
  } catch (e) {
    console.warn(`${data.event} parsen fehlgeschlagen:`, e);
  }
};

/**
 * Handler fuer Designer Events.
 */
export const handleDesignerEvent = (data, setAgentData) => {
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
};

/**
 * Handler fuer Worker Status Events.
 */
export const handleWorkerStatus = (data, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);
    const office = payload.office;
    const agentKey = OFFICE_KEY_MAP[office];

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
};

/**
 * AENDERUNG 01.02.2026: Handler fuer UTDS (Universal Task Derivation System) Events.
 */
export const handleUTDSEvent = (data, setAgentData) => {
  try {
    const payload = JSON.parse(data.message);

    switch(data.event) {
      case 'DerivationStart':
        setAgentData(prev => ({
          ...prev,
          utds: {
            status: 'deriving',
            source: payload.source,
            feedbackLength: payload.feedback_length,
            startTime: new Date().toISOString()
          }
        }));
        break;

      case 'TasksDerived':
        setAgentData(prev => ({
          ...prev,
          utds: {
            ...prev.utds,
            status: 'executing',
            totalTasks: payload.total,
            byCategory: payload.by_category,
            byPriority: payload.by_priority,
            byAgent: payload.by_agent,
            derivationTime: payload.derivation_time
          }
        }));
        break;

      case 'BatchExecutionStart':
        setAgentData(prev => ({
          ...prev,
          utds: {
            ...prev.utds,
            currentBatch: {
              id: payload.batch_id,
              number: payload.batch_number,
              total: payload.total_batches,
              taskCount: payload.task_count
            }
          }
        }));
        break;

      case 'BatchExecutionComplete':
        setAgentData(prev => ({
          ...prev,
          utds: {
            ...prev.utds,
            lastBatch: {
              id: payload.batch_id,
              success: payload.success,
              completed: payload.completed,
              failed: payload.failed,
              executionTime: payload.execution_time
            }
          }
        }));
        break;

      case 'DerivationComplete':
        setAgentData(prev => ({
          ...prev,
          utds: {
            ...prev.utds,
            status: payload.success ? 'complete' : 'partial',
            completedTasks: payload.completed_tasks,
            failedTasks: payload.failed_tasks,
            modifiedFiles: payload.modified_files,
            endTime: new Date().toISOString()
          }
        }));
        break;

      default:
        // Unbekannte UTDS Events als allgemeine Info speichern
        setAgentData(prev => ({
          ...prev,
          utds: {
            ...prev.utds,
            lastEvent: { event: data.event, payload, timestamp: new Date().toISOString() }
          }
        }));
    }
  } catch (e) {
    console.warn('UTDS Event parsen fehlgeschlagen:', e);
  }
};
