/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.1
 * Beschreibung: TechStack Office - Detailansicht für den TechStack-Architekten mit Stack-Übersicht.
 *
 * # ÄNDERUNG 24.01.2026: Echte Echtzeit-Daten statt Dummy-Daten
 * - Props erweitert für blueprint, model, decisions, dependencies, reasoning
 * - Dummy-Daten entfernt (Regel 10 Compliance)
 * - "Warte auf Daten..." Zustände implementiert
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
  Terminal,
  Rocket,
  Bug,
  CloudUpload,
  Gauge,
  FileCode,
  Server,
  Database,
  Globe,
  Maximize2,
  Cpu,
  Code,
  Zap,
  HardDrive
} from 'lucide-react';

const TechStackOffice = ({
  agentName = "Tech-Stack",
  status = "Idle",
  logs = [],
  onBack,
  color = "purple",
  // Echte Daten vom Backend
  blueprint = {},
  model = "",
  decisions = [],
  dependencies = [],
  reasoning = ""
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const deploymentLogRef = useRef(null);

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-violet-500/20 text-violet-300 border-violet-500/20 font-semibold shadow-[0_0_8px_rgba(139,92,246,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Analysiert...' : badge.text}
      </span>
    );
  };

  // Prüfe ob Daten vorhanden sind
  const hasData = Object.keys(blueprint).length > 0 || decisions.length > 0;

  // Icon für Entscheidungstyp
  const getDecisionIcon = (type) => {
    switch (type) {
      case 'Sprache': return <Code size={14} className="text-blue-400" />;
      case 'Framework': return <Layers size={14} className="text-violet-400" />;
      case 'Datenbank': return <Database size={14} className="text-green-400" />;
      case 'Server': return <Server size={14} className="text-orange-400" />;
      default: return <Zap size={14} className="text-slate-400" />;
    }
  };

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
              <div className="text-xs text-slate-400 font-medium tracking-wide flex items-center gap-2">
                {model ? (
                  <>
                    <Cpu size={12} className="text-violet-400" />
                    <span className="text-violet-400">{model}</span>
                  </>
                ) : (
                  <span className="text-slate-500 italic">Warte auf Modell-Info...</span>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Blueprint Type Badge */}
          {blueprint.project_type && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-violet-500/30 transition-colors">
              <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-fuchsia-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-fuchsia-500"></span>
              </span>
              <Package size={14} className="text-fuchsia-500" />
              <span className="text-xs font-semibold text-white">{blueprint.project_type}</span>
            </div>
          )}
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

        {/* Left Sidebar - Dependencies */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Package size={16} className="text-violet-500" />
              Dependencies
            </h3>
            {dependencies.length > 0 && (
              <span className="text-[10px] bg-violet-950 text-violet-300 border border-violet-900 px-1.5 py-0.5 rounded font-mono">
                {dependencies.length} Pakete
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto techstack-scrollbar p-4 space-y-3">
            {dependencies.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4">
                <Package size={32} className="text-slate-600 mb-3" />
                <p className="text-sm text-slate-500">Keine Dependencies</p>
                <p className="text-xs text-slate-600 mt-1">Starte einen Task um den TechStack zu analysieren</p>
              </div>
            ) : (
              dependencies.map((dep, index) => (
                <div key={index} className="group cursor-pointer">
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-violet-500/30 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 uppercase">
                        <span className="size-1.5 bg-emerald-500 rounded-full"></span>
                        Package
                      </span>
                      <CheckCircle size={14} className="text-slate-500" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-violet-100 transition-colors">
                      {dep}
                    </h4>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Blueprint Info Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            {blueprint.language ? (
              <>
                <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                  <span className="flex items-center gap-1">
                    <Code size={12} />
                    Sprache
                  </span>
                  <span className="text-violet-300 font-semibold">{blueprint.language}</span>
                </div>
                {blueprint.database && (
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="flex items-center gap-1">
                      <Database size={12} />
                      Datenbank
                    </span>
                    <span className="text-violet-300 font-semibold">{blueprint.database}</span>
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-500 text-center italic">Warte auf Blueprint...</p>
            )}
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
                Agent Terminal
              </h3>
              <div className="flex items-center gap-3">
                {model && <span className="text-[10px] text-slate-500 font-mono">{model}</span>}
                <span className="size-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto techstack-scrollbar font-mono text-xs space-y-4"
            >
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center">
                  <Terminal size={32} className="text-slate-600 mb-3" />
                  <p className="text-sm text-slate-500">Keine Aktivität</p>
                  <p className="text-xs text-slate-600 mt-1">Starte einen Task um die Analyse zu beginnen</p>
                </div>
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

          {/* Reasoning / Entscheidungsbegründung */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Rocket size={14} className="text-fuchsia-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Entscheidungsbegründung</span>
              </div>
            </div>

            <div
              ref={deploymentLogRef}
              className="flex-1 p-6 overflow-y-auto techstack-scrollbar font-mono text-sm leading-6"
            >
              {reasoning ? (
                <div className="space-y-4">
                  <div className="bg-violet-950/20 p-4 rounded-lg border border-violet-500/30">
                    <p className="text-violet-200 whitespace-pre-wrap">{reasoning}</p>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center">
                  <Rocket size={32} className="text-slate-600 mb-3" />
                  <p className="text-sm text-slate-500">Keine Begründung vorhanden</p>
                  <p className="text-xs text-slate-600 mt-1">Der Agent wird seine Entscheidung hier erklären</p>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <Bug size={16} />
                Details anzeigen
              </button>
              <button
                className={`flex-[2] px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 ${
                  hasData
                    ? 'bg-violet-600 hover:bg-violet-500 text-white shadow-[0_0_15px_rgba(139,92,246,0.4)]'
                    : 'bg-slate-700 text-slate-400 cursor-not-allowed'
                }`}
                disabled={!hasData}
              >
                <CloudUpload size={16} />
                Blueprint exportieren
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Stack Decisions */}
        <aside className="w-[340px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Gauge size={16} className="text-violet-500" />
              Stack Entscheidungen
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto techstack-scrollbar p-5 space-y-6">
            {/* Decisions List */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155]">
              <p className="text-xs text-slate-400 uppercase font-semibold mb-3">Architektur-Entscheidungen</p>
              {decisions.length === 0 ? (
                <div className="text-center py-4">
                  <Layers size={24} className="text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">Keine Entscheidungen</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {decisions.map((decision, i) => (
                    <div key={i} className="flex items-center gap-3 p-2 bg-[#0f172a] rounded-lg border border-slate-700/50">
                      {getDecisionIcon(decision.type)}
                      <div className="flex-1 min-w-0">
                        <p className="text-[10px] text-slate-500 uppercase">{decision.type}</p>
                        <p className="text-sm font-semibold text-white truncate">{decision.value}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Blueprint Details */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <FileCode size={14} className="text-violet-400" />
                Blueprint Details
              </h4>
              {hasData ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                    <p className="text-[9px] text-slate-400 uppercase">Projekt-Typ</p>
                    <p className="text-sm font-bold text-white truncate">{blueprint.project_type || '-'}</p>
                  </div>
                  <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                    <p className="text-[9px] text-slate-400 uppercase">Sprache</p>
                    <p className="text-sm font-bold text-white">{blueprint.language || '-'}</p>
                  </div>
                  {blueprint.server_port && (
                    <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                      <p className="text-[9px] text-slate-400 uppercase">Server Port</p>
                      <p className="text-sm font-bold text-white">{blueprint.server_port}</p>
                    </div>
                  )}
                  {blueprint.database && (
                    <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                      <p className="text-[9px] text-slate-400 uppercase">Datenbank</p>
                      <p className="text-sm font-bold text-white">{blueprint.database}</p>
                    </div>
                  )}
                  {blueprint.run_command && (
                    <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50">
                      <p className="text-[9px] text-slate-400 uppercase">Run Command</p>
                      <p className="text-xs font-mono text-violet-300 truncate">{blueprint.run_command}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-4">
                  <HardDrive size={24} className="text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">Warte auf Blueprint...</p>
                </div>
              )}
            </div>

            {/* Server Status */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <div className="flex justify-between items-center mb-2">
                <p className="text-xs text-slate-400 uppercase font-semibold">Server Status</p>
                <span className={`text-[10px] px-1.5 rounded border ${
                  blueprint.requires_server
                    ? 'text-emerald-300 bg-emerald-950 border-emerald-900'
                    : 'text-slate-300 bg-slate-800 border-slate-700'
                }`}>
                  {blueprint.requires_server ? 'Benötigt' : 'Nicht benötigt'}
                </span>
              </div>
              {blueprint.requires_server && blueprint.server_port && (
                <div className="flex items-center gap-2 mt-2">
                  <Server size={14} className="text-violet-400" />
                  <span className="text-sm text-slate-300">Port: </span>
                  <span className="text-sm font-bold text-violet-300">{blueprint.server_port}</span>
                </div>
              )}
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
                <div className={`size-2 rounded-full ${hasData ? 'bg-violet-500 animate-ping shadow-[0_0_5px_violet]' : 'bg-slate-600'}`}></div>
              </div>
              <span className="text-[9px] font-mono text-violet-300 bg-black/50 px-1 rounded backdrop-blur-sm border border-violet-900/50">
                SECTOR: TECH-STACK
              </span>
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
