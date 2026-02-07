/**
 * Author: rahn
 * Datum: 07.02.2026
 * Version: 1.0
 * Beschreibung: Fix Office - Detailansicht fuer den Fix-Agenten.
 *               Zeigt Fix-Aktivitaet, modifizierte Dateien und Metriken.
 *               AENDERUNG 07.02.2026: Neue Komponente (Fix 14)
 */

import React from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Wrench,
  FileCode,
  Clock,
  Cpu,
  History,
  Settings,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Hash
} from 'lucide-react';

const FixOffice = ({
  logs = [],
  status = "Idle",
  fixData = {},
  onBack
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);

  // Fix-Daten extrahieren
  const fixCount = fixData.fixCount || 0;
  const currentFile = fixData.currentFile || '';
  const currentTask = fixData.currentTask || '';
  const errorType = fixData.errorType || '';
  const modifiedFiles = fixData.modifiedFiles || [];
  const model = fixData.model || '';
  const totalDuration = fixData.totalDuration || 0;

  // Status-Indikatoren
  const isFixing = status === 'Working' || fixData.status === 'fixing';
  const isCompleted = fixCount > 0;

  // Einzigartige modifizierte Dateien (Set)
  const uniqueFiles = [...new Set(modifiedFiles)];

  // Status Badge
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-amber-500/20 text-amber-300 border-amber-500/20 font-semibold shadow-[0_0_8px_rgba(245,158,11,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Fixing Active' : badge.text}
      </span>
    );
  };

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-amber-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-amber-950 text-amber-400 border border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.1)]">
              <Wrench size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                Fix Agent
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-12-FIX</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] hover:border-amber-500/30 transition-colors">
            <Wrench size={14} className="text-amber-500" />
            <span className="text-xs font-semibold text-white">Targeted Fix Strategy</span>
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
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.05] pointer-events-none"></div>

        {/* Left Sidebar - Fix Overview */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Wrench size={16} className="text-amber-400" />
              Fix Overview
            </h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
              isFixing ? 'bg-amber-950 text-amber-400 border-amber-900' :
              isCompleted ? 'bg-green-950 text-green-400 border-green-900' :
              'bg-slate-800 text-slate-400 border-slate-700'
            }`}>
              {isFixing ? 'FIXING' : isCompleted ? 'DONE' : 'IDLE'}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto planner-scrollbar p-4 space-y-4">
            {/* Statistiken */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
                <div className="flex items-center gap-2 mb-1">
                  <Wrench size={14} className="text-amber-400" />
                  <span className="text-[10px] text-slate-400 uppercase">Fixes</span>
                </div>
                <p className="text-2xl font-bold text-white">{fixCount}</p>
              </div>
              <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
                <div className="flex items-center gap-2 mb-1">
                  <FileCode size={14} className="text-amber-400" />
                  <span className="text-[10px] text-slate-400 uppercase">Dateien</span>
                </div>
                <p className="text-2xl font-bold text-white">{uniqueFiles.length}</p>
              </div>
            </div>

            {/* Aktuelle Aufgabe */}
            {(currentFile || currentTask) && (
              <div className="bg-amber-900/20 rounded-lg p-3 border border-amber-700/30">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <span className="text-xs font-bold text-amber-300 uppercase">Aktuelle Aufgabe</span>
                </div>
                {currentTask && <p className="text-xs text-white mb-1 truncate">{currentTask}</p>}
                {currentFile && (
                  <div className="flex items-center gap-2 text-xs text-slate-300">
                    <FileCode size={12} className="text-amber-400 flex-shrink-0" />
                    <span className="truncate">{currentFile}</span>
                  </div>
                )}
                {errorType && (
                  <span className="inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-900/50 text-amber-300 border border-amber-800">
                    {errorType}
                  </span>
                )}
              </div>
            )}

            {/* Modifizierte Dateien */}
            {uniqueFiles.length > 0 && (
              <div className="bg-[#1e293b] rounded-lg border border-[#334155]">
                <div className="p-3 border-b border-[#334155]">
                  <span className="text-xs font-bold text-slate-300 uppercase">Modifizierte Dateien</span>
                </div>
                <div className="p-2 max-h-[250px] overflow-y-auto planner-scrollbar">
                  {uniqueFiles.slice(0, 15).map((file, index) => (
                    <div key={index} className="flex items-center gap-2 px-2 py-1.5 hover:bg-[#0f172a] rounded text-xs">
                      <CheckCircle size={12} className="text-green-400 flex-shrink-0" />
                      <span className="text-slate-300 truncate">{file}</span>
                    </div>
                  ))}
                  {uniqueFiles.length > 15 && (
                    <div className="px-2 py-1.5 text-xs text-slate-500">
                      ... und {uniqueFiles.length - 15} weitere
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Status</span>
              <span className="flex items-center gap-1">
                {isCompleted && !isFixing ? (
                  <>
                    <CheckCircle size={12} className="text-green-400" />
                    <span className="text-green-400">{fixCount} Fixes</span>
                  </>
                ) : isFixing ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    >
                      <Wrench size={12} className="text-amber-400" />
                    </motion.div>
                    <span className="text-amber-400">Fixing...</span>
                  </>
                ) : (
                  <>
                    <Clock size={12} />
                    <span>Waiting</span>
                  </>
                )}
              </span>
            </div>
          </div>
        </aside>

        {/* Main Content Area - Logs */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wrench size={14} className="text-amber-500" />
              <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Fix Activity</span>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">{logs.length} events</span>
          </div>

          <div
            ref={logRef}
            className="flex-1 p-5 overflow-y-auto planner-scrollbar font-mono text-xs space-y-3"
          >
            {logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="size-16 rounded-full bg-slate-800/50 flex items-center justify-center mb-4">
                  <Wrench size={32} className="text-slate-500" />
                </div>
                <p className="text-slate-400 text-sm">Keine Fix-Aktivitaet</p>
                <p className="text-slate-500 text-xs mt-2">Der Fix-Agent wird bei Fehlern im DevLoop aktiv.</p>
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                  {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-amber-900"></div>}
                  <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-amber-700' : 'text-slate-600'}`}>
                    [{formatTime(i)}]
                  </span>
                  <div className={`flex-1 ${i === logs.length - 1 ? 'bg-amber-950/20 p-2 rounded border-l-2 border-amber-500' : ''}`}>
                    <p className={
                      log.event === 'Error' ? 'text-red-400' :
                      log.event === 'Warning' ? 'text-yellow-400' :
                      log.event === 'FixOutput' ? 'text-green-400' :
                      i === logs.length - 1 ? 'text-amber-100' :
                      'text-slate-300'
                    }>{log.message}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </main>

        {/* Right Sidebar - Metrics */}
        <aside className="w-[280px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Cpu size={16} className="text-amber-400" />
              Metrics
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto planner-scrollbar p-4 space-y-4">
            {/* Dauer */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Clock size={14} className="text-amber-400" />
                Gesamtdauer
              </h4>
              <div className="text-3xl font-bold text-white mb-1">
                {totalDuration > 0 ? `${totalDuration.toFixed(1)}s` : '-'}
              </div>
              <p className="text-[10px] text-slate-500">{fixCount} Fix(es) gesamt</p>
            </div>

            {/* Model Info */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Cpu size={14} className="text-amber-400" />
                Model
              </h4>
              <p className="text-sm text-white truncate">{model || 'Nicht zugewiesen'}</p>
            </div>

            {/* Status */}
            <div className={`rounded-lg p-4 border ${
              isCompleted && !isFixing ? 'bg-green-900/20 border-green-700/50' :
              isFixing ? 'bg-amber-900/20 border-amber-700/50' :
              'bg-[#1e293b] border-[#334155]'
            }`}>
              <div className="flex items-center gap-2">
                {isCompleted && !isFixing ? (
                  <CheckCircle size={18} className="text-green-400" />
                ) : isFixing ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  >
                    <Wrench size={18} className="text-amber-400" />
                  </motion.div>
                ) : (
                  <AlertCircle size={18} className="text-slate-400" />
                )}
                <span className={`text-sm font-semibold ${
                  isCompleted && !isFixing ? 'text-green-400' :
                  isFixing ? 'text-amber-400' :
                  'text-slate-400'
                }`}>
                  {isCompleted && !isFixing ? `${fixCount} Fix(es) erledigt` : isFixing ? 'Korrektur...' : 'Bereit'}
                </span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`size-2 rounded-full ${
                  isFixing ? 'bg-amber-500 animate-pulse shadow-[0_0_5px_amber]' :
                  isCompleted ? 'bg-green-500' :
                  'bg-slate-600'
                }`}></div>
                <span className="text-[10px] font-mono text-slate-400">
                  {model ? model.split('/').pop() : 'Kein Model'}
                </span>
              </div>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                isFixing ? 'text-amber-400 bg-amber-950 border-amber-900' :
                isCompleted ? 'text-green-400 bg-green-950 border-green-900' :
                'text-slate-400 bg-slate-800 border-slate-700'
              }`}>
                {isFixing ? 'ACTIVE' : isCompleted ? 'DONE' : 'IDLE'}
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default FixOffice;
