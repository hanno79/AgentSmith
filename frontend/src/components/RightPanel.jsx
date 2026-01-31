/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Right Panel - Live Canvas und Global Output Loop.
 * # ÄNDERUNG [31.01.2026]: Right Panel aus App.jsx ausgelagert.
 */

import React, { useEffect, useRef } from 'react';
import {
  RefreshCw,
  Search,
  Code2,
  Palette,
  ShieldCheck,
  Bug,
  Cpu,
  Database,
  Lock,
  FileText,
  CheckSquare
} from 'lucide-react';
import { formatLogForUser, HIDDEN_USER_EVENTS } from '../utils/LogFormatter';

// ÄNDERUNG 25.01.2026: Icon- und Farb-Mapping für Global Output Loop
const agentIconMap = {
  Researcher: { icon: Search, color: 'text-cyan-400' },
  Coder: { icon: Code2, color: 'text-blue-400' },
  Designer: { icon: Palette, color: 'text-pink-400' },
  Reviewer: { icon: ShieldCheck, color: 'text-yellow-400' },
  Tester: { icon: Bug, color: 'text-orange-400' },
  TechArchitect: { icon: Cpu, color: 'text-purple-400' },
  DBDesigner: { icon: Database, color: 'text-green-400' },
  Security: { icon: Lock, color: 'text-red-400' },
  Orchestrator: { icon: Cpu, color: 'text-slate-400' },
  System: { icon: RefreshCw, color: 'text-slate-500' },
  // ÄNDERUNG 30.01.2026: Documentation Manager und Quality Gate
  DocumentationManager: { icon: FileText, color: 'text-white' },
  QualityGate: { icon: CheckSquare, color: 'text-white' }
};

const getAgentIcon = (agentName) => {
  const mapping = agentIconMap[agentName];
  if (mapping) {
    const IconComponent = mapping.icon;
    return <IconComponent size={14} className={mapping.color} />;
  }
  return <Code2 size={14} className="text-slate-400" />;
};

