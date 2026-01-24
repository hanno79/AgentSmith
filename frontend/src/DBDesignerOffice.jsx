import React, { useRef, useEffect } from 'react';
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

const DBDesignerOffice = ({ agentName = "Database Designer", status = "Idle", logs = [], onBack, color = "green" }) => {
  const terminalLogRef = useRef(null);
  const migrationLogRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (terminalLogRef.current) {
      terminalLogRef.current.scrollTop = terminalLogRef.current.scrollHeight;
    }
  }, [logs]);

  // Status badge styling
  const getStatusBadge = () => {
    const isActive = status !== 'Idle' && status !== 'Success' && status !== 'Failure';
    if (isActive) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 uppercase tracking-wide font-semibold shadow-[0_0_8px_rgba(16,185,129,0.2)]">
          System Status: Optimized
        </span>
      );
    }
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide">
        {status}
      </span>
    );
  };

  // Mock schema data
  const schemaItems = [
    {
      id: 1,
      type: 'active',
      name: 'users_auth_log',
      rows: '1.2M',
      columns: [
        { name: 'id (UUID)', isPrimary: true },
        { name: 'user_id (FK)', isForeign: true },
      ],
      efficiency: 98
    },
    {
      id: 2,
      type: 'unoptimized',
      name: 'transactions_history',
      detail: "Missing index on 'created_at'"
    },
    {
      id: 3,
      type: 'view',
      name: 'daily_metrics_view',
      detail: 'Materialized • Refreshing...'
    },
    {
      id: 4,
      type: 'vacuuming',
      name: 'orders_archived'
    },
  ];

  // Mock SQL code lines
  const sqlCode = [
    { line: 1, type: 'normal', content: 'CREATE TABLE public.users_auth_log (', parts: [{ text: 'CREATE TABLE', class: 'text-emerald-400' }, { text: ' public.users_auth_log (', class: 'text-slate-300' }] },
    { line: 2, type: 'normal', content: '  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),', indent: true },
    { line: 3, type: 'normal', content: '  user_id UUID NOT NULL REFERENCES users(id),', indent: true },
    { line: 4, type: 'normal', content: '  login_timestamp TIMESTAMPTZ DEFAULT NOW(),', indent: true },
    { line: 5, type: 'normal', content: '  ip_address INET,', indent: true },
    { line: 6, type: 'normal', content: '  device_info JSONB', indent: true },
    { line: 7, type: 'normal', content: ');' },
  ];

  // Mock migration log entries
  const migrationEntries = [
    {
      title: 'Transaction 0X88A2 (Committed)',
      items: [
        { text: 'Table', highlight: 'users_auth_log', suffix: ' created successfully. Storage engine:', highlight2: 'Heap', suffix2: '.' },
        { text: 'Constraint', highlight: 'fk_user_id', suffix: ' validated against 1.2M rows. Duration:', highlight2: '420ms', suffix2: '.' },
      ]
    },
    {
      title: 'Query Planner Result',
      items: [
        { text: 'Seq Scan skipped.', highlight: 'Index Scan using idx_users_email', suffix: ' utilized.' },
        { isPatch: true, title: 'OPTIMIZATION DETECTED', text: 'Estimated cost reduced from 154.2 to 12.4 by applying partial index filter.' },
      ]
    }
  ];

  // Mock cluster health data
  const clusterHealth = [
    { name: 'PRIMARY', value: 92, status: 'OK' },
    { name: 'REPL-1', value: 99, status: 'OK' },
    { name: 'REPL-2', value: 100, status: 'SYNC', isSync: true },
  ];

  // Format timestamp
  const formatTime = (index) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * 3);
    return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

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
                {getStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-05-DB</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Schema Migration Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] relative group hover:border-emerald-500/30 transition-colors">
            <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
            </span>
            <Table2 size={14} className="text-teal-500" />
            <span className="text-xs font-semibold text-white">Schema Migration #892</span>
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
            {schemaItems.map((item) => (
              <div key={item.id} className={item.type === 'active' ? 'relative group' : item.type === 'vacuuming' ? 'group cursor-pointer opacity-80' : 'group cursor-pointer'}>
                {item.type === 'active' ? (
                  <>
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-600 to-teal-600 rounded-lg opacity-20 blur-sm group-hover:opacity-40 transition-opacity"></div>
                    <div className="relative bg-[#1e293b] p-3 rounded-lg border border-emerald-500/30 shadow-lg">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-[10px] font-bold text-emerald-300 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-800 animate-pulse">ACTIVE</span>
                        <span className="text-[10px] text-slate-400 font-mono">{item.rows} Rows</span>
                      </div>
                      <h4 className="text-sm font-semibold text-white mb-2 truncate flex items-center gap-2">
                        <Table2 size={14} className="text-emerald-400" />
                        {item.name}
                      </h4>
                      <div className="space-y-1.5 pl-1">
                        {item.columns.map((col, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs text-slate-400">
                            {col.isPrimary ? (
                              <Key size={12} className="text-yellow-500" />
                            ) : (
                              <Link size={12} className="text-slate-500" />
                            )}
                            <span className="font-mono text-slate-300">{col.name}</span>
                          </div>
                        ))}
                        <div className="h-px w-full bg-slate-700/50 my-1"></div>
                        <div className="flex items-center justify-between text-xs text-slate-300">
                          <span className="flex items-center gap-1.5 text-[10px]">Index Scan</span>
                          <span className="font-mono text-emerald-400 text-[10px]">{item.efficiency}% Efficiency</span>
                        </div>
                      </div>
                    </div>
                  </>
                ) : item.type === 'unoptimized' ? (
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 uppercase">
                        <span className="size-1.5 bg-amber-500 rounded-full"></span>
                        Unoptimized
                      </span>
                      <AlertTriangle size={14} className="text-slate-500" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-emerald-100 transition-colors flex items-center gap-2">
                      <Table2 size={14} className="text-slate-400" />
                      {item.name}
                    </h4>
                    <p className="text-[11px] text-slate-500 mt-1 font-mono truncate">{item.detail}</p>
                  </div>
                ) : item.type === 'view' ? (
                  <div className="bg-[#1e293b]/40 hover:bg-[#1e293b] p-3 rounded-lg border border-[#334155] group-hover:border-slate-500 transition-all">
                    <div className="flex justify-between items-start mb-1">
                      <span className="flex items-center gap-1 text-[10px] font-bold text-teal-400 uppercase">
                        <span className="size-1.5 bg-teal-500 rounded-full"></span>
                        View
                      </span>
                      <Eye size={14} className="text-slate-500" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-300 group-hover:text-emerald-100 transition-colors flex items-center gap-2">
                      <Table2 size={14} className="text-slate-400" />
                      {item.name}
                    </h4>
                    <p className="text-[11px] text-slate-500 mt-1 font-mono truncate">{item.detail}</p>
                  </div>
                ) : (
                  <div className="bg-[#1e293b]/20 p-3 rounded-lg border border-[#334155] border-dashed">
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-[10px] font-bold text-slate-500 uppercase">Vacuuming</span>
                      <Trash2 size={14} className="text-slate-600 animate-pulse" />
                    </div>
                    <h4 className="text-sm font-medium text-slate-400">Autovacuum: {item.name}</h4>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Schema Validation Footer */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Schema Validation</span>
              <span className="text-emerald-400">No Errors</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              <div className="h-full w-[100%] bg-gradient-to-r from-emerald-600 to-teal-500 rounded-full"></div>
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
              ref={terminalLogRef}
              className="flex-1 p-5 overflow-y-auto dbdesigner-scrollbar font-mono text-xs space-y-1"
            >
              {logs.length === 0 ? (
                <>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">1</span>
                    <div className="flex-1">
                      <p className="text-slate-300">
                        <span className="text-emerald-400">CREATE TABLE</span> public.users_auth_log (
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1 pl-4">
                      <p className="text-slate-300">
                        id <span className="text-blue-400">UUID</span> <span className="text-emerald-400">PRIMARY KEY DEFAULT</span> gen_random_uuid(),
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1 pl-4">
                      <p className="text-slate-300">
                        user_id <span className="text-blue-400">UUID</span> <span className="text-emerald-400">NOT NULL REFERENCES</span> users(id),
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1 pl-4">
                      <p className="text-slate-300">
                        login_timestamp <span className="text-blue-400">TIMESTAMPTZ</span> <span className="text-emerald-400">DEFAULT NOW</span>(),
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1 pl-4">
                      <p className="text-slate-300">
                        ip_address <span className="text-blue-400">INET</span>,
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1 pl-4">
                      <p className="text-slate-300">
                        device_info <span className="text-blue-400">JSONB</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none"></span>
                    <div className="flex-1">
                      <p className="text-slate-300">);</p>
                    </div>
                  </div>
                  <div className="h-2"></div>
                  <div className="flex gap-4 group relative">
                    <div className="absolute left-[3.5rem] top-2 bottom-2 w-0.5 bg-emerald-900"></div>
                    <span className="text-emerald-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">2</span>
                    <div className="flex-1 bg-emerald-950/20 p-2 rounded border-l-2 border-emerald-500">
                      <p className="text-slate-300">
                        <span className="text-emerald-400">CREATE INDEX CONCURRENTLY</span> idx_auth_log_timestamp<br />
                        <span className="text-emerald-400">ON</span> public.users_auth_log (login_timestamp <span className="text-emerald-400">DESC</span>);
                      </p>
                      <p className="text-emerald-400/70 italic text-[10px] mt-1">-- Performance hint: Optimized for recent login lookups</p>
                    </div>
                  </div>
                  <div className="h-2"></div>
                  <div className="flex gap-4 group">
                    <span className="text-slate-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">3</span>
                    <div className="flex-1">
                      <p className="text-slate-300">
                        <span className="text-emerald-400">EXPLAIN ANALYZE SELECT</span> * <span className="text-emerald-400">FROM</span> users_auth_log<br />
                        <span className="text-emerald-400">WHERE</span> user_id = <span className="text-teal-300">'550e8400-e29b-41d4-a716-446655440000'</span>;
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4 group animate-pulse">
                    <span className="text-emerald-600 w-12 shrink-0 pt-0.5 border-r border-slate-800 pr-2 select-none">4</span>
                    <span className="w-2 h-4 bg-emerald-500 block"></span>
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
              <div className="space-y-6">
                {migrationEntries.map((entry, entryIndex) => (
                  <div key={entryIndex}>
                    <h5 className="text-slate-500 text-xs uppercase tracking-wider mb-2 border-b border-slate-800 pb-1">{entry.title}</h5>
                    <ul className="space-y-2">
                      {entry.items.map((item, itemIndex) => (
                        <li key={itemIndex} className="flex items-start text-slate-300">
                          <span className="text-emerald-500 mr-2">●</span>
                          {item.isPatch ? (
                            <div className="bg-slate-800/50 p-2 rounded w-full border border-slate-700/50 border-l-4 border-l-emerald-500">
                              <span className="text-xs text-emerald-400 block mb-1 font-bold">{item.title}</span>
                              <span>{item.text}</span>
                            </div>
                          ) : (
                            <span>
                              {item.text} <span className="text-teal-300">{item.highlight}</span>{item.suffix}
                              {item.highlight2 && <span className="text-emerald-400">{item.highlight2}</span>}
                              {item.suffix2}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className="h-4 w-2 bg-emerald-500 animate-pulse mt-4"></div>
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
          </div>

          <div className="flex-1 overflow-y-auto dbdesigner-scrollbar p-5 space-y-6">
            {/* Query Latency */}
            <div className="bg-[#1e293b] rounded-xl p-4 border border-[#334155] relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                <Activity size={60} />
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Query Latency</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white">4.2ms</span>
                <span className="text-sm text-teal-400 font-medium font-mono">P99</span>
              </div>
              <div className="mt-3 h-2 w-full bg-[#0f172a] rounded-full overflow-hidden flex gap-0.5">
                <div className="h-full w-[15%] bg-emerald-600 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
                <div className="h-full w-[30%] bg-teal-500/80"></div>
                <div className="h-full w-[55%] bg-slate-700/20"></div>
              </div>
              <div className="flex justify-between mt-1 text-[9px] text-slate-500 uppercase font-bold">
                <span>Fast</span>
                <span>Avg</span>
                <span>Slow</span>
              </div>
            </div>

            {/* Storage Usage */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <HardDrive size={14} className="text-emerald-400" />
                Storage Usage
              </h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Data Size</p>
                  <p className="text-lg font-bold text-white">84 <span className="text-[10px] text-slate-500 font-normal">GB</span></p>
                </div>
                <div className="bg-[#0f172a] p-2 rounded border border-slate-700/50">
                  <p className="text-[9px] text-slate-400 uppercase">Index Size</p>
                  <p className="text-lg font-bold text-white">12 <span className="text-[10px] text-slate-500 font-normal">GB</span></p>
                </div>
                <div className="col-span-2 bg-[#0f172a] p-2 rounded border border-slate-700/50 flex items-center justify-between">
                  <div>
                    <p className="text-[9px] text-slate-400 uppercase">Index Health</p>
                    <p className="text-lg font-bold text-white">99.4% <span className="text-[10px] text-slate-500 font-normal">Hit Ratio</span></p>
                  </div>
                  <div className="size-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
                </div>
              </div>
            </div>

            {/* Cluster Health */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155] flex flex-col justify-between">
              <div className="flex justify-between items-center mb-2">
                <p className="text-xs text-slate-400 uppercase font-semibold">Cluster Health</p>
                <span className="text-[10px] text-emerald-300 bg-emerald-950 px-1.5 rounded border border-emerald-900">Live</span>
              </div>
              <div className="space-y-2">
                {clusterHealth.map((node, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]">
                    <span className="w-12 text-slate-500 text-right">{node.name}</span>
                    <div className="flex-1 h-2 bg-[#0f172a] rounded-sm overflow-hidden">
                      <div
                        className={`h-full rounded-sm ${node.isSync ? 'bg-teal-500 shadow-[0_0_8px_rgba(16,185,129,0.4)] animate-pulse' : 'bg-emerald-500'}`}
                        style={{ width: `${node.value}%` }}
                      ></div>
                    </div>
                    <span className="w-8 text-slate-300 text-right">{node.status}</span>
                  </div>
                ))}
              </div>
            </div>
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
