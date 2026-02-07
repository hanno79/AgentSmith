/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Threat Intelligence Sidebar für SecurityOffice.
 *               Extrahiert aus SecurityOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import React from 'react';
import {
  Target,
  ShieldAlert,
  AlertTriangle,
  ShieldCheck,
  Radio,
  Zap
} from 'lucide-react';

const ThreatIntelligence = ({
  threatIntel,
  isScanning,
  hasData,
  overallStatus
}) => {
  return (
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
            <Zap size={12} className={isScanning ? 'text-amber-400 animate-pulse' : hasData ? 'text-green-400' : 'text-slate-500'} />
            Firewall Load
          </span>
          <span className={`font-mono ${
            isScanning ? 'text-amber-300' :
            hasData && overallStatus === 'SECURE' ? 'text-green-300' :
            hasData ? 'text-amber-300' : 'text-slate-500'
          }`}>
            {isScanning ? '...' : hasData ? (overallStatus === 'SECURE' ? '25%' : '60%') : '0%'}
          </span>
        </div>
        <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
          {isScanning ? (
            <div className="h-full w-full bg-gradient-to-r from-amber-600 to-amber-400 rounded-full animate-pulse"></div>
          ) : hasData ? (
            <div
              className={`h-full rounded-full ${
                overallStatus === 'SECURE' ? 'bg-gradient-to-r from-green-600 to-green-400' :
                'bg-gradient-to-r from-amber-600 to-amber-400'
              }`}
              style={{ width: overallStatus === 'SECURE' ? '25%' : '60%' }}
            ></div>
          ) : (
            <div className="h-full w-0 bg-slate-600 rounded-full"></div>
          )}
        </div>
      </div>
    </aside>
  );
};

export default ThreatIntelligence;