const RightPanel = ({
  agentData = {},
  status = 'Idle',
  previewHeight = 60,
  onResizeMouseDown,
  isDragging = false,
  outputMode = 'user',
  onOutputModeChange,
  logs = []
}) => {
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleOutputModeChange = (mode) => {
    if (typeof onOutputModeChange === 'function') {
      onOutputModeChange(mode);
    }
  };

  return (
    <aside
      id="right-sidebar"
      className="w-[400px] border-l border-border-dark bg-[#0d1216] hidden 2xl:flex flex-col z-20"
    >
      {/* Live Canvas Panel (variable Höhe) */}
      <div
        className="flex flex-col overflow-hidden"
        style={{ height: `${previewHeight}%` }}
      >
        <div className="h-10 border-b border-border-dark flex items-center justify-between px-4 bg-[#111418] shrink-0">
          <div className="flex items-center gap-2 text-sm font-bold">
            <RefreshCw size={14} className="text-slate-400" />
            <span>Live Canvas</span>
          </div>
          <span className="text-[10px] text-emerald-400 font-mono">● Live</span>
        </div>

        <div className="flex-1 p-3 bg-[#1e1e1e] overflow-hidden">
          <div className="w-full h-full bg-white rounded shadow-2xl flex flex-col overflow-hidden">
            {/* Browser Chrome */}
            <div className="bg-gray-100 border-b border-gray-200 px-3 py-1.5 flex items-center gap-2 shrink-0">
              <div className="flex gap-1">
                <div className="w-2 h-2 rounded-full bg-red-400" />
                <div className="w-2 h-2 rounded-full bg-yellow-400" />
                <div className="w-2 h-2 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 bg-white h-4 rounded border border-gray-200 text-[9px] text-gray-400 flex items-center px-2">
                localhost:3000
              </div>
            </div>
            {/* Canvas Content - Echter Screenshot oder Placeholder */}
            <div className="flex-1 flex items-center justify-center overflow-hidden bg-gray-50">
              {agentData?.tester?.screenshot ? (
                <img
                  src={agentData.tester.screenshot}
                  alt="Live Preview"
                  className="w-full h-full object-contain"
                />
              ) : status === 'Working' ? (
                <div className="flex flex-col items-center gap-2 p-4">
                  <RefreshCw size={32} className="text-gray-400 animate-spin" />
                  <div className="text-gray-500 text-xs">Generiere Vorschau...</div>
                </div>
              ) : status === 'Success' ? (
                <div className="text-green-600 text-sm font-medium">Fertig</div>
              ) : (
                <div className="text-gray-400 text-xs italic text-center px-4">
                  Canvas leer. Starte ein Projekt.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Resize Handle */}
      <div
        onMouseDown={onResizeMouseDown}
        className={`h-2 bg-[#1a1a2e] hover:bg-violet-600 cursor-row-resize flex items-center justify-center transition-colors shrink-0 ${isDragging ? 'bg-violet-600' : ''}`}
      >
        <div className="w-10 h-0.5 bg-slate-600 rounded-full"></div>
      </div>

      {/* Global Output Loop (restliche Höhe) */}
      <div
        className="flex flex-col overflow-hidden"
        style={{ height: `${100 - previewHeight}%` }}
      >
        {/* ÄNDERUNG 25.01.2026: Header mit USER/DEBUG Toggle */}
        <div className="px-4 py-2 border-b border-border-dark flex justify-between items-center bg-[#111418] shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Global Output Loop</span>
            {/* Toggle Buttons */}
            <div className="flex gap-0.5 bg-slate-800/50 p-0.5 rounded">
              <button
                onClick={() => handleOutputModeChange('user')}
                className={`px-2 py-0.5 text-[9px] font-bold rounded transition-colors ${
                  outputMode === 'user'
                    ? 'bg-blue-500/30 text-blue-300'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                USER
              </button>
              <button
                onClick={() => handleOutputModeChange('debug')}
                className={`px-2 py-0.5 text-[9px] font-bold rounded transition-colors ${
                  outputMode === 'debug'
                    ? 'bg-purple-500/30 text-purple-300'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                DEBUG
              </button>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[10px] text-green-500 font-mono">CONNECTED</span>
          </div>
        </div>
        {/* ÄNDERUNG 25.01.2026: Log-Ausgabe mit USER/DEBUG Formatierung */}
        {/* ÄNDERUNG 28.01.2026: Performance-Limit und Null-Filter hinzugefügt */}
        <div className="flex-1 p-3 overflow-y-auto terminal-scroll text-[10px] flex flex-col gap-1">
          {logs
            .slice(-500)  // Performance: Max 500 Logs anzeigen
            .filter(log => {
              // Debug: Alles anzeigen
              if (outputMode === 'debug') return true;
              // User: Technische Events ausblenden
              return !HIDDEN_USER_EVENTS.includes(log.event);
            })
            .map((log, index) => {
              if (outputMode === 'debug') {
                // ÄNDERUNG 29.01.2026: Message zu String konvertieren falls Objekt
                // Verhindert React-Fehler "Objects are not valid as a React child"
                let messageStr = log.message;
                if (typeof log.message === 'object' && log.message !== null) {
                  try {
                    messageStr = JSON.stringify(log.message);
                  } catch {
                    messageStr = String(log.message);
                  }
                } else if (typeof log.message !== 'string') {
                  messageStr = String(log.message ?? '');
                }

                // Debug-Ansicht (rohe Daten mit Event-Typ)
                return (
                  <div key={index} className="flex gap-2 font-mono">
                    <span className="text-purple-500/60 shrink-0">[{log.event}]</span>
                    <span className="text-slate-600 shrink-0">[{log.agent}]</span>
                    <span className={log.event === 'Error' ? 'text-red-400' : 'text-slate-300'}>{messageStr}</span>
                  </div>
                );
              }

              // User-Ansicht (formatiert)
              const formatted = formatLogForUser(log);
              if (!formatted) return null;

              return (
                <div key={index} className="py-1.5 border-b border-slate-800/30 last:border-0">
                  <div className="flex items-start gap-2">
                    <span className="shrink-0 mt-0.5">{getAgentIcon(log.agent)}</span>
                    <div className="flex-1 min-w-0">
                      <span className="text-slate-200 font-medium text-[11px]">{formatted.title}</span>
                      <p className="text-slate-400 text-[10px] break-words leading-relaxed">{formatted.summary}</p>
                      {formatted.detail && (
                        <p className="text-slate-500 text-[9px] mt-0.5 italic leading-relaxed">{formatted.detail}</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
            .filter(Boolean)
          }
          <div ref={logEndRef} />
        </div>
      </div>
    </aside>
  );
};

export default RightPanel;
