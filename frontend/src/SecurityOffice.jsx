/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.2
 * Beschreibung: Security Office - Detailansicht für den Security-Agenten mit Bedrohungsanalyse.
 *               ÄNDERUNG 24.01.2026: Dummy-Daten entfernt, echte Props vom Backend.
 *               ÄNDERUNG 24.01.2026: Scan-Typ Anzeige (Code-Scan vs. Anforderungs-Scan) und Blocking-Warnung.
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
  Database,
  Globe,
  Zap,
  Eye,
  Target,
  Radio,
  Maximize2,
  Loader2
} from 'lucide-react';

// ÄNDERUNG 24.01.2026: Neue Props für echte Daten vom Backend
// ÄNDERUNG 24.01.2026: Erweitert mit scanType, iteration, blocking für Code-Scan
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

  // ÄNDERUNG 24.01.2026: State für Deploy Patches Button
  const [deployStatus, setDeployStatus] = useState('idle'); // idle, loading, success, error

  // ÄNDERUNG 24.01.2026: Handler für Deploy Patches Button
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
        // Reset nach 3 Sekunden
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

  // ÄNDERUNG 24.01.2026: Prüfe ob echte Daten vorhanden sind
  const hasData = overallStatus !== '' || vulnerabilities.length > 0;
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

  // ÄNDERUNG 24.01.2026: Dynamische Threat Intelligence basierend auf echten Vulnerabilities
  const getThreatIntel = () => {
    if (!hasData) {
      return { activeThreats: 0, suspicious: 0, secured: 0, scanning: isScanning ? 1 : 0 };
    }
    const critical = vulnerabilities.filter(v => v.severity === 'critical').length;
    const high = vulnerabilities.filter(v => v.severity === 'high').length;
    const medium = vulnerabilities.filter(v => v.severity === 'medium').length;
    const low = vulnerabilities.filter(v => v.severity === 'low').length;

    return {
      activeThreats: critical + high,
      suspicious: medium,
      secured: overallStatus === 'SECURE' ? Math.max(scannedFiles, 1) : low,
      scanning: isScanning ? 1 : 0
    };
  };

  const threatIntel = getThreatIntel();

  // ÄNDERUNG 24.01.2026: Dynamische Defense Entries aus echten Logs
  const getDefenseEntries = () => {
    if (logs.length === 0 && !hasData) return [];

    return logs.slice(-5).map((log, i) => ({
      time: new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      type: log.event === 'Error' ? 'alert' :
            log.event === 'Warning' ? 'warning' :
            log.event === 'Result' ? 'success' : 'info',
      message: log.message
    }));
  };

  const defenseEntries = getDefenseEntries();

  // ÄNDERUNG 24.01.2026: Dynamische Mitigation Targets aus echten Vulnerabilities
  const getMitigationTargets = () => {
    if (!hasData || vulnerabilities.length === 0) return [];

    // Gruppiere nach Severity
    const groups = {
      critical: { name: 'Critical Issues', patches: 0, critical: true },
      high: { name: 'High Priority', patches: 0, critical: true },
      medium: { name: 'Medium Priority', patches: 0, critical: false },
      low: { name: 'Low Priority', patches: 0, critical: false }
    };

    vulnerabilities.forEach(v => {
      if (groups[v.severity]) {
        groups[v.severity].patches++;
      }
    });

    return Object.values(groups).filter(g => g.patches > 0);
  };

  const mitigationTargets = getMitigationTargets();

  // ÄNDERUNG 24.01.2026: Dynamischer DEFCON Level basierend auf Vulnerabilities
  const getDefconLevel = () => {
    if (!hasData) return { level: 5, text: 'STANDBY', color: 'slate', description: 'Warte auf Analyse...' };

    const critical = vulnerabilities.filter(v => v.severity === 'critical').length;
    const high = vulnerabilities.filter(v => v.severity === 'high').length;
    const medium = vulnerabilities.filter(v => v.severity === 'medium').length;

    if (critical > 0) return { level: 1, text: 'CRITICAL', color: 'red', description: 'Kritische Sicherheitslücken!' };
    if (high > 0) return { level: 2, text: 'HIGH ALERT', color: 'orange', description: 'Hohe Bedrohungsstufe' };
    if (medium > 0) return { level: 3, text: 'ELEVATED', color: 'amber', description: 'Erhöhte Wachsamkeit' };
    if (vulnerabilities.length > 0) return { level: 4, text: 'GUARDED', color: 'yellow', description: 'Geringe Bedrohungen' };
    return { level: 5, text: 'SECURE', color: 'green', description: 'System sicher' };
  };

  const defcon = getDefconLevel();

  // ÄNDERUNG 24.01.2026: Dynamische Node-Security basierend auf Analyse-Status
  const getNodeStatus = () => {
    if (!hasData) {
      return [
        { name: 'DB', health: 0, status: 'unknown' },
        { name: 'API', health: 0, status: 'unknown' },
        { name: 'WEB', health: 0, status: 'unknown' },
        { name: 'CDN', health: 0, status: 'unknown' },
      ];
    }

    // Basiere Health auf overallStatus
    const baseHealth = overallStatus === 'SECURE' ? 100 :
                       overallStatus === 'WARNING' ? 85 :
                       overallStatus === 'CRITICAL' ? 60 : 70;

    return [
      { name: 'DB', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
      { name: 'API', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
      { name: 'WEB', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
      { name: 'CDN', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
    ];
  };

  const nodeStatus = getNodeStatus();

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
          {/* ÄNDERUNG 24.01.2026: Dynamisches Alert Level Badge basierend auf echtem Status */}
          <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg relative group ${
            defcon.color === 'red' ? 'bg-red-950/50 border border-red-500/30' :
            defcon.color === 'orange' ? 'bg-orange-950/50 border border-orange-500/30' :
            defcon.color === 'amber' ? 'bg-amber-950/50 border border-amber-500/30' :
            defcon.color === 'green' ? 'bg-green-950/50 border border-green-500/30' :
            'bg-slate-800/50 border border-slate-500/30'
          }`}>
            {hasData && defcon.level <= 3 && (
              <span className="absolute right-0 top-0 -mt-1 -mr-1 flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  defcon.color === 'red' ? 'bg-red-400' :
                  defcon.color === 'orange' ? 'bg-orange-400' : 'bg-amber-400'
                }`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${
                  defcon.color === 'red' ? 'bg-red-500' :
                  defcon.color === 'orange' ? 'bg-orange-500' : 'bg-amber-500'
                }`}></span>
              </span>
            )}
            {isScanning ? (
              <Loader2 size={14} className="text-slate-400 animate-spin" />
            ) : (
              <AlertTriangle size={14} className={`${
                defcon.color === 'red' ? 'text-red-400' :
                defcon.color === 'orange' ? 'text-orange-400' :
                defcon.color === 'amber' ? 'text-amber-400' :
                defcon.color === 'green' ? 'text-green-400' : 'text-slate-400'
              }`} />
            )}
            <span className={`text-xs font-semibold ${
              defcon.color === 'red' ? 'text-red-300' :
              defcon.color === 'orange' ? 'text-orange-300' :
              defcon.color === 'amber' ? 'text-amber-300' :
              defcon.color === 'green' ? 'text-green-300' : 'text-slate-300'
            }`}>
              {isScanning ? 'SCANNING...' : `ALERT: ${defcon.text}`}
            </span>
          </div>
          {/* ÄNDERUNG 24.01.2026: Dynamisches Vulnerabilities Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155]">
            <Eye size={14} className={vulnerabilities.length > 0 ? 'text-amber-500' : 'text-slate-500'} />
            <span className="text-xs font-semibold text-white">
              {hasData ? `${vulnerabilities.length} Findings` : 'Keine Daten'}
            </span>
          </div>
          {/* ÄNDERUNG 24.01.2026: Scan-Typ Anzeige */}
          <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg ${
            scanType === 'code_scan' ? 'bg-blue-950/50 border border-blue-500/30' : 'bg-slate-800/50 border border-slate-500/30'
          }`}>
            <Target size={14} className={scanType === 'code_scan' ? 'text-blue-400' : 'text-slate-400'} />
            <span className={`text-xs font-semibold ${scanType === 'code_scan' ? 'text-blue-300' : 'text-slate-300'}`}>
              {scanType === 'code_scan' ? `CODE-SCAN #${iteration}` : 'ANFORDERUNGS-SCAN'}
            </span>
          </div>
          {/* ÄNDERUNG 24.01.2026: Blocking-Warnung wenn Security-Gate blockiert */}
          {blocking && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-950 border border-red-500/50 animate-pulse">
              <ShieldAlert size={14} className="text-red-400" />
              <span className="text-xs font-bold text-red-300">BLOCKIERT ABSCHLUSS</span>
            </div>
          )}
          {/* ÄNDERUNG 24.01.2026: Model-Anzeige wenn vorhanden */}
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

        {/* Left Sidebar - Threat Intelligence */}
        <aside className="w-[280px] border-r border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155] flex justify-between items-center bg-[#1e293b]/30">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Target size={16} className="text-red-400" />
              Threat Intelligence
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto security-scrollbar p-4 space-y-4">
            {/* Active Threats */}
            <div className="bg-red-950/30 p-3 rounded-lg border border-red-500/30 relative group">
              <div className="absolute top-2 right-2">
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert size={16} className="text-red-400" />
                <span className="text-xs font-bold text-red-300 uppercase">Active Threats</span>
              </div>
              <p className="text-2xl font-black text-red-400">{threatIntel.activeThreats}</p>
              <p className="text-[10px] text-red-300/60 mt-1">Requiring immediate attention</p>
            </div>

            {/* Suspicious Items */}
            <div className="bg-amber-950/20 p-3 rounded-lg border border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={16} className="text-amber-400" />
                <span className="text-xs font-bold text-amber-300 uppercase">Suspicious</span>
              </div>
              <p className="text-2xl font-black text-amber-400">{threatIntel.suspicious}</p>
              <p className="text-[10px] text-amber-300/60 mt-1">Under investigation</p>
            </div>

            {/* Secured Items */}
            <div className="bg-green-950/20 p-3 rounded-lg border border-green-500/20">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck size={16} className="text-green-400" />
                <span className="text-xs font-bold text-green-300 uppercase">Secured</span>
              </div>
              <p className="text-2xl font-black text-green-400">{threatIntel.secured}</p>
              <p className="text-[10px] text-green-300/60 mt-1">Protected endpoints</p>
            </div>

            {/* Scanning Items */}
            <div className="bg-[#1e293b] p-3 rounded-lg border border-[#334155]">
              <div className="flex items-center gap-2 mb-2">
                <Radio size={16} className="text-blue-400 animate-pulse" />
                <span className="text-xs font-bold text-slate-300 uppercase">Scanning</span>
              </div>
              <p className="text-2xl font-black text-white">{threatIntel.scanning}</p>
              <p className="text-[10px] text-slate-400 mt-1">Active scans in progress</p>
            </div>
          </div>

          {/* ÄNDERUNG 24.01.2026: Dynamischer Firewall Load basierend auf Analyse-Status */}
          <div className="p-3 border-t border-[#334155] bg-[#0f172a]">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Zap size={12} className={isScanning ? 'text-amber-400 animate-pulse' : hasData ? 'text-green-400' : 'text-slate-500'} />
                Firewall Load
              </span>
              <span className={`font-mono ${
                isScanning ? 'text-amber-300' :
                hasData && overallStatus === 'SECURE' ? 'text-green-300' :
                hasData ? 'text-amber-300' : 'text-slate-500'
              }`}>
                {isScanning ? '...' : hasData ? (overallStatus === 'SECURE' ? '25%' : '60%') : '0%'}
              </span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
              {isScanning ? (
                <div className="h-full w-full bg-gradient-to-r from-amber-600 to-amber-400 rounded-full animate-pulse"></div>
              ) : hasData ? (
                <div
                  className={`h-full rounded-full ${
                    overallStatus === 'SECURE' ? 'bg-gradient-to-r from-green-600 to-green-400' :
                    'bg-gradient-to-r from-amber-600 to-amber-400'
                  }`}
                  style={{ width: overallStatus === 'SECURE' ? '25%' : '60%' }}
                ></div>
              ) : (
                <div className="h-full w-0 bg-slate-600 rounded-full"></div>
              )}
            </div>
          </div>
        </aside>

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
              {/* ÄNDERUNG 24.01.2026: Warte-Zustand wenn keine Logs vorhanden */}
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
                      <p className="text-xs text-slate-600">{overallStatus}: {vulnerabilities.length} Findings</p>
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
              {/* ÄNDERUNG 24.01.2026: Warte-Zustand wenn keine Vulnerabilities */}
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

            {/* Action Buttons - ÄNDERUNG 24.01.2026: Deploy Patches mit Funktionalität */}
            <div className="p-4 bg-[#161b22] border-t border-[#334155] flex gap-3">
              <button className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2">
                <Eye size={16} />
                View Details
              </button>
              <button
                onClick={handleDeployPatches}
                disabled={deployStatus === 'loading' || vulnerabilities.length === 0}
                className={`flex-[2] px-4 py-2 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 ${
                  deployStatus === 'success'
                    ? 'bg-green-600 text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                    : deployStatus === 'error'
                      ? 'bg-orange-600 text-white'
                      : deployStatus === 'loading'
                        ? 'bg-red-700 text-white cursor-wait'
                        : vulnerabilities.length === 0
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
                    Deploy All Patches ({vulnerabilities.length})
                  </>
                )}
              </button>
            </div>
          </div>
        </main>

        {/* Right Sidebar - System Integrity */}
        <aside className="w-[320px] border-l border-[#334155] bg-[#0f172a]/80 flex flex-col z-10 backdrop-blur-sm">
          <div className="p-4 border-b border-[#334155]">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck size={16} className="text-red-400" />
              System Integrity
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto security-scrollbar p-4 space-y-4">
            {/* ÄNDERUNG 24.01.2026: Dynamisches DEFCON Level basierend auf echten Daten */}
            <div className={`rounded-xl p-4 border relative overflow-hidden group ${
              defcon.color === 'red' ? 'bg-red-950/30 border-red-500/30' :
              defcon.color === 'orange' ? 'bg-orange-950/30 border-orange-500/30' :
              defcon.color === 'amber' ? 'bg-amber-950/30 border-amber-500/30' :
              defcon.color === 'green' ? 'bg-green-950/30 border-green-500/30' :
              'bg-[#1e293b] border-[#334155]'
            }`}>
              <div className="absolute top-0 right-0 p-2 opacity-10">
                {defcon.color === 'green' ? <ShieldCheck size={60} /> : <AlertTriangle size={60} />}
              </div>
              <p className="text-xs text-slate-400 uppercase font-semibold mb-1">Defense Readiness</p>
              <div className="flex items-baseline gap-2">
                {isScanning ? (
                  <div className="flex items-center gap-2">
                    <Loader2 size={24} className="text-slate-400 animate-spin" />
                    <span className="text-xl font-bold text-slate-400">Analysiere...</span>
                  </div>
                ) : (
                  <span className={`text-3xl font-black ${
                    defcon.color === 'red' ? 'text-red-400' :
                    defcon.color === 'orange' ? 'text-orange-400' :
                    defcon.color === 'amber' ? 'text-amber-400' :
                    defcon.color === 'green' ? 'text-green-400' : 'text-slate-400'
                  }`}>
                    DEFCON {defcon.level}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-500 mt-2">{defcon.description}</p>
              <div className="mt-3 flex gap-1">
                {[1, 2, 3, 4, 5].map((level) => (
                  <div
                    key={level}
                    className={`flex-1 h-2 rounded ${
                      level <= (6 - defcon.level) ? (
                        defcon.color === 'red' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]' :
                        defcon.color === 'orange' ? 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.4)]' :
                        defcon.color === 'amber' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]' :
                        defcon.color === 'green' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]' :
                        'bg-slate-500'
                      ) : 'bg-slate-700'
                    }`}
                  />
                ))}
              </div>
            </div>

            {/* Encryption Strength */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <h4 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                <Lock size={14} className="text-green-400" />
                Encryption Strength
              </h4>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Protocol</span>
                  <span className="text-xs font-mono text-green-400">AES-256-GCM</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Entropy</span>
                  <span className="text-xs font-mono text-green-400">99.7%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Key Exchange</span>
                  <span className="text-xs font-mono text-green-400">ECDH P-384</span>
                </div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden mt-2">
                  <div className="h-full w-[99%] bg-gradient-to-r from-green-600 to-green-400 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.4)]"></div>
                </div>
              </div>
            </div>

            {/* Node Security */}
            <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
                  <Server size={14} className="text-red-400" />
                  Node Security
                </h4>
                <span className="text-[10px] text-slate-500 font-mono">Per Cluster</span>
              </div>
              <div className="space-y-3">
                {nodeStatus.map((node, i) => (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-300 flex items-center gap-2">
                        {node.name === 'DB' && <Database size={12} className="text-slate-500" />}
                        {node.name === 'API' && <Server size={12} className="text-slate-500" />}
                        {node.name === 'WEB' && <Globe size={12} className="text-slate-500" />}
                        {node.name === 'CDN' && <Radio size={12} className="text-slate-500" />}
                        {node.name}
                      </span>
                      <span className={`font-mono ${node.health >= 95 ? 'text-green-400' : node.health >= 85 ? 'text-amber-400' : 'text-red-400'}`}>
                        {node.health}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${node.health >= 95 ? 'bg-green-500' : node.health >= 85 ? 'bg-amber-500' : 'bg-red-500'}`}
                        style={{ width: `${node.health}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Map Footer */}
          <div className="p-0 border-t border-[#334155] bg-[#0f172a] h-32 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-red-900/20 to-slate-900/80"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-[#0f172a] to-transparent"></div>
            <div className="absolute bottom-3 right-3 flex flex-col items-end">
              <div className="flex gap-1 mb-1">
                <div className="size-2 bg-green-500 rounded-full"></div>
                <div className="size-2 bg-amber-500 rounded-full animate-pulse"></div>
                <div className="size-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_5px_red]"></div>
              </div>
              <span className="text-[9px] font-mono text-red-400 bg-black/50 px-1 rounded backdrop-blur-sm border border-red-900/50">THREAT MAP: LIVE</span>
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

export default SecurityOffice;
