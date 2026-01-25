/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.2
 * Beschreibung: App Hauptkomponente - Zentrale UI mit WebSocket-Verbindung und Agenten-Steuerung.
 *               Refaktoriert: WebSocket, Config, AgentCard und NavigationHeader extrahiert.
 */

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Database,
  Send,
  Mic,
  PlusCircle,
  BarChart3,
  Code2,
  Palette,
  ShieldCheck,
  Bug,
  Scaling,
  RefreshCw,
  Search,
  Cpu,
  Lock
} from 'lucide-react';
import { motion } from 'framer-motion';

// Eigene Komponenten und Hooks
import MainframeHub from './MainframeHub';
import BudgetDashboard from './BudgetDashboard';
import CoderOffice from './CoderOffice';
import TesterOffice from './TesterOffice';
import DesignerOffice from './DesignerOffice';
import ReviewerOffice from './ReviewerOffice';
import ResearcherOffice from './ResearcherOffice';
import SecurityOffice from './SecurityOffice';
import TechStackOffice from './TechStackOffice';
import DBDesignerOffice from './DBDesignerOffice';
import AgentCard from './components/AgentCard';
import NavigationHeader from './components/NavigationHeader';
import useWebSocket from './hooks/useWebSocket';
import useConfig from './hooks/useConfig';
import { API_BASE } from './constants/config';

