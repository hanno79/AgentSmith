/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.4
 * Beschreibung: Security Office - Detailansicht für den Security-Agenten mit Bedrohungsanalyse.
 *               ÄNDERUNG 24.01.2026: Dummy-Daten entfernt, echte Props vom Backend.
 *               ÄNDERUNG 24.01.2026: Scan-Typ Anzeige (Code-Scan vs. Anforderungs-Scan) und Blocking-Warnung.
 *               ÄNDERUNG 24.01.2026: Individuelle Vulnerabilities mit FIX-Vorschlägen anzeigen.
 *               ÄNDERUNG 01.02.2026 v1.4: Refaktoriert in Komponenten (Regel 1: Max 500 Zeilen)
 *               - utils/SecurityCalculations.js: Utility-Funktionen
 *               - components/ThreatIntelligence.jsx: Left Sidebar
 *               - components/SystemIntegrity.jsx: Right Sidebar
 */

import React, { useRef, useState } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion } from 'framer-motion';
import { API_BASE } from './constants/config';
import {
  ArrowLeft,
  Shield,
  History,
  Settings,
  AlertTriangle,
  Lock,
  ShieldCheck,
  ShieldAlert,
  Activity,
  Server,
  Eye,
  Target,
  Loader2
} from 'lucide-react';

// ÄNDERUNG 01.02.2026: Extrahierte Komponenten und Utilities
import ThreatIntelligence from './components/ThreatIntelligence';
import SystemIntegrity from './components/SystemIntegrity';
import {
  getThreatIntel,
  getMitigationTargets,
  getDefconLevel,
  getNodeStatus,
  getDefconColorClass
} from './utils/SecurityCalculations';

