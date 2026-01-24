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
    coder: { code: '', files: [], iteration: 0, maxIterations: 3, model: '' },
    reviewer: { feedback: '', metrics: {} },
    tester: { results: [], metrics: {} },
    designer: { concept: '', metrics: {} },
    security: { report: '', metrics: {} },
    researcher: { query: '', result: '', status: '', model: '', error: '' },
  });

  const logEndRef = useRef(null);

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
      />
    );
  }
  if (currentRoom === 'agent-tester') {
    return <TesterOffice agentName="Tester" status={activeAgents.tester.status} logs={logs.filter(l => l.agent === 'Tester')} onBack={() => setCurrentRoom('mission-control')} color="orange" />;
  }
  if (currentRoom === 'agent-designer') {
    return <DesignerOffice agentName="Designer" status={activeAgents.designer.status} logs={logs.filter(l => l.agent === 'Designer')} onBack={() => setCurrentRoom('mission-control')} color="pink" />;
  }
  if (currentRoom === 'agent-reviewer') {
    return <ReviewerOffice agentName="Reviewer" status={activeAgents.reviewer.status} logs={logs.filter(l => l.agent === 'Reviewer')} onBack={() => setCurrentRoom('mission-control')} color="yellow" />;
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
    return <SecurityOffice agentName="Security" status={activeAgents.security.status} logs={logs.filter(l => l.agent === 'Security')} onBack={() => setCurrentRoom('mission-control')} color="red" />;
  }
  if (currentRoom === 'agent-techstack') {
    return <TechStackOffice agentName="Tech-Stack" status={activeAgents.techarchitect.status} logs={logs.filter(l => l.agent === 'TechArchitect')} onBack={() => setCurrentRoom('mission-control')} color="purple" />;
  }
  if (currentRoom === 'agent-dbdesigner') {
    return <DBDesignerOffice agentName="Database Designer" status={activeAgents.dbdesigner.status} logs={logs.filter(l => l.agent === 'DBDesigner')} onBack={() => setCurrentRoom('mission-control')} color="green" />;
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

        {/* Right Panel: Logs & Canvas */}
        <aside className="w-[400px] border-l border-border-dark bg-[#0d1216] hidden 2xl:flex flex-col z-20">
          <div className="h-14 border-b border-border-dark flex items-center justify-between px-4 bg-[#111418]">
            <div className="flex items-center gap-2 text-sm font-bold"><RefreshCw size={16} className="text-slate-400" />Live Canvas</div>
          </div>

          <div className="flex-1 p-4 bg-[#1e1e1e]">
            <div className="w-full h-full bg-white rounded shadow-2xl flex flex-col overflow-hidden">
              <div className="bg-gray-100 border-b border-gray-200 px-3 py-2 flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                  <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 bg-white h-4 rounded border border-gray-200" />
              </div>
              <div className="flex-1 flex items-center justify-center p-8 text-center">
                {status === 'Idle' && <div className="text-slate-400 italic">Canvas leer. Starte ein Projekt um Ergebnisse zu sehen.</div>}
                {status === 'Working' && (
                  <div className="flex flex-col items-center gap-4">
                    <RefreshCw size={48} className="text-primary animate-spin" />
                    <div className="text-slate-600 font-bold">Generiere Live-Vorschau...</div>
                  </div>
                )}
                {status === 'Success' && <div className="text-green-600 font-bold">Projekt erfolgreich erstellt!</div>}
              </div>
            </div>
          </div>

          <div className="h-48 border-t border-border-dark bg-[#111418] flex flex-col">
            <div className="px-4 py-2 border-b border-border-dark flex justify-between items-center">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Global Output Loop</span>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                <span className="text-[10px] text-green-500 font-mono">CONNECTED</span>
              </div>
            </div>
            <div className="p-4 overflow-y-auto terminal-scroll font-mono text-[10px] text-slate-400 flex flex-col gap-1">
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
