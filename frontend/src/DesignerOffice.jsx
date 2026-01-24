import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Palette,
  History,
  Settings,
  Sparkles,
  Type,
  Shapes,
  Eye,
  Lightbulb,
  Send,
  RefreshCw,
  CheckCircle,
  ThumbsUp
} from 'lucide-react';

const DesignerOffice = ({ agentName = "Designer", status = "Idle", logs = [], onBack, color = "pink" }) => {
  const thoughtLogRef = useRef(null);

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
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-pink-500/20 text-pink-400 border border-pink-500/20 uppercase tracking-wide">
          Creative Mode
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide">
        {status}
      </span>
    );
  };

  // Mock design system data
  const colorPalette = [
    { name: 'Primary', hex: '#6366F1', tw: 'bg-indigo-500' },
    { name: 'Secondary', hex: '#EC4899', tw: 'bg-pink-500' },
    { name: 'Accent', hex: '#10B981', tw: 'bg-emerald-500' },
    { name: 'Neutral', hex: '#6B7280', tw: 'bg-gray-500' },
  ];

  const typography = [
    { name: 'Display', font: 'Inter', weight: '700', size: '48px' },
    { name: 'Heading', font: 'Inter', weight: '600', size: '24px' },
    { name: 'Body', font: 'Inter', weight: '400', size: '16px' },
  ];

  const atomicAssets = [
    { name: 'Button Primary', status: 'approved' },
    { name: 'Card Component', status: 'approved' },
    { name: 'Input Field', status: 'pending' },
    { name: 'Modal Dialog', status: 'wip' },
  ];

  // Visual quality score (mock data)
  const qualityScore = 87;

  // Format timestamp
  const formatTime = (index) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * 2);
    return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="bg-[#0d1117] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#30363d] px-6 py-3 bg-[#0d1117] z-20">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-8 flex items-center justify-center rounded bg-pink-500/20 text-pink-400 border border-pink-500/30">
              <Palette size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName} Agent
                {getStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">CREATIVE STATION ID: AGENT-03</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#161b22] border border-[#30363d]">
            <Sparkles size={14} className="text-pink-400" />
            <span className="text-xs font-semibold text-white">Design Iteration #42</span>
          </div>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#161b22] hover:bg-[#21262d] text-white transition-colors border border-[#30363d]">
            <History size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#161b22] hover:bg-[#21262d] text-white transition-colors border border-[#30363d]">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative bg-[#0d1117]">
        {/* Grid Background */}
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.03] pointer-events-none"></div>

        {/* Left Sidebar - Design System */}
        <aside className="w-[280px] border-r border-[#30363d] bg-[#0d1117]/50 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#30363d] flex justify-between items-center">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Sparkles size={16} className="text-pink-400" />
              Design System
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto designer-scrollbar p-4 space-y-5">
            {/* Color Palette */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Palette size={14} className="text-pink-400" />
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Palette</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {colorPalette.map((c, i) => (
                  <div key={i} className="bg-[#161b22] rounded-lg p-2 border border-[#30363d] group hover:border-pink-500/50 transition-colors">
                    <div className={`h-8 rounded ${c.tw} mb-2`}></div>
                    <p className="text-[10px] text-slate-400 font-medium">{c.name}</p>
                    <p className="text-[10px] text-slate-500 font-mono">{c.hex}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Typography */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Type size={14} className="text-pink-400" />
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Typography</span>
              </div>
              <div className="space-y-2">
                {typography.map((t, i) => (
                  <div key={i} className="bg-[#161b22] rounded-lg p-3 border border-[#30363d]">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-semibold text-white">{t.name}</span>
                      <span className="text-[10px] text-slate-500 font-mono">{t.size}</span>
                    </div>
                    <p className="text-[10px] text-slate-400">{t.font} / {t.weight}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Atomic Assets */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Shapes size={14} className="text-pink-400" />
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Atomic Assets</span>
              </div>
              <div className="space-y-2">
                {atomicAssets.map((a, i) => (
                  <div key={i} className="flex items-center justify-between bg-[#161b22] rounded-lg px-3 py-2 border border-[#30363d]">
                    <span className="text-xs text-slate-300">{a.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                      a.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                      a.status === 'wip' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-slate-500/20 text-slate-400'
                    }`}>{a.status}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content Area - Live UI Preview Canvas */}
        <main className="flex-1 flex flex-col min-w-0 z-10">
          <div className="flex-1 bg-[#161b22] flex flex-col relative overflow-hidden">
            {/* Canvas Header */}
            <div className="px-4 py-2 bg-[#0d1117] border-b border-[#30363d] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Eye size={14} className="text-pink-400" />
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Live UI Preview Canvas</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-500 font-mono">VIEWPORT: 1440x900</span>
                <div className="size-2 rounded-full bg-pink-500 animate-pulse"></div>
              </div>
            </div>

            {/* Canvas Area */}
            <div className="flex-1 p-8 flex items-center justify-center relative">
              {/* Scan line animation */}
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <motion.div
                  className="w-full h-1 bg-gradient-to-r from-transparent via-pink-500/40 to-transparent"
                  initial={{ y: -10 }}
                  animate={{ y: '100%' }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                />
              </div>

              {/* Preview Frame */}
              <div className="w-full max-w-[900px] h-full bg-[#0d1117] rounded-xl border border-[#30363d] shadow-2xl overflow-hidden">
                {/* Browser Chrome */}
                <div className="bg-[#21262d] border-b border-[#30363d] px-4 py-2 flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <div className="size-2.5 rounded-full bg-[#ff5f56]"></div>
                    <div className="size-2.5 rounded-full bg-[#ffbd2e]"></div>
                    <div className="size-2.5 rounded-full bg-[#27c93f]"></div>
                  </div>
                  <div className="flex-1 bg-[#0d1117] rounded px-3 py-1 text-[10px] text-slate-500 font-mono">
                    https://preview.design-agent.local
                  </div>
                </div>

                {/* Preview Content */}
                <div className="flex-1 p-8 flex flex-col items-center justify-center text-center h-[calc(100%-40px)]">
                  {status === 'Idle' ? (
                    <div className="text-slate-500">
                      <Palette size={64} className="mx-auto mb-4 opacity-20" />
                      <p className="text-sm">Awaiting design task...</p>
                      <p className="text-xs text-slate-600 mt-1">UI preview will render here</p>
                    </div>
                  ) : (
                    <div className="w-full h-full">
                      {/* Placeholder design elements */}
                      <div className="space-y-4 animate-pulse">
                        <div className="h-8 bg-gradient-to-r from-pink-500/20 to-pink-400/20 rounded w-1/3 mx-auto"></div>
                        <div className="h-4 bg-slate-700/50 rounded w-2/3 mx-auto"></div>
                        <div className="h-4 bg-slate-700/30 rounded w-1/2 mx-auto"></div>
                        <div className="grid grid-cols-3 gap-4 mt-8 px-12">
                          <div className="h-32 bg-gradient-to-br from-pink-500/10 to-pink-400/10 rounded-lg border border-pink-500/20"></div>
                          <div className="h-32 bg-gradient-to-br from-pink-500/10 to-pink-400/10 rounded-lg border border-pink-500/20"></div>
                          <div className="h-32 bg-gradient-to-br from-pink-500/10 to-pink-400/10 rounded-lg border border-pink-500/20"></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Footer - Iteration Progress & Actions */}
          <div className="p-4 bg-[#0d1117] border-t border-[#30363d] flex items-center justify-between gap-4">
            {/* Iteration Progress */}
            <div className="flex-1 max-w-xs">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-400">Iteration Progress</span>
                <span className="text-pink-400 font-mono">72%</span>
              </div>
              <div className="h-1.5 bg-[#21262d] rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-pink-500 to-pink-400 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: '72%' }}
                  transition={{ duration: 1 }}
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-colors bg-[#21262d] hover:bg-[#30363d] text-slate-300 border border-[#30363d]">
                <RefreshCw size={16} />
                Request Variation
              </button>
              <button className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-bold transition-colors bg-gradient-to-r from-pink-600 to-pink-500 hover:from-pink-500 hover:to-pink-400 text-white shadow-[0_0_20px_rgba(236,72,153,0.3)]">
                <ThumbsUp size={16} />
                Approve Style
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Quality Score & Thought Process */}
        <aside className="w-[320px] border-l border-[#30363d] bg-[#0d1117]/50 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#30363d]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Eye size={16} className="text-pink-400" />
              Visual Quality Score
            </h3>
          </div>

          {/* Quality Score Donut Chart */}
          <div className="p-5 border-b border-[#30363d]">
            <div className="relative flex items-center justify-center">
              <svg className="w-32 h-32 transform -rotate-90">
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  stroke="#21262d"
                  strokeWidth="8"
                  fill="none"
                />
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  stroke="url(#gradient)"
                  strokeWidth="8"
                  fill="none"
                  strokeDasharray={`${(qualityScore / 100) * 351.86} 351.86`}
                  strokeLinecap="round"
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#ec4899" />
                    <stop offset="100%" stopColor="#f472b6" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-3xl font-black text-white">{qualityScore}</span>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider">Score</span>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-sm font-bold text-green-400">92</div>
                <div className="text-[9px] text-slate-500 uppercase">Contrast</div>
              </div>
              <div>
                <div className="text-sm font-bold text-yellow-400">78</div>
                <div className="text-[9px] text-slate-500 uppercase">Hierarchy</div>
              </div>
              <div>
                <div className="text-sm font-bold text-pink-400">91</div>
                <div className="text-[9px] text-slate-500 uppercase">Consistency</div>
              </div>
            </div>
          </div>

          {/* Agent Thought Process */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="px-4 py-2 border-b border-[#30363d] flex justify-between items-center">
              <h4 className="text-xs font-bold text-pink-400 uppercase tracking-wider flex items-center gap-2">
                <Lightbulb size={12} className="animate-pulse" />
                Agent Thought Process
              </h4>
              <span className="text-[10px] text-slate-500 font-mono">STREAMING</span>
            </div>
            <div
              ref={thoughtLogRef}
              className="flex-1 p-4 overflow-y-auto designer-scrollbar font-mono text-xs space-y-2"
            >
              {logs.length === 0 ? (
                <div className="text-slate-500 opacity-50 italic">
                  Waiting for creative input...
                </div>
              ) : (
                logs.map((log, i) => (
                  <div
                    key={i}
                    className={`flex gap-2 ${
                      log.event === 'Error' ? 'text-red-400' :
                      log.event === 'Success' ? 'text-green-400' :
                      i === logs.length - 1 ? 'text-white border-l-2 border-pink-500 pl-2 bg-pink-500/5 py-1' :
                      'text-slate-400'
                    }`}
                  >
                    <span className="text-slate-600 shrink-0">[{formatTime(i)}]</span>
                    <p>{log.message}</p>
                  </div>
                ))
              )}
              {logs.length > 0 && (
                <div className="text-slate-500 opacity-50 italic flex items-center gap-2">
                  <span className="inline-block w-1.5 h-1.5 bg-pink-500 rounded-full animate-pulse"></span>
                  Conceptualizing...
                </div>
              )}
            </div>
          </div>

          {/* Style Refinement Input */}
          <div className="p-4 border-t border-[#30363d] bg-[#0d1117]">
            <div className="flex items-center gap-2 bg-[#161b22] rounded-lg border border-[#30363d] p-2">
              <input
                type="text"
                placeholder="Refine style direction..."
                className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
              />
              <button className="p-1.5 rounded bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 transition-colors">
                <Send size={14} />
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default DesignerOffice;