const SecurityOffice = ({
  agentName = "Security",
  status = "Idle",
  logs = [],
  onBack,
  color = "red",
  // Echte Daten Props vom Backend
  vulnerabilities = [],
  overallStatus = "",
  scanResult = "",
  model = "",
  scannedFiles = 0,
  // Neue Props für Code-Scan
  scanType = "requirement_scan",
  iteration = 0,
  blocking = false
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);
  const mitigationRef = useRef(null);

  // State für Deploy Patches Button
  const [deployStatus, setDeployStatus] = useState('idle'); // idle, loading, success, error

  // Handler für Deploy Patches Button
  const handleDeployPatches = async () => {
    if (deployStatus === 'loading') return;

    setDeployStatus('loading');
    try {
      const response = await fetch(`${API_BASE}/security-feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        setDeployStatus('success');
        setTimeout(() => setDeployStatus('idle'), 3000);
      } else {
        setDeployStatus('error');
        setTimeout(() => setDeployStatus('idle'), 3000);
      }
    } catch (error) {
      console.error('Deploy Patches fehlgeschlagen:', error);
      setDeployStatus('error');
      setTimeout(() => setDeployStatus('idle'), 3000);
    }
  };

  // Prüfe ob echte Daten vorhanden sind
  const safeVulnerabilities = Array.isArray(vulnerabilities) ? vulnerabilities : [];
  const hasData = overallStatus !== '' || safeVulnerabilities.length > 0;
  const isScanning = status === 'Status' || status === 'Working';

  // Status Badge Rendering Helper
  const renderStatusBadge = () => {
    const badge = getStatusBadge(status, 'bg-red-500/20 text-red-300 border-red-500/20 font-semibold shadow-[0_0_8px_rgba(239,68,68,0.2)]');
    return (
      <span className={badge.className}>
        {badge.isActive ? 'Analysiere...' : badge.text}
      </span>
    );
  };

  // ÄNDERUNG 01.02.2026: Utility-Funktionen aus SecurityCalculations.js
  const threatIntel = getThreatIntel({
    vulnerabilities: safeVulnerabilities,
    overallStatus,
    scannedFiles,
    hasData,
    isScanning
  });
  const mitigationTargets = getMitigationTargets({
    vulnerabilities: safeVulnerabilities,
    hasData
  });
  const defcon = getDefconLevel({
    vulnerabilities: safeVulnerabilities,
    hasData
  });
  const nodeStatus = getNodeStatus({
    overallStatus,
    hasData
  });

  return (
    <div className="bg-[#0f172a] text-white font-display overflow-hidden h-screen flex flex-col">
      {/* Header */}
      <header className="flex-none flex items-center justify-between whitespace-nowrap border-b border-[#334155] px-6 py-3 bg-[#0f172a] z-20 shadow-md shadow-red-900/5">
        <div className="flex items-center gap-4 text-white">
          <button
            onClick={onBack}
            className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="h-6 w-px bg-slate-700"></div>
          <div className="flex items-center gap-3">
            <div className="size-9 flex items-center justify-center rounded-lg bg-red-950 text-red-400 border border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.1)]">
              <Shield size={18} />
            </div>
            <div>
              <h2 className="text-white text-lg font-bold leading-tight tracking-[-0.015em] flex items-center gap-2">
                {agentName}
                {renderStatusBadge()}
              </h2>
              <div className="text-xs text-slate-400 font-medium tracking-wide">WORKSTATION ID: AGENT-09-SEC</div>
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          {/* Dynamisches Alert Level Badge basierend auf echtem Status */}
          <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg relative group ${getDefconColorClass(defcon.color, 'bg')}`}>
            {hasData && defcon.level <= 3 && (
              <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${getDefconColorClass(defcon.color, 'ping')}`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${getDefconColorClass(defcon.color, 'dot')}`}></span>
              </span>
            )}
            {isScanning ? (
              <Loader2 size={14} className="text-slate-400 animate-spin" />
            ) : (
              <AlertTriangle size={14} className={getDefconColorClass(defcon.color, 'icon')} />
            )}
            <span className={`text-xs font-semibold ${getDefconColorClass(defcon.color, 'text')}`}>
              {isScanning ? 'SCANNING...' : `ALERT: ${defcon.text}`}
            </span>
          </div>
          {/* Dynamisches Vulnerabilities Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155]">
            <Eye size={14} className={safeVulnerabilities.length > 0 ? 'text-amber-500' : 'text-slate-500'} />
            <span className="text-xs font-semibold text-white">
              {hasData ? `${safeVulnerabilities.length} Findings` : 'Keine Daten'}
            </span>
          </div>
          {/* Scan-Typ Anzeige */}
          <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg ${
            scanType === 'code_scan' ? 'bg-blue-950/50 border border-blue-500/30' : 'bg-slate-800/50 border border-slate-500/30'
          }`}>
            <Target size={14} className={scanType === 'code_scan' ? 'text-blue-400' : 'text-slate-400'} />
            <span className={`text-xs font-semibold ${scanType === 'code_scan' ? 'text-blue-300' : 'text-slate-300'}`}>
              {scanType === 'code_scan' ? `CODE-SCAN #${iteration}` : 'ANFORDERUNGS-SCAN'}
            </span>
          </div>
          {/* Blocking-Warnung wenn Security-Gate blockiert */}
          {blocking && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-950 border border-red-500/50 animate-pulse">
              <ShieldAlert size={14} className="text-red-400" />
              <span className="text-xs font-bold text-red-300">BLOCKIERT ABSCHLUSS</span>
            </div>
          )}
          {/* Model-Anzeige wenn vorhanden */}
          {model && (
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155]">
              <Shield size={14} className="text-slate-400" />
              <span className="text-xs font-mono text-slate-300">{model}</span>
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

        {/* Left Sidebar - Threat Intelligence (ÄNDERUNG 01.02.2026: Extrahiert) */}
        <ThreatIntelligence
          threatIntel={threatIntel}
          isScanning={isScanning}
          hasData={hasData}
          overallStatus={overallStatus}
        />

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col min-w-0 z-10 bg-[#0d1117]">
          {/* Defense Terminal */}
          <div className="h-[45%] border-b border-[#334155] bg-[#1e293b]/20 flex flex-col relative">
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
              <Shield size={180} />
            </div>
            <div className="px-4 py-2 border-b border-[#334155] bg-[#1e293b]/40 flex justify-between items-center backdrop-blur-md">
              <h3 className="text-xs font-bold text-red-400 uppercase tracking-wider flex items-center gap-2">
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Activity size={14} />
                </motion.div>
                Defense Terminal
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-slate-500 font-mono">PROTOCOL: ACTIVE-DEFENSE</span>
                <span className="size-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
              </div>
            </div>

            <div
              ref={logRef}
              className="flex-1 p-5 overflow-y-auto security-scrollbar font-mono text-xs space-y-3"
            >
              {/* Warte-Zustand wenn keine Logs vorhanden */}
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
                  {isScanning ? (
                    <>
                      <Loader2 size={32} className="animate-spin text-red-400" />
                      <p className="text-sm">Führe Sicherheitsanalyse durch...</p>
                      <p className="text-xs text-slate-600">Prüfe auf OWASP Top 10, Injection-Angriffe, XSS...</p>
                    </>
                  ) : hasData ? (
                    <>
                      <ShieldCheck size={32} className="text-green-400" />
                      <p className="text-sm text-green-400">Analyse abgeschlossen</p>
                      <p className="text-xs text-slate-600">{overallStatus}: {safeVulnerabilities.length} Findings</p>
                    </>
                  ) : (
                    <>
                      <Shield size={32} className="text-slate-600" />
                      <p className="text-sm">Warte auf Sicherheitsanalyse...</p>
                      <p className="text-xs text-slate-600">Starte ein Projekt um die Analyse zu beginnen</p>
                    </>
                  )}
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`flex gap-4 group ${i === logs.length - 1 ? 'relative' : ''}`}>
                    {i === logs.length - 1 && <div className="absolute left-[4.5rem] top-2 bottom-2 w-0.5 bg-red-900"></div>}
                    <span className={`w-16 shrink-0 pt-0.5 border-r border-slate-800 pr-2 ${i === logs.length - 1 ? 'text-red-700' : 'text-slate-600'}`}>
                      [{formatTime(i)}]
                    </span>
                    <div className={`flex-1 ${i === logs.length - 1 ? 'bg-red-950/20 p-2 rounded border-l-2 border-red-500' : ''}`}>
                      <p className={
                        log.event === 'Error' ? 'text-red-400' :
                        log.event === 'Warning' ? 'text-amber-400' :
                        log.event === 'Success' ? 'text-green-400' :
                        i === logs.length - 1 ? 'text-red-100' :
                        'text-slate-300'
                      }>{log.message}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Risk Mitigation Log */}
          <div className="flex-1 bg-[#0b1016] flex flex-col relative overflow-hidden">
            <div className="px-4 py-2 bg-[#161b22] border-b border-[#334155] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock size={14} className="text-rose-500" />
                <span className="text-xs font-mono text-slate-300 uppercase tracking-wide">Risk Mitigation Log</span>
              </div>
              <span className="text-[10px] bg-rose-950 text-rose-300 px-2 py-0.5 rounded border border-rose-800">
                {mitigationTargets.reduce((acc, t) => acc + t.patches, 0)} Patches Pending
              </span>
            </div>

            <div
              ref={mitigationRef}
              className="flex-1 p-4 overflow-y-auto security-scrollbar"
            >
              {/* Warte-Zustand wenn keine Vulnerabilities */}
              {mitigationTargets.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
                  {isScanning ? (
                    <>
                      <Loader2 size={24} className="animate-spin text-rose-400" />
                      <p className="text-xs">Identifiziere Risiken...</p>
                    </>
                  ) : hasData && overallStatus === 'SECURE' ? (
                    <>
                      <ShieldCheck size={24} className="text-green-400" />
                      <p className="text-xs text-green-400">Keine Patches erforderlich</p>
                    </>
                  ) : (
                    <>
                      <Lock size={24} className="text-slate-600" />
                      <p className="text-xs">Warte auf Analyse...</p>
                    </>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Individuelle Vulnerabilities mit FIX-Vorschlägen */}
                  {safeVulnerabilities.length > 0 && (
                    <div className="space-y-2 mb-4">
                      <h5 className="text-xs font-bold text-slate-400 uppercase mb-2">Gefundene Schwachstellen</h5>
                      {safeVulnerabilities.map((vuln, i) => (
                        <div key={`vuln-${i}`} className={`p-3 rounded-lg border ${
                          vuln.severity === 'critical' ? 'bg-red-950/30 border-red-500/40' :
                          vuln.severity === 'high' ? 'bg-orange-950/30 border-orange-500/40' :
                          vuln.severity === 'medium' ? 'bg-amber-950/30 border-amber-500/40' :
                          'bg-slate-800/30 border-slate-600/40'
                        }`}>
                          <div className="flex items-start gap-2">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase shrink-0 ${
                              vuln.severity === 'critical' ? 'bg-red-500/20 text-red-300' :
                              vuln.severity === 'high' ? 'bg-orange-500/20 text-orange-300' :
                              vuln.severity === 'medium' ? 'bg-amber-500/20 text-amber-300' :
                              'bg-slate-500/20 text-slate-300'
                            }`}>{vuln.severity}</span>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs text-white break-words">{vuln.description}</p>
                              {vuln.fix && (
                                <p className="text-[11px] text-green-400 mt-1 flex items-start gap-1">
                                  <span className="text-green-500 shrink-0">→</span>
                                  <span className="break-words">FIX: {vuln.fix}</span>
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Gruppierte Mitigation Targets */}
                  {mitigationTargets.map((target, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-lg border ${target.critical ? 'bg-red-950/20 border-red-500/30' : 'bg-[#1e293b]/40 border-[#334155]'}`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <div className="flex items-center gap-2">
                          <Server size={14} className={target.critical ? 'text-red-400' : 'text-slate-400'} />
                          <span className="text-sm font-semibold text-white">{target.name}</span>
                          {target.critical && (
                            <span className="text-[9px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded border border-red-500/30 uppercase font-bold">
                              Critical
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-slate-400 font-mono">{target.patches} issues</span>
                      </div>
                      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(10, 100 - target.patches * 20)}%` }}
                          transition={{ duration: 1, delay: i * 0.2 }}
                          className={`h-full rounded-full ${target.critical ? 'bg-red-500' : 'bg-green-500'}`}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Action Buttons - Deploy Patches mit Funktionalität */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <Eye size={16} />
                View Details
              </button>
              <button
                onClick={handleDeployPatches}
                disabled={deployStatus === 'loading' || safeVulnerabilities.length === 0}
                className={`flex-[2] px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 ${
                  deployStatus === 'success'
                    ? 'bg-green-600 text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                  : deployStatus === 'error'
                      ? 'bg-orange-600 text-white'
                      : deployStatus === 'loading'
                        ? 'bg-red-700 text-white cursor-wait'
                        : safeVulnerabilities.length === 0
                          ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                          : 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.3)]'
                }`}
              >
                {deployStatus === 'loading' ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Aktiviere Fixes...
                  </>
                ) : deployStatus === 'success' ? (
                  <>
                    <ShieldCheck size={16} />
                    Fixes aktiviert!
                  </>
                ) : deployStatus === 'error' ? (
                  <>
                    <AlertTriangle size={16} />
                    Fehler aufgetreten
                  </>
                ) : (
                  <>
                    <Shield size={16} />
                    Deploy All Patches ({safeVulnerabilities.length})
                  </>
                )}
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - System Integrity (ÄNDERUNG 01.02.2026: Extrahiert) */}
        <SystemIntegrity
          defcon={defcon}
          nodeStatus={nodeStatus}
          isScanning={isScanning}
        />
      </div>
    </div>
  );
};

export default SecurityOffice;
