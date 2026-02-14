/**
 * Author: rahn
 * Datum: 30.01.2026
 * Version: 1.12
 * Beschreibung: App Hauptkomponente - Zentrale UI mit WebSocket-Verbindung und Agenten-Steuerung.
 *               Refaktoriert: WebSocket, Config, AgentCard und NavigationHeader extrahiert.
 *               ÄNDERUNG 25.01.2026: Token-Metriken Props für CoderOffice hinzugefügt.
 *               ÄNDERUNG 25.01.2026: Worker-Daten werden an AgentCard Komponenten weitergegeben.
 *               ÄNDERUNG 25.01.2026: Toggle USER/DEBUG im Global Output Loop mit formatierter Ausgabe.
 *               ÄNDERUNG 25.01.2026: Einheitliche Lucide-Icons mit Farbcodierung im Global Output Loop.
 *               ÄNDERUNG 28.01.2026: LibraryOffice für Protokoll und Archiv hinzugefügt.
 *               ÄNDERUNG 28.01.2026: Session-Persistenz - State-Recovery nach Browser-Refresh.
 *               ÄNDERUNG 29.01.2026: Discovery Briefing an Backend senden für Agent-Kontext.
 *               # ÄNDERUNG [30.01.2026]: HelpPanel für HELP_NEEDED Events — Anpassung gemäß Kommunikationsprotokoll.
 *               # ÄNDERUNG [31.01.2026]: Mission Control, Right Panel und Agent Routing ausgelagert.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

import MainframeHub from './MainframeHub';
import BudgetDashboard from './BudgetDashboard';
import NavigationHeader from './components/NavigationHeader';
import HelpPanel from './components/HelpPanel';
import MissionControl from './components/MissionControl';
import RightPanel from './components/RightPanel';
import AgentRouter, { isAgentRoute } from './components/AgentRouter';
// AENDERUNG 13.02.2026: Kanban-Board Import
import KanbanBoard from './components/KanbanBoard';
// AENDERUNG 14.02.2026: Celebration-Overlay bei Projekt-Erfolg
import CelebrationOverlay from './components/CelebrationOverlay';
// AENDERUNG 14.02.2026: Toast-Benachrichtigungen fuer Agent-Events
import ToastContainer from './components/ToastContainer';
import useWebSocket from './hooks/useWebSocket';
import useConfig from './hooks/useConfig';
import { API_BASE, COLORS } from './constants/config';

// AENDERUNG 10.02.2026: CSS Custom Properties aus COLORS generieren (fuer Scrollbar-Farben)
const injectColorCssVars = () => {
  Object.entries(COLORS).forEach(([key, val]) => {
    if (val.rgb) {
      document.documentElement.style.setProperty(`--color-${key}-rgb`, val.rgb);
    }
  });
};

const App = () => {
  // AENDERUNG 10.02.2026: Farb-CSS-Variablen einmalig auf :root setzen
  useEffect(() => { injectColorCssVars(); }, []);

  // Navigation State
  const [currentRoom, setCurrentRoom] = useState('mission-control');

  // Mission Control State
  const [goal, setGoal] = useState('');
  // AENDERUNG 09.02.2026: Benutzerdefinierter Projektname
  const [projectName, setProjectName] = useState('');
  // ÄNDERUNG 29.01.2026: Discovery Briefing für Agent-Kontext speichern
  const [discoveryBriefing, setDiscoveryBriefing] = useState(null);
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('Idle');
  // ÄNDERUNG 25.01.2026: Toggle für Global Output Loop Ansicht
  const [outputMode, setOutputMode] = useState('user'); // 'user' | 'debug'
  const [activeAgents, setActiveAgents] = useState({
    orchestrator: { status: 'Idle', lastUpdate: '' },
    coder: { status: 'Idle', lastUpdate: '' },
    designer: { status: 'Idle', lastUpdate: '' },
    reviewer: { status: 'Idle', lastUpdate: '' },
    tester: { status: 'Idle', lastUpdate: '' },
    researcher: { status: 'Idle', lastUpdate: '' },
    techarchitect: { status: 'Idle', lastUpdate: '' },
    dbdesigner: { status: 'Idle', lastUpdate: '' },
    security: { status: 'Idle', lastUpdate: '' },
    // ÄNDERUNG 30.01.2026: Documentation Manager und Quality Gate
    documentationmanager: { status: 'Idle', lastUpdate: '' },
    qualitygate: { status: 'Idle', lastUpdate: '' },
    // AENDERUNG 02.02.2026: Planner Agent
    planner: { status: 'Idle', lastUpdate: '' },
    // AENDERUNG 07.02.2026: Fix-Agent (Fix 14)
    fix: { status: 'Idle', lastUpdate: '' },
  });

  // Strukturierte Agent-Daten für Live-Anzeige in Agent Offices
  const [agentData, setAgentData] = useState({
    // ÄNDERUNG 25.01.2026: Erweitert mit tasks, taskCount und Modellwechsel-Daten
    coder: {
      code: '', files: [], iteration: 0, maxIterations: 3, model: '',
      tasks: [], taskCount: 0,
      // Modellwechsel-Tracking ("Kollegen fragen")
      modelsUsed: [], currentModel: '', previousModel: '', failedAttempts: 0
    },
    // ÄNDERUNG 24.01.2026: Reviewer Echtzeit-Daten
    reviewer: {
      verdict: '',           // "OK" oder "FEEDBACK"
      feedback: '',
      model: '',
      iteration: 0,
      maxIterations: 3,
      sandboxStatus: '',     // "PASS" oder "FAIL"
      sandboxResult: '',
      testSummary: '',
      reviewOutput: ''
    },
    tester: {
      results: [],
      metrics: {},
      defects: [],           // Echte Test-Issues/Fehler
      coverage: [],          // Coverage pro Pfad
      stability: null,       // { value: number, trend: number }
      risk: null,            // { level: string, reason: string }
      screenshot: null,      // Base64 oder URL für Browser-Vorschau
      model: ''              // Verwendetes Modell
    },
    // ÄNDERUNG 24.01.2026: Erweiterte Designer Echtzeit-Daten
    designer: {
      colorPalette: [],
      typography: [],
      atomicAssets: [],
      qualityScore: null,
      iterationInfo: null,
      viewport: null,
      previewUrl: '',
      concept: '',
      model: '',
      timestamp: ''
    },
    // ÄNDERUNG 24.01.2026: Security Echtzeit-Daten vom Backend
    // ÄNDERUNG 24.01.2026: Erweitert mit scanType, iteration, blocking für Code-Scan
    security: {
      vulnerabilities: [],      // Array von {severity, description, type}
      overallStatus: '',        // "SECURE" oder "WARNING" oder "CRITICAL" oder "VULNERABLE"
      scanResult: '',           // Vollständiger Scan-Output
      model: '',                // Verwendetes Modell
      scannedFiles: 0,          // Anzahl gescannter Dateien
      scanType: 'requirement_scan',  // "requirement_scan" oder "code_scan"
      iteration: 0,             // Aktuelle Iteration bei Code-Scan
      blocking: false,          // true wenn Security-Issues den Abschluss blockieren
      timestamp: ''             // Zeitstempel
    },
    researcher: { query: '', result: '', status: '', model: '', error: '' },
    // ÄNDERUNG 24.01.2026: TechStack-Architect Echtzeit-Daten
    techstack: {
      blueprint: {},         // Komplettes tech_blueprint Objekt
      model: '',             // Verwendetes Modell (z.B. "gpt-4o-mini")
      decisions: [],         // Array von {type, value} Entscheidungen
      dependencies: [],      // Liste der Dependencies
      reasoning: '',         // Begründung der Entscheidung
      timestamp: null        // Zeitstempel
    },
    // ÄNDERUNG 24.01.2026: DB Designer Echtzeit-Daten
    dbdesigner: {
      schema: '',            // SQL Schema als String
      model: '',             // Verwendetes Modell
      status: '',            // "completed" oder leer
      tables: [],            // Array von Tabellen mit columns
      timestamp: ''          // Zeitstempel
    },
    // ÄNDERUNG 30.01.2026: Documentation Manager und Quality Gate Daten
    documentationmanager: {
      readme: '',            // README.md Inhalt
      changelog: '',         // CHANGELOG.md Inhalt
      files: [],             // Generierte Dokumentations-Dateien
      model: '',             // Verwendetes Modell
      status: '',            // "working", "completed", "error"
      timestamp: ''          // Zeitstempel
    },
    qualitygate: {
      validations: [],       // Array von Validierungsergebnissen
      overallScore: 0,       // Gesamt-Quality-Score (0-100)
      issues: [],            // Offene Issues
      warnings: []           // Warnings
    },
    // AENDERUNG 02.02.2026: Planner Agent Daten
    planner: {
      files: [],             // Geplante Dateien
      fileCount: 0,          // Anzahl der Dateien
      estimatedLines: 0,     // Geschaetzte Zeilen
      model: '',             // Verwendetes Modell
      totalTokens: 0,        // Token-Verbrauch (geschaetzt)
      source: ''             // "planner" oder "default"
    },
    // AENDERUNG 07.02.2026: Fix-Agent Daten (Fix 14)
    fix: {
      status: '',              // 'fixing', 'completed', ''
      currentFile: '',         // Aktuell bearbeitete Datei
      currentTask: '',         // Aktueller Task-Titel
      errorType: '',           // Fehlertyp (code, test, security)
      modifiedFiles: [],       // Alle modifizierten Dateien
      model: '',               // Verwendetes Modell
      fixCount: 0,             // Anzahl durchgefuehrter Fixes
      totalDuration: 0,        // Gesamtdauer in Sekunden
      lastResult: null         // Letztes Fix-Ergebnis
    }
  });

  // AENDERUNG 13.02.2026: Feature-Tracking State fuer Kanban-Board
  const [featureData, setFeatureData] = useState([]);
  const [currentRunId, setCurrentRunId] = useState(null);
  // AENDERUNG 14.02.2026: Celebration-Overlay State
  const [showCelebration, setShowCelebration] = useState(false);

  // ÄNDERUNG 24.01.2026: Resizable Panel State für rechte Sidebar
  const [previewHeight, setPreviewHeight] = useState(60); // 60% für Preview
  const [isDragging, setIsDragging] = useState(false);

  // Drag-Handler für Resize
  const handleResizeMouseDown = (e) => {
    setIsDragging(true);
    e.preventDefault();
  };

  // Effect für Resize-Logik
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      const container = document.getElementById('right-sidebar');
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const newHeight = ((e.clientY - rect.top) / rect.height) * 100;
      setPreviewHeight(Math.min(Math.max(newHeight, 20), 80)); // Min 20%, Max 80%
    };

    const handleMouseUp = () => setIsDragging(false);

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // Custom Hooks für WebSocket und Konfiguration
  // ÄNDERUNG 30.01.2026: HELP_NEEDED Support aus useWebSocket
  const {
    helpRequests,
    dismissHelpRequest,
    clearHelpRequests
  } = useWebSocket(setLogs, activeAgents, setActiveAgents, setAgentData, setStatus);
  // ÄNDERUNG 08.02.2026: researchTimeoutMinutes + handleResearchTimeoutChange entfernt (pro Agent im ModelModal)
  const {
    maxRetriesConfig,
    maxModelAttempts,
    handleMaxRetriesChange,
    handleMaxModelAttemptsChange
  } = useConfig(setAgentData);

  // ÄNDERUNG 28.01.2026: Session-Recovery nach Browser-Refresh
  // Lädt aktiven State vom Backend oder aus localStorage
  useEffect(() => {
    const loadPersistedState = async () => {
      try {
        // 1. Prüfe ob Backend eine aktive Session hat
        const response = await fetch(`${API_BASE}/session/current`);
        if (response.ok) {
          const sessionData = await response.json();

          // Wenn Backend eine aktive oder beendete Session hat
          if (sessionData.is_active || sessionData.session?.status !== 'Idle') {
            console.log('[Session] Backend-Session gefunden:', sessionData.session?.status);

            // State aus Backend übernehmen
            if (sessionData.session?.goal) {
              setGoal(sessionData.session.goal);
            }
            if (sessionData.session?.status) {
              setStatus(sessionData.session.status);
            }
            if (sessionData.recent_logs?.length > 0) {
              setLogs(sessionData.recent_logs.map(log => ({
                agent: log.agent,
                event: log.event,
                message: log.message,
                timestamp: log.timestamp
              })));
            }

            // Agent-Data aus Snapshots wiederherstellen
            if (sessionData.agent_data && Object.keys(sessionData.agent_data).length > 0) {
              setAgentData(prev => ({
                ...prev,
                ...Object.fromEntries(
                  Object.entries(sessionData.agent_data)
                    .filter(([_, data]) => data && Object.keys(data).length > 0)
                    .map(([name, data]) => [name, { ...prev[name], ...data }])
                )
              }));
            }

            return; // Backend-Session hat Vorrang
          }
        }
      } catch (err) {
        console.warn('[Session] Backend nicht erreichbar, versuche localStorage...');
      }

      // 2. Fallback: Lade aus localStorage wenn kein Backend verfügbar
      try {
        const saved = localStorage.getItem('agent_office_state');
        if (saved) {
          const { goal: savedGoal, projectName: savedProjectName, status: savedStatus, logs: savedLogs, timestamp } = JSON.parse(saved);

          // Nur wiederherstellen wenn nicht älter als 24 Stunden
          const age = Date.now() - (timestamp || 0);
          const maxAge = 24 * 60 * 60 * 1000; // 24 Stunden

          if (age < maxAge) {
            console.log('[Session] localStorage-State wiederhergestellt');
            if (savedGoal) setGoal(savedGoal);
            // AENDERUNG 09.02.2026: Projektname wiederherstellen
            if (savedProjectName) setProjectName(savedProjectName);
            // ÄNDERUNG 28.01.2026: Status wiederherstellen für Reset-Button
            if (savedStatus && savedStatus !== 'Idle') setStatus(savedStatus);
            if (savedLogs?.length > 0) setLogs(savedLogs.slice(-100));
          } else {
            // Alten State löschen
            localStorage.removeItem('agent_office_state');
          }
        }
      } catch (err) {
        console.warn('[Session] localStorage-Wiederherstellung fehlgeschlagen:', err);
      }
    };

    loadPersistedState();
  }, []); // Nur einmal beim Mount

  // ÄNDERUNG 28.01.2026: State in localStorage persistieren
  // Speichert goal, logs und status für Offline-Recovery
  useEffect(() => {
    // Nur speichern wenn relevante Daten vorhanden
    if (goal || logs.length > 0) {
      const stateToSave = {
        goal,
        projectName, // AENDERUNG 09.02.2026: Projektname mitspeichern
        status, // ÄNDERUNG 28.01.2026: Status mitspeichern für Reset-Button
        logs: logs.slice(-200), // Max 200 Logs speichern
        timestamp: Date.now()
      };
      try {
        localStorage.setItem('agent_office_state', JSON.stringify(stateToSave));
      } catch (err) {
        // localStorage voll oder nicht verfügbar - ignorieren
        console.warn('[Session] localStorage-Speicherung fehlgeschlagen:', err);
      }
    }
  }, [goal, logs, status]);

  // AENDERUNG 13.02.2026: Feature-Events aus dem Log-Stream extrahieren
  useEffect(() => {
    if (logs.length === 0) return;
    const latest = logs[logs.length - 1];
    if (latest?.agent !== 'System') return;

    if (latest.event === 'FeaturesCreated' || latest.event === 'FeatureStats') {
      // Stats-Update — run_id aus dem vorherigen ProjectStart Event ermitteln
      try {
        const statsData = JSON.parse(latest.message);
        if (statsData.total > 0 && currentRunId) {
          // Features vom Backend neu laden
          fetch(`${API_BASE}/features/${currentRunId}`)
            .then(res => res.json())
            .then(data => {
              if (data.status === 'ok' && Array.isArray(data.features)) {
                setFeatureData(data.features);
              }
            })
            .catch(() => {});
        }
      } catch {
        // JSON-Parse fehlgeschlagen - ignorieren
      }
    }

    if (latest.event === 'FeatureUpdate') {
      try {
        const update = JSON.parse(latest.message);
        setFeatureData(prev => prev.map(f =>
          f.id === update.id ? { ...f, status: update.status, ...update } : f
        ));
      } catch {
        // JSON-Parse fehlgeschlagen - ignorieren
      }
    }

    // Run-ID aus Library ProjectStart Event extrahieren
    if (latest.agent === 'Library' && latest.event === 'ProjectStart') {
      const match = latest.message?.match(/Protokollierung gestartet:\s*(\S+)/);
      if (match) {
        setCurrentRunId(match[1]);
      }
    }
  }, [logs, currentRunId]);

  // AENDERUNG 14.02.2026: Celebration bei Success anzeigen (Auto-Dismiss nach 6s)
  useEffect(() => {
    if (status === 'Success') {
      setShowCelebration(true);
      const timer = setTimeout(() => setShowCelebration(false), 6000);
      return () => clearTimeout(timer);
    }
  }, [status]);

  // AENDERUNG 14.02.2026: Browser-Tab Titel + Favicon dynamisch je nach Status
  useEffect(() => {
    const STATUS_TAB = {
      Idle:    { title: 'AgentSmith',                      color: '#06b6d4' },
      Working: { title: '\u2699 Arbeitet... | AgentSmith', color: '#f59e0b' },
      Success: { title: '\u2705 Fertig! | AgentSmith',     color: '#22c55e' },
      Error:   { title: '\u274C Fehler | AgentSmith',      color: '#ef4444' },
    };
    const cfg = STATUS_TAB[status] || STATUS_TAB.Idle;
    document.title = cfg.title;

    // Canvas-Favicon generieren
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 32; canvas.height = 32;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = cfg.color;
      ctx.beginPath();
      ctx.arc(16, 16, 14, 0, Math.PI * 2);
      ctx.fill();
      // Weisser Punkt in der Mitte
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(16, 16, 5, 0, Math.PI * 2);
      ctx.fill();
      const link = document.querySelector("link[rel~='icon']") || document.createElement('link');
      link.rel = 'icon';
      link.href = canvas.toDataURL();
      document.head.appendChild(link);
    } catch {
      // Canvas nicht verfuegbar — Favicon bleibt unveraendert
    }
  }, [status]);

  // AENDERUNG 14.02.2026: Keyboard Shortcuts (Ctrl+Enter = Deploy, Escape = Schliessen)
  const toastRef = useRef(null);

  const handleDeploy = useCallback(async () => {
    if (!goal) return;
    setStatus('Working');
    setLogs([]);
    try {
      const payload = { goal };
      if (projectName.trim()) {
        payload.project_name = projectName.trim();
      }
      await axios.post(`${API_BASE}/run`, payload);
    } catch (err) {
      console.error("Backend-Verbindung fehlgeschlagen:", err);
      setLogs(prev => [...prev, { agent: 'System', event: 'Error', message: 'Keine Verbindung zum Backend.' }]);
      setStatus('Error');
    }
  }, [goal, projectName]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+Enter: Deploy starten (nur wenn Idle + Goal vorhanden)
      if (e.ctrlKey && e.key === 'Enter' && status === 'Idle' && goal.trim()) {
        e.preventDefault();
        handleDeploy();
      }
      // Escape: Stufenweise schliessen
      if (e.key === 'Escape') {
        if (showCelebration) { setShowCelebration(false); return; }
        if (helpRequests.length > 0) { clearHelpRequests(); return; }
        if (currentRoom !== 'mission-control') { setCurrentRoom('mission-control'); }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [status, goal, currentRoom, showCelebration, helpRequests, clearHelpRequests, handleDeploy]);

  // AENDERUNG 14.02.2026: Toast-Trigger — Agent-Events aus Logs als Benachrichtigungen
  const lastToastLogIdx = useRef(-1);
  useEffect(() => {
    if (logs.length === 0) { lastToastLogIdx.current = -1; return; }
    // Nur neue Logs seit letztem Check verarbeiten
    const startIdx = Math.max(0, lastToastLogIdx.current + 1);
    lastToastLogIdx.current = logs.length - 1;
    if (!toastRef.current) return;

    for (let i = startIdx; i < logs.length; i++) {
      const log = logs[i];
      if (!log?.event) continue;

      // Events die bereits eigene UI haben → kein Toast
      if (log.event === 'Success') continue;          // CelebrationOverlay
      if (log.event === 'HELP_NEEDED') continue;       // HelpPanel

      // Agent-Completion Events
      if (log.event === 'CodeOutput') {
        toastRef.current.addToast(log.agent || 'Coder', 'Code generiert', 'info');
      } else if (log.event === 'ReviewOutput') {
        const isOk = log.message?.includes('OK') || log.message?.includes('APPROVED');
        toastRef.current.addToast('Reviewer', isOk ? 'Review bestanden' : 'Feedback erhalten', isOk ? 'success' : 'warning');
      } else if (log.event === 'UITestResult') {
        toastRef.current.addToast('Tester', 'Tests durchgefuehrt', 'info');
      } else if (log.event === 'SecurityOutput') {
        const secure = log.message?.includes('SECURE');
        toastRef.current.addToast('Security', secure ? 'Sicherheitsscan: OK' : 'Sicherheitswarnung!', secure ? 'success' : 'warning');
      } else if (log.event === 'DesignerOutput') {
        toastRef.current.addToast('Designer', 'Design erstellt', 'info');
      } else if (log.event === 'ModelSwitch') {
        toastRef.current.addToast(log.agent || 'System', 'Modell gewechselt', 'info');
      } else if (log.event === 'Failure') {
        toastRef.current.addToast('System', 'Fehler aufgetreten', 'error');
      } else if (log.event === 'TechStackOutput') {
        toastRef.current.addToast('TechArchitect', 'Tech-Stack definiert', 'info');
      }
    }
  }, [logs]);

  // ÄNDERUNG 25.01.2026: Reset-Funktion für Projekt-Neustart
  // ÄNDERUNG 28.01.2026: localStorage und Session ebenfalls zurücksetzen
  const handleReset = async () => {
    try {
      // Backend zurücksetzen
      await axios.post(`${API_BASE}/reset`);

      // Session zurücksetzen
      try {
        await axios.post(`${API_BASE}/session/reset`);
      } catch (err) {
        console.warn('[Session] Session-Reset fehlgeschlagen:', err);
      }

      // localStorage leeren
      localStorage.removeItem('agent_office_state');

      // Frontend States zurücksetzen
      setGoal('');
      setProjectName('');
      setLogs([]);
      setStatus('Idle');
      setOutputMode('user');
      // AENDERUNG 13.02.2026: Feature-Daten zuruecksetzen
      setFeatureData([]);
      setCurrentRunId(null);
      // AENDERUNG 14.02.2026: Celebration zuruecksetzen
      setShowCelebration(false);

      // Alle Agenten auf Idle setzen
      setActiveAgents({
        orchestrator: { status: 'Idle', lastUpdate: '' },
        coder: { status: 'Idle', lastUpdate: '' },
        reviewer: { status: 'Idle', lastUpdate: '' },
        tester: { status: 'Idle', lastUpdate: '' },
        designer: { status: 'Idle', lastUpdate: '' },
        security: { status: 'Idle', lastUpdate: '' },
        researcher: { status: 'Idle', lastUpdate: '' },
        techarchitect: { status: 'Idle', lastUpdate: '' },
        dbdesigner: { status: 'Idle', lastUpdate: '' },
        // ÄNDERUNG 30.01.2026: Documentation Manager und Quality Gate
        documentationmanager: { status: 'Idle', lastUpdate: '' },
        qualitygate: { status: 'Idle', lastUpdate: '' },
        // AENDERUNG 02.02.2026: Planner Agent
        planner: { status: 'Idle', lastUpdate: '' },
      });

      // AgentData zurücksetzen
      setAgentData({
        coder: { code: '', files: [], iteration: 0, maxIterations: 3, model: '', tasks: [], taskCount: 0, modelsUsed: [], currentModel: '', previousModel: '', failedAttempts: 0, totalTokens: 0, totalCost: 0, workers: [] },
        reviewer: { verdict: '', feedback: '', model: '', iteration: 0, maxIterations: 3, sandboxStatus: '', sandboxResult: '', testSummary: '', reviewOutput: '' },
        tester: { results: [], metrics: {}, defects: [], coverage: [], stability: null, risk: null, screenshot: null, model: '' },
        designer: { colorPalette: [], typography: [], atomicAssets: [], qualityScore: null, iterationInfo: null, viewport: null, previewUrl: '', concept: '', model: '', timestamp: '' },
        security: { vulnerabilities: [], overallStatus: '', scanResult: '', model: '', scannedFiles: 0, scanType: 'requirement_scan', iteration: 0, blocking: false, timestamp: '' },
        researcher: { query: '', result: '', status: '', model: '', error: '', workers: [] },
        techstack: { blueprint: {}, model: '', decisions: [], dependencies: [], reasoning: '', timestamp: null, workers: [] },
        dbdesigner: { schema: '', model: '', status: '', tables: [], timestamp: '', workers: [] },
        // ÄNDERUNG 30.01.2026: Documentation Manager und Quality Gate
        documentationmanager: { readme: '', changelog: '', files: [], model: '', status: '', timestamp: '', workers: [] },
        qualitygate: { validations: [], overallScore: 0, issues: [], warnings: [] },
        // AENDERUNG 02.02.2026: Planner Agent
        planner: { files: [], fileCount: 0, estimatedLines: 0, model: '', totalTokens: 0, source: '' },
      });

    } catch (error) {
      console.error('Reset failed:', error);
      setLogs(prev => [...prev, { agent: 'System', event: 'Error', message: 'Reset fehlgeschlagen.' }]);
    }
  };

  // ÄNDERUNG [31.01.2026]: Agent-Routing in eigene Komponente ausgelagert
  if (isAgentRoute(currentRoom)) {
    return (
      <AgentRouter
        currentRoom={currentRoom}
        setCurrentRoom={setCurrentRoom}
        logs={logs}
        activeAgents={activeAgents}
        agentData={agentData}
        setDiscoveryBriefing={setDiscoveryBriefing}
        setGoal={setGoal}
      />
    );
  }

  // AENDERUNG 13.02.2026: Render Kanban-Board
  if (currentRoom === 'kanban') {
    return (
      <div className="bg-background-dark text-white font-sans overflow-hidden h-screen flex flex-col">
        <NavigationHeader currentRoom={currentRoom} setCurrentRoom={setCurrentRoom} />
        <div className="flex-1 overflow-y-auto overflow-x-hidden page-scrollbar">
          <KanbanBoard
            runId={currentRunId}
            featureData={featureData}
            onFeatureDataChange={setFeatureData}
          />
        </div>
      </div>
    );
  }

  // Render Mainframe Hub oder Budget Dashboard
  if (currentRoom === 'mainframe' || currentRoom === 'budget-dashboard') {
    return (
      <div className="bg-background-dark text-white font-sans overflow-hidden h-screen flex flex-col">
        <NavigationHeader currentRoom={currentRoom} setCurrentRoom={setCurrentRoom} />
        <div className="flex-1 overflow-y-auto overflow-x-hidden page-scrollbar">
          {currentRoom === 'mainframe' && (
            <MainframeHub maxRetries={maxRetriesConfig} onMaxRetriesChange={handleMaxRetriesChange}
              maxModelAttempts={maxModelAttempts} onMaxModelAttemptsChange={handleMaxModelAttemptsChange} />
          )}
          {currentRoom === 'budget-dashboard' && <BudgetDashboard />}
        </div>
      </div>
    );
  }

  // Default: Mission Control
  return (
    <div className="bg-background-dark text-white font-sans overflow-hidden h-screen flex flex-col">
      <NavigationHeader currentRoom={currentRoom} setCurrentRoom={setCurrentRoom} showConnectButton />

      <div className="flex flex-1 overflow-hidden relative">
        <MissionControl
          goal={goal}
          onGoalChange={setGoal}
          projectName={projectName}
          onProjectNameChange={setProjectName}
          onDeploy={handleDeploy}
          onReset={handleReset}
          status={status}
          logs={logs}
          activeAgents={activeAgents}
          agentData={agentData}
          onOpenOffice={setCurrentRoom}
          featureStats={featureData.length > 0 ? (() => {
            const s = { pending: 0, in_progress: 0, review: 0, done: 0, failed: 0, total: featureData.length, percentage: 0 };
            featureData.forEach(f => { const st = f.status || 'pending'; if (s[st] !== undefined) s[st]++; });
            s.percentage = s.total > 0 ? Math.round((s.done / s.total) * 100) : 0;
            return s;
          })() : null}
          onOpenKanban={() => setCurrentRoom('kanban')}
        />
        <RightPanel
          agentData={agentData}
          status={status}
          previewHeight={previewHeight}
          onResizeMouseDown={handleResizeMouseDown}
          isDragging={isDragging}
          outputMode={outputMode}
          onOutputModeChange={setOutputMode}
          logs={logs}
        />
      </div>

      {/* AENDERUNG 14.02.2026: Toast-Benachrichtigungen fuer Agent-Events */}
      <ToastContainer ref={toastRef} />

      {/* ÄNDERUNG 30.01.2026: HelpPanel für HELP_NEEDED Events */}
      <HelpPanel
        helpRequests={helpRequests}
        onDismiss={dismissHelpRequest}
        onDismissAll={clearHelpRequests}
      />

      {/* AENDERUNG 14.02.2026: Celebration-Overlay bei Projekt-Erfolg */}
      <CelebrationOverlay
        show={showCelebration}
        onDismiss={() => setShowCelebration(false)}
        featureStats={featureData.length > 0 ? {
          total: featureData.length,
          done: featureData.filter(f => f.status === 'done').length,
        } : null}
      />
    </div>
  );
};

export default App;
