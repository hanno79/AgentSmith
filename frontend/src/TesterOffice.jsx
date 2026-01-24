/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.1
 * Beschreibung: Tester Office - Detailansicht für den Tester-Agenten mit UI-Tests und Coverage.
 *
 * # ÄNDERUNG 24.01.2026: Echte Echtzeit-Daten statt Dummy-Daten
 * - Props erweitert für defects, coverage, stability, risk, screenshot, model
 * - Dummy-Daten entfernt (Regel 10 Compliance)
 * - Browser-Vorschau für Playwright-Screenshots hinzugefügt
 * - "Warte auf Daten..." Zustände implementiert
 */

import React from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Bug,
  Shield,
  Clock,
  RefreshCw,
  Settings,
  Bell,
  Activity,
  TrendingUp,
  Gauge,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Brain,
  Terminal,
  FileCheck,
  Globe,
  Cpu,
  TrendingDown
} from 'lucide-react';

const TesterOffice = ({
  agentName = "Tester",
  status = "Idle",
  logs = [],
  onBack,
  color = "orange",
  // Echte Daten vom Backend
  defects = [],
  coverage = [],
  stability = null,
  risk = null,
  screenshot = null,
  model = ""
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);

  // Status Badge Rendering Helper (with Activity icon for active state)
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-green-500/20 text-green-400 border-green-500/20');
    if (badge.isActive) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] bg-green-500/20 text-green-400 border border-green-500/20 uppercase tracking-wide flex items-center gap-1">
          <Activity size={10} className="animate-pulse" />
          Suite Active
        </span>
      );
    }
    return (
      <span className={badge.className}>
        {badge.text}
      </span>
    );
  };

  // Coverage-Prozent berechnen (Durchschnitt aller Pfade)
  const calculateCoveragePercent = () => {
    if (!coverage || coverage.length === 0) return null;
    const avg = coverage.reduce((sum, item) => sum + (item.percent || 0), 0) / coverage.length;
    return avg.toFixed(1);
  };

  // Farbe basierend auf Prozent ermitteln
  const getPercentColor = (percent) => {
    if (percent >= 80) return 'green';
    if (percent >= 50) return 'orange';
    return 'red';
  };

  // Risk-Level Farbe ermitteln
  const getRiskColor = (level) => {
    switch (level?.toUpperCase()) {
      case 'LOW': return 'text-green-400';
      case 'MODERATE': return 'text-orange-400';
      case 'HIGH': return 'text-red-400';
      case 'CRITICAL': return 'text-red-500';
      default: return 'text-slate-400';
    }
  };

  // Gauge-Rotation basierend auf Risk-Level
  const getRiskRotation = (level) => {
    switch (level?.toUpperCase()) {
      case 'LOW': return '-45deg';
      case 'MODERATE': return '0deg';
      case 'HIGH': return '35deg';
      case 'CRITICAL': return '60deg';
      default: return '-60deg';
    }
  };

  const getSeverityColors = (severity) => {
    switch (severity) {
      case 'CRITICAL': return { bg: 'bg-[#231818]', border: 'border-red-900/30 hover:border-red-500/50', text: 'text-red-400' };
      case 'HIGH': return { bg: 'bg-[#231e18]', border: 'border-orange-900/30 hover:border-orange-500/50', text: 'text-orange-400' };
      default: return { bg: 'bg-[#1c2127]', border: 'border-[#283039] hover:border-slate-500', text: 'text-blue-400' };
    }
  };

  return (
    <div className="bg-[#101922] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#283039] px-6 py-3 bg-[#111418] z-20">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="size-8 flex items-center justify-center rounded bg-orange-500/20 text-orange-400 border border-orange-500/20">
            <Bug size={18} />
          </div>
          <div>
            <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
              {agentName} Agent Workstation
              {renderStatusBadge()}
            </h2>
            <div className="text-xs text-slate-400 font-medium tracking-wide flex items-center gap-2">
              {model ? (
                <>
                  <Cpu size={12} className="text-orange-400" />
                  <span className="text-orange-400">{model}</span>
                </>
              ) : (
                <span className="text-slate-500 italic">Warte auf Modell-Info...</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <button className="flex cursor-pointer items-center justify-center overflow-hidden rounded-lg h-9 px-4 bg-[#283039] hover:bg-[#3b4754] text-white text-sm font-bold leading-normal transition-colors border border-[#283039]">
            <span>Logs</span>
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#283039] hover:bg-[#3b4754] text-white transition-colors border border-[#283039]">
            <Settings size={18} />
          </button>
          <button className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-lg bg-[#283039] hover:bg-[#3b4754] text-white transition-colors border border-[#283039]">
            <Bell size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden relative flex flex-col bg-[#101922]">
        <div className="absolute inset-0 bg-grid-pattern grid-bg opacity-[0.05] pointer-events-none"></div>

        <div className="flex-1 w-full max-w-[1920px] mx-auto p-4 lg:p-6 grid grid-cols-12 gap-6 overflow-y-auto tester-scrollbar z-10">

          {/* Left Column */}
          <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
            {/* Active Defects / Test Issues */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col overflow-hidden h-1/2 min-h-[300px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Bug size={16} className="text-orange-400" />
                  Test Issues
                </h3>
                {defects.length > 0 && (
                  <span className="bg-orange-500/20 text-orange-400 text-[10px] px-2 py-0.5 rounded border border-orange-500/20">
                    {defects.length} Gefunden
                  </span>
                )}
              </div>
              <div className="flex-1 overflow-y-auto tester-scrollbar p-2">
                {defects.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-4">
                    <CheckCircle size={32} className="text-slate-600 mb-3" />
                    <p className="text-sm text-slate-500">Keine Issues gefunden</p>
                    <p className="text-xs text-slate-600 mt-1">Starte einen Test um Ergebnisse zu sehen</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {defects.map((defect, index) => {
                      const colors = getSeverityColors(defect.severity || 'NORMAL');
                      return (
                        <div
                          key={defect.id || index}
                          className={`p-3 rounded ${colors.bg} border ${colors.border} transition-colors cursor-pointer group`}
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className={`text-xs font-bold ${colors.text}`}>{defect.severity || 'INFO'}</span>
                            {defect.id && <span className="text-[10px] text-slate-500">#{defect.id}</span>}
                          </div>
                          <p className="text-sm text-slate-200 font-medium mb-1 group-hover:text-white">{defect.title || defect.message || 'Unbekanntes Issue'}</p>
                          {defect.time && (
                            <div className="text-[10px] text-slate-500 flex items-center gap-1">
                              <Clock size={10} /> {defect.time}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Coverage Map */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col flex-1 min-h-[250px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Shield size={16} className="text-green-400" />
                  Coverage Map
                </h3>
                {calculateCoveragePercent() !== null && (
                  <span className="text-xs font-mono text-slate-400">{calculateCoveragePercent()}%</span>
                )}
              </div>
              <div className="p-4 flex flex-col gap-4 overflow-y-auto tester-scrollbar">
                {coverage.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-4">
                    <Shield size={32} className="text-slate-600 mb-3" />
                    <p className="text-sm text-slate-500">Keine Coverage-Daten</p>
                    <p className="text-xs text-slate-600 mt-1">Führe Tests aus um Coverage zu messen</p>
                  </div>
                ) : (
                  <>
                    {coverage.map((item, i) => {
                      const itemColor = item.color || getPercentColor(item.percent);
                      return (
                        <div key={i} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-slate-300 font-mono">{item.path}</span>
                            <span className={`font-bold ${itemColor === 'green' ? 'text-green-400' : itemColor === 'orange' ? 'text-orange-400' : 'text-red-400'}`}>
                              {item.percent}%
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-[#111418] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${itemColor === 'green' ? 'bg-green-500' : itemColor === 'orange' ? 'bg-orange-500' : 'bg-red-500'}`}
                              style={{ width: `${item.percent}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </>
                )}
              </div>
            </div>

            {/* Browser Preview (wenn Screenshot vorhanden) */}
            {screenshot && (
              <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col overflow-hidden">
                <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                  <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                    <Globe size={16} className="text-blue-400" />
                    Browser Preview
                  </h3>
                  <span className="text-[10px] text-slate-400 border border-slate-700 rounded px-1.5">Live</span>
                </div>
                <div className="p-2">
                  <img
                    src={screenshot}
                    alt="Playwright Screenshot"
                    className="w-full rounded border border-[#283039] object-contain max-h-48"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Center Column */}
          <div className="col-span-12 lg:col-span-6 flex flex-col gap-6">
            {/* Control Bar */}
            <div className="flex items-center justify-between bg-[#1c2127] p-3 rounded-xl border border-[#283039] shadow-lg">
              <div className="flex items-center gap-4">
                <button className="flex items-center gap-2 px-4 py-2 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 text-sm font-bold rounded-lg transition-all group">
                  <RefreshCw size={16} className="group-hover:rotate-180 transition-transform" />
                  Run Full Audit
                </button>
                <div className="h-6 w-px bg-[#283039]"></div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Stress Test</span>
                  <div className="w-9 h-5 bg-[#111418] border border-slate-600 rounded-full relative cursor-pointer">
                    <div className="absolute top-[2px] left-[2px] size-4 bg-slate-400 rounded-full transition-transform"></div>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono text-slate-500">
                <span className="size-2 rounded-full bg-green-500 animate-pulse"></span>
                <span>LIVE CONNECTION</span>
              </div>
            </div>

            {/* Test Runner Terminal */}
            <div className="flex-1 bg-[#0d1116] rounded-xl border border-[#283039] relative flex flex-col shadow-2xl overflow-hidden">
              <div className="bg-[#151a20] border-b border-[#283039] px-4 py-2 flex justify-between items-center">
                <div className="flex gap-2 items-center">
                  <Terminal size={16} className="text-slate-500" />
                  <span className="text-xs font-bold text-slate-300">Playwright Test Runner</span>
                  {model && <span className="text-[10px] text-slate-500 font-mono">({model})</span>}
                </div>
                <div className="flex gap-1.5">
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                  <div className="size-2.5 rounded-full bg-[#283039]"></div>
                </div>
              </div>

              {/* Analysis Banner */}
              <div className="relative bg-[#111418] border-b border-[#283039] p-4">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-orange-500/10 to-transparent animate-pulse pointer-events-none z-0"></div>
                <div className="relative z-10 flex items-start gap-3">
                  <div className="mt-1">
                    <div className="size-6 rounded bg-orange-500/20 flex items-center justify-center text-orange-400 animate-pulse">
                      <Brain size={14} />
                    </div>
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-white">Analyzing Failure Pattern...</h4>
                      <span className="text-[10px] font-mono text-orange-400 bg-orange-500/10 px-2 rounded border border-orange-500/20">HEURISTIC SCAN</span>
                    </div>
                    <div className="space-y-1">
                      <div className="h-2 w-3/4 bg-slate-700/50 rounded overflow-hidden">
                        <div className="h-full bg-orange-500/50 w-2/3 animate-pulse"></div>
                      </div>
                      <div className="h-2 w-1/2 bg-slate-700/50 rounded"></div>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-2">&gt; Detecting patterns in test failures...</p>
                  </div>
                </div>
              </div>

              {/* Terminal Output */}
              <div
                ref={logRef}
                className="flex-1 overflow-y-auto tester-scrollbar p-4 font-mono text-xs space-y-1 text-slate-400"
              >
                {logs.length === 0 ? (
                  <>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span>Waiting for test execution...</span></div>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span className="text-green-400">✓ Test runner ready</span></div>
                    <div className="flex gap-2"><span className="text-slate-600">[--:--:--]</span> <span className="animate-pulse">_</span></div>
                  </>
                ) : (
                  <>
                    {logs.map((log, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-slate-600">[{formatTime(i)}]</span>
                        <span className={
                          log.event === 'Error' ? 'text-red-400' :
                          log.event === 'Success' ? 'text-green-400' :
                          log.event === 'Warning' ? 'text-orange-400' :
                          'text-slate-300'
                        }>
                          {log.event === 'Success' && '✓ '}
                          {log.event === 'Error' && '✖ '}
                          {log.event === 'Warning' && '! '}
                          {log.message}
                        </span>
                      </div>
                    ))}
                    <div className="flex gap-2"><span className="text-slate-600">[{formatTime(logs.length)}]</span> <span className="animate-pulse">_</span></div>
                  </>
                )}
              </div>

              {/* Status Bar */}
              <div className="h-1 w-full bg-[#111418] relative">
                <div className="absolute inset-y-0 left-0 bg-orange-500 w-full animate-pulse opacity-50 shadow-[0_0_15px_rgba(249,115,22,0.5)]"></div>
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
            {/* System Stability / Test-Erfolgsrate */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col h-1/2 min-h-[300px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <TrendingUp size={16} className="text-blue-400" />
                  Test-Erfolgsrate
                </h3>
                <span className="text-[10px] text-slate-400 border border-slate-700 rounded px-1.5">Session</span>
              </div>
              <div className="p-4 flex-1 flex flex-col justify-center relative">
                {stability ? (
                  <>
                    {/* Erfolgsrate Anzeige */}
                    <div className="text-center">
                      <div className="text-4xl font-bold text-white mb-2">{stability.value?.toFixed(1) || 0}%</div>
                      {stability.trend !== undefined && stability.trend !== 0 && (
                        <div className={`text-sm flex items-center justify-center gap-1 ${stability.trend >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                          {stability.trend >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          {stability.trend >= 0 ? '+' : ''}{stability.trend.toFixed(1)}%
                        </div>
                      )}
                    </div>
                    {/* Fortschrittsbalken */}
                    <div className="mt-6">
                      <div className="h-3 w-full bg-[#111418] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            stability.value >= 80 ? 'bg-green-500' :
                            stability.value >= 50 ? 'bg-orange-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${Math.min(stability.value || 0, 100)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 mt-2">
                        <span>0%</span>
                        <span>50%</span>
                        <span>100%</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center">
                    <Activity size={32} className="text-slate-600 mb-3" />
                    <p className="text-sm text-slate-500">Keine Statistiken</p>
                    <p className="text-xs text-slate-600 mt-1">Führe Tests aus um Daten zu sammeln</p>
                  </div>
                )}
              </div>
            </div>

            {/* Risk Assessment */}
            <div className="bg-[#1c2127] border border-[#283039] rounded-xl flex flex-col flex-1 min-h-[250px]">
              <div className="p-4 border-b border-[#283039] flex justify-between items-center bg-[#151a20]">
                <h3 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                  <Gauge size={16} className="text-orange-400" />
                  Risk Assessment
                </h3>
              </div>
              <div className="flex-1 flex flex-col items-center justify-center p-6 relative">
                {risk ? (
                  <>
                    {/* Gauge */}
                    <div className="relative w-48 h-24 overflow-hidden mb-4">
                      <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 200 100">
                        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#283039" strokeWidth="20" />
                        <path d="M 20 100 A 80 80 0 0 1 120 36" fill="none" stroke="#22c55e" strokeLinecap="round" strokeWidth="20" />
                        <path d="M 120 36 A 80 80 0 0 1 150 25" fill="none" stroke="#f97316" strokeLinecap="round" strokeWidth="20" />
                        <path d="M 150 25 A 80 80 0 0 1 180 100" fill="none" stroke="#ef4444" strokeLinecap="round" strokeWidth="20" />
                      </svg>
                      {/* Needle */}
                      <div
                        className="absolute bottom-0 left-1/2 w-1 h-[80px] bg-white origin-bottom rounded-full shadow-lg z-10 transition-transform duration-500"
                        style={{ transform: `translateX(-50%) rotate(${getRiskRotation(risk.level)})` }}
                      >
                        <div className="absolute -top-1 -left-1.5 size-4 bg-white rounded-full border-2 border-slate-900"></div>
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-slate-400 uppercase tracking-widest font-bold mb-1">Current Risk</div>
                      <div className={`text-2xl font-bold ${getRiskColor(risk.level)}`}>{risk.level || 'UNKNOWN'}</div>
                      {risk.reason && (
                        <p className="text-xs text-slate-500 mt-2 max-w-[200px]">
                          {risk.reason}
                        </p>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center">
                    <AlertTriangle size={32} className="text-slate-600 mb-3" />
                    <p className="text-sm text-slate-500">Keine Risiko-Analyse</p>
                    <p className="text-xs text-slate-600 mt-1">Führe Tests aus um Risiken zu bewerten</p>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default TesterOffice;
