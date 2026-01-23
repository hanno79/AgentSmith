import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Terminal,
  Settings,
  Bell,
  Wifi,
  Database,
  Send,
  Mic,
  PlusCircle,
  BarChart3,
  LayoutDashboard,
  Code2,
  Palette,
  ShieldCheck,
  Bug,
  Scaling,
  RefreshCw,
  ExternalLink,
  Search,
  Cpu,
  Lock
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const App = () => {
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

  const logEndRef = useRef(null);
  const ws = useRef(null);

  useEffect(() => {
    // WebSocket Setup
    ws.current = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs((prev) => [...prev, data]);

      // Update Agent Status
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

      if (data.agent === 'System' && data.event === 'Success') setStatus('Success');
      if (data.agent === 'System' && data.event === 'Failure') setStatus('Error');
    };

    return () => ws.current?.close();
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleDeploy = async () => {
    if (!goal) return;
    setStatus('Working');
    setLogs([]);
    try {
      await axios.post('http://localhost:8000/run', { goal });
    } catch (err) {
      console.error("Failed to start task:", err);
      setLogs(prev => [...prev, { agent: 'System', event: 'Error', message: 'Could not connect to backend.' }]);
      setStatus('Error');
    }
  };

  return (
    <div className="bg-background-dark text-white font-sans overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between border-b border-border-dark px-6 py-3 bg-[#111418] z-20">
        <div className="flex items-center gap-4">
          <div className="p-2 rounded bg-primary/20 text-primary">
            <LayoutDashboard size={24} />
          </div>
          <div>
            <h2 className="text-lg font-bold leading-tight">Agent Office</h2>
            <div className="text-xs text-slate-400 font-medium">PROJECT: ALPHA-WEB-INTEGRATION</div>
          </div>
        </div>

        <div className="flex gap-3 items-center">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1c2127] border border-[#283039]">
            <Wifi size={14} className="text-green-500" />
            <span className="text-xs font-semibold text-white">System Online</span>
          </div>
          <button className="h-9 px-4 bg-primary hover:bg-blue-600 text-white text-sm font-bold rounded-lg transition-colors">
            Connect Agent
          </button>
          <Settings size={20} className="text-slate-400 cursor-pointer hover:text-white" />
          <Bell size={20} className="text-slate-400 cursor-pointer hover:text-white" />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Side: Mission Control */}
        <main className="flex-1 overflow-y-auto relative flex flex-col items-center bg-[#101922] p-6 lg:p-8">
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
            <motion.div
              layout
              className="w-full rounded-xl border border-border-dark bg-[#1c2127] p-6 shadow-2xl relative overflow-hidden group"
            >
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
                  <div key={i} className="mb-1">
                    <span className="text-slate-500 mr-2">[{l.event}]</span>
                    <span>{l.message}</span>
                  </div>
                ))}
                {logs.filter(l => l.agent === 'Orchestrator').length === 0 && (
                  <div className="opacity-50">&gt; Awaiting initial command sequence...</div>
                )}
              </div>
            </motion.div>

            {/* Agent Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <AgentCard
                name="Researcher"
                icon={<Search size={24} />}
                color="cyan"
                status={activeAgents.researcher.status}
                logs={logs.filter(l => l.agent === 'Researcher')}
              />
              <AgentCard
                name="Coder"
                icon={<Code2 size={24} />}
                color="blue"
                status={activeAgents.coder.status}
                logs={logs.filter(l => l.agent === 'Coder')}
              />
              <AgentCard
                name="Designer"
                icon={<Palette size={24} />}
                color="purple"
                status={activeAgents.designer.status}
                logs={logs.filter(l => l.agent === 'Designer')}
              />
              <AgentCard
                name="Reviewer"
                icon={<ShieldCheck size={24} />}
                color="yellow"
                status={activeAgents.reviewer.status}
                logs={logs.filter(l => l.agent === 'Reviewer')}
              />
              <AgentCard
                name="Tester"
                icon={<Bug size={24} />}
                color="red"
                status={activeAgents.tester.status}
                logs={logs.filter(l => l.agent === 'Tester')}
              />
              <AgentCard
                name="Tech Architect"
                icon={<Cpu size={24} />}
                color="indigo"
                status={activeAgents.techarchitect.status}
                logs={logs.filter(l => l.agent === 'TechArchitect')}
              />
              <AgentCard
                name="DB Designer"
                icon={<Database size={24} />}
                color="green"
                status={activeAgents.dbdesigner.status}
                logs={logs.filter(l => l.agent === 'DBDesigner')}
              />
              <AgentCard
                name="Security"
                icon={<Lock size={24} />}
                color="orange"
                status={activeAgents.security.status}
                logs={logs.filter(l => l.agent === 'Security')}
              />
            </div>
          </div>

          {/* Floating Command Bar */}
          <div className="fixed bottom-8 w-[90%] max-w-[800px] flex items-center gap-2 p-2 rounded-xl bg-[#1c2127]/90 backdrop-blur-md border border-border-dark shadow-2xl ring-1 ring-white/5 z-50">
            <PlusCircle className="ml-2 text-slate-400 cursor-pointer hover:text-white" />
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleDeploy()}
              placeholder="What should the team build today?"
              className="flex-1 bg-transparent border-none text-white focus:ring-0 text-sm"
              disabled={status === 'Working'}
            />
            <Mic size={20} className="text-slate-400 cursor-pointer hover:text-white" />
            <button
              onClick={handleDeploy}
              disabled={status === 'Working' || !goal}
              className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold text-sm transition-all ${status === 'Working'
                ? 'bg-slate-700 text-slate-400'
                : 'bg-primary hover:bg-blue-600 text-white shadow-lg'
                }`}
            >
              <span>Deploy</span>
              <Send size={16} />
            </button>
          </div>
        </main>

        {/* Right Panel: Logs & Canvas */}
        <aside className="w-[400px] border-l border-border-dark bg-[#0d1216] hidden 2xl:flex flex-col z-20">
          <div className="h-14 border-b border-border-dark flex items-center justify-between px-4 bg-[#111418]">
            <div className="flex items-center gap-2 text-sm font-bold">
              <RefreshCw size={16} className="text-slate-400" />
              Live Canvas
            </div>
            <ExternalLink size={16} className="text-slate-400 cursor-pointer hover:text-white" />
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
                {status === 'Idle' && <div className="text-slate-400 italic">Canvas empty. Start a project to see results.</div>}
                {status === 'Working' && (
                  <div className="flex flex-col items-center gap-4">
                    <RefreshCw size={48} className="text-primary animate-spin" />
                    <div className="text-slate-600 font-bold">Generating Live Preview...</div>
                  </div>
                )}
                {status === 'Success' && (
                  <div className="text-green-600 font-bold">Project Built Successfully!</div>
                )}
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

const AgentCard = ({ name, icon, color, status, logs }) => {
  const colors = {
    blue: 'border-blue-500/40 text-blue-400 bg-blue-500/10',
    purple: 'border-purple-500/40 text-purple-400 bg-purple-500/10',
    yellow: 'border-yellow-500/40 text-yellow-400 bg-yellow-500/10',
    red: 'border-red-500/40 text-red-400 bg-red-500/10',
    green: 'border-green-500/40 text-green-400 bg-green-500/10',
    orange: 'border-orange-500/40 text-orange-400 bg-orange-500/10',
    cyan: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10',
    indigo: 'border-indigo-500/40 text-indigo-400 bg-indigo-500/10',
  };

  const glowStyles = {
    blue: '0 0 30px rgba(59, 130, 246, 0.8), 0 0 15px rgba(59, 130, 246, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    purple: '0 0 30px rgba(168, 85, 247, 0.8), 0 0 15px rgba(168, 85, 247, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    yellow: '0 0 30px rgba(234, 179, 8, 0.8), 0 0 15px rgba(234, 179, 8, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    red: '0 0 30px rgba(239, 68, 68, 0.8), 0 0 15px rgba(239, 68, 68, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    green: '0 0 30px rgba(34, 197, 94, 0.8), 0 0 15px rgba(34, 197, 94, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    orange: '0 0 30px rgba(249, 115, 22, 0.8), 0 0 15px rgba(249, 115, 22, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    cyan: '0 0 30px rgba(6, 182, 212, 0.8), 0 0 15px rgba(6, 182, 212, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
    indigo: '0 0 30px rgba(79, 70, 229, 0.8), 0 0 15px rgba(79, 70, 229, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  };

  const finishedStates = ['Idle', 'Success', 'Failure', 'Error', 'Result', 'Files', 'OK'];
  const isActive = status && !finishedStates.includes(status);

  const borderColors = {
    blue: '#3b82f6',
    purple: '#a855f7',
    yellow: '#eab308',
    red: '#ef4444',
    green: '#22c55e',
    orange: '#f97316',
    cyan: '#06b6d4',
    indigo: '#4f46e5',
  };

  return (
    <motion.div
      initial={false}
      animate={{
        boxShadow: isActive ? glowStyles[color] : 'none',
        borderColor: isActive ? borderColors[color] : '',
      }}
      transition={{ duration: 0.6, repeat: isActive ? Infinity : 0, repeatType: 'reverse', ease: 'easeInOut' }}
      className={`p-4 rounded-xl border ${colors[color].split(' ')[0]} bg-[#1c2127] transition-all relative overflow-hidden group ${isActive ? 'ring-1 ring-white/10' : ''}`}
    >
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        {React.cloneElement(icon, { size: 64 })}
      </div>
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-slate-800 border border-border-dark ${colors[color].split(' ')[1]}`}>
            {icon}
          </div>
          <div>
            <h4 className="font-bold uppercase tracking-tight">{name}</h4>
            <p className="text-[10px] text-slate-500">Node Status: Online</p>
          </div>
        </div>
        <div className={`px-2 py-0.5 rounded-full border text-[9px] font-bold uppercase transition-all ${status !== 'Idle' ? colors[color] : 'bg-[#283039] border-border-dark text-slate-500'
          }`}>
          {status}
        </div>
      </div>

      <div className="bg-black/50 rounded-lg p-3 h-24 overflow-y-auto terminal-scroll font-mono text-[10px] border border-white/5 relative z-10">
        {logs.slice(-5).map((l, i) => (
          <div key={i} className="mb-1">
            <span className="opacity-50 mr-2">&gt;</span>
            <span className="text-slate-300">{l.message}</span>
          </div>
        ))}
        {logs.length === 0 && <div className="text-slate-600 italic mt-6 text-center">Waiting for task...</div>}
      </div>
    </motion.div>
  );
};

export default App;
