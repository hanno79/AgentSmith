/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Mission Control UI - Zentrale Steuerung und Agenten-Übersicht.
 * # ÄNDERUNG [31.01.2026]: Mission Control aus App.jsx ausgelagert.
 */

import React from 'react';
import { motion } from 'framer-motion';
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
  Search,
  Cpu,
  Lock,
  RotateCcw,
  FileText
} from 'lucide-react';
import AgentCard from './AgentCard';

const MissionControl = ({
  goal = '',
  onGoalChange,
  onDeploy,
  onReset,
  status = 'Idle',
  logs = [],
  activeAgents = {},
  agentData = {},
  onOpenOffice
}) => {
  const handleGoalChange = (event) => {
    if (typeof onGoalChange === 'function') {
      onGoalChange(event.target.value);
    }
  };

  const handleOpenOffice = (room) => {
    if (typeof onOpenOffice === 'function') {
      onOpenOffice(room);
    }
  };

  const orchestratorStatus = activeAgents?.orchestrator?.status || 'Idle';

  return (
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

        {/* ÄNDERUNG 25.01.2026: Command Input - Prominent über dem Orchestrator */}
        <div className="w-full flex items-center gap-3 p-4 rounded-xl bg-[#1c2127] border border-border-dark shadow-2xl">
          <PlusCircle className="text-slate-400 cursor-pointer hover:text-white flex-shrink-0" />
          <input
            value={goal}
            onChange={handleGoalChange}
            onKeyDown={(event) => event.key === 'Enter' && onDeploy?.()}
            placeholder="What should the team build today?"
            className="flex-1 bg-transparent border-none text-white focus:ring-0 text-base py-2"
            disabled={status === 'Working'}
          />
          <Mic size={20} className="text-slate-400 cursor-pointer hover:text-white flex-shrink-0" />

          {/* ÄNDERUNG 25.01.2026: Reset Button - Nur sichtbar wenn nicht Idle */}
          {status !== 'Idle' && (
            <button
              onClick={onReset}
              className="flex items-center gap-2 px-4 py-3 rounded-lg font-bold text-sm transition-all bg-red-600 hover:bg-red-700 text-white shadow-lg border-2 border-red-800 active:scale-95"
              title="Projekt zurücksetzen"
            >
              <RotateCcw size={16} />
              <span>Reset</span>
            </button>
          )}

          <button
            onClick={onDeploy}
            disabled={status === 'Working' || !goal}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-bold text-sm transition-all ${
              status === 'Working' ? 'bg-slate-700 text-slate-400' : 'bg-primary hover:bg-blue-600 text-white shadow-lg'
            }`}
          >
            <span>Deploy</span>
            <Send size={16} />
          </button>
        </div>

        {/* Orchestrator Center - ÄNDERUNG 25.01.2026: Höhe angepasst (wie AgentCards) */}
        <motion.div layout className="w-full rounded-xl border border-border-dark bg-[#1c2127] p-4 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-primary" />
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/30">
              <Scaling size={24} className="text-primary" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Orchestrator Desk</h3>
              <p className="text-primary text-xs animate-pulse">
                {orchestratorStatus !== 'Idle' ? 'Active: Routing Tasks...' : 'Ready for Instructions'}
              </p>
            </div>
          </div>
          <div className="bg-black/40 rounded-lg p-2.5 font-mono text-xs text-slate-300 h-20 overflow-y-auto terminal-scroll border border-white/5">
            {logs.filter(l => l.agent === 'Orchestrator').slice(-3).map((log, index) => (
              <div key={index} className="mb-1">
                <span className="text-slate-500 mr-2">[{log.event}]</span>
                <span>{log.message}</span>
              </div>
            ))}
            {logs.filter(l => l.agent === 'Orchestrator').length === 0 && (
              <div className="opacity-50">&gt; Awaiting initial command sequence...</div>
            )}
          </div>
        </motion.div>

        {/* Agent Grid - ÄNDERUNG 25.01.2026: Worker-Daten hinzugefügt */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AgentCard
            name="Researcher"
            icon={<Search size={24} />}
            color="cyan"
            status={activeAgents?.researcher?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Researcher')}
            onOpenOffice={() => handleOpenOffice('agent-researcher')}
            workers={agentData?.researcher?.workers || []}
          />
          <AgentCard
            name="Coder"
            icon={<Code2 size={24} />}
            color="blue"
            status={activeAgents?.coder?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Coder')}
            onOpenOffice={() => handleOpenOffice('agent-coder')}
            workers={agentData?.coder?.workers || []}
          />
          <AgentCard
            name="Designer"
            icon={<Palette size={24} />}
            color="pink"
            status={activeAgents?.designer?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Designer')}
            onOpenOffice={() => handleOpenOffice('agent-designer')}
            workers={agentData?.designer?.workers || []}
          />
          <AgentCard
            name="Reviewer"
            icon={<ShieldCheck size={24} />}
            color="yellow"
            status={activeAgents?.reviewer?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Reviewer')}
            onOpenOffice={() => handleOpenOffice('agent-reviewer')}
            workers={agentData?.reviewer?.workers || []}
          />
          <AgentCard
            name="Tester"
            icon={<Bug size={24} />}
            color="orange"
            status={activeAgents?.tester?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Tester')}
            onOpenOffice={() => handleOpenOffice('agent-tester')}
            workers={agentData?.tester?.workers || []}
          />
          <AgentCard
            name="Tech Architect"
            icon={<Cpu size={24} />}
            color="purple"
            status={activeAgents?.techarchitect?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'TechArchitect')}
            onOpenOffice={() => handleOpenOffice('agent-techstack')}
            workers={agentData?.techstack?.workers || []}
          />
          <AgentCard
            name="DB Designer"
            icon={<Database size={24} />}
            color="green"
            status={activeAgents?.dbdesigner?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'DBDesigner')}
            onOpenOffice={() => handleOpenOffice('agent-dbdesigner')}
            workers={agentData?.dbdesigner?.workers || []}
          />
          <AgentCard
            name="Security"
            icon={<Lock size={24} />}
            color="red"
            status={activeAgents?.security?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'Security')}
            onOpenOffice={() => handleOpenOffice('agent-security')}
            workers={agentData?.security?.workers || []}
          />
          {/* ÄNDERUNG 30.01.2026: Documentation Manager (Platinum) */}
          <AgentCard
            name="Documentation"
            icon={<FileText size={24} />}
            color="platinum"
            status={activeAgents?.documentationmanager?.status || 'Idle'}
            logs={logs.filter(l => l.agent === 'DocumentationManager' || l.agent === 'QualityGate')}
            onOpenOffice={() => handleOpenOffice('agent-documentation')}
            workers={agentData?.documentationmanager?.workers || []}
          />
        </div>
      </div>
    </main>
  );
};

export default MissionControl;
