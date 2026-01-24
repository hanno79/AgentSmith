/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Reviewer Office - Detailansicht für den Reviewer-Agenten mit Code-Qualitätsprüfung.
 */

import React, { useRef } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ShieldCheck,
  History,
  Settings,
  Shield,
  Gauge,
  BookOpen,
  FlaskConical,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  FileCode,
  Send,
  ChevronLeft,
  ChevronRight,
  Gavel,
  Edit3
} from 'lucide-react';

const ReviewerOffice = ({ agentName = "Reviewer", status = "Idle", logs = [], onBack, color = "yellow" }) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const reviewLogRef = useRef(null);

  // Status Badge Rendering Helper (with pulse indicator for active state)
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20');
    if (badge.isActive) {
      return (
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-yellow-500/20 text-yellow-400 border border-yellow-500/20 uppercase tracking-wide flex items-center gap-1">
          <span className="size-1.5 rounded-full bg-yellow-400 animate-pulse"></span>
          Active
        </span>
      );
    }
    return (
      <span className={badge.className}>
        {badge.text}
      </span>
    );
  };

  // MOCK-DATEN: Demo-Diff-Daten
  const diffFiles = [
    {
      name: 'src/components/Auth.tsx',
      status: 'modified',
      lines: [
        { num: 12, type: 'removed', code: '- const user = await db.getUser(id);' },
        { num: 12, type: 'added', code: '+ const user = await db.getUserSafe(id);' },
        { num: 13, type: 'context', code: '  if (!user) return null;' },
        { num: 14, type: 'context', code: '  return user.profile;' },
      ]
    },
    {
      name: 'src/api/routes.ts',
      status: 'modified',
      lines: [
        { num: 45, type: 'context', code: "  app.post('/login', (req, res) => {" },
        { num: 46, type: 'added', code: '+   validateInput(req.body);', highlight: true },
        { num: 47, type: 'context', code: '    const { email, password } = req.body;' },
      ]
    }
  ];

  // MOCK-DATEN: Demo-Status-Karten
  const statusCards = [
    { title: 'Security', icon: Shield, status: 'passed', value: 'Passed', color: 'green' },
    { title: 'Performance', icon: Gauge, status: 'passed', value: '98/100', color: 'green' },
    { title: 'Readability', icon: BookOpen, status: 'warning', value: 'Review', color: 'yellow' },
    { title: 'Test Coverage', icon: FlaskConical, status: 'pending', value: 'Calculating...', color: 'slate' },
  ];

  // MOCK-DATEN: Konfidenz-Bewertung
  const confidenceScore = 92;

  return (
    <div className="bg-[#010409] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#30363d] px-6 py-3 bg-[#010409] z-20">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded bg-gradient-to-br from-yellow-500 to-yellow-600 text-black shadow-[0_0_15px_rgba(234,179,8,0.4)]">
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName} Workstation
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">AGENT: REVIEW-09</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#161b22] border border-[#30363d]">
            <Shield size={14} className="text-yellow-500" />
            <span className="text-xs font-semibold text-white">Security Scan: Active</span>
          </div>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#161b22] hover:bg-[#21262d] text-white transition-colors border border-[#30363d]">
            <History size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#161b22] hover:bg-[#21262d] text-white transition-colors border border-[#30363d]">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Sidebar - Code Diff Viewer */}
        <aside className="w-[320px] border-r border-[#30363d] bg-[#0d1117] flex flex-col z-10 hidden md:flex">
          <div className="p-4 border-b border-[#30363d] flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <FileCode size={16} className="text-yellow-500" />
              Code Diff Viewer
            </h3>
            <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">PR #402</span>
          </div>

          <div className="flex-1 overflow-y-auto reviewer-scrollbar">
            {diffFiles.map((file, fileIndex) => (
              <div key={fileIndex} className="flex flex-col">
                <div className="px-4 py-2 bg-slate-800/50 border-b border-[#30363d] text-xs text-slate-400 font-mono flex justify-between">
                  <span>{file.name}</span>
                  <span className="text-yellow-500 capitalize">{file.status}</span>
                </div>
                <div className="font-mono text-[11px] leading-5">
                  {file.lines.map((line, lineIndex) => (
                    <div
                      key={lineIndex}
                      className={`flex relative ${
                        line.type === 'removed' ? 'bg-red-900/20 text-slate-400 hover:bg-red-900/30' :
                        line.type === 'added' ? 'bg-green-900/20 text-green-200 hover:bg-green-900/30' :
                        'text-slate-400 hover:bg-slate-800/30'
                      }`}
                    >
                      <span className="w-8 text-right pr-2 text-slate-600 select-none border-r border-slate-700 mr-2 bg-[#0d1117]">
                        {line.num}
                      </span>
                      <span>{line.code}</span>
                      {line.highlight && (
                        <div className="absolute right-2 top-0.5 w-1.5 h-1.5 bg-yellow-500 rounded-full animate-ping"></div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Assets Changed Section */}
            <div className="mt-6 px-4 pb-4">
              <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-2">Assets Changed</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="aspect-video bg-slate-800 rounded border border-slate-700 flex items-center justify-center relative overflow-hidden group cursor-pointer">
                  <span className="text-[10px] text-slate-500">old_logo.svg</span>
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-red-400 text-xs font-bold">DELETED</span>
                  </div>
                </div>
                <div className="aspect-video bg-slate-800 rounded border border-slate-700 flex items-center justify-center relative overflow-hidden group cursor-pointer">
                  <span className="text-[10px] text-slate-500">new_logo.svg</span>
                  <div className="absolute inset-0 bg-yellow-500/10 border-2 border-yellow-500"></div>
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-yellow-500 text-xs font-bold">ADDED</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col relative bg-[#010409]">
          {/* Grid Background */}
          <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.15] pointer-events-none"
            style={{ backgroundSize: '24px 24px' }}
          ></div>

          {/* Toolbar */}
          <div className="h-12 border-b border-[#30363d] flex items-center justify-between px-4 bg-[#161b22]/50 backdrop-blur z-10">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-yellow-500 font-bold text-sm" style={{ textShadow: '0 0 10px rgba(234, 179, 8, 0.5)' }}>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <Shield size={18} />
                </motion.div>
                <span>SCANNING CODEBASE...</span>
              </div>
              <div className="h-4 w-px bg-[#30363d]"></div>
              <div className="flex gap-1">
                <button className="px-2 py-1 rounded bg-white/5 text-slate-200 text-xs flex items-center gap-1 border border-[#30363d]">
                  <AlertTriangle size={12} className="text-yellow-500" />
                  0 Bugs
                </button>
                <button className="px-2 py-1 rounded bg-white/5 text-slate-200 text-xs flex items-center gap-1 border border-[#30363d]">
                  <AlertTriangle size={12} className="text-yellow-500" />
                  2 Warnings
                </button>
                <button className="px-2 py-1 rounded bg-white/5 text-slate-200 text-xs flex items-center gap-1 border border-[#30363d]">
                  <Info size={12} className="text-blue-400" />
                  5 Info
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Lines: +45 / -12</span>
              <div className="h-4 w-px bg-slate-700 mx-2"></div>
              <button className="p-1 text-slate-400 hover:text-white">
                <ChevronLeft size={16} />
              </button>
              <span className="text-xs text-white">File 2 of 5</span>
              <button className="p-1 text-slate-400 hover:text-white">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 relative overflow-hidden flex flex-col p-6 gap-6 z-10">
            {/* Status Cards */}
            <div className="grid grid-cols-4 gap-4">
              {statusCards.map((card, i) => {
                const Icon = card.icon;
                const borderColor = card.color === 'green' ? 'border-green-500/30' :
                                   card.color === 'yellow' ? 'border-yellow-500/30' :
                                   'border-[#30363d]';
                const textColor = card.color === 'green' ? 'text-green-400' :
                                 card.color === 'yellow' ? 'text-yellow-500' :
                                 'text-slate-300';
                const StatusIcon = card.status === 'passed' ? CheckCircle :
                                  card.status === 'warning' ? AlertTriangle :
                                  FlaskConical;

                return (
                  <div key={i} className={`bg-[#161b22] border ${borderColor} rounded-lg p-3 flex flex-col relative overflow-hidden`}>
                    <div className="absolute right-0 top-0 p-1 opacity-20">
                      <Icon size={40} className={textColor} />
                    </div>
                    <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">{card.title}</span>
                    <div className={`flex items-center gap-2 ${textColor} font-bold text-lg`}>
                      <StatusIcon size={18} />
                      {card.value}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Analysis Output Log */}
            <div className="flex-1 bg-[#0d1117] rounded-xl border border-[#30363d] overflow-hidden flex flex-col shadow-2xl relative">
              {/* Shimmer Animation */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-yellow-500/10 to-transparent pointer-events-none z-10"
                initial={{ x: '-100%' }}
                animate={{ x: '100%' }}
                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              />

              <div className="bg-[#161b22] px-4 py-2 border-b border-[#30363d] flex justify-between items-center">
                <div className="flex gap-2 text-xs font-mono text-slate-400">
                  <span>analysis_output.log</span>
                  <span className="text-slate-600">|</span>
                  <span className="text-yellow-500">Live Analysis</span>
                </div>
                <div className="flex gap-1.5">
                  <div className="size-2.5 rounded-full bg-slate-600"></div>
                  <div className="size-2.5 rounded-full bg-slate-600"></div>
                </div>
              </div>

              <div
                ref={logRef}
                className="p-6 font-mono text-sm overflow-y-auto reviewer-scrollbar relative flex-1"
              >
                <div className="space-y-4">
                  {logs.length === 0 ? (
                    <>
                      <div className="flex gap-4 opacity-50">
                        <span className="text-slate-500 select-none">01</span>
                        <span className="text-slate-300">Initiating static analysis on module 'Auth'...</span>
                      </div>
                      <div className="flex gap-4 opacity-70">
                        <span className="text-slate-500 select-none">02</span>
                        <span className="text-slate-300">Checking for known vulnerabilities (CVE database v2023.4)...</span>
                      </div>
                      <div className="flex gap-4">
                        <span className="text-slate-500 select-none">03</span>
                        <span className="text-green-400">No critical vulnerabilities found.</span>
                      </div>
                      <div className="flex gap-4 mt-8">
                        <span className="text-slate-500 select-none">04</span>
                        <span className="text-yellow-500 animate-pulse">_ Waiting for review task...</span>
                      </div>
                    </>
                  ) : (
                    logs.map((log, i) => (
                      <div
                        key={i}
                        className={`flex gap-4 ${
                          log.event === 'Error' ? 'border-l-2 border-red-500 pl-4 bg-red-500/5 py-2' :
                          log.event === 'Warning' ? 'border-l-2 border-yellow-500 pl-4 bg-yellow-500/5 py-2' :
                          log.event === 'Success' ? 'text-green-400' :
                          i === logs.length - 1 ? 'border-l-2 border-yellow-500 pl-4 bg-yellow-500/5 py-2' :
                          ''
                        }`}
                      >
                        <span className="text-slate-500 select-none">{String(i + 1).padStart(2, '0')}</span>
                        <span className={
                          log.event === 'Error' ? 'text-red-400' :
                          log.event === 'Warning' ? 'text-yellow-500' :
                          log.event === 'Success' ? 'text-green-400' :
                          'text-slate-300'
                        }>{log.message}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Mini Code Preview */}
              <div className="absolute bottom-4 right-4 w-32 h-40 bg-[#161b22] border border-[#30363d] rounded opacity-80 shadow-lg z-20 hidden md:block">
                <div className="w-full h-full p-1 space-y-0.5">
                  <div className="h-1 bg-slate-700 w-3/4"></div>
                  <div className="h-1 bg-slate-700 w-1/2"></div>
                  <div className="h-1 bg-slate-700 w-full"></div>
                  <div className="h-1 bg-green-500/50 w-full"></div>
                  <div className="h-1 bg-green-500/50 w-2/3"></div>
                  <div className="h-1 bg-slate-700 w-1/2"></div>
                  <div className="h-1 bg-yellow-500/50 w-full"></div>
                  <div className="h-1 bg-slate-700 w-3/4"></div>
                </div>
                <div className="absolute inset-x-0 top-1/2 h-8 bg-yellow-500/10 border-y border-yellow-500/30 pointer-events-none"></div>
              </div>
            </div>
          </div>
        </main>

        {/* Right Sidebar - Confidence & Decision */}
        <aside className="w-[320px] border-l border-[#30363d] bg-[#0d1117] flex flex-col z-10 hidden lg:flex">
          {/* Confidence Score */}
          <div className="p-6 border-b border-[#30363d] flex flex-col items-center">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 w-full text-center">Confidence Score</h3>
            <div className="relative size-40 flex items-center justify-center mb-2">
              <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="8"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  fill="none"
                  stroke="#eab308"
                  strokeWidth="8"
                  strokeDasharray={`${(confidenceScore / 100) * 251.2} 251.2`}
                  strokeLinecap="round"
                  style={{ filter: 'drop-shadow(0 0 8px rgba(234,179,8,0.5))' }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-black text-white" style={{ textShadow: '0 0 10px rgba(234, 179, 8, 0.5)' }}>{confidenceScore}%</span>
                <span className="text-[10px] text-yellow-500 font-bold tracking-widest uppercase">High Confidence</span>
              </div>
            </div>
            <p className="text-center text-xs text-slate-500 px-4">Based on 142 checks and historical data patterns.</p>
          </div>

          {/* Decision Panel */}
          <div className="p-4 border-b border-[#30363d] bg-[#161b22]">
            <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2 mb-3">
              <Gavel size={16} className="text-yellow-500" />
              Decision Panel
            </h3>
            <div className="space-y-3">
              <button className="w-full py-3 rounded-lg bg-green-600 hover:bg-green-500 text-white font-bold text-sm shadow-[0_0_15px_rgba(34,197,94,0.3)] transition-all flex items-center justify-center gap-2">
                <CheckCircle size={16} />
                Approve Changes
              </button>
              <button className="w-full py-3 rounded-lg bg-[#0d1117] border border-yellow-500/50 hover:bg-yellow-500/10 text-yellow-500 font-bold text-sm transition-all flex items-center justify-center gap-2">
                <Edit3 size={16} />
                Request Changes
              </button>
              <button className="w-full py-3 rounded-lg bg-[#0d1117] border border-red-500/50 hover:bg-red-500/10 text-red-500 font-bold text-sm transition-all flex items-center justify-center gap-2">
                <XCircle size={16} />
                Reject
              </button>
            </div>
          </div>

          {/* Review Log */}
          <div className="flex-1 overflow-y-auto p-4 reviewer-scrollbar bg-[#0d1117]">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Review Log</h3>
            <div
              ref={reviewLogRef}
              className="space-y-3"
            >
              {logs.length === 0 ? (
                <>
                  <div className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">10:45</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Started review of <span className="text-yellow-500">PR #402</span></p>
                    </div>
                  </div>
                  <div className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">10:46</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Flagged complexity in <span className="font-mono text-slate-400">auth.ts</span></p>
                    </div>
                  </div>
                  <div className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">10:46</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Verified security compliance for token storage.</p>
                    </div>
                  </div>
                  <div className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">10:47</span>
                    <div className="flex-1">
                      <p className="text-slate-300">Performance regression check passed.</p>
                    </div>
                  </div>
                </>
              ) : (
                logs.slice(-10).map((log, i) => (
                  <div key={i} className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">{formatTime(i)}</span>
                    <div className="flex-1">
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-yellow-500' :
                        log.event === 'Success' ? 'text-green-400' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Comment Input */}
          <div className="p-3 border-t border-[#30363d] bg-[#0d1117]">
            <div className="relative">
              <textarea
                className="w-full bg-[#161b22] border border-[#30363d] rounded-md py-2 pl-3 pr-8 text-xs text-white placeholder-slate-600 focus:ring-1 focus:ring-yellow-500 focus:border-yellow-500 resize-none h-20"
                placeholder="Add a summary comment..."
              ></textarea>
              <button className="absolute right-2 bottom-2 text-yellow-500 hover:text-white bg-yellow-500/10 hover:bg-yellow-500 p-1 rounded transition-colors">
                <Send size={14} />
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ReviewerOffice;
