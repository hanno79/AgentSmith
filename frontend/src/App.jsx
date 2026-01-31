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

import React, { useState, useEffect } from 'react';
import axios from 'axios';

import MainframeHub from './MainframeHub';
import BudgetDashboard from './BudgetDashboard';
import NavigationHeader from './components/NavigationHeader';
import HelpPanel from './components/HelpPanel';
import MissionControl from './components/MissionControl';
import RightPanel from './components/RightPanel';
import AgentRouter, { isAgentRoute } from './components/AgentRouter';
import useWebSocket from './hooks/useWebSocket';
import useConfig from './hooks/useConfig';
import { API_BASE } from './constants/config';

const App = () => {
  // Navigation State
  const [currentRoom, setCurrentRoom] = useState('mission-control');

  // Mission Control State
  const [goal, setGoal] = useState('');
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
    }
  });

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
  const {
    researchTimeoutMinutes,
    maxRetriesConfig,
    maxModelAttempts,
    handleResearchTimeoutChange,
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
          const { goal: savedGoal, status: savedStatus, logs: savedLogs, timestamp } = JSON.parse(saved);

          // Nur wiederherstellen wenn nicht älter als 24 Stunden
          const age = Date.now() - (timestamp || 0);
          const maxAge = 24 * 60 * 60 * 1000; // 24 Stunden

          if (age < maxAge) {
            console.log('[Session] localStorage-State wiederhergestellt');
            if (savedGoal) setGoal(savedGoal);
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

  // Deploy-Handler: Startet die Agenten-Pipeline
  const handleDeploy = async () => {
    if (!goal) return;
    setStatus('Working');
    setLogs([]);
    try {
      await axios.post(`${API_BASE}/run`, { goal });
    } catch (err) {
      console.error("Backend-Verbindung fehlgeschlagen:", err);
      setLogs(prev => [...prev, { agent: 'System', event: 'Error', message: 'Keine Verbindung zum Backend.' }]);
      setStatus('Error');
    }
  };

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
      setLogs([]);
      setStatus('Idle');
      setOutputMode('user');

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
        researchTimeoutMinutes={researchTimeoutMinutes}
        onResearchTimeoutChange={handleResearchTimeoutChange}
        setDiscoveryBriefing={setDiscoveryBriefing}
        setGoal={setGoal}
      />
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
              researchTimeout={researchTimeoutMinutes} onResearchTimeoutChange={handleResearchTimeoutChange}
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
          onDeploy={handleDeploy}
          onReset={handleReset}
          status={status}
          logs={logs}
          activeAgents={activeAgents}
          agentData={agentData}
          onOpenOffice={setCurrentRoom}
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

      {/* ÄNDERUNG 30.01.2026: HelpPanel für HELP_NEEDED Events */}
      <HelpPanel
        helpRequests={helpRequests}
        onDismiss={dismissHelpRequest}
        onDismissAll={clearHelpRequests}
      />
    </div>
  );
};

export default App;
