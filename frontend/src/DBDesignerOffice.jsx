/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.1
 * Beschreibung: DB Designer Office - Detailansicht für den Datenbank-Designer mit Schema-Übersicht.
 *               ÄNDERUNG 24.01.2026: Dummy-Daten durch echte Backend-Daten ersetzt (DBDesignerOutput Event).
 */

import React, { useRef } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Database,
  History,
  Settings,
  Table2,
  Key,
  Link,
  AlertTriangle,
  Eye,
  Trash2,
  Code,
  FileText,
  BarChart3,
  HardDrive,
  Server,
  Activity,
  Play,
  Maximize2
} from 'lucide-react';

const DBDesignerOffice = ({
  agentName = "Database Designer",
  status = "Idle",
  logs = [],
  onBack,
  color = "green",
  // ÄNDERUNG 24.01.2026: Echte Daten Props vom Backend
  schema = "",
  model = "",
  tables = [],
  dbStatus = ""
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const migrationLogRef = useRef(null);

  // Prüfen ob echte Daten vorhanden sind
  const hasData = schema !== '' || tables.length > 0 || dbStatus === 'completed';

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-emerald-500/20 text-emerald-300 border-emerald-500/20 font-semibold shadow-[0_0_8px_rgba(16,185,129,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'System Status: Optimized' : badge.text}
      </span>
    );
  };

  // ÄNDERUNG 24.01.2026: Schema Items aus echten Tabellen-Daten generieren
  const getSchemaItems = () => {
    if (!hasData || tables.length === 0) return [];

    return tables.map((table, index) => ({
      id: index + 1,
      type: index === 0 ? 'active' : 'table',
      name: table.name,
      columns: table.columns?.map(col => ({
        name: `${col.name} (${col.type})`,
        isPrimary: col.isPrimary,
        isForeign: col.isForeign
      })) || [],
      efficiency: 95 + Math.floor(Math.random() * 5) // Platzhalter für echte Metriken
    }));
  };

  const schemaItems = getSchemaItems();

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-emerald-900/10">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
              <Database size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-05-DB</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Schema Status Badge - ÄNDERUNG 24.01.2026: Dynamisch statt hardcodiert */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-emerald-500/30 transition-colors">
            {dbStatus === 'completed' && (
              <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            )}
            {!hasData && (
              <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
              </span>
            )}
            <Table2 size={14} className="text-teal-500" />
            <span className="text-xs font-semibold text-white">
              {hasData ? `${tables.length} Tabellen definiert` : 'Schema in Arbeit...'}
            </span>
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

        {/* Left Sidebar - Schema Explorer */}
        <aside className="w-[320px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Table2 size={16} className="text-emerald-500" />
              Schema Explorer
            </h3>
            <span className="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-900 px-1.5 py-0.5 rounded font-mono">public</span>
          </div>

          <div className="flex-1 overflow-y-auto dbdesigner-scrollbar p-4 space-y-4">
            {/* ÄNDERUNG 24.01.2026: Dynamische Schema Explorer Anzeige */}
            {!hasData ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-10">
                <Database size={48} className="text-slate-700 mb-4" />
                <p className="text-slate-400 text-sm">Warte auf Schema...</p>
                <p className="text-slate-500 text-xs mt-2">Der DB Designer erstellt das Schema.</p>
              </div>
            ) : schemaItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-10">
                <Table2 size={48} className="text-slate-700 mb-4" />
                <p className="text-slate-400 text-sm">Keine Tabellen definiert</p>
              </div>
            ) : (
              schemaItems.map((item, index) => (
                <div key={item.id} className={index === 0 ? 'relative group' : 'group cursor-pointer'}>
                  {index === 0 ? (
                    <>
                      {/* Erste Tabelle hervorgehoben */}
                      <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-lg opacity-20 blur-sm group-hover:opacity-40 transition-opacity"></div>
                      <div className="relative bg-[#1e293b] p-3 rounded-lg border border-emerald-500/30 shadow-lg">
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-[10px] font-bold text-emerald-300 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-800">TABLE</span>
                          <span className="text-[10px] text-slate-400 font-mono">{item.columns?.length || 0} cols</span>
                        </div>
                        <h4 className="text-sm font-semibold text-white mb-2 truncate flex items-center gap-2">
                          <Table2 size={14} className="text-emerald-400" />
                          {item.name}
                        </h4>
                        {item.columns && item.columns.length > 0 && (
                          <div className="space-y-1.5 pl-1">
                            {item.columns.slice(0, 5).map((col, i) => (
                              <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
                                {col.isPrimary ? (
                                  <Key size={12} className="text-yellow-500" />
                                ) : col.isForeign ? (
                                  <Link size={12} className="text-blue-400" />
                                ) : (
                                  <span className="w-3 h-3" />
                                )}
                                <span className="font-mono text-slate-300 truncate">{col.name}</span>
                              </div>
                            ))}
                            {item.columns.length > 5 && (
                              <p className="text-[10px] text-slate-500 italic">+{item.columns.length - 5} weitere Spalten</p>
                            )}
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    /* Weitere Tabellen */
                    <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                      <div className="flex justify-between items-start mb-1">
                        <span className="flex items-center gap-1 text-[10px] font-bold text-teal-400 uppercase">
                          <span className="size-1.5 bg-teal-500 rounded-full"></span>
                          Table
                        </span>
                        <span className="text-[10px] text-slate-500">{item.columns?.length || 0} cols</span>
                      </div>
                      <h4 className="text-sm font-medium text-slate-300 group-hover:text-emerald-100 transition-colors flex items-center gap-2">
                        <Table2 size={14} className="text-slate-400" />
                        {item.name}
                      </h4>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Schema Validation Footer - ÄNDERUNG 24.01.2026: Dynamisch */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Schema Validation</span>
              <span className={hasData && dbStatus === 'completed' ? 'text-emerald-400' : 'text-slate-500'}>
                {!hasData ? 'Warte...' : dbStatus === 'completed' ? 'Validiert' : 'In Arbeit'}
              </span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div
                className={`h-full rounded-full transition-all ${hasData && dbStatus === 'completed' ? 'bg-gradient-to-r from-emerald-600 to-teal-500' : 'bg-slate-600'}`}
                style={{ width: hasData ? (dbStatus === 'completed' ? '100%' : '50%') : '0%' }}
              ></div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Query & Schema Terminal */}
          <div className="h-[45%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Code size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Code size={14} />
                </motion.div>
                Query & Schema Terminal
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">CONNECTION: POSTGRES-PRIMARY-01</span>
                <span className="size-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto dbdesigner-scrollbar font-mono text-xs space-y-1"
            >
              {/* ÄNDERUNG 24.01.2026: Dynamische Anzeige basierend auf echten Daten */}
              {logs.length === 0 && !hasData ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <Database size={48} className="text-slate-700 mb-4" />
                  <p className="text-slate-400">Warte auf DB Designer...</p>
                  <p className="text-slate-500 text-[10px] mt-2">Das Schema wird hier angezeigt.</p>
                </div>
              ) : logs.length === 0 && schema ? (
                <>
                  {/* Zeige echten Schema-String */}
                  <div className="flex gap-4 group mb-2">
                    <span className="text-emerald-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">SQL</span>
                    <div className="flex-1 bg-emerald-950/20 p-2 rounded border-l-2 border-emerald-500">
                      <p className="text-emerald-400/70 italic text-[10px] mb-2">-- Generiertes Schema vom DB Designer</p>
                    </div>
                  </div>
                  {schema.split('\n').map((line, i) => (
                    <div key={i} className="flex gap-4 group">
                      <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">{i + 1}</span>
                      <div className="flex-1">
                        <p className="text-slate-300 whitespace-pre-wrap">
                          {line.includes('CREATE TABLE') ? (
                            <>
                              <span className="text-emerald-400">CREATE TABLE</span>
                              {line.replace('CREATE TABLE', '')}
                            </>
                          ) : line.includes('PRIMARY KEY') ? (
                            <>
                              {line.split('PRIMARY KEY')[0]}
                              <span className="text-emerald-400">PRIMARY KEY</span>
                              {line.split('PRIMARY KEY')[1] || ''}
                            </>
                          ) : line.includes('REFERENCES') ? (
                            <>
                              {line.split('REFERENCES')[0]}
                              <span className="text-blue-400">REFERENCES</span>
                              {line.split('REFERENCES')[1] || ''}
                            </>
                          ) : (
                            line
                          )}
                        </p>
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-4 group animate-pulse mt-2">
                    <span className="text-emerald-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">✓</span>
                    <span className="text-emerald-400">Schema erfolgreich generiert</span>
                  </div>
                </>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[3.5rem] top-2 bottom-2 w-0.5 bg-emerald-900"></div>}
                    <span className={`w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none ${i === logs.length - 1 ? 'text-emerald-600' : 'text-slate-600'}`}>
                      {i + 1}
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-emerald-950/20 p-2 rounded border-l-2 border-emerald-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-amber-400' :
                        log.event === 'Success' ? 'text-emerald-400' :
                        i === logs.length - 1 ? 'text-emerald-200' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Migration Log */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-teal-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Migration Log</span>
              </div>
              <div className="flex gap-2">
                <button className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded hover:bg-slate-700 transition-colors">Output</button>
                <button className="text-[10px] bg-emerald-900/40 text-emerald-300 border border-emerald-700/50 px-2 py-0.5 rounded">Execution Plan</button>
              </div>
            </div>

            <div
              ref={migrationLogRef}
              className="flex-1 p-6 overflow-y-auto dbdesigner-scrollbar font-mono text-sm leading-6"
            >
              {/* ÄNDERUNG 24.01.2026: Dynamischer Migration Log basierend auf echten Daten */}
              <div className="space-y-6">
                {!hasData ? (
                  <div className="flex flex-col items-center justify-center h-full text-center py-8">
                    <FileText size={32} className="text-slate-700 mb-3" />
                    <p className="text-slate-500 text-xs">Warte auf Schema-Erstellung...</p>
                  </div>
                ) : (
                  <>
                    {/* Tabellen-Übersicht aus echten Daten */}
                    <div>
                      <h5 className="text-slate-500 text-xs uppercase tracking-wider mb-2 border-b border-slate-800 pb-1">
                        Schema Erstellung ({dbStatus === 'completed' ? 'Abgeschlossen' : 'In Arbeit'})
                      </h5>
                      <ul className="space-y-2">
                        {tables.map((table, i) => (
                          <li key={i} className="flex items-start text-slate-300">
                            <span className="text-emerald-500 mr-2">●</span>
                            <span>
                              Tabelle <span className="text-teal-300">{table.name}</span> erstellt.
                              {table.columns && table.columns.length > 0 && (
                                <span className="text-slate-500"> ({table.columns.length} Spalten)</span>
                              )}
                            </span>
                          </li>
                        ))}
                        {tables.length === 0 && (
                          <li className="text-slate-500 italic">Keine Tabellen definiert</li>
                        )}
                      </ul>
                    </div>

                    {/* Status-Info */}
                    {dbStatus === 'completed' && (
                      <div>
                        <h5 className="text-slate-500 text-xs uppercase tracking-wider mb-2 border-b border-slate-800 pb-1">Status</h5>
                        <ul className="space-y-2">
                          <li className="flex items-start text-slate-300">
                            <span className="text-emerald-500 mr-2">●</span>
                            <div className="bg-slate-800/50 p-2 rounded w-full border border-slate-700/50 border-l-4 border-l-emerald-500">
                              <span className="text-xs text-emerald-400 block mb-1 font-bold">SCHEMA VALIDIERT</span>
                              <span>Alle {tables.length} Tabellen wurden erfolgreich erstellt und validiert.</span>
                            </div>
                          </li>
                        </ul>
                      </div>
                    )}
                  </>
                )}
                {hasData && <div className="h-4 w-2 bg-emerald-500 animate-pulse mt-4"></div>}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <BarChart3 size={16} />
                Analyze Query
              </button>
              <button className="flex-[2] bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(16,185,129,0.4)] animate-pulse">
                <Play size={16} />
                EXECUTE MIGRATION
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - DB Performance */}
        <aside className="w-[340px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Activity size={16} className="text-emerald-500" />
              DB Performance
            </h3>
            {/* ÄNDERUNG 24.01.2026: Model-Info anzeigen */}
            {model && (
              <p className="text-[10px] text-slate-500 mt-1 font-mono">Model: {model}</p>
            )}
          </div>

          <div className="flex-1 overflow-y-auto dbdesigner-scrollbar p-5 space-y-6">
            {/* ÄNDERUNG 24.01.2026: Warte-Zustand wenn keine Daten */}
            {!hasData ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-10">
                <Database size={48} className="text-slate-600 mb-4" />
                <p className="text-slate-400 text-sm">Warte auf Schema-Daten...</p>
                <p className="text-slate-500 text-xs mt-2">Der DB Designer erstellt das Schema.</p>
              </div>
            ) : (
              <>
                {/* Schema Status */}
                <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
                  <div className="absolute top-0 right-0 p-2 opacity-10">
                    <Activity size={60} />
                  </div>
                  <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Schema Status</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-white">{tables.length}</span>
                    <span className="text-sm text-teal-400 font-medium font-mono">Tabellen</span>
                  </div>
                  <div className="mt-3 h-2 w-full bg-[#0f172a] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-600 shadow-[0_0_10px_rgba(16,185,129,0.5)] transition-all"
                      style={{ width: dbStatus === 'completed' ? '100%' : '50%' }}
                    ></div>
                  </div>
                  <div className="flex justify-between mt-1 text-[9px] text-slate-500 uppercase font-bold">
                    <span>Design</span>
                    <span>Validation</span>
                    <span>{dbStatus === 'completed' ? 'Fertig' : 'In Arbeit'}</span>
                  </div>
                </div>

                {/* Schema Details */}
                <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
                  <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                    <HardDrive size={14} className="text-emerald-400" />
                    Schema Details
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                      <p className="text-[9px] text-slate-400 uppercase">Tabellen</p>
                      <p className="text-lg font-bold text-white">{tables.length}</p>
                    </div>
                    <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                      <p className="text-[9px] text-slate-400 uppercase">Spalten</p>
                      <p className="text-lg font-bold text-white">
                        {tables.reduce((sum, t) => sum + (t.columns?.length || 0), 0)}
                      </p>
                    </div>
                    <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50 flex items-center justify-between">
                      <div>
                        <p className="text-[9px] text-slate-400 uppercase">Status</p>
                        <p className="text-lg font-bold text-emerald-400">
                          {dbStatus === 'completed' ? 'Fertig' : 'In Arbeit'}
                        </p>
                      </div>
                      {dbStatus === 'completed' ? (
                        <div className="size-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                          <span className="text-emerald-400">✓</span>
                        </div>
                      ) : (
                        <div className="size-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Table List */}
                <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] flex flex-col justify-between">
                  <div className="flex justify-between items-center mb-2">
                    <p className="text-xs text-slate-400 uppercase font-semibold">Tabellen-Übersicht</p>
                    <span className="text-[10px] text-emerald-300 bg-emerald-950 px-1.5 rounded border border-emerald-900">
                      {tables.length} Total
                    </span>
                  </div>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {tables.map((table, i) => (
                      <div key={i} className="flex items-center gap-2 text-[10px]">
                        <Table2 size={12} className="text-emerald-500" />
                        <span className="flex-1 text-slate-300 truncate">{table.name}</span>
                        <span className="text-slate-500">{table.columns?.length || 0} cols</span>
                      </div>
                    ))}
                    {tables.length === 0 && (
                      <p className="text-slate-500 text-xs italic">Keine Tabellen definiert</p>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Map Footer */}
          <div className="p-0 border-t border-[#334155] bg-[#0f172a] h-40 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-900/20 to-slate-900/80"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] to-transparent"></div>
            <div className="absolute bottom-3 right-3 flex flex-col items-end">
              <div className="flex gap-1 mb-1">
                <div className="size-2 bg-slate-600 rounded-full"></div>
                <div className="size-2 bg-emerald-500 rounded-full animate-ping shadow-[0_0_5px_emerald]"></div>
                <div className="size-2 bg-slate-600 rounded-full"></div>
              </div>
              <span className="text-[9px] font-mono text-emerald-300 bg-black/50 px-1 rounded backdrop-blur-sm border border-emerald-900/50">SECTOR: DATA-CORE</span>
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

export default DBDesignerOffice;
