/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Researcher Office - Detailansicht für den Researcher-Agenten mit Web-Recherche.
 */

import React, { useRef } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Search,
  History,
  Settings,
  Rss,
  Globe,
  Database,
  Clock,
  Sparkles,
  Shield,
  Layers,
  PauseCircle,
  FileText,
  RefreshCw,
  Maximize2
} from 'lucide-react';

const ResearcherOffice = ({
  agentName = "Researcher",
  status = "Idle",
  logs = [],
  onBack,
  color = "cyan",
  // Live-Daten vom Backend
  query = "",
  result = "",
  researchStatus = "",
  model = "",
  error = "",
  // ÄNDERUNG 08.02.2026: researchTimeoutMinutes entfernt - pro Agent im ModelModal
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const knowledgeRef = useRef(null);

  // Status-Indikatoren basierend auf echten Daten
  const isSearching = researchStatus === 'searching';
  const isCompleted = researchStatus === 'completed';
  const hasError = researchStatus === 'error' || researchStatus === 'timeout';
  const hasData = query || result;

  // Berechne Recherche-Statistiken aus dem Ergebnis
  const resultLength = result ? result.length : 0;
  const wordCount = result ? result.split(/\s+/).filter(w => w.length > 0).length : 0;

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-cyan-500/20 text-cyan-300 border-cyan-500/20 font-semibold shadow-[0_0_8px_rgba(6,182,212,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Node Status: Online' : badge.text}
      </span>
    );
  };

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-cyan-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-500/30 shadow-[0_0_10px_rgba(34,211,238,0.1)]">
              <Search size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-04-RES</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-cyan-500/30 transition-colors">
            <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
            <Globe size={14} className="text-cyan-500" />
            <span className="text-xs font-semibold text-white">Deep Crawl #4402</span>
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

        {/* Left Sidebar - Research Query */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Rss size={16} className="text-cyan-400" />
              Research Task
            </h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
              isSearching ? 'bg-cyan-950 text-cyan-400 border-cyan-900' :
              isCompleted ? 'bg-green-950 text-green-400 border-green-900' :
              hasError ? 'bg-red-950 text-red-400 border-red-900' :
              'bg-slate-800 text-slate-400 border-slate-700'
            }`}>
              {isSearching ? 'SEARCHING' : isCompleted ? 'COMPLETED' : hasError ? 'ERROR' : 'IDLE'}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto researcher-scrollbar p-4 space-y-4">
            {/* Aktuelle Query */}
            {query ? (
              <div className="relative group">
                {isSearching && (
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-teal-500 rounded-lg opacity-20 blur-sm group-hover:opacity-40 transition-opacity"></div>
                )}
                <div className={`relative bg-[#1e293b] p-3 rounded-lg border shadow-lg ${
                  isSearching ? 'border-cyan-500/30' :
                  isCompleted ? 'border-green-500/30' :
                  hasError ? 'border-red-500/30' :
                  'border-[#334155]'
                }`}>
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                      isSearching ? 'text-cyan-400 bg-cyan-950/50 border-cyan-800' :
                      isCompleted ? 'text-green-400 bg-green-950/50 border-green-800' :
                      hasError ? 'text-red-400 bg-red-950/50 border-red-800' :
                      'text-slate-400 bg-slate-800 border-slate-700'
                    }`}>
                      {isSearching ? 'SEARCHING' : isCompleted ? 'DONE' : hasError ? 'FAILED' : 'QUERY'}
                    </span>
                    <Globe size={14} className="text-slate-500" />
                  </div>
                  <h4 className="text-sm font-semibold text-white mb-2">{query}</h4>
                  {isSearching && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-300">
                        <span className="flex items-center gap-1.5">
                          <RefreshCw size={12} className="text-cyan-400 animate-spin" />
                          Sucht im Web...
                        </span>
                      </div>
                      <div className="h-1 w-full bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-cyan-400 rounded-full animate-pulse w-[60%]"></div>
                      </div>
                    </div>
                  )}
                  {hasError && error && (
                    <p className="text-xs text-red-400 mt-2">{error}</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-[#1e293b]/20 p-4 rounded-lg border border-[#334155] border-dashed">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Waiting</span>
                  <Clock size={14} className="text-slate-600" />
                </div>
                <h4 className="text-sm font-medium text-slate-400">Keine aktive Recherche</h4>
                <p className="text-xs text-slate-500 mt-1">Starte eine Aufgabe um die Recherche zu beginnen.</p>
              </div>
            )}

            {/* Model Info */}
            {model && (
              <div className="bg-[#1e293b]/40 p-3 rounded-lg border border-[#334155]">
                <div className="flex justify-between items-start mb-1">
                  <span className="flex items-center gap-1 text-[10px] font-bold text-cyan-400 uppercase">
                    <span className="size-1.5 bg-cyan-500 rounded-full"></span>
                    Model
                  </span>
                  <Database size={14} className="text-slate-500" />
                </div>
                <h4 className="text-sm font-medium text-slate-300">{model}</h4>
              </div>
            )}
          </div>

          {/* Result Stats Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Ergebnis</span>
              <span>{wordCount} Wörter</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div
                className={`h-full rounded-full transition-all duration-500 ${isCompleted ? 'bg-gradient-to-r from-green-600 to-green-400' : 'bg-gradient-to-r from-cyan-600 to-cyan-400'}`}
                style={{ width: isCompleted ? '100%' : isSearching ? '50%' : '0%' }}
              ></div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Insight Synthesis Panel */}
          <div className="h-[40%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Sparkles size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                >
                  <Sparkles size={14} />
                </motion.div>
                Insight Synthesis
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">CONFIDENCE: 92.4%</span>
                <span className="size-2 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto researcher-scrollbar font-mono text-xs space-y-4"
            >
              {logs.length === 0 ? (
                <>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:10]</span>
                    <div className="flex-1">
                      <p className="text-slate-400 mb-1">Correlating data points from <span className="text-cyan-600">Source A</span> and <span className="text-cyan-600">Source C</span>...</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:12]</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Pattern Detected: Significant overlap in "Agentic Workflows" terminology across 4 recent papers.</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group relative">
                    <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-cyan-900"></div>
                    <span className="text-cyan-700 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">[14:02:15]</span>
                    <div className="flex-1 bg-cyan-950/20 p-2 rounded border-l-2 border-cyan-500">
                      <p className="text-cyan-300 font-semibold mb-1">Hypothesis Formulation:</p>
                      <p className="text-cyan-100/80 italic">The current implementation of the 'Coder' agent lacks context retention for long-running tasks, leading to repetitive queries. Proposed solution: Vector memory integration.</p>
                    </div>
                  </div>
                  <div className="flex gap-4 group animate-pulse">
                    <span className="text-cyan-500 w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2">...</span>
                    <p className="text-cyan-500/70 italic">Synthesizing final report...</p>
                  </div>
                </>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-cyan-900"></div>}
                    <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-cyan-700' : 'text-slate-600'}`}>
                      [{formatTime(i)}]
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-cyan-950/20 p-2 rounded border-l-2 border-cyan-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-yellow-400' :
                        log.event === 'Success' ? 'text-green-400' :
                        i === logs.length - 1 ? 'text-cyan-100' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Research Result Panel */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Search size={14} className="text-teal-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Recherche-Ergebnis</span>
              </div>
              <div className="flex gap-2">
                {result && (
                  <span className="text-[10px] bg-green-900/40 text-green-300 border border-green-700/50 px-2 py-0.5 rounded">
                    {resultLength} Zeichen
                  </span>
                )}
              </div>
            </div>

            <div
              ref={knowledgeRef}
              className="flex-1 p-6 overflow-y-auto researcher-scrollbar font-mono text-sm leading-6"
            >
              {result ? (
                <div className="space-y-4">
                  <div className="bg-[#1e293b]/30 p-4 rounded-lg border border-[#334155]">
                    <h5 className="text-cyan-400 text-xs uppercase tracking-wider mb-3 border-b border-slate-800 pb-2 flex items-center gap-2">
                      <FileText size={14} />
                      Recherche-Zusammenfassung
                    </h5>
                    <div className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {result}
                    </div>
                  </div>
                </div>
              ) : isSearching ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <RefreshCw size={48} className="text-cyan-400 animate-spin mb-4" />
                  <p className="text-slate-400 text-sm">Durchsuche das Web nach relevanten Informationen...</p>
                  <p className="text-slate-500 text-xs mt-2">Dies kann einige Minuten dauern.</p>
                </div>
              ) : hasError ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="size-16 rounded-full bg-red-900/20 flex items-center justify-center mb-4">
                    <Shield size={32} className="text-red-400" />
                  </div>
                  <p className="text-red-400 text-sm font-semibold">Recherche fehlgeschlagen</p>
                  {error && <p className="text-slate-500 text-xs mt-2">{error}</p>}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="size-16 rounded-full bg-slate-800/50 flex items-center justify-center mb-4">
                    <Search size={32} className="text-slate-500" />
                  </div>
                  <p className="text-slate-400 text-sm">Keine Recherche-Ergebnisse</p>
                  <p className="text-slate-500 text-xs mt-2">Starte eine Aufgabe um die Web-Recherche zu beginnen.</p>
                </div>
              )}
              {isSearching && <div className="h-4 w-2 bg-cyan-400 animate-pulse mt-4"></div>}
            </div>

            {/* Status Footer */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <div className={`flex-1 px-4 py-2 rounded-lg text-sm font-bold flex items-center justify-center gap-2 ${
                isCompleted ? 'bg-green-900/30 text-green-400 border border-green-700/50' :
                isSearching ? 'bg-cyan-900/30 text-cyan-400 border border-cyan-700/50' :
                hasError ? 'bg-red-900/30 text-red-400 border border-red-700/50' :
                'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
                {isCompleted ? (
                  <>
                    <Shield size={16} />
                    Recherche abgeschlossen
                  </>
                ) : isSearching ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    Recherche läuft...
                  </>
                ) : hasError ? (
                  <>
                    <Shield size={16} />
                    Fehler aufgetreten
                  </>
                ) : (
                  <>
                    <Clock size={16} />
                    Bereit für Recherche
                  </>
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Research Statistics */}
        <aside className="w-[340px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Shield size={16} className="text-teal-400" />
              Research Statistics
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto researcher-scrollbar p-5 space-y-6">
            {/* Status Overview */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Shield size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Status</p>
              <div className="flex items-baseline gap-2">
                <span className={`text-3xl font-black ${
                  isCompleted ? 'text-green-400' :
                  isSearching ? 'text-cyan-400' :
                  hasError ? 'text-red-400' :
                  'text-slate-400'
                }`}>
                  {isCompleted ? 'Done' : isSearching ? 'Active' : hasError ? 'Error' : 'Idle'}
                </span>
              </div>
              <div className="mt-3 h-2 w-full bg-[#0f172a] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isCompleted ? 'bg-green-500 w-full' :
                    isSearching ? 'bg-cyan-500 w-1/2 animate-pulse' :
                    hasError ? 'bg-red-500 w-full' :
                    'bg-slate-600 w-0'
                  }`}
                ></div>
              </div>
              <div className="flex justify-between mt-1 text-[9px] text-slate-500 uppercase font-bold">
                <span>Start</span>
                <span>Searching</span>
                <span>Complete</span>
              </div>
            </div>

            {/* Research Metrics */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Layers size={14} className="text-cyan-400" />
                Ergebnis-Metriken
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Wörter</p>
                  <p className="text-lg font-bold text-white">{wordCount}</p>
                </div>
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Zeichen</p>
                  <p className="text-lg font-bold text-white">{resultLength}</p>
                </div>
                <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50 flex items-center justify-between">
                  <div>
                    <p className="text-[9px] text-slate-400 uppercase">Model</p>
                    <p className="text-sm font-bold text-white truncate">{model || 'Nicht zugewiesen'}</p>
                  </div>
                  {isSearching && (
                    <div className="size-8 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin"></div>
                  )}
                </div>
              </div>
            </div>

            {/* Query Info */}
            {query && (
              <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-xs text-slate-400 uppercase font-semibold">Aktuelle Query</p>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{query}</p>
              </div>
            )}

            {/* ÄNDERUNG 08.02.2026: Research Timeout Slider entfernt - pro Agent im ModelModal */}

            {/* Error Info */}
            {hasError && error && (
              <div className="bg-red-900/20 rounded-lg p-4 border border-red-700/50">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-xs text-red-400 uppercase font-semibold">Fehler</p>
                </div>
                <p className="text-sm text-red-300 leading-relaxed">{error}</p>
              </div>
            )}
          </div>

          {/* Model Footer */}
          <div className="p-4 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`size-2 rounded-full ${
                  isSearching ? 'bg-cyan-500 animate-pulse shadow-[0_0_5px_cyan]' :
                  isCompleted ? 'bg-green-500' :
                  hasError ? 'bg-red-500' :
                  'bg-slate-600'
                }`}></div>
                <span className="text-[10px] font-mono text-slate-400">
                  {model || 'Kein Model'}
                </span>
              </div>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                isSearching ? 'text-cyan-400 bg-cyan-950 border-cyan-900' :
                isCompleted ? 'text-green-400 bg-green-950 border-green-900' :
                hasError ? 'text-red-400 bg-red-950 border-red-900' :
                'text-slate-400 bg-slate-800 border-slate-700'
              }`}>
                {isSearching ? 'ACTIVE' : isCompleted ? 'DONE' : hasError ? 'ERROR' : 'IDLE'}
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ResearcherOffice;
