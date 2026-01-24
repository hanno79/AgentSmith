/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Security Office - Detailansicht für den Security-Agenten mit Bedrohungsanalyse.
 */

import React, { useRef } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Shield,
  History,
  Settings,
  AlertTriangle,
  Lock,
  ShieldCheck,
  ShieldAlert,
  Activity,
  Server,
  Database,
  Globe,
  Zap,
  Eye,
  Target,
  Radio,
  Maximize2
} from 'lucide-react';

const SecurityOffice = ({ agentName = "Security", status = "Idle", logs = [], onBack, color = "red" }) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const mitigationRef = useRef(null);

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-red-500/20 text-red-300 border-red-500/20 font-semibold shadow-[0_0_8px_rgba(239,68,68,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Node Status: Online' : badge.text}
      </span>
    );
  };

  // MOCK-DATEN: Nur für Demo-Zwecke - Echte Bedrohungsdaten kommen vom Security-Agenten
  const threatIntel = {
    activeThreats: 3,
    suspicious: 12,
    secured: 847,
    scanning: 24
  };

  // MOCK-DATEN: Nur für Demo-Zwecke - Echte Einträge kommen vom Security-Agenten
  const defenseEntries = [
    { time: '14:32:01', type: 'alert', message: 'Anomalous traffic pattern detected from 192.168.1.105' },
    { time: '14:32:04', type: 'action', message: 'Initiating deep packet inspection on flagged connection...' },
    { time: '14:32:08', type: 'success', message: 'Threat contained. Connection terminated. IP added to watchlist.' },
    { time: '14:32:15', type: 'info', message: 'Deploying countermeasure DELTA-7 to perimeter nodes.' },
    { time: '14:32:22', type: 'warning', message: 'Elevated privilege escalation attempt on node API-03.' },
  ];

  // MOCK-DATEN: Nur für Demo-Zwecke - Echte Daten kommen vom Security-Agenten
  const mitigationTargets = [
    { name: 'auth-service', patches: 2, critical: true },
    { name: 'api-gateway', patches: 1, critical: false },
    { name: 'user-db', patches: 3, critical: true },
    { name: 'cdn-edge', patches: 1, critical: false },
  ];

  // MOCK-DATEN: Demo-Node-Security-Daten
  const nodeStatus = [
    { name: 'DB', health: 98, status: 'secured' },
    { name: 'API', health: 94, status: 'secured' },
    { name: 'WEB', health: 87, status: 'warning' },
    { name: 'CDN', health: 100, status: 'secured' },
  ];

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-red-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-red-950 text-red-400 border border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.1)]">
              <Shield size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-09-SEC</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Alert Level Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-950/50 border border-red-500/30 relative group">
            <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
            <AlertTriangle size={14} className="text-red-400" />
            <span className="text-xs font-semibold text-red-300">ALERT LEVEL: ELEVATED</span>
          </div>
          {/* Intrusion Attempts Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155]">
            <Eye size={14} className="text-amber-500" />
            <span className="text-xs font-semibold text-white">3 Intrusion Attempts</span>
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

        {/* Left Sidebar - Threat Intelligence */}
        <aside className="w-[280px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Target size={16} className="text-red-400" />
              Threat Intelligence
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto security-scrollbar p-4 space-y-4">
            {/* Active Threats */}
            <div className="bg-red-950/30 p-3 rounded-lg border border-red-500/30 relative group">
              <div className="absolute top-2 right-2">
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert size={16} className="text-red-400" />
                <span className="text-xs font-bold text-red-300 uppercase">Active Threats</span>
              </div>
              <p className="text-2xl font-black text-red-400">{threatIntel.activeThreats}</p>
              <p className="text-[10px] text-red-300/60 mt-1">Requiring immediate attention</p>
            </div>

            {/* Suspicious Items */}
            <div className="bg-amber-950/20 p-3 rounded-lg border border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} className="text-amber-400" />
                <span className="text-xs font-bold text-amber-300 uppercase">Suspicious</span>
              </div>
              <p className="text-2xl font-black text-amber-400">{threatIntel.suspicious}</p>
              <p className="text-[10px] text-amber-300/60 mt-1">Under investigation</p>
            </div>

            {/* Secured Items */}
            <div className="bg-green-950/20 p-3 rounded-lg border border-green-500/20">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck size={16} className="text-green-400" />
                <span className="text-xs font-bold text-green-300 uppercase">Secured</span>
              </div>
              <p className="text-2xl font-black text-green-400">{threatIntel.secured}</p>
              <p className="text-[10px] text-green-300/60 mt-1">Protected endpoints</p>
            </div>

            {/* Scanning Items */}
            <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
              <div className="flex items-center gap-2 mb-2">
                <Radio size={16} className="text-blue-400 animate-pulse" />
                <span className="text-xs font-bold text-slate-300 uppercase">Scanning</span>
              </div>
              <p className="text-2xl font-black text-white">{threatIntel.scanning}</p>
              <p className="text-[10px] text-slate-400 mt-1">Active scans in progress</p>
            </div>
          </div>

          {/* Firewall Load */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Zap size={12} className="text-red-400" />
                Firewall Load
              </span>
              <span className="text-red-300 font-mono">78%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div className="h-full w-[78%] bg-gradient-to-r from-red-600 to-red-400 rounded-full"></div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Defense Terminal */}
          <div className="h-[45%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Shield size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-red-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Activity size={14} />
                </motion.div>
                Defense Terminal
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">PROTOCOL: ACTIVE-DEFENSE</span>
                <span className="size-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto security-scrollbar font-mono text-xs space-y-3"
            >
              {logs.length === 0 ? (
                <>
                  {defenseEntries.map((entry, i) => (
                    <div key={i} className="flex gap-4 group">
                      <span className="text-slate-600 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[{entry.time}]</span>
                      <div className="flex-1">
                        <p className={
                          entry.type === 'alert' ? 'text-red-400' :
                          entry.type === 'warning' ? 'text-amber-400' :
                          entry.type === 'success' ? 'text-green-400' :
                          entry.type === 'action' ? 'text-blue-400' :
                          'text-slate-300'
                        }>{entry.message}</p>
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-4 group animate-pulse">
                    <span className="text-red-500 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">...</span>
                    <p className="text-red-500/70 italic">Monitoring threat vectors...</p>
                  </div>
                </>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-red-900"></div>}
                    <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-red-700' : 'text-slate-600'}`}>
                      [{formatTime(i)}]
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-red-950/20 p-2 rounded border-l-2 border-red-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-amber-400' :
                        log.event === 'Success' ? 'text-green-400' :
                        i === logs.length - 1 ? 'text-red-100' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Risk Mitigation Log */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock size={14} className="text-rose-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Risk Mitigation Log</span>
              </div>
              <span className="text-[10px] bg-rose-950 text-rose-300 px-2 py-0.5 rounded border border-rose-800">
                {mitigationTargets.reduce((acc, t) => acc + t.patches, 0)} Patches Pending
              </span>
            </div>

            <div
              ref={mitigationRef}
              className="flex-1 p-4 overflow-y-auto security-scrollbar"
            >
              <div className="space-y-3">
                {mitigationTargets.map((target, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg border ${target.critical ? 'bg-red-950/20 border-red-500/30' : 'bg-[#1e293b]/40 border-[#334155]'}`}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <div className="flex items-center gap-2">
                        <Server size={14} className={target.critical ? 'text-red-400' : 'text-slate-400'} />
                        <span className="text-sm font-semibold text-white">{target.name}</span>
                        {target.critical && (
                          <span className="text-[9px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded border border-red-500/30 uppercase font-bold">
                            Critical
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-slate-400 font-mono">{target.patches} patches</span>
                    </div>
                    <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${(3 - target.patches) / 3 * 100}%` }}
                        transition={{ duration: 1, delay: i * 0.2 }}
                        className={`h-full rounded-full ${target.critical ? 'bg-red-500' : 'bg-green-500'}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <Eye size={16} />
                View Details
              </button>
              <button className="flex-[2] bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.3)]">
                <Shield size={16} />
                Deploy All Patches
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - System Integrity */}
        <aside className="w-[320px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck size={16} className="text-red-400" />
              System Integrity
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto security-scrollbar p-4 space-y-4">
            {/* DEFCON Level */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <AlertTriangle size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Defense Readiness</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-amber-400">DEFCON 3</span>
              </div>
              <p className="text-[10px] text-slate-500 mt-2">Elevated threat level detected</p>
              <div className="mt-3 flex gap-1">
                {[1, 2, 3, 4, 5].map((level) => (
                  <div
                    key={level}
                    className={`flex-1 h-2 rounded ${level <= 3 ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]' : 'bg-slate-700'}`}
                  />
                ))}
              </div>
            </div>

            {/* Encryption Strength */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Lock size={14} className="text-green-400" />
                Encryption Strength
              </h4>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Protocol</span>
                  <span className="text-xs font-mono text-green-400">AES-256-GCM</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Entropy</span>
                  <span className="text-xs font-mono text-green-400">99.7%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Key Exchange</span>
                  <span className="text-xs font-mono text-green-400">ECDH P-384</span>
                </div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden mt-2">
                  <div className="h-full w-[99%] bg-gradient-to-r from-green-600 to-green-400 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.4)]"></div>
                </div>
              </div>
            </div>

            {/* Node Security */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
                  <Server size={14} className="text-red-400" />
                  Node Security
                </h4>
                <span className="text-[10px] text-slate-500 font-mono">Per Cluster</span>
              </div>
              <div className="space-y-3">
                {nodeStatus.map((node, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-300 flex items-center gap-2">
                        {node.name === 'DB' && <Database size={12} className="text-slate-500" />}
                        {node.name === 'API' && <Server size={12} className="text-slate-500" />}
                        {node.name === 'WEB' && <Globe size={12} className="text-slate-500" />}
                        {node.name === 'CDN' && <Radio size={12} className="text-slate-500" />}
                        {node.name}
                      </span>
                      <span className={`font-mono ${node.health >= 95 ? 'text-green-400' : node.health >= 85 ? 'text-amber-400' : 'text-red-400'}`}>
                        {node.health}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${node.health >= 95 ? 'bg-green-500' : node.health >= 85 ? 'bg-amber-500' : 'bg-red-500'}`}
                        style={{ width: `${node.health}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Map Footer */}
          <div className="p-0 border-t border-[#334155] bg-[#0f172a] h-32 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-red-900/20 to-slate-900/80"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] to-transparent"></div>
            <div className="absolute bottom-3 right-3 flex flex-col items-end">
              <div className="flex gap-1 mb-1">
                <div className="size-2 bg-green-500 rounded-full"></div>
                <div className="size-2 bg-amber-500 rounded-full animate-pulse"></div>
                <div className="size-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_5px_red]"></div>
              </div>
              <span className="text-[9px] font-mono text-red-400 bg-black/50 px-1 rounded backdrop-blur-sm border border-red-900/50">THREAT MAP: LIVE</span>
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

export default SecurityOffice;
