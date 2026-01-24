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
  Edit3,
  Cpu,
  RefreshCw
} from 'lucide-react';

// ÄNDERUNG 24.01.2026: Erweiterte Props für echte Daten vom Backend (inkl. humanSummary)
const ReviewerOffice = ({
  agentName = "Reviewer",
  status = "Idle",
  logs = [],
  onBack,
  color = "yellow",
  verdict = "",
  isApproved = false,
  humanSummary = "",
  feedback = "",
  model = "",
  iteration = 0,
  maxIterations = 3,
  sandboxStatus = "",
  sandboxResult = "",
  testSummary = ""
}) => {
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

  // ÄNDERUNG 24.01.2026: Prüfe ob echte Daten vorhanden sind
  const hasData = verdict !== '' || iteration > 0;

  // ÄNDERUNG 24.01.2026: Dynamischer Confidence Score basierend auf Verdict und Sandbox-Status
  const calculateConfidence = () => {
    if (!hasData) return null;
    if (verdict === 'OK' && sandboxStatus === 'PASS') return 100;
    if (verdict === 'OK' && sandboxStatus === 'FAIL') return 60;
    if (verdict === 'FEEDBACK' && sandboxStatus === 'PASS') return 70;
    if (verdict === 'FEEDBACK' && sandboxStatus === 'FAIL') return 30;
    return 50;
  };
  const confidenceScore = calculateConfidence();

  // ÄNDERUNG 24.01.2026: Dynamische Status Cards basierend auf echten Daten
  const getStatusCards = () => {
    if (!hasData) {
      return [
        { title: 'Sandbox', icon: Shield, status: 'pending', value: 'Warte...', color: 'slate' },
        { title: 'Verdict', icon: Gavel, status: 'pending', value: 'Warte...', color: 'slate' },
        { title: 'Iteration', icon: RefreshCw, status: 'pending', value: '0/0', color: 'slate' },
        { title: 'Tests', icon: FlaskConical, status: 'pending', value: 'Warte...', color: 'slate' },
      ];
    }
    return [
      {
        title: 'Sandbox',
        icon: Shield,
        status: sandboxStatus === 'PASS' ? 'passed' : sandboxStatus === 'FAIL' ? 'failed' : 'pending',
        value: sandboxStatus || 'Pending',
        color: sandboxStatus === 'PASS' ? 'green' : sandboxStatus === 'FAIL' ? 'red' : 'slate'
      },
      {
        title: 'Verdict',
        icon: Gavel,
        status: verdict === 'OK' ? 'passed' : verdict === 'FEEDBACK' ? 'warning' : 'pending',
        value: verdict || 'Pending',
        color: verdict === 'OK' ? 'green' : verdict === 'FEEDBACK' ? 'yellow' : 'slate'
      },
      {
        title: 'Iteration',
        icon: RefreshCw,
        status: iteration > 0 ? 'active' : 'pending',
        value: `${iteration}/${maxIterations}`,
        color: iteration >= maxIterations ? 'red' : 'slate'
      },
      {
        title: 'Tests',
        icon: FlaskConical,
        status: testSummary.includes('❌') ? 'failed' : testSummary ? 'passed' : 'pending',
        value: testSummary.includes('❌') ? 'Issues' : testSummary ? 'OK' : 'Warte...',
        color: testSummary.includes('❌') ? 'red' : testSummary ? 'green' : 'slate'
      }
    ];
  };
  const statusCards = getStatusCards();

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
              <div className="text-xs text-slate-400 font-medium tracking-wide">
                {model ? `Model: ${model}` : 'Warte auf Modell-Info...'}
              </div>
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
        {/* Left Sidebar - Review History (ÄNDERUNG 24.01.2026: Echte Logs statt Mock DiffFiles) */}
        <aside className="w-[320px] border-r border-[#30363d] bg-[#0d1117] flex flex-col z-10 hidden md:flex">
          <div className="p-4 border-b border-[#30363d] flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <History size={16} className="text-yellow-500" />
              Review History
            </h3>
            {iteration > 0 && (
              <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
                Iteration {iteration}/{maxIterations}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto reviewer-scrollbar p-4">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4">
                <FileCode size={32} className="text-slate-600 mb-3" />
                <p className="text-sm text-slate-500">Keine Reviews</p>
                <p className="text-xs text-slate-600 mt-1">Starte einen Task um Reviews zu sehen</p>
              </div>
            ) : (
              <div className="space-y-3">
                {logs.map((log, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg border transition-colors ${
                      log.event === 'Feedback' || log.event === 'ReviewOutput'
                        ? 'bg-yellow-900/10 border-yellow-500/20'
                        : log.event === 'Error'
                        ? 'bg-red-900/10 border-red-500/20'
                        : log.event === 'Status' && log.message.includes('OK')
                        ? 'bg-green-900/10 border-green-500/20'
                        : 'bg-slate-800/50 border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] font-bold uppercase ${
                        log.event === 'Feedback' || log.event === 'ReviewOutput' ? 'text-yellow-500' :
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Status' && log.message.includes('OK') ? 'text-green-400' :
                        'text-slate-400'
                      }`}>{log.event}</span>
                      <span className="text-[10px] text-slate-500">{formatTime(i)}</span>
                    </div>
                    <p className="text-xs text-slate-300 line-clamp-3">{log.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sandbox Result Summary */}
          {sandboxResult && (
            <div className="p-4 border-t border-[#30363d]">
              <h4 className="text-xs font-bold text-slate-400 uppercase mb-2">Sandbox Result</h4>
              <div className={`p-2 rounded text-xs font-mono overflow-auto max-h-24 ${
                sandboxStatus === 'PASS' ? 'bg-green-900/20 text-green-400' : 'bg-red-900/20 text-red-400'
              }`}>
                {sandboxResult.slice(0, 200)}{sandboxResult.length > 200 ? '...' : ''}
              </div>
            </div>
          )}
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col relative bg-[#010409]">
          {/* Grid Background */}
          <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.15] pointer-events-none"
            style={{ backgroundSize: '24px 24px' }}
          ></div>

          {/* Toolbar - ÄNDERUNG 24.01.2026: Dynamische Statuswerte */}
          <div className="h-12 border-b border-[#30363d] flex items-center justify-between px-4 bg-[#161b22]/50 backdrop-blur z-10">
            <div className="flex items-center gap-4">
              {status === 'Status' || status === 'Feedback' || status === 'ReviewOutput' ? (
                <div className="flex items-center gap-2 text-yellow-500 font-bold text-sm" style={{ textShadow: '0 0 10px rgba(234, 179, 8, 0.5)' }}>
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}>
                    <Shield size={18} />
                  </motion.div>
                  <span>REVIEWING CODE...</span>
                </div>
              ) : verdict ? (
                <div className={`flex items-center gap-2 font-bold text-sm ${verdict === 'OK' ? 'text-green-500' : 'text-yellow-500'}`}>
                  {verdict === 'OK' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
                  <span>{verdict === 'OK' ? 'REVIEW PASSED' : 'CHANGES REQUIRED'}</span>
                </div>
              ) : (
                <span className="text-slate-500 text-sm">Warte auf Review...</span>
              )}
              <div className="h-4 w-px bg-[#30363d]"></div>
              <div className="flex gap-1">
                <button className={`px-2 py-1 rounded text-xs flex items-center gap-1 border ${
                  sandboxStatus === 'FAIL' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-white/5 text-slate-200 border-[#30363d]'
                }`}>
                  <Shield size={12} />
                  Sandbox: {sandboxStatus || '-'}
                </button>
                <button className="px-2 py-1 rounded bg-white/5 text-slate-200 text-xs flex items-center gap-1 border border-[#30363d]">
                  <Info size={12} className="text-blue-400" />
                  Iteration: {iteration}/{maxIterations}
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {model && <span className="text-xs text-slate-500 font-mono">{model}</span>}
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

        {/* Right Sidebar - Confidence & Decision (ÄNDERUNG 24.01.2026: Dynamische Werte) */}
        <aside className="w-[320px] border-l border-[#30363d] bg-[#0d1117] flex flex-col z-10 hidden lg:flex">
          {/* Model Info Header */}
          <div className="p-4 border-b border-[#30363d] bg-[#161b22]">
            <div className="flex items-center gap-2 text-sm">
              <Cpu size={14} className="text-yellow-500" />
              <span className="text-slate-400">Modell:</span>
              {model ? (
                <span className="text-yellow-400 font-semibold">{model}</span>
              ) : (
                <span className="text-slate-500 italic">Warte auf Modell-Info...</span>
              )}
            </div>
          </div>

          {/* Confidence Score */}
          <div className="p-6 border-b border-[#30363d] flex flex-col items-center">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 w-full text-center">Confidence Score</h3>
            {confidenceScore !== null ? (
              <>
                <div className="relative size-40 flex items-center justify-center mb-2">
                  <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="8" />
                    <circle
                      cx="50" cy="50" r="40" fill="none"
                      stroke={confidenceScore >= 80 ? '#22c55e' : confidenceScore >= 50 ? '#eab308' : '#ef4444'}
                      strokeWidth="8"
                      strokeDasharray={`${(confidenceScore / 100) * 251.2} 251.2`}
                      strokeLinecap="round"
                      style={{ filter: `drop-shadow(0 0 8px ${confidenceScore >= 80 ? 'rgba(34,197,94,0.5)' : confidenceScore >= 50 ? 'rgba(234,179,8,0.5)' : 'rgba(239,68,68,0.5)'})` }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-4xl font-black text-white">{confidenceScore}%</span>
                    <span className={`text-[10px] font-bold tracking-widest uppercase ${
                      confidenceScore >= 80 ? 'text-green-500' : confidenceScore >= 50 ? 'text-yellow-500' : 'text-red-500'
                    }`}>
                      {confidenceScore >= 80 ? 'High Confidence' : confidenceScore >= 50 ? 'Medium' : 'Low Confidence'}
                    </span>
                  </div>
                </div>
                <p className="text-center text-xs text-slate-500 px-4">
                  Basierend auf Sandbox ({sandboxStatus || '-'}) und Verdict ({verdict || '-'})
                </p>
              </>
            ) : (
              <div className="h-40 flex flex-col items-center justify-center">
                <Gauge size={32} className="text-slate-600 mb-3" />
                <p className="text-sm text-slate-500">Keine Bewertung</p>
                <p className="text-xs text-slate-600 mt-1">Warte auf Review-Ergebnis</p>
              </div>
            )}
          </div>

          {/* Decision Panel - Zeigt aktuelles Verdict mit menschenlesbarer Zusammenfassung */}
          <div className="p-4 border-b border-[#30363d] bg-[#161b22]">
            <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2 mb-3">
              <Gavel size={16} className="text-yellow-500" />
              Review Ergebnis
            </h3>
            {verdict ? (
              <>
                {/* Hauptstatus-Box mit klarem OK/NICHT OK */}
                <div className={`w-full py-4 px-4 rounded-lg font-bold text-base flex flex-col items-center justify-center gap-2 ${
                  isApproved
                    ? 'bg-green-600 text-white shadow-[0_0_20px_rgba(34,197,94,0.4)]'
                    : sandboxStatus === 'FAIL'
                      ? 'bg-red-600/20 border-2 border-red-500 text-red-400'
                      : 'bg-yellow-500/20 border-2 border-yellow-500 text-yellow-400'
                }`}>
                  <div className="flex items-center gap-2">
                    {isApproved ? (
                      <CheckCircle size={24} />
                    ) : sandboxStatus === 'FAIL' ? (
                      <XCircle size={24} />
                    ) : (
                      <AlertTriangle size={24} />
                    )}
                    <span className="text-lg">
                      {isApproved ? 'REVIEW BESTANDEN' : sandboxStatus === 'FAIL' ? 'REVIEW FEHLGESCHLAGEN' : 'ÄNDERUNGEN NÖTIG'}
                    </span>
                  </div>
                </div>
                {/* Menschenlesbare Zusammenfassung */}
                {humanSummary && (
                  <div className={`mt-3 p-3 rounded-lg text-sm ${
                    isApproved
                      ? 'bg-green-900/20 border border-green-500/30 text-green-300'
                      : sandboxStatus === 'FAIL'
                        ? 'bg-red-900/20 border border-red-500/30 text-red-300'
                        : 'bg-yellow-900/20 border border-yellow-500/30 text-yellow-300'
                  }`}>
                    {humanSummary}
                  </div>
                )}
              </>
            ) : (
              <div className="w-full py-4 rounded-lg bg-slate-800 border border-slate-700 text-slate-500 font-medium text-sm text-center flex items-center justify-center gap-2">
                <RefreshCw size={16} className="animate-spin" />
                Warte auf Review-Ergebnis...
              </div>
            )}
          </div>

          {/* Feedback Section (wenn vorhanden) - ÄNDERUNG: Vollständiges Feedback ohne Begrenzung */}
          {feedback && (
            <div className="p-4 border-b border-[#30363d] bg-[#0d1117]">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                Vollständiges Reviewer Feedback
              </h3>
              <div className="bg-yellow-900/10 border border-yellow-500/20 rounded-lg p-3 max-h-60 overflow-auto">
                <p className="text-sm text-yellow-200 whitespace-pre-wrap">{feedback}</p>
              </div>
            </div>
          )}

          {/* Review Log */}
          <div className="flex-1 overflow-y-auto p-4 reviewer-scrollbar bg-[#0d1117]">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Review Log</h3>
            <div ref={reviewLogRef} className="space-y-3">
              {logs.length === 0 ? (
                <div className="text-center py-8">
                  <History size={24} className="text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">Keine Log-Einträge</p>
                  <p className="text-xs text-slate-600 mt-1">Starte einen Task</p>
                </div>
              ) : (
                logs.slice(-10).map((log, i) => (
                  <div key={i} className="flex gap-3 text-xs">
                    <span className="text-slate-500 font-mono">{formatTime(i)}</span>
                    <div className="flex-1">
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' || log.event === 'Feedback' ? 'text-yellow-500' :
                        log.event === 'Success' || (log.event === 'Status' && log.message.includes('OK')) ? 'text-green-400' :
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
