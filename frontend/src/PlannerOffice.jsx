/**
 * Author: rahn
 * Datum: 02.02.2026
 * Version: 1.0
 * Beschreibung: Planner Office - Detailansicht fuer den Planner-Agenten.
 *               Zeigt File-by-File Plan, geschaetzte Lines und Token-Metriken.
 */

import React from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Layers,
  FileCode,
  Clock,
  Cpu,
  History,
  Settings,
  CheckCircle,
  AlertCircle,
  FolderTree,
  Hash
} from 'lucide-react';

const PlannerOffice = ({
  logs = [],
  status = "Idle",
  planData = {},
  onBack
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);

  // Plan-Daten extrahieren
  const files = planData.files || [];
  const fileCount = planData.fileCount || files.length || 0;
  const estimatedLines = planData.estimatedLines || 0;
  const model = planData.model || '';
  const totalTokens = planData.totalTokens || 0;
  const source = planData.source || '';

  // Status-Indikatoren
  const isPlanning = status === 'Working';
  const isCompleted = fileCount > 0;

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-indigo-500/20 text-indigo-300 border-indigo-500/20 font-semibold shadow-[0_0_8px_rgba(99,102,241,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Planning Active' : badge.text}
      </span>
    );
  };

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-indigo-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-indigo-950 text-indigo-400 border border-indigo-500/30 shadow-[0_0_10px_rgba(99,102,241,0.1)]">
              <Layers size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                Planner
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-10-PLN</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-indigo-500/30 transition-colors">
            <FolderTree size={14} className="text-indigo-500" />
            <span className="text-xs font-semibold text-white">File-by-File Strategy</span>
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

        {/* Left Sidebar - Plan Overview */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <FileCode size={16} className="text-indigo-400" />
              Plan Overview
            </h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
              isPlanning ? 'bg-indigo-950 text-indigo-400 border-indigo-900' :
              isCompleted ? 'bg-green-950 text-green-400 border-green-900' :
              'bg-slate-800 text-slate-400 border-slate-700'
            }`}>
              {isPlanning ? 'PLANNING' : isCompleted ? 'READY' : 'IDLE'}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto planner-scrollbar p-4 space-y-4">
            {/* Statistiken */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
                <div className="flex items-center gap-2 mb-1">
                  <FileCode size={14} className="text-indigo-400" />
                  <span className="text-[10px] text-slate-400 uppercase">Dateien</span>
                </div>
                <p className="text-2xl font-bold text-white">{fileCount}</p>
              </div>
              <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
                <div className="flex items-center gap-2 mb-1">
                  <Hash size={14} className="text-indigo-400" />
                  <span className="text-[10px] text-slate-400 uppercase">~Lines</span>
                </div>
                <p className="text-2xl font-bold text-white">{estimatedLines}</p>
              </div>
            </div>

            {/* Dateiliste */}
            {files.length > 0 && (
              <div className="bg-[#1e293b] rounded-lg border border-[#334155]">
                <div className="p-3 border-b border-[#334155]">
                  <span className="text-xs font-bold text-slate-300 uppercase">Geplante Dateien</span>
                </div>
                <div className="p-2 max-h-[300px] overflow-y-auto planner-scrollbar">
                  {files.slice(0, 10).map((file, index) => (
                    <div key={index} className="flex items-center gap-2 px-2 py-1.5 hover:bg-[#0f172a] rounded text-xs">
                      <FileCode size={12} className="text-indigo-400 flex-shrink-0" />
                      <span className="text-slate-300 truncate">{typeof file === 'string' ? file : file.path || file}</span>
                    </div>
                  ))}
                  {files.length > 10 && (
                    <div className="px-2 py-1.5 text-xs text-slate-500">
                      ... und {files.length - 10} weitere
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Quelle */}
            {source && (
              <div className="bg-[#1e293b]/40 p-3 rounded-lg border border-[#334155]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] text-slate-400 uppercase">Quelle</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  source === 'planner' ? 'bg-indigo-900/50 text-indigo-300' : 'bg-yellow-900/50 text-yellow-300'
                }`}>
                  {source === 'planner' ? 'AI Planner' : 'Default Fallback'}
                </span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Status</span>
              <span className="flex items-center gap-1">
                {isCompleted ? (
                  <>
                    <CheckCircle size={12} className="text-green-400" />
                    <span className="text-green-400">Plan Ready</span>
                  </>
                ) : isPlanning ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    >
                      <Layers size={12} className="text-indigo-400" />
                    </motion.div>
                    <span className="text-indigo-400">Planning...</span>
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
              <Layers size={14} className="text-indigo-500" />
              <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Planner Activity</span>
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
                  <Layers size={32} className="text-slate-500" />
                </div>
                <p className="text-slate-400 text-sm">Keine Planner-Aktivitaet</p>
                <p className="text-slate-500 text-xs mt-2">Starte eine Aufgabe um den Planner zu aktivieren.</p>
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                  {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-indigo-900"></div>}
                  <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-indigo-700' : 'text-slate-600'}`}>
                    [{formatTime(i)}]
                  </span>
                  <div className={`flex-1 ${i === logs.length - 1 ? 'bg-indigo-950/20 p-2 rounded border-l-2 border-indigo-500' : ''}`}>
                    <p className={
                      log.event === 'Error' ? 'text-red-400' :
                      log.event === 'Warning' ? 'text-yellow-400' :
                      log.event === 'Success' ? 'text-green-400' :
                      i === logs.length - 1 ? 'text-indigo-100' :
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
              <Cpu size={16} className="text-indigo-400" />
              Metrics
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto planner-scrollbar p-4 space-y-4">
            {/* Token Metrics */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Hash size={14} className="text-indigo-400" />
                Token Verbrauch
              </h4>
              <div className="text-3xl font-bold text-white mb-1">
                {totalTokens > 0 ? totalTokens.toLocaleString() : '-'}
              </div>
              <p className="text-[10px] text-slate-500">geschaetzt</p>
            </div>

            {/* Model Info */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Cpu size={14} className="text-indigo-400" />
                Model
              </h4>
              <p className="text-sm text-white truncate">{model || 'Nicht zugewiesen'}</p>
            </div>

            {/* Status Info */}
            <div className={`rounded-lg p-4 border ${
              isCompleted ? 'bg-green-900/20 border-green-700/50' :
              isPlanning ? 'bg-indigo-900/20 border-indigo-700/50' :
              'bg-[#1e293b] border-[#334155]'
            }`}>
              <div className="flex items-center gap-2">
                {isCompleted ? (
                  <CheckCircle size={18} className="text-green-400" />
                ) : isPlanning ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  >
                    <Layers size={18} className="text-indigo-400" />
                  </motion.div>
                ) : (
                  <AlertCircle size={18} className="text-slate-400" />
                )}
                <span className={`text-sm font-semibold ${
                  isCompleted ? 'text-green-400' :
                  isPlanning ? 'text-indigo-400' :
                  'text-slate-400'
                }`}>
                  {isCompleted ? 'Plan erstellt' : isPlanning ? 'Planung...' : 'Bereit'}
                </span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`size-2 rounded-full ${
                  isPlanning ? 'bg-indigo-500 animate-pulse shadow-[0_0_5px_indigo]' :
                  isCompleted ? 'bg-green-500' :
                  'bg-slate-600'
                }`}></div>
                <span className="text-[10px] font-mono text-slate-400">
                  {model ? model.split('/').pop() : 'Kein Model'}
                </span>
              </div>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                isPlanning ? 'text-indigo-400 bg-indigo-950 border-indigo-900' :
                isCompleted ? 'text-green-400 bg-green-950 border-green-900' :
                'text-slate-400 bg-slate-800 border-slate-700'
              }`}>
                {isPlanning ? 'ACTIVE' : isCompleted ? 'DONE' : 'IDLE'}
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default PlannerOffice;
