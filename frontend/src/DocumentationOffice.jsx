/**
 * Author: rahn
 * Datum: 30.01.2026
 * Version: 1.1
 * Beschreibung: Documentation Office - UI für den Documentation Manager Agent.
 *               Zeigt README/CHANGELOG Generierung, Quality Metrics und Agent-Kommunikation.
 *               Platinum/Weiß Farbschema für den 5. Core Agent.
 *               ÄNDERUNG 30.01.2026: Zurück-Button hinzugefügt (fehlte).
 *               # ÄNDERUNG [31.01.2026]: Parse-Fehler protokolliert, Result-Handling entkoppelt.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  CheckSquare,
  AlertTriangle,
  BookOpen,
  Folder,
  FileCode,
  Clock,
  Activity,
  MessageSquare,
  BarChart2,
  Check,
  X,
  ChevronRight,
  RefreshCw,
  ArrowLeft  // ÄNDERUNG 30.01.2026: Zurück-Button
} from 'lucide-react';

// Platinum Farben
const PLATINUM = {
  border: 'border-white/30',
  text: 'text-white',
  bg: 'bg-white/10',
  glow: '0 0 30px rgba(255, 255, 255, 0.8), 0 0 15px rgba(255, 255, 255, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
};

/**
 * DocumentationOffice Komponente
 *
 * @param {Array} logs - WebSocket Logs für den Documentation Manager
 * @param {Object} workerData - Worker-Status Daten
 * @param {string} status - Aktueller Agent-Status
 * @param {Function} onBack - Callback für Zurück-Navigation
 */
