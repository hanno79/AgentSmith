import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Terminal,
  CheckCircle,
  Circle,
  GripVertical,
  Brain,
  Code,
  Cpu,
  TrendingUp,
  TrendingDown,
  History,
  Settings,
  StopCircle,
  MessageSquarePlus
} from 'lucide-react';

const CoderOffice = ({ agentName = "Coder", status = "Idle", logs = [], onBack, color = "blue" }) => {
  const thoughtLogRef = useRef(null);
  const codeOutputRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (thoughtLogRef.current) {
      thoughtLogRef.current.scrollTop = thoughtLogRef.current.scrollHeight;
    }
  }, [logs]);

  // Status badge styling
  const getStatusBadge = () => {
    const isActive = status !== 'Idle' && status !== 'Success' && status !== 'Failure';
    if (isActive) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-green-500/20 text-green-400 border border-green-500/20 uppercase tracking-wide">
          Active
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide">
        {status}
      </span>
    );
  };

  // Mock task data - in real implementation, this would come from backend
  const tasks = [
    { id: 'T-8821-A', title: 'Generate Hero Component', status: 'current', steps: [
      { text: 'Analyze requirements', done: true },
      { text: 'Setup props interface', done: true },
      { text: 'Implement responsive layout', current: true },
      { text: 'Add tailwind classes', done: false },
    ]},
    { id: 'T-8822', title: 'Create Navigation Bar', status: 'next', dependency: 'Designer Assets' },
    { id: 'T-8823', title: 'Hook up State Management', status: 'queued' },
  ];

  // Extract code from logs (messages containing code blocks)
  const getLatestCode = () => {
    const codeLog = [...logs].reverse().find(l =>
      l.message && (l.message.includes('```') || l.message.includes('def ') || l.message.includes('function ') || l.message.includes('class '))
    );
    return codeLog?.message || `// Waiting for code generation...
// The Coder Agent will output code here when processing tasks.

import React from 'react';

export const Component = () => {
  return (
    <div className="flex items-center justify-center">
      <span>Loading...</span>
    </div>
  );
};`;
  };

  // Format timestamp
  const formatTime = (index) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * 2);
    return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-8 flex items-center justify-center rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
              <Terminal size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName} Agent
                {getStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-02</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155]">
            <Cpu size={14} className="text-green-500" />
            <span className="text-xs font-semibold text-white">Running Task #{tasks[0]?.id?.split('-')[1] || '0000'}</span>
          </div>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#1e293b] hover:bg-[#334155] text-white transition-colors border border-[#334155]">
            <History size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#1e293b] hover:bg-[#334155] text-white transition-colors border border-[#334155]">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative bg-[#0f172a]">
        {/* Grid Background */}
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.05] pointer-events-none"></div>

        {/* Left Sidebar - Task Queue */}
        <aside className="w-[300px] border-r border-[#334155] bg-[#0f172a]/50 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <CheckCircle size={16} className="text-blue-400" />
              Task Queue
            </h3>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">{tasks.length} Tasks</span>
          </div>

          <div className="flex-1 overflow-y-auto office-scrollbar p-4 space-y-4">
            {/* Current Task */}
            {tasks.filter(t => t.status === 'current').map(task => (
              <div key={task.id} className="relative group">
                <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg opacity-30 blur-sm"></div>
                <div className="relative bg-[#1e293b] p-3 rounded-lg border border-blue-500/50 shadow-lg">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-blue-400">CURRENT FOCUS</span>
                    <span className="text-[10px] text-slate-400 font-mono">ID: {task.id}</span>
                  </div>
                  <h4 className="text-sm font-semibold text-white mb-2">{task.title}</h4>
                  <div className="space-y-2">
                    {task.steps?.map((step, i) => (
                      <div key={i} className={`flex items-center gap-2 text-xs ${step.current ? 'text-white' : step.done ? 'text-slate-300' : 'text-slate-500'}`}>
                        {step.done ? (
                          <CheckCircle size={14} className="text-green-400" />
                        ) : step.current ? (
                          <div className="size-3.5 flex items-center justify-center">
                            <div className="size-2 bg-blue-500 rounded-full animate-pulse"></div>
                          </div>
                        ) : (
                          <Circle size={14} />
                        )}
                        <span className={step.current ? 'font-medium' : ''}>{step.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            {/* Queued Tasks */}
            {tasks.filter(t => t.status !== 'current').map(task => (
              <div key={task.id} className="opacity-60 hover:opacity-100 transition-opacity">
                <div className="bg-[#1e293b]/50 p-3 rounded-lg border border-[#334155]">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase">
                      {task.status === 'next' ? 'Next' : 'Queued'}
                    </span>
                    <GripVertical size={14} className="text-slate-500" />
                  </div>
                  <h4 className="text-sm font-medium text-slate-300">{task.title}</h4>
                  {task.dependency && (
                    <p className="text-[11px] text-slate-500 mt-1">Dependant on: {task.dependency}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Progress Bar */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full w-[65%] bg-blue-500 rounded-full"></div>
              </div>
              <span>65%</span>
            </div>
            <p className="text-[10px] text-slate-500 mt-1 text-center">Batch Progress</p>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10">
          {/* Thought Process Panel */}
          <div className="h-[35%] border-b border-[#334155] bg-[#1e293b]/30 flex flex-col">
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/50 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
                <Brain size={14} className="animate-pulse" />
                Agent Thought Process
              </h3>
              <span className="text-[10px] text-slate-500 font-mono">LOG_STREAM: ACTIVE</span>
            </div>
            <div
              ref={thoughtLogRef}
              className="flex-1 p-4 overflow-y-auto office-scrollbar font-mono text-xs space-y-3"
            >
              {logs.length === 0 ? (
                <div className="flex gap-3 text-slate-400 opacity-50">
                  <span className="text-slate-600 w-16 shrink-0">...</span>
                  <p className="italic">Waiting for agent activity...</p>
                </div>
              ) : (
                logs.map((log, i) => (
                  <div
                    key={i}
                    className={`flex gap-3 ${
                      log.event === 'Error' ? 'text-red-400' :
                      log.event === 'Success' ? 'text-green-400' :
                      log.event === 'Warning' ? 'text-yellow-400' :
                      i === logs.length - 1 ? 'text-white border-l-2 border-cyan-500 pl-3 bg-cyan-500/5 py-1' :
                      'text-slate-300'
                    }`}
                  >
                    <span className="text-slate-600 w-16 shrink-0">[{formatTime(i)}]</span>
                    <p>{log.message}</p>
                  </div>
                ))
              )}
              {logs.length > 0 && (
                <div className="flex gap-3 text-slate-400 opacity-50">
                  <span className="text-slate-600 w-16 shrink-0">...</span>
                  <p className="italic">Thinking...</p>
                </div>
              )}
            </div>
          </div>

          {/* Code Output Panel */}
          <div className="flex-1 bg-[#0d1117] flex flex-col relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
              <Code size={120} />
            </div>
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal size={14} className="text-slate-500" />
                <span className="text-xs font-mono text-slate-300">src/components/Generated.tsx</span>
              </div>
              <div className="flex gap-1.5">
                <div className="size-2.5 rounded-full bg-[#334155]"></div>
                <div className="size-2.5 rounded-full bg-[#334155]"></div>
              </div>
            </div>
            <div
              ref={codeOutputRef}
              className="flex-1 p-6 overflow-y-auto office-scrollbar font-mono text-sm leading-6"
            >
              <pre className="text-slate-300 whitespace-pre-wrap">{getLatestCode()}</pre>
              <span className="animate-pulse text-blue-400">|</span>
            </div>
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 group">
                <StopCircle size={16} className="group-hover:scale-110 transition-transform" />
                Interrupt Agent
              </button>
              <button className="flex-[2] bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(37,99,235,0.3)]">
                <MessageSquarePlus size={16} />
                Add Context / Modify Instructions
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Performance Metrics */}
        <aside className="w-[320px] border-l border-[#334155] bg-[#0f172a]/50 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <TrendingUp size={16} className="text-purple-400" />
              Performance Metrics
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto office-scrollbar p-5 space-y-6">
            {/* Processing Speed */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Cpu size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Processing Speed</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white">48.2</span>
                <span className="text-sm text-slate-400 font-medium">tok/s</span>
              </div>
              <div className="mt-3 h-1.5 w-full bg-[#0f172a] rounded-full overflow-hidden">
                <div className="h-full w-[70%] bg-gradient-to-r from-blue-500 to-green-400 rounded-full"></div>
              </div>
            </div>

            {/* Memory & Success Rate */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155]">
                <p className="text-[10px] text-slate-400 uppercase font-semibold mb-1">Memory Usage</p>
                <div className="text-lg font-bold text-white mb-1">1.2 GB</div>
                <div className="text-[10px] text-green-400 flex items-center gap-1">
                  <TrendingDown size={12} />
                  stable
                </div>
              </div>
              <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155]">
                <p className="text-[10px] text-slate-400 uppercase font-semibold mb-1">Success Rate</p>
                <div className="text-lg font-bold text-white mb-1">98.5%</div>
                <div className="text-[10px] text-green-400 flex items-center gap-1">
                  <TrendingUp size={12} />
                  +2.1%
                </div>
              </div>
            </div>

            {/* Active Model */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-bold text-slate-300">ACTIVE MODEL</span>
                <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 text-[10px] rounded font-mono border border-purple-500/30">GPT-4-Turbo</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Context Window</span>
                  <span className="text-slate-300 font-mono">128k</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Temperature</span>
                  <span className="text-slate-300 font-mono">0.7</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Top P</span>
                  <span className="text-slate-300 font-mono">1.0</span>
                </div>
              </div>
            </div>

            {/* Compute Load Chart */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] h-32 flex flex-col justify-between">
              <p className="text-xs text-slate-400 uppercase font-semibold">Compute Load (1h)</p>
              <div className="flex items-end justify-between gap-1 h-16 px-1">
                {[40, 60, 50, 80, 70, 90, 60, 75, 85, 95].map((height, i) => (
                  <div
                    key={i}
                    className={`w-2 rounded-sm ${i === 9 ? 'bg-blue-400 shadow-[0_0_10px_rgba(96,165,250,0.5)]' : 'bg-blue-500'}`}
                    style={{ height: `${height}%`, opacity: 0.2 + (i * 0.08) }}
                  ></div>
                ))}
              </div>
            </div>
          </div>

          {/* Footer Link */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a] text-center">
            <button className="text-[11px] text-blue-400 hover:text-blue-300 underline underline-offset-2">
              View Detailed Logs
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default CoderOffice;
