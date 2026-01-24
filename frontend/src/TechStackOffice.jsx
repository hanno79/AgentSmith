/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: TechStack Office - Detailansicht für den TechStack-Architekten mit Stack-Übersicht.
 */

import React, { useRef } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Layers,
  History,
  Settings,
  Package,
  AlertTriangle,
  CheckCircle,
  Search,
  Terminal,
  Rocket,
  Bug,
  CloudUpload,
  Gauge,
  FileCode,
  Server,
  Database,
  Globe,
  Radio,
  Maximize2,
  RefreshCw
} from 'lucide-react';

const TechStackOffice = ({ agentName = "Tech-Stack", status = "Idle", logs = [], onBack, color = "purple" }) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const deploymentLogRef = useRef(null);

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-violet-500/20 text-violet-300 border-violet-500/20 font-semibold shadow-[0_0_8px_rgba(139,92,246,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'System Status: Stable' : badge.text}
      </span>
    );
  };

  // MOCK-DATEN: Demo-Dependency-Daten
  const dependencies = [
    { id: 1, type: 'updating', name: 'React Core Framework v19', source: 'NPM Registry', progress: 62 },
    { id: 2, type: 'compatibility', name: 'Webpack Config Mismatch', detail: 'Dep: css-loader v6.2.0 (Legacy)' },
    { id: 3, type: 'stable', name: 'Tailwind CSS v3.4', detail: 'JIT Engine Active' },
    { id: 4, type: 'indexing', name: 'Node_Modules Indexing...' },
  ];

  // MOCK-DATEN: Demo-Terminal-Einträge
  const terminalEntries = [
    { time: '09:14:02', type: 'info', message: 'Initializing Docker container', highlight: 'api-gateway-v2' },
    { time: '09:14:05', type: 'info', message: 'Pulling image:', highlight: 'registry.internal/node-alpine:18' },
    { time: '09:14:12', type: 'config', title: 'Config Injection:', message: 'Injecting ENV variables for REDIS_HOST. Mapping ports 3000:8080. Hot-reload enabled.' },
    { time: '09:14:15', type: 'success', message: 'Verifying network bridge -', highlight: 'Connected' },
  ];

  // MOCK-DATEN: Demo-Deployment-Ziele
  const deploymentTargets = [
    {
      title: 'Target: Production Cluster A',
      items: [
        { text: 'Optimization routine applied to', highlight: 'next.config.js', suffix: '. Image formats converted to', highlight2: 'AVIF', suffix2: '.' },
        { text: 'Edge caching rules updated. TTL set to', highlight: '3600s', suffix: ' for static assets.' },
      ]
    },
    {
      title: 'Service Worker Status',
      items: [
        { text: 'Precaching', highlight: '/dashboard', suffix: ' routes for offline support.' },
        { isPatch: true, title: 'PERFORMANCE PATCH', text: 'Lazy loading strategy implemented for', highlight: 'ChartWidgets', suffix: ' component. Reduced initial load by 45%.' },
      ]
    }
  ];

  // MOCK-DATEN: Demo-Stack-Health-Daten
  const stackHealth = [
    { name: 'FE', value: 99, status: 'healthy' },
    { name: 'API', value: 95, status: 'healthy' },
    { name: 'DB', value: 85, status: 'warning', label: 'LOAD' },
    { name: 'CDN', value: 100, status: 'optimal' },
  ];

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-violet-900/10">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-violet-950 text-violet-400 border border-violet-500/30 shadow-[0_0_10px_rgba(139,92,246,0.2)]">
              <Layers size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-04-TCH</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Bundle Optimization Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-violet-500/30 transition-colors">
            <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-fuchsia-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-fuchsia-500"></span>
            </span>
            <Package size={14} className="text-fuchsia-500" />
            <span className="text-xs font-semibold text-white">Bundle Optimization #442</span>
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

        {/* Left Sidebar - Dependency Tree */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Package size={16} className="text-violet-500" />
              Dependency Tree
            </h3>
            <span className="text-[10px] bg-violet-950 text-violet-300 border border-violet-900 px-1.5 py-0.5 rounded font-mono">v4.2.0</span>
          </div>

          <div className="flex-1 overflow-y-auto techstack-scrollbar p-4 space-y-4">
            {dependencies.map((dep) => (
              <div key={dep.id} className={dep.type === 'updating' ? 'relative group' : dep.type === 'indexing' ? 'group cursor-pointer opacity-70' : 'group cursor-pointer'}>
                {dep.type === 'updating' ? (
                  <>
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-lg opacity-20 blur-sm group-hover:opacity-40 transition-opacity"></div>
                    <div className="relative bg-[#1e293b] p-3 rounded-lg border border-violet-500/30 shadow-lg">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] font-bold text-violet-300 bg-violet-950/50 px-1.5 py-0.5 rounded border border-violet-800 animate-pulse">UPDATING</span>
                        <span className="text-[10px] text-slate-400 font-mono">{dep.source}</span>
                      </div>
                      <h4 className="text-sm font-semibold text-white mb-2 truncate">{dep.name}</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs text-slate-300">
                          <span className="flex items-center gap-1.5">
                            <RefreshCw size={12} className="text-violet-400 animate-spin" />
                            Downloading
                          </span>
                          <span className="font-mono text-violet-200">{dep.progress}%</span>
                        </div>
                        <div className="h-1 w-full bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-violet-500 rounded-full animate-pulse" style={{ width: `${dep.progress}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : dep.type === 'compatibility' ? (
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 uppercase">
                        <span className="size-1.5 bg-amber-500 rounded-full"></span>
                        Compatibility
                      </span>
                      <AlertTriangle size={14} className="text-slate-500" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-violet-100 transition-colors">{dep.name}</h4>
                    <p className="text-[11px] text-slate-500 mt-1 font-mono truncate">{dep.detail}</p>
                  </div>
                ) : dep.type === 'stable' ? (
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 uppercase">
                        <span className="size-1.5 bg-emerald-500 rounded-full"></span>
                        Stable
                      </span>
                      <CheckCircle size={14} className="text-slate-500" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-violet-100 transition-colors">{dep.name}</h4>
                    <p className="text-[11px] text-slate-500 mt-1 font-mono truncate">{dep.detail}</p>
                  </div>
                ) : (
                  <div className="bg-[#1e293b]/20 p-3 rounded-lg border border-[#334155] border-dashed">
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-[10px] font-bold text-slate-500 uppercase">Indexing</span>
                      <Search size={14} className="text-slate-600 animate-spin" style={{ animationDuration: '3s' }} />
                    </div>
                    <h4 className="text-sm font-medium text-slate-400">{dep.name}</h4>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Registry Load Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Registry Load</span>
              <span>34ms Latency</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div className="h-full w-[24%] bg-gradient-to-r from-violet-600 to-fuchsia-500 rounded-full"></div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Infrastructure Terminal */}
          <div className="h-[40%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Server size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-violet-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Terminal size={14} />
                </motion.div>
                Infrastructure Terminal
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">ENV: STAGING-04</span>
                <span className="size-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto techstack-scrollbar font-mono text-xs space-y-4"
            >
              {logs.length === 0 ? (
                <>
                  {terminalEntries.map((entry, i) => (
                    <div key={i} className={`flex gap-4 group ${entry.type === 'config' ? 'relative' : ''}`}>
                      {entry.type === 'config' && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-violet-900"></div>}
                      <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${entry.type === 'config' ? 'text-violet-500' : 'text-slate-600'}`}>[{entry.time}]</span>
                      <div className={`flex-1 ${entry.type === 'config' ? 'bg-violet-950/20 p-2 rounded border-l-2 border-violet-500' : ''}`}>
                        {entry.type === 'config' ? (
                          <>
                            <p className="text-violet-400 font-semibold mb-1">{entry.title}</p>
                            <p className="text-violet-200/80 italic">{entry.message}</p>
                          </>
                        ) : (
                          <p className={entry.type === 'success' ? 'text-slate-300' : 'text-slate-400'}>
                            {entry.message} <span className={entry.type === 'success' ? 'text-emerald-500' : 'text-violet-400'}>{entry.highlight}</span>
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-4 group animate-pulse">
                    <span className="text-violet-500 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">...</span>
                    <p className="text-violet-400/70 italic">Waiting for database migration scripts...</p>
                  </div>
                </>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-violet-900"></div>}
                    <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-violet-500' : 'text-slate-600'}`}>
                      [{formatTime(i)}]
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-violet-950/20 p-2 rounded border-l-2 border-violet-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-amber-400' :
                        log.event === 'Success' ? 'text-emerald-400' :
                        i === logs.length - 1 ? 'text-violet-200' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Deployment Readiness Log */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Rocket size={14} className="text-fuchsia-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Deployment Readiness Log</span>
              </div>
              <div className="flex gap-2">
                <button className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded hover:bg-slate-700 transition-colors">Verbose</button>
                <button className="text-[10px] bg-violet-900/40 text-violet-300 border border-violet-700/50 px-2 py-0.5 rounded">Filtered</button>
              </div>
            </div>

            <div
              ref={deploymentLogRef}
              className="flex-1 p-6 overflow-y-auto techstack-scrollbar font-mono text-sm leading-6"
            >
              <div className="space-y-6">
                {deploymentTargets.map((target, targetIndex) => (
                  <div key={targetIndex}>
                    <h5 className="text-slate-500 text-xs uppercase tracking-wider mb-2 border-b border-slate-800 pb-1">{target.title}</h5>
                    <ul className="space-y-2">
                      {target.items.map((item, itemIndex) => (
                        <li key={itemIndex} className="flex items-start text-slate-300">
                          <span className="text-fuchsia-500 mr-2">●</span>
                          {item.isPatch ? (
                            <div className="bg-slate-800/50 p-2 rounded w-full border border-slate-700/50 border-l-4 border-l-violet-500">
                              <span className="text-xs text-violet-400 block mb-1 font-bold">{item.title}</span>
                              <span>{item.text} <span className="text-fuchsia-400">{item.highlight}</span>{item.suffix}</span>
                            </div>
                          ) : (
                            <span>
                              {item.text} <span className="text-fuchsia-300">{item.highlight}</span>{item.suffix}
                              {item.highlight2 && <span className="text-fuchsia-300">{item.highlight2}</span>}
                              {item.suffix2}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className="h-4 w-2 bg-violet-500 animate-pulse mt-4"></div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <Bug size={16} />
                Run Diagnostics
              </button>
              <button className="flex-[2] bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(139,92,246,0.4)] animate-pulse">
                <CloudUpload size={16} />
                DEPLOY STACK
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Stack Metrics */}
        <aside className="w-[340px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Gauge size={16} className="text-violet-500" />
              Stack Metrics
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto techstack-scrollbar p-5 space-y-6">
            {/* Scalability Gauge */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Gauge size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Scalability Gauge</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white">Elastic</span>
                <span className="text-sm text-fuchsia-400 font-medium font-mono">AUTOSCALE ON</span>
              </div>
              <div className="mt-3 h-2 w-full bg-[#0f172a] rounded-full overflow-hidden flex gap-0.5">
                <div className="h-full w-[20%] bg-violet-600 shadow-[0_0_10px_rgba(139,92,246,0.5)]"></div>
                <div className="h-full w-[45%] bg-fuchsia-500/80"></div>
                <div className="h-full w-[35%] bg-slate-700/20"></div>
              </div>
              <div className="flex justify-between mt-1 text-[9px] text-slate-500 uppercase font-bold">
                <span>Min Replicas</span>
                <span>Current</span>
                <span>Max Cap</span>
              </div>
            </div>

            {/* Bundle Size */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <FileCode size={14} className="text-violet-400" />
                Bundle Size
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">JS Main</p>
                  <p className="text-lg font-bold text-white">142 <span className="text-[10px] text-slate-500 font-normal">KB</span></p>
                </div>
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">CSS</p>
                  <p className="text-lg font-bold text-white">24 <span className="text-[10px] text-slate-500 font-normal">KB</span></p>
                </div>
                <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50 flex items-center justify-between">
                  <div>
                    <p className="text-[9px] text-slate-400 uppercase">Compression</p>
                    <p className="text-lg font-bold text-white">Brotli <span className="text-[10px] text-slate-500 font-normal">Active</span></p>
                  </div>
                  <div className="size-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin"></div>
                </div>
              </div>
            </div>

            {/* Stack Health */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] flex flex-col justify-between">
              <div className="flex justify-between items-center mb-2">
                <p className="text-xs text-slate-400 uppercase font-semibold">Stack Health</p>
                <span className="text-[10px] text-violet-300 bg-violet-950 px-1.5 rounded border border-violet-900">Real-time</span>
              </div>
              <div className="space-y-2">
                {stackHealth.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]">
                    <span className="w-8 text-slate-500 text-right">{item.name}</span>
                    <div className="flex-1 h-2 bg-[#0f172a] rounded-sm overflow-hidden">
                      <div
                        className={`h-full rounded-sm ${
                          item.status === 'optimal' ? 'bg-violet-500 shadow-[0_0_8px_rgba(139,92,246,0.4)] animate-pulse' :
                          item.status === 'healthy' ? 'bg-emerald-500' :
                          'bg-amber-500'
                        }`}
                        style={{ width: `${item.value}%` }}
                      ></div>
                    </div>
                    <span className={`w-8 text-right ${item.status === 'warning' ? 'text-amber-400 font-bold' : 'text-slate-300'}`}>
                      {item.label || `${item.value}%`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Map Footer */}
          <div className="p-0 border-t border-[#334155] bg-[#0f172a] h-40 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-violet-900/20 to-slate-900/80"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] to-transparent"></div>
            <div className="absolute bottom-3 right-3 flex flex-col items-end">
              <div className="flex gap-1 mb-1">
                <div className="size-2 bg-slate-600 rounded-full"></div>
                <div className="size-2 bg-slate-600 rounded-full"></div>
                <div className="size-2 bg-violet-500 rounded-full animate-ping shadow-[0_0_5px_violet]"></div>
              </div>
              <span className="text-[9px] font-mono text-violet-300 bg-black/50 px-1 rounded backdrop-blur-sm border border-violet-900/50">SECTOR: TECH-STACK</span>
            </div>
            <button className="absolute top-2 right-2 text-white/50 hover:text-white transition-colors">
              <Maximize2 size={14} />
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default TechStackOffice;
