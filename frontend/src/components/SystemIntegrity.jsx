/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: System Integrity Sidebar für SecurityOffice.
 *               Extrahiert aus SecurityOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import React from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Lock,
  Server,
  Database,
  Globe,
  Radio,
  Maximize2,
  Loader2
} from 'lucide-react';

const SystemIntegrity = ({
  defcon,
  nodeStatus,
  isScanning
}) => {
  return (
    <aside className="w-[320px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
      <div className="p-4 border-b border-[#334155]">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <ShieldCheck size={16} className="text-red-400" />
          System Integrity
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto security-scrollbar p-4 space-y-4">
        {/* DEFCON Level */}
        <div className={`rounded-xl p-4 border relative overflow-hidden group ${
          defcon.color === 'red' ? 'bg-red-950/30 border-red-500/30' :
          defcon.color === 'orange' ? 'bg-orange-950/30 border-orange-500/30' :
          defcon.color === 'amber' ? 'bg-amber-950/30 border-amber-500/30' :
          defcon.color === 'green' ? 'bg-green-950/30 border-green-500/30' :
          'bg-[#1e293b] border-[#334155]'
        }`}>
          <div className="absolute top-0 right-0 p-2 opacity-10">
            {defcon.color === 'green' ? <ShieldCheck size={60} /> : <AlertTriangle size={60} />}
          </div>
          <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Defense Readiness</p>
          <div className="flex items-baseline gap-2">
            {isScanning ? (
              <div className="flex items-center gap-2">
                <Loader2 size={24} className="text-slate-400 animate-spin" />
                <span className="text-xl font-bold text-slate-400">Analysiere...</span>
              </div>
            ) : (
              <span className={`text-3xl font-black ${
                defcon.color === 'red' ? 'text-red-400' :
                defcon.color === 'orange' ? 'text-orange-400' :
                defcon.color === 'amber' ? 'text-amber-400' :
                defcon.color === 'green' ? 'text-green-400' : 'text-slate-400'
              }`}>
                DEFCON {defcon.level}
              </span>
            )}
          </div>
          <p className="text-[10px] text-slate-500 mt-2">{defcon.description}</p>
          <div className="mt-3 flex gap-1">
            {[1, 2, 3, 4, 5].map((level) => (
              <div
                key={level}
                className={`flex-1 h-2 rounded ${
                  level <= (6 - defcon.level) ? (
                    defcon.color === 'red' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]' :
                    defcon.color === 'orange' ? 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.4)]' :
                    defcon.color === 'amber' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]' :
                    defcon.color === 'green' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' :
                    'bg-slate-500'
                  ) : 'bg-slate-700'
                }`}
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
  );
};

export default SystemIntegrity;