const App = () => {
  // Navigation State
  const [currentRoom, setCurrentRoom] = useState('mission-control');

  // Mission Control State
  const [goal, setGoal] = useState('');
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('Idle');
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
    }
  });

  const logEndRef = useRef(null);

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
  useWebSocket(setLogs, activeAgents, setActiveAgents, setAgentData, setStatus);
  const {
    researchTimeoutMinutes,
    maxRetriesConfig,
    handleResearchTimeoutChange,
    handleMaxRetriesChange
  } = useConfig(setAgentData);

  // Auto-Scroll bei neuen Logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

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

  // Render Agent Offices
  if (currentRoom === 'agent-coder') {
    return (
      <CoderOffice
        agentName="Coder" status={activeAgents.coder.status}
        logs={logs.filter(l => l.agent === 'Coder')} onBack={() => setCurrentRoom('mission-control')}
        color="blue" code={agentData.coder.code} files={agentData.coder.files}
        iteration={agentData.coder.iteration} maxIterations={agentData.coder.maxIterations} model={agentData.coder.model}
        tasks={agentData.coder.tasks} taskCount={agentData.coder.taskCount}
        modelsUsed={agentData.coder.modelsUsed} currentModel={agentData.coder.currentModel}
        previousModel={agentData.coder.previousModel} failedAttempts={agentData.coder.failedAttempts}
      />
    );
  }
  if (currentRoom === 'agent-tester') {
    return (
      <TesterOffice
        agentName="Tester"
        status={activeAgents.tester.status}
        logs={logs.filter(l => l.agent === 'Tester')}
        onBack={() => setCurrentRoom('mission-control')}
        color="orange"
        defects={agentData.tester.defects}
        coverage={agentData.tester.coverage}
        stability={agentData.tester.stability}
        risk={agentData.tester.risk}
        screenshot={agentData.tester.screenshot}
        model={agentData.tester.model}
      />
    );
  }
  if (currentRoom === 'agent-designer') {
    return (
      <DesignerOffice
        agentName="Designer"
        status={activeAgents.designer.status}
        logs={logs.filter(l => l.agent === 'Designer')}
        onBack={() => setCurrentRoom('mission-control')}
        color="pink"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        colorPalette={agentData.designer.colorPalette}
        typography={agentData.designer.typography}
        atomicAssets={agentData.designer.atomicAssets}
        qualityScore={agentData.designer.qualityScore}
        iterationInfo={agentData.designer.iterationInfo}
        viewport={agentData.designer.viewport}
        previewUrl={agentData.designer.previewUrl}
        concept={agentData.designer.concept}
        model={agentData.designer.model}
      />
    );
  }
  if (currentRoom === 'agent-reviewer') {
    return (
      <ReviewerOffice
        agentName="Reviewer"
        status={activeAgents.reviewer.status}
        logs={logs.filter(l => l.agent === 'Reviewer')}
        onBack={() => setCurrentRoom('mission-control')}
        color="yellow"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend (erweitert mit humanSummary)
        verdict={agentData.reviewer.verdict}
        isApproved={agentData.reviewer.isApproved}
        humanSummary={agentData.reviewer.humanSummary}
        feedback={agentData.reviewer.feedback}
        model={agentData.reviewer.model}
        iteration={agentData.reviewer.iteration}
        maxIterations={agentData.reviewer.maxIterations}
        sandboxStatus={agentData.reviewer.sandboxStatus}
        sandboxResult={agentData.reviewer.sandboxResult}
        testSummary={agentData.reviewer.testSummary}
      />
    );
  }
  if (currentRoom === 'agent-researcher') {
    return (
      <ResearcherOffice
        agentName="Researcher" status={activeAgents.researcher.status}
        logs={logs.filter(l => l.agent === 'Researcher')} onBack={() => setCurrentRoom('mission-control')}
        color="cyan" query={agentData.researcher.query} result={agentData.researcher.result}
        researchStatus={agentData.researcher.status} model={agentData.researcher.model} error={agentData.researcher.error}
        researchTimeoutMinutes={researchTimeoutMinutes} onResearchTimeoutChange={handleResearchTimeoutChange}
      />
    );
  }
  if (currentRoom === 'agent-security') {
    return (
      <SecurityOffice
        agentName="Security"
        status={activeAgents.security.status}
        logs={logs.filter(l => l.agent === 'Security')}
        onBack={() => setCurrentRoom('mission-control')}
        color="red"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        vulnerabilities={agentData.security.vulnerabilities}
        overallStatus={agentData.security.overallStatus}
        scanResult={agentData.security.scanResult}
        model={agentData.security.model}
        scannedFiles={agentData.security.scannedFiles}
        // ÄNDERUNG 24.01.2026: Neue Props für Code-Scan
        scanType={agentData.security.scanType}
        iteration={agentData.security.iteration}
        blocking={agentData.security.blocking}
      />
    );
  }
  if (currentRoom === 'agent-techstack') {
    return (
      <TechStackOffice
        agentName="Tech-Stack"
        status={activeAgents.techarchitect.status}
        logs={logs.filter(l => l.agent === 'TechArchitect')}
        onBack={() => setCurrentRoom('mission-control')}
        color="purple"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        blueprint={agentData.techstack.blueprint}
        model={agentData.techstack.model}
        decisions={agentData.techstack.decisions}
        dependencies={agentData.techstack.dependencies}
        reasoning={agentData.techstack.reasoning}
      />
    );
  }
  if (currentRoom === 'agent-dbdesigner') {
    return (
      <DBDesignerOffice
        agentName="Database Designer"
        status={activeAgents.dbdesigner.status}
        logs={logs.filter(l => l.agent === 'DBDesigner')}
        onBack={() => setCurrentRoom('mission-control')}
        color="green"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        schema={agentData.dbdesigner.schema}
        model={agentData.dbdesigner.model}
        tables={agentData.dbdesigner.tables}
        dbStatus={agentData.dbdesigner.status}
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
              researchTimeout={researchTimeoutMinutes} onResearchTimeoutChange={handleResearchTimeoutChange} />
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
        {/* Mission Control Hauptbereich */}
        <main className="flex-1 overflow-y-auto page-scrollbar relative flex flex-col items-center bg-[#101922] p-6 lg:p-8">
          <div className="absolute inset-0 bg-grid-pattern opacity-[0.05] pointer-events-none"></div>

          <div className="w-full max-w-[1000px] flex flex-col gap-8 z-10">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Mission Control Floor</h1>
                <p className="text-slate-400 text-sm">Orchestrating autonomous agents in real-time.</p>
              </div>
              <div className="bg-[#1c2127] border border-border-dark px-4 py-2 rounded-lg flex items-center gap-3">
                <BarChart3 size={16} className="text-primary" />
                <span className="text-sm text-slate-300 font-mono">Status: {status}</span>
              </div>
            </div>

            {/* Orchestrator Center */}
            <motion.div layout className="w-full rounded-xl border border-border-dark bg-[#1c2127] p-6 shadow-2xl relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1 h-full bg-primary" />
              <div className="flex items-center gap-4 mb-4">
                <div className="p-3 rounded-lg bg-primary/10 border border-primary/30">
                  <Scaling size={24} className="text-primary" />
                </div>
                <div>
                  <h3 className="text-xl font-bold">Orchestrator Desk</h3>
                  <p className="text-primary text-sm animate-pulse">{activeAgents.orchestrator.status !== 'Idle' ? 'Active: Routing Tasks...' : 'Ready for Instructions'}</p>
                </div>
              </div>
              <div className="bg-black/40 rounded-lg p-4 font-mono text-xs text-slate-300 h-24 overflow-y-auto terminal-scroll border border-white/5">
                {logs.filter(l => l.agent === 'Orchestrator').slice(-3).map((l, i) => (
                  <div key={i} className="mb-1"><span className="text-slate-500 mr-2">[{l.event}]</span><span>{l.message}</span></div>
                ))}
                {logs.filter(l => l.agent === 'Orchestrator').length === 0 && <div className="opacity-50">&gt; Awaiting initial command sequence...</div>}
              </div>
            </motion.div>

            {/* Agent Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <AgentCard name="Researcher" icon={<Search size={24} />} color="cyan" status={activeAgents.researcher.status} logs={logs.filter(l => l.agent === 'Researcher')} onOpenOffice={() => setCurrentRoom('agent-researcher')} />
              <AgentCard name="Coder" icon={<Code2 size={24} />} color="blue" status={activeAgents.coder.status} logs={logs.filter(l => l.agent === 'Coder')} onOpenOffice={() => setCurrentRoom('agent-coder')} />
              <AgentCard name="Designer" icon={<Palette size={24} />} color="pink" status={activeAgents.designer.status} logs={logs.filter(l => l.agent === 'Designer')} onOpenOffice={() => setCurrentRoom('agent-designer')} />
              <AgentCard name="Reviewer" icon={<ShieldCheck size={24} />} color="yellow" status={activeAgents.reviewer.status} logs={logs.filter(l => l.agent === 'Reviewer')} onOpenOffice={() => setCurrentRoom('agent-reviewer')} />
              <AgentCard name="Tester" icon={<Bug size={24} />} color="orange" status={activeAgents.tester.status} logs={logs.filter(l => l.agent === 'Tester')} onOpenOffice={() => setCurrentRoom('agent-tester')} />
              <AgentCard name="Tech Architect" icon={<Cpu size={24} />} color="purple" status={activeAgents.techarchitect.status} logs={logs.filter(l => l.agent === 'TechArchitect')} onOpenOffice={() => setCurrentRoom('agent-techstack')} />
              <AgentCard name="DB Designer" icon={<Database size={24} />} color="green" status={activeAgents.dbdesigner.status} logs={logs.filter(l => l.agent === 'DBDesigner')} onOpenOffice={() => setCurrentRoom('agent-dbdesigner')} />
              <AgentCard name="Security" icon={<Lock size={24} />} color="red" status={activeAgents.security.status} logs={logs.filter(l => l.agent === 'Security')} onOpenOffice={() => setCurrentRoom('agent-security')} />
            </div>
          </div>

          {/* Floating Command Bar */}
          <div className="fixed bottom-8 w-[90%] max-w-[800px] flex items-center gap-2 p-2 rounded-xl bg-[#1c2127]/90 backdrop-blur-md border border-border-dark shadow-2xl ring-1 ring-white/5 z-50">
            <PlusCircle className="ml-2 text-slate-400 cursor-pointer hover:text-white" />
            <input value={goal} onChange={(e) => setGoal(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleDeploy()}
              placeholder="What should the team build today?" className="flex-1 bg-transparent border-none text-white focus:ring-0 text-sm" disabled={status === 'Working'} />
            <Mic size={20} className="text-slate-400 cursor-pointer hover:text-white" />
            <button onClick={handleDeploy} disabled={status === 'Working' || !goal}
              className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold text-sm transition-all ${status === 'Working' ? 'bg-slate-700 text-slate-400' : 'bg-primary hover:bg-blue-600 text-white shadow-lg'}`}>
              <span>Deploy</span><Send size={16} />
            </button>
          </div>
        </main>

        {/* Right Panel: Resizable Logs & Canvas - ÄNDERUNG 24.01.2026 */}
        <aside
          id="right-sidebar"
          className="w-[400px] border-l border-border-dark bg-[#0d1216] hidden 2xl:flex flex-col z-20"
        >
          {/* Live Canvas Panel (variable Höhe) */}
          <div
            className="flex flex-col overflow-hidden"
            style={{ height: `${previewHeight}%` }}
          >
            <div className="h-10 border-b border-border-dark flex items-center justify-between px-4 bg-[#111418] shrink-0">
              <div className="flex items-center gap-2 text-sm font-bold">
                <RefreshCw size={14} className="text-slate-400" />
                <span>Live Canvas</span>
              </div>
              <span className="text-[10px] text-emerald-400 font-mono">● Live</span>
            </div>

            <div className="flex-1 p-3 bg-[#1e1e1e] overflow-hidden">
              <div className="w-full h-full bg-white rounded shadow-2xl flex flex-col overflow-hidden">
                {/* Browser Chrome */}
                <div className="bg-gray-100 border-b border-gray-200 px-3 py-1.5 flex items-center gap-2 shrink-0">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-red-400" />
                    <div className="w-2 h-2 rounded-full bg-yellow-400" />
                    <div className="w-2 h-2 rounded-full bg-green-400" />
                  </div>
                  <div className="flex-1 bg-white h-4 rounded border border-gray-200 text-[9px] text-gray-400 flex items-center px-2">
                    localhost:3000
                  </div>
                </div>
                {/* Canvas Content - Echter Screenshot oder Placeholder */}
                <div className="flex-1 flex items-center justify-center overflow-hidden bg-gray-50">
                  {agentData.tester.screenshot ? (
                    <img
                      src={agentData.tester.screenshot}
                      alt="Live Preview"
                      className="w-full h-full object-contain"
                    />
                  ) : status === 'Working' ? (
                    <div className="flex flex-col items-center gap-2 p-4">
                      <RefreshCw size={32} className="text-gray-400 animate-spin" />
                      <div className="text-gray-500 text-xs">Generiere Vorschau...</div>
                    </div>
                  ) : status === 'Success' ? (
                    <div className="text-green-600 text-sm font-medium">Fertig</div>
                  ) : (
                    <div className="text-gray-400 text-xs italic text-center px-4">
                      Canvas leer. Starte ein Projekt.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Resize Handle */}
          <div
            onMouseDown={handleResizeMouseDown}
            className={`h-2 bg-[#1a1a2e] hover:bg-violet-600 cursor-row-resize flex items-center justify-center transition-colors shrink-0 ${isDragging ? 'bg-violet-600' : ''}`}
          >
            <div className="w-10 h-0.5 bg-slate-600 rounded-full"></div>
          </div>

          {/* Global Output Loop (restliche Höhe) */}
          <div
            className="flex flex-col overflow-hidden"
            style={{ height: `${100 - previewHeight}%` }}
          >
            <div className="px-4 py-2 border-b border-border-dark flex justify-between items-center bg-[#111418] shrink-0">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Global Output Loop</span>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-[10px] text-green-500 font-mono">CONNECTED</span>
              </div>
            </div>
            <div className="flex-1 p-3 overflow-y-auto terminal-scroll font-mono text-[10px] text-slate-400 flex flex-col gap-1">
              {logs.map((l, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-slate-600 shrink-0">[{l.agent}]</span>
                  <span className={l.event === 'Error' ? 'text-red-400' : 'text-slate-300'}>{l.message}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default App;
