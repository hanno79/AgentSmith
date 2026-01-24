import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Bug,
  Shield,
  Clock,
  RefreshCw,
  Settings,
  Bell,
  Activity,
  TrendingUp,
  Gauge,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Brain,
  Terminal,
  FileCheck
} from 'lucide-react';

const TesterOffice = ({ agentName = "Tester", status = "Idle", logs = [], onBack, color = "orange" }) => {
  const terminalRef = useRef(null);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  // Status badge styling
  const getStatusBadge = () => {
    const isActive = status !== 'Idle' && status !== 'Success' && status !== 'Failure';
    if (isActive) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] bg-green-500/20 text-green-400 border border-green-500/20 uppercase tracking-wide flex items-center gap-1">
          <Activity size={10} className="animate-pulse" />
          Suite Active
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide">
        {status}
      </span>
    );
  };

  // Mock defects data
  const defects = [
    { id: 'bug-4921', severity: 'CRITICAL', title: 'Auth Token Timeout', time: '12m ago', color: 'red' },
    { id: 'bug-4882', severity: 'HIGH', title: 'Checkout Flow Deadlock', time: '1h ago', color: 'orange' },
    { id: 'bug-4810', severity: 'NORMAL', title: 'Footer Alignment Flex', time: '3h ago', color: 'blue' },
    { id: 'bug-4811', severity: 'NORMAL', title: 'Mobile Menu Z-Index', time: '4h ago', color: 'blue' },
  ];

  // Mock coverage data
  const coverage = [
    { path: '/src/auth', percent: 98, color: 'green' },
    { path: '/src/api/routes', percent: 92, color: 'green' },
    { path: '/src/components/ui', percent: 74, color: 'orange' },
    { path: '/src/legacy', percent: 32, color: 'red' },
  ];

  // Format timestamp
  const formatTime = (index) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * 2);
    return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const getSeverityColors = (severity) => {
    switch (severity) {
      case 'CRITICAL': return { bg: 'bg-[#231818]', border: 'border-red-900/30 hover:border-red-500/50', text: 'text-red-400' };
      case 'HIGH': return { bg: 'bg-[#231e18]', border: 'border-orange-900/30 hover:border-orange-500/50', text: 'text-orange-400' };
      default: return { bg: 'bg-[#1c2127]', border: 'border-[#283039] hover:border-slate-500', text: 'text-blue-400' };
    }
  };

  return (
    <div className="bg-[#101922] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#283039] px-6 py-3 bg-[#111418] z-20">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="size-8 flex items-center justify-center rounded bg-orange-500/20 text-orange-400 border border-orange-500/20">
            <Bug size={18} />
          </div>
          <div>
            <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
              {agentName} Agent Workstation
              {getStatusBadge()}
            </h2>
            <div className="text-xs text-slate-400 font-medium tracking-wide flex items-center gap-2">
              <span>PROJECT: ALPHA-1</span>
              <span className="text-slate-600">/</span>
              <span className="text-orange-400">NODE: TEST-04</span>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <button className="flex cursor-pointer items-center justify-center overflow-hidden rounded-lg h-9 px-4 bg-[#283039] hover:bg-[#3b4754] text-white text-sm font-bold leading-normal transition-colors border border-[#283039]">
            <span>Logs</span>
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#283039] hover:bg-[#3b4754] text-white transition-colors border border-[#283039]">
            <Settings size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#283039] hover:bg-[#3b4754] text-white transition-colors border border-[#283039]">
            <Bell size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden relative flex flex-col bg-[#101922]">
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.05] pointer-events-none"></div>

        <div className="flex-1 w-full max-w-[1920px] mx-auto p-4 lg:p-6 grid grid-cols-12 gap-6 overflow-y-auto tester-scrollbar z-10">

          {/* Left Column */}
          <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
            {/* Active Defects */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col overflow-hidden h-1/2 min-h-[300px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Bug size={16} className="text-orange-400" />
                  Active Defects
                </h3>
                <span className="bg-orange-500/20 text-orange-400 text-[10px] px-2 py-0.5 rounded border border-orange-500/20">
                  {defects.length} Open
                </span>
              </div>
              <div className="flex-1 overflow-y-auto tester-scrollbar p-2">
                <div className="space-y-2">
                  {defects.map((defect) => {
                    const colors = getSeverityColors(defect.severity);
                    return (
                      <div
                        key={defect.id}
                        className={`p-3 rounded ${colors.bg} border ${colors.border} transition-colors cursor-pointer group`}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className={`text-xs font-bold ${colors.text}`}>{defect.severity}</span>
                          <span className="text-[10px] text-slate-500">#{defect.id}</span>
                        </div>
                        <p className="text-sm text-slate-200 font-medium mb-1 group-hover:text-white">{defect.title}</p>
                        <div className="text-[10px] text-slate-500 flex items-center gap-1">
                          <Clock size={10} /> {defect.time}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Coverage Map */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col flex-1 min-h-[250px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Shield size={16} className="text-green-400" />
                  Coverage Map
                </h3>
                <span className="text-xs font-mono text-slate-400">88.4%</span>
              </div>
              <div className="p-4 flex flex-col gap-4 overflow-y-auto tester-scrollbar">
                {coverage.map((item, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-300 font-mono">{item.path}</span>
                      <span className={`font-bold ${item.color === 'green' ? 'text-green-400' : item.color === 'orange' ? 'text-orange-400' : 'text-red-400'}`}>
                        {item.percent}%
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-[#111418] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${item.color === 'green' ? 'bg-green-500' : item.color === 'orange' ? 'bg-orange-500' : 'bg-red-500'}`}
                        style={{ width: `${item.percent}%` }}
                      />
                    </div>
                  </div>
                ))}
                {/* Topography placeholder */}
                <div className="mt-auto h-24 border border-[#283039] rounded bg-[#111418] relative overflow-hidden opacity-60">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-[10px] text-slate-500">Topography View</div>
                  </div>
                  <div className="absolute top-2 left-2 size-8 bg-green-500/20 rounded"></div>
                  <div className="absolute top-2 left-12 size-4 bg-green-500/20 rounded"></div>
                  <div className="absolute top-8 left-6 size-12 bg-orange-500/20 rounded"></div>
                  <div className="absolute bottom-2 right-4 size-10 bg-red-500/20 rounded"></div>
                </div>
              </div>
            </div>
          </div>

          {/* Center Column */}
          <div className="col-span-12 lg:col-span-6 flex flex-col gap-6">
            {/* Control Bar */}
            <div className="flex items-center justify-between bg-[#1c2127] p-3 rounded-xl border border-[#283039] shadow-lg">
              <div className="flex items-center gap-4">
                <button className="flex items-center gap-2 px-4 py-2 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 text-sm font-bold rounded-lg transition-all group">
                  <RefreshCw size={16} className="group-hover:rotate-180 transition-transform" />
                  Run Full Audit
                </button>
                <div className="h-6 w-px bg-[#283039]"></div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Stress Test</span>
                  <div className="w-9 h-5 bg-[#111418] border border-slate-600 rounded-full relative cursor-pointer">
                    <div className="absolute top-[2px] left-[2px] size-4 bg-slate-400 rounded-full transition-transform"></div>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
                <span className="size-2 rounded-full bg-green-500 animate-pulse"></span>
                <span>LIVE CONNECTION</span>
              </div>
            </div>

            {/* Test Runner Terminal */}
            <div className="flex-1 bg-[#0d1116] rounded-xl border border-[#283039] relative flex flex-col shadow-2xl overflow-hidden">
              <div className="bg-[#151a20] border-b border-[#283039] px-4 py-2 flex justify-between items-center">
                <div className="flex gap-2 items-center">
                  <Terminal size={16} className="text-slate-500" />
                  <span className="text-xs font-bold text-slate-300">Test_Runner_v4.2.exe</span>
                </div>
                <div className="flex gap-1.5">
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                </div>
              </div>

              {/* Analysis Banner */}
              <div className="relative bg-[#111418] border-b border-[#283039] p-4">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-orange-500/10 to-transparent animate-pulse pointer-events-none z-0"></div>
                <div className="relative z-10 flex items-start gap-3">
                  <div className="mt-1">
                    <div className="size-6 rounded bg-orange-500/20 flex items-center justify-center text-orange-400 animate-pulse">
                      <Brain size={14} />
                    </div>
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-white">Analyzing Failure Pattern...</h4>
                      <span className="text-[10px] font-mono text-orange-400 bg-orange-500/10 px-2 rounded border border-orange-500/20">HEURISTIC SCAN</span>
                    </div>
                    <div className="space-y-1">
                      <div className="h-2 w-3/4 bg-slate-700/50 rounded overflow-hidden">
                        <div className="h-full bg-orange-500/50 w-2/3 animate-pulse"></div>
                      </div>
                      <div className="h-2 w-1/2 bg-slate-700/50 rounded"></div>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-2">&gt; Detecting patterns in test failures...</p>
                  </div>
                </div>
              </div>

              {/* Terminal Output */}
              <div
                ref={terminalRef}
                className="flex-1 overflow-y-auto tester-scrollbar p-4 font-mono text-xs space-y-1 text-slate-400"
              >
                {logs.length === 0 ? (
                  <>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span>Waiting for test execution...</span></div>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span className="text-green-400">✓ Test runner ready</span></div>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span className="animate-pulse">_</span></div>
                  </>
                ) : (
                  <>
                    {logs.map((log, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-slate-600">[{formatTime(i)}]</span>
                        <span className={
                          log.event === 'Error' ? 'text-red-400' :
                          log.event === 'Success' ? 'text-green-400' :
                          log.event === 'Warning' ? 'text-orange-400' :
                          'text-slate-300'
                        }>
                          {log.event === 'Success' && '✓ '}
                          {log.event === 'Error' && '✖ '}
                          {log.event === 'Warning' && '! '}
                          {log.message}
                        </span>
                      </div>
                    ))}
                    <div className="flex gap-2"><span className="text-slate-600">[{formatTime(logs.length)}]</span> <span className="animate-pulse">_</span></div>
                  </>
                )}
              </div>

              {/* Status Bar */}
              <div className="h-1 w-full bg-[#111418] relative">
                <div className="absolute inset-y-0 left-0 bg-orange-500 w-full animate-pulse opacity-50 shadow-[0_0_15px_rgba(249,115,22,0.5)]"></div>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
            {/* System Stability */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col h-1/2 min-h-[300px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <TrendingUp size={16} className="text-blue-400" />
                  System Stability
                </h3>
                <span className="text-[10px] text-slate-400 border border-slate-700 rounded px-1.5">24h</span>
              </div>
              <div className="p-4 flex-1 flex flex-col justify-end relative">
                {/* Chart */}
                <svg className="w-full h-40 overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 50">
                  <line stroke="#283039" strokeWidth="0.5" x1="0" x2="100" y1="10" y2="10" />
                  <line stroke="#283039" strokeWidth="0.5" x1="0" x2="100" y1="25" y2="25" />
                  <line stroke="#283039" strokeWidth="0.5" x1="0" x2="100" y1="40" y2="40" />
                  <path
                    d="M0,45 C10,42 20,40 30,42 C40,44 50,30 60,35 C70,38 80,20 90,25 C95,28 100,15 100,15"
                    fill="none"
                    stroke="#f97316"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                  />
                  <path
                    d="M0,45 C10,42 20,40 30,42 C40,44 50,30 60,35 C70,38 80,20 90,25 C95,28 100,15 100,15 L100,50 L0,50 Z"
                    fill="url(#testerGradient)"
                    opacity="0.2"
                  />
                  <defs>
                    <linearGradient id="testerGradient" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#f97316" />
                      <stop offset="100%" stopColor="transparent" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-2">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                </div>
                <div className="absolute top-4 right-4 text-right">
                  <div className="text-2xl font-bold text-white">99.2%</div>
                  <div className="text-xs text-green-500 flex items-center justify-end gap-1">
                    <TrendingUp size={12} /> +0.4%
                  </div>
                </div>
              </div>
            </div>

            {/* Risk Assessment */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col flex-1 min-h-[250px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Gauge size={16} className="text-orange-400" />
                  Risk Assessment
                </h3>
              </div>
              <div className="flex-1 flex flex-col items-center justify-center p-6 relative">
                {/* Gauge */}
                <div className="relative w-48 h-24 overflow-hidden mb-4">
                  <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 200 100">
                    <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#283039" strokeWidth="20" />
                    <path d="M 20 100 A 80 80 0 0 1 120 36" fill="none" stroke="#22c55e" strokeLinecap="round" strokeWidth="20" />
                    <path d="M 120 36 A 80 80 0 0 1 150 25" fill="none" stroke="#f97316" strokeLinecap="round" strokeWidth="20" />
                  </svg>
                  {/* Needle */}
                  <div
                    className="absolute bottom-0 left-1/2 w-1 h-[80px] bg-white origin-bottom rounded-full shadow-lg z-10"
                    style={{ transform: 'translateX(-50%) rotate(35deg)' }}
                  >
                    <div className="absolute -top-1 -left-1.5 size-4 bg-white rounded-full border-2 border-slate-900"></div>
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-sm text-slate-400 uppercase tracking-widest font-bold mb-1">Current Risk</div>
                  <div className="text-2xl font-bold text-orange-400">MODERATE</div>
                  <p className="text-xs text-slate-500 mt-2 max-w-[200px]">
                    Elevated due to recent dependency updates in pay_module.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default TesterOffice;