const DocumentationOffice = ({ logs = [], workerData = {}, status = 'Idle', onBack }) => {
  // State für verschiedene Ansichten und Daten
  const [activeTab, setActiveTab] = useState('readme');
  const [readmeContent, setReadmeContent] = useState('');
  const [changelogContent, setChangelogContent] = useState('');
  const [qualityMetrics, setQualityMetrics] = useState({
    completeness: 0,
    clarity: 0,
    sections: {}
  });
  const [documentFiles, setDocumentFiles] = useState([]);
  const [qualityGateLogs, setQualityGateLogs] = useState([]);

  // Extrahiere relevante Logs für Documentation Manager und Quality Gate
  useEffect(() => {
    const docLogs = logs.filter(l =>
      l.agent === 'DocumentationManager' ||
      l.agent === 'QualityGate'
    );

    // Quality Gate Logs separat sammeln
    const qgLogs = logs.filter(l => l.agent === 'QualityGate');
    setQualityGateLogs(qgLogs);

    // Dokumentations-Output extrahieren
    docLogs.forEach(log => {
      if (log.event === 'DocumentationComplete' && log.message) {
        try {
          const data = JSON.parse(log.message);
          if (data.readme) setReadmeContent(data.readme);
          if (data.changelog) setChangelogContent(data.changelog);
          if (data.files) setDocumentFiles(data.files);
        } catch (e) {
          console.debug('[DocumentationOffice] Dokumentations-JSON konnte nicht geparst werden:', e);
        }
      }
      if (log.event === 'Result' && log.message) {
        // README/CHANGELOG Content aus Result-Events
        if (log.message.includes('# ') || log.message.includes('## ')) {
          const lowerMessage = log.message.toLowerCase();
          const isReadme = lowerMessage.includes('readme');
          const isChangelog = lowerMessage.includes('changelog');
          if (isReadme) {
            setReadmeContent(log.message);
          } else if (isChangelog) {
            setChangelogContent(log.message);
          } else {
            setReadmeContent(prev => prev || log.message);
            setChangelogContent(prev => prev || log.message);
          }
        }
      }
    });

    // Quality Metrics aus Quality Gate Logs extrahieren
    qgLogs.forEach(log => {
      if (log.message) {
        try {
          const data = JSON.parse(log.message);
          if (data.score !== undefined) {
            setQualityMetrics(prev => ({
              ...prev,
              [data.step?.toLowerCase() || 'overall']: {
                passed: data.passed,
                score: data.score,
                issues: data.issues || [],
                warnings: data.warnings || []
              }
            }));
          }
        } catch (e) {
          console.debug('[DocumentationOffice] Quality-Gate-JSON konnte nicht geparst werden:', e);
        }
      }
    });
  }, [logs]);

  // Berechne Gesamt-Qualitätsscore
  const overallQualityScore = useMemo(() => {
    const scores = Object.values(qualityMetrics).filter(v => v.score !== undefined);
    if (scores.length === 0) return 0;
    const avg = scores.reduce((sum, v) => sum + v.score, 0) / scores.length;
    return Math.round(avg * 100);
  }, [qualityMetrics]);

  // Status-Indikator
  const isActive = status !== 'Idle' && status !== 'completed';

  return (
    <div className="h-full flex flex-col bg-[#0f172a]">
      {/* Header */}
      <div className={`px-6 py-4 border-b ${PLATINUM.border} bg-[#1e293b] flex justify-between items-center`}>
        <div className="flex items-center gap-4">
          {/* ÄNDERUNG 30.01.2026: Zurück-Button */}
          {onBack && (
            <button
              onClick={onBack}
              className="size-8 flex items-center justify-center rounded bg-slate-800 hover:bg-slate-700 text-slate-400 transition-colors"
              title="Zurück zur Übersicht"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <div className="h-6 w-px bg-slate-700"></div>
          <motion.div
            animate={isActive ? {
              boxShadow: [PLATINUM.glow, 'none', PLATINUM.glow],
            } : {}}
            transition={{ duration: 1.5, repeat: Infinity }}
            className={`p-3 rounded-xl ${PLATINUM.bg} ${PLATINUM.border} border`}
          >
            <FileText size={24} className={PLATINUM.text} />
          </motion.div>
          <div>
            <h2 className={`text-xl font-bold ${PLATINUM.text}`}>Documentation Office</h2>
            <p className="text-slate-400 text-sm">README & CHANGELOG Generierung</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {/* Quality Score Badge */}
          <div className={`px-4 py-2 rounded-lg ${PLATINUM.bg} ${PLATINUM.border} border`}>
            <div className="flex items-center gap-2">
              <BarChart2 size={16} className={PLATINUM.text} />
              <span className={`font-bold ${PLATINUM.text}`}>
                Quality: {overallQualityScore}%
              </span>
            </div>
          </div>
          {/* Status Badge */}
          <div className={`px-3 py-1.5 rounded-full border text-sm font-bold uppercase ${
            isActive
              ? `${PLATINUM.bg} ${PLATINUM.border} ${PLATINUM.text}`
              : 'bg-slate-800 border-slate-700 text-slate-500'
          }`}>
            {status}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 grid grid-cols-12 gap-4 p-4 overflow-hidden">

        {/* Left Sidebar: Document Structure */}
        <div className="col-span-3 flex flex-col gap-4">
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] overflow-hidden flex-1`}>
            <div className={`px-4 py-3 border-b ${PLATINUM.border} bg-[#0f172a]`}>
              <h3 className={`font-bold text-sm uppercase tracking-wider ${PLATINUM.text}`}>
                <Folder size={14} className="inline mr-2" />
                Document Structure
              </h3>
            </div>
            <div className="p-3 space-y-2 overflow-y-auto max-h-[300px] custom-scrollbar">
              {/* Tabs für README/CHANGELOG */}
              <div className="flex gap-2 mb-3">
                <button
                  onClick={() => setActiveTab('readme')}
                  className={`flex-1 px-3 py-2 rounded-lg border text-xs font-bold uppercase transition-all ${
                    activeTab === 'readme'
                      ? `${PLATINUM.bg} ${PLATINUM.border} ${PLATINUM.text}`
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  README.md
                </button>
                <button
                  onClick={() => setActiveTab('changelog')}
                  className={`flex-1 px-3 py-2 rounded-lg border text-xs font-bold uppercase transition-all ${
                    activeTab === 'changelog'
                      ? `${PLATINUM.bg} ${PLATINUM.border} ${PLATINUM.text}`
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  CHANGELOG.md
                </button>
              </div>

              {/* Dateiliste */}
              {documentFiles.length > 0 ? (
                documentFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-sm`}
                  >
                    <FileCode size={14} className="text-slate-400" />
                    <span className="text-slate-300 truncate">{file}</span>
                  </div>
                ))
              ) : (
                <div className="text-slate-500 text-xs text-center py-4">
                  Keine Dateien generiert
                </div>
              )}
            </div>
          </div>

          {/* Quality Gate Log */}
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] overflow-hidden flex-1`}>
            <div className={`px-4 py-3 border-b ${PLATINUM.border} bg-[#0f172a]`}>
              <h3 className={`font-bold text-sm uppercase tracking-wider ${PLATINUM.text}`}>
                <CheckSquare size={14} className="inline mr-2" />
                Quality Gate
              </h3>
            </div>
            <div className="p-3 space-y-2 overflow-y-auto max-h-[200px] custom-scrollbar">
              {qualityGateLogs.length > 0 ? (
                qualityGateLogs.slice(-5).map((log, idx) => {
                  let data = {};
                  try { data = JSON.parse(log.message); } catch {}
                  return (
                    <div
                      key={idx}
                      className={`px-3 py-2 rounded-lg border text-xs ${
                        data.passed
                          ? 'bg-green-500/10 border-green-500/30 text-green-400'
                          : 'bg-red-500/10 border-red-500/30 text-red-400'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {data.passed ? <Check size={12} /> : <X size={12} />}
                        <span className="font-bold">{data.step || log.event}</span>
                        {data.score !== undefined && (
                          <span className="ml-auto opacity-70">
                            {Math.round(data.score * 100)}%
                          </span>
                        )}
                      </div>
                      {data.issues?.length > 0 && (
                        <div className="mt-1 text-[10px] opacity-70">
                          {data.issues[0]}
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-slate-500 text-xs text-center py-4">
                  Keine Validierungen
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center: Synthesis Terminal (README/CHANGELOG Preview) */}
        <div className="col-span-6 flex flex-col">
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] overflow-hidden flex-1 flex flex-col`}>
            <div className={`px-4 py-3 border-b ${PLATINUM.border} bg-[#0f172a] flex justify-between items-center`}>
              <h3 className={`font-bold text-sm uppercase tracking-wider ${PLATINUM.text}`}>
                <BookOpen size={14} className="inline mr-2" />
                {activeTab === 'readme' ? 'README.md' : 'CHANGELOG.md'} Preview
              </h3>
              {isActive && (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <RefreshCw size={14} className={PLATINUM.text} />
                </motion.div>
              )}
            </div>
            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
              <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                {activeTab === 'readme' ? (
                  readmeContent || `# Projekt README

Dieses Dokument wird automatisch generiert...

## Beschreibung
Warte auf Projekt-Informationen...

## Installation
Warte auf TechStack-Blueprint...

## Verwendung
Warte auf Code-Generierung...`
                ) : (
                  changelogContent || `# CHANGELOG

Dieses Dokument wird automatisch generiert...

## [Unreleased]
Warte auf Iterations-Daten...`
                )}
              </pre>
            </div>
          </div>
        </div>

        {/* Right Sidebar: Quality Metrics */}
        <div className="col-span-3 flex flex-col gap-4">
          {/* Completeness Meter */}
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] p-4`}>
            <h3 className={`font-bold text-sm uppercase tracking-wider mb-3 ${PLATINUM.text}`}>
              Vollständigkeit
            </h3>
            <div className="space-y-3">
              {['TechStack', 'Schema', 'Design', 'Code', 'Review', 'Security'].map((section) => {
                const metric = qualityMetrics[section.toLowerCase()];
                const score = metric?.score ?? 0;
                const passed = metric?.passed ?? null;
                return (
                  <div key={section} className="flex items-center gap-2">
                    <span className="text-xs text-slate-400 w-20">{section}</span>
                    <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${score * 100}%` }}
                        transition={{ duration: 0.5 }}
                        className={`h-full ${
                          passed === true ? 'bg-green-500' :
                          passed === false ? 'bg-red-500' :
                          'bg-white/50'
                        }`}
                      />
                    </div>
                    <span className="text-xs text-slate-500 w-8 text-right">
                      {Math.round(score * 100)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Clarity Score */}
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] p-4`}>
            <h3 className={`font-bold text-sm uppercase tracking-wider mb-3 ${PLATINUM.text}`}>
              Dokumentations-Score
            </h3>
            <div className="flex items-center justify-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className={`w-24 h-24 rounded-full ${PLATINUM.border} border-2 flex items-center justify-center`}
                style={{
                  background: `conic-gradient(rgba(255,255,255,0.8) ${overallQualityScore}%, transparent ${overallQualityScore}%)`
                }}
              >
                <div className="w-20 h-20 rounded-full bg-[#1e293b] flex items-center justify-center">
                  <span className={`text-2xl font-bold ${PLATINUM.text}`}>
                    {overallQualityScore}
                  </span>
                </div>
              </motion.div>
            </div>
            <div className="text-center mt-3 text-xs text-slate-400">
              {overallQualityScore >= 80 ? 'Exzellent' :
               overallQualityScore >= 60 ? 'Gut' :
               overallQualityScore >= 40 ? 'Akzeptabel' : 'Verbesserung nötig'}
            </div>
          </div>

          {/* Issues Summary */}
          <div className={`rounded-xl border ${PLATINUM.border} bg-[#1e293b] p-4 flex-1`}>
            <h3 className={`font-bold text-sm uppercase tracking-wider mb-3 ${PLATINUM.text}`}>
              <AlertTriangle size={14} className="inline mr-2" />
              Issues & Warnings
            </h3>
            <div className="space-y-2 overflow-y-auto max-h-[150px] custom-scrollbar">
              {Object.entries(qualityMetrics).map(([step, data]) => (
                data?.issues?.map((issue, idx) => (
                  <div
                    key={`${step}-${idx}`}
                    className="px-2 py-1.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-400"
                  >
                    <span className="font-bold">[{step}]</span> {issue}
                  </div>
                ))
              ))}
              {Object.entries(qualityMetrics).map(([step, data]) => (
                data?.warnings?.map((warning, idx) => (
                  <div
                    key={`${step}-warn-${idx}`}
                    className="px-2 py-1.5 rounded bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-400"
                  >
                    <span className="font-bold">[{step}]</span> {warning}
                  </div>
                ))
              ))}
              {Object.values(qualityMetrics).every(v => (!v?.issues?.length && !v?.warnings?.length)) && (
                <div className="text-slate-500 text-xs text-center py-4">
                  Keine Issues oder Warnings
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: Activity Log */}
      <div className={`border-t ${PLATINUM.border} bg-[#1e293b] px-4 py-3`}>
        <div className="flex items-center gap-2 mb-2">
          <Activity size={14} className={PLATINUM.text} />
          <span className={`text-xs font-bold uppercase tracking-wider ${PLATINUM.text}`}>
            Agent Activity
          </span>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
          {logs.filter(l => l.agent === 'DocumentationManager' || l.agent === 'QualityGate').slice(-6).map((log, idx) => (
            <div
              key={idx}
              className={`flex-shrink-0 px-3 py-2 rounded-lg border text-xs ${
                log.agent === 'QualityGate'
                  ? 'bg-white/5 border-white/20 text-white'
                  : 'bg-slate-800 border-slate-700 text-slate-300'
              }`}
            >
              <div className="flex items-center gap-2">
                {log.agent === 'QualityGate' ? <CheckSquare size={12} /> : <FileText size={12} />}
                <span className="font-bold">{log.event}</span>
              </div>
              <div className="text-[10px] opacity-70 mt-1 max-w-[200px] truncate">
                {log.message?.substring(0, 50)}...
              </div>
            </div>
          ))}
          {logs.filter(l => l.agent === 'DocumentationManager' || l.agent === 'QualityGate').length === 0 && (
            <div className="text-slate-500 text-xs py-2">
              Warte auf Agent-Aktivität...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentationOffice;
