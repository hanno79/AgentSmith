/**
 * Author: rahn
 * Datum: 25.01.2026
 * Version: 1.5
 * Beschreibung: AgentCard Komponente - Zeigt Status und Logs eines einzelnen Agenten.
 *               Mit farbigem Glow-Effekt bei aktiven Agenten.
 *               ÄNDERUNG 25.01.2026: Bug Fix - Glow nur bei explizit aktiven Status (nicht bei *Output).
 *               ÄNDERUNG 25.01.2026: Worker-Anzeige für parallele Verarbeitung (Badge mit aktiv/total).
 *               ÄNDERUNG 25.01.2026: Kompaktere Status-Badges und gefilterte Logs.
 *               ÄNDERUNG 25.01.2026: BUG FIX - Glow-Effekt auch bei aktiven Workern (activeWorkers > 0).
 */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Users } from 'lucide-react';

// Farbkonfiguration für verschiedene Agenten
const colors = {
  blue: 'border-blue-500/40 text-blue-400 bg-blue-500/10',
  purple: 'border-purple-500/40 text-purple-400 bg-purple-500/10',
  pink: 'border-pink-500/40 text-pink-400 bg-pink-500/10',
  yellow: 'border-yellow-500/40 text-yellow-400 bg-yellow-500/10',
  red: 'border-red-500/40 text-red-400 bg-red-500/10',
  green: 'border-green-500/40 text-green-400 bg-green-500/10',
  orange: 'border-orange-500/40 text-orange-400 bg-orange-500/10',
  cyan: 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10',
  indigo: 'border-indigo-500/40 text-indigo-400 bg-indigo-500/10',
  // ÄNDERUNG 30.01.2026: Platinum/Weiß für Documentation Manager
  platinum: 'border-white/30 text-white bg-white/10',
};

// Glow-Effekte für aktive Agenten
const glowStyles = {
  blue: '0 0 30px rgba(59, 130, 246, 0.8), 0 0 15px rgba(59, 130, 246, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  purple: '0 0 30px rgba(168, 85, 247, 0.8), 0 0 15px rgba(168, 85, 247, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  pink: '0 0 30px rgba(236, 72, 153, 0.8), 0 0 15px rgba(236, 72, 153, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  yellow: '0 0 30px rgba(234, 179, 8, 0.8), 0 0 15px rgba(234, 179, 8, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  red: '0 0 30px rgba(239, 68, 68, 0.8), 0 0 15px rgba(239, 68, 68, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  green: '0 0 30px rgba(34, 197, 94, 0.8), 0 0 15px rgba(34, 197, 94, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  orange: '0 0 30px rgba(249, 115, 22, 0.8), 0 0 15px rgba(249, 115, 22, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  cyan: '0 0 30px rgba(6, 182, 212, 0.8), 0 0 15px rgba(6, 182, 212, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  indigo: '0 0 30px rgba(79, 70, 229, 0.8), 0 0 15px rgba(79, 70, 229, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
  // ÄNDERUNG 30.01.2026: Platinum/Weiß für Documentation Manager
  platinum: '0 0 30px rgba(255, 255, 255, 0.8), 0 0 15px rgba(255, 255, 255, 0.5), 0 0 5px rgba(255, 255, 255, 0.3)',
};

// Border-Farben für Animation
const borderColors = {
  blue: '#3b82f6',
  purple: '#a855f7',
  pink: '#ec4899',
  yellow: '#eab308',
  red: '#ef4444',
  green: '#22c55e',
  orange: '#f97316',
  cyan: '#06b6d4',
  indigo: '#4f46e5',
  // ÄNDERUNG 30.01.2026: Platinum/Weiß für Documentation Manager
  platinum: '#ffffff',
};

// ÄNDERUNG 25.01.2026: Aktive Status-Werte (Agent arbeitet gerade)
// ÄNDERUNG 28.01.2026: 'Working' hinzugefügt als universeller Arbeitsstatus
// Nur diese Status lösen den Glow-Effekt aus
const activeStates = [
  'Status',           // Generischer "arbeitet" Status
  'Iteration',        // Coder arbeitet an Iteration
  'searching',        // Researcher sucht
  'RescanStart',      // Security scannt Code
  'Analysis',         // Orchestrator analysiert
  'generating',       // Agent generiert etwas
  'processing',       // Agent verarbeitet
  'testing',          // Tester testet
  'reviewing',        // Reviewer prüft
  'designing',        // Designer arbeitet
  'Working',          // Universeller Arbeitsstatus (neu)
];

// ÄNDERUNG 25.01.2026: Status-Mapping für kompakte Anzeige
const statusDisplayMap = {
  'CodeOutput': 'Code',
  'CoderTasksOutput': 'Tasks',
  'WorkerStatus': 'Active',
  'ResearchOutput': 'Done',
  'TechStackOutput': 'Stack',
  'DBDesignerOutput': 'Schema',
  'DesignerOutput': 'Design',
  'ReviewOutput': 'Review',
  'UITestResult': 'Test',
  'SecurityOutput': 'Scan',
  'SecurityRescanOutput': 'Rescan',
  'TokenMetrics': 'Metrics',
  'RescanStart': 'Scan...',
  'RescanResult': 'Result',
};

// ÄNDERUNG 25.01.2026: Events die aus Logs gefiltert werden (interne/technische Events)
const hiddenLogEvents = ['WorkerStatus', 'TokenMetrics', 'LoopDecision'];

/**
 * Formatiert den Status für kompakte Anzeige
 */
const formatStatus = (status) => {
  if (!status) return 'Idle';
  // Prüfe auf bekannte Mappings
  if (statusDisplayMap[status]) return statusDisplayMap[status];
  // Kürze lange Status auf max 10 Zeichen
  if (status.length > 10) return status.substring(0, 8) + '..';
  return status;
};

/**
 * Filtert und formatiert Logs für die Anzeige
 */
const filterLogs = (logs) => {
  return logs
    .filter(l => !hiddenLogEvents.includes(l.event))  // Technische Events ausblenden
    .filter(l => !l.message?.startsWith('{'));         // JSON-Nachrichten ausblenden
};

/**
 * AgentCard Komponente - Zeigt einen einzelnen Agenten mit Status und Logs.
 *
 * @param {string} name - Name des Agenten
 * @param {React.Element} icon - Lucide Icon
 * @param {string} color - Farbschema (blue, purple, pink, etc.)
 * @param {string} status - Aktueller Status
 * @param {Array} logs - Log-Einträge
 * @param {Function} onOpenOffice - Callback zum Öffnen des Agent Office
 * @param {Array} workers - Worker-Daten für dieses Office (optional)
 */
const AgentCard = ({ name, icon, color, status, logs, onOpenOffice, workers = [] }) => {
  // ÄNDERUNG 25.01.2026: Worker-Statistiken berechnen
  const activeWorkers = workers.filter(w => w.status === 'working').length;
  const totalWorkers = workers.length;
  // ÄNDERUNG 25.01.2026: Prüfe ob Status in activeStates ODER mit "Status" beginnt
  // ÄNDERUNG 25.01.2026: BUG FIX - Glow auch wenn Worker aktiv sind!
  const isActive = (status && (activeStates.includes(status) || status === 'Status')) || activeWorkers > 0;
  // ÄNDERUNG 25.01.2026: Gefilterte Logs einmal berechnen statt zweimal
  const filteredLogs = useMemo(() => filterLogs(logs), [logs]);

  return (
    <motion.div
      initial={false}
      animate={{
        boxShadow: isActive ? glowStyles[color] : 'none',
        borderColor: isActive ? borderColors[color] : '',
      }}
      transition={{ duration: 0.6, repeat: isActive ? Infinity : 0, repeatType: 'reverse', ease: 'easeInOut' }}
      className={`p-4 rounded-xl border ${colors[color].split(' ')[0]} bg-[#1c2127] transition-all relative overflow-hidden group ${isActive ? 'ring-1 ring-white/10' : ''}`}
    >
      {/* Hintergrund-Icon */}
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        {React.cloneElement(icon, { size: 64 })}
      </div>

      {/* Header mit Name und Status - ÄNDERUNG 25.01.2026: Kompakteres Layout */}
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg bg-slate-800 border border-border-dark ${colors[color].split(' ')[1]}`}>
            {icon}
          </div>
          <div className="min-w-0">
            <h4 className="font-bold uppercase tracking-tight text-sm">{name}</h4>
            <p className="text-[9px] text-slate-500">Online</p>
          </div>
        </div>
        {/* ÄNDERUNG 25.01.2026: Badges in Spalte statt Zeile auf engem Platz */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {/* Worker-Badge: kompakter */}
          {totalWorkers > 1 && (
            <div className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded-full border text-[8px] font-medium ${
              activeWorkers > 0 ? colors[color] : 'bg-[#283039] border-border-dark text-slate-500'
            }`} title={`${activeWorkers} von ${totalWorkers} Worker aktiv`}>
              <Users size={9} />
              <span>{activeWorkers}/{totalWorkers}</span>
            </div>
          )}
          {/* Status-Badge: gekürzt */}
          <div className={`px-1.5 py-0.5 rounded-full border text-[8px] font-bold uppercase transition-all max-w-[60px] truncate ${
            status !== 'Idle' ? colors[color] : 'bg-[#283039] border-border-dark text-slate-500'
          }`} title={status}>
            {formatStatus(status)}
          </div>
          {/* Office-Button */}
          {onOpenOffice && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onOpenOffice(name.toLowerCase().replace(' ', ''));
              }}
              className={`p-1 rounded-lg border transition-all hover:scale-105 ${colors[color]}`}
              title={`${name} Office öffnen`}
            >
              <ExternalLink size={11} />
            </button>
          )}
        </div>
      </div>

      {/* Log-Ausgabe - ÄNDERUNG 25.01.2026: Gefilterte Logs (keine JSON/technischen Events) */}
      <div className="bg-black/50 rounded-lg p-2.5 h-20 overflow-y-auto terminal-scroll font-mono text-[9px] border border-white/5 relative z-10">
        {filteredLogs.slice(-4).map((l, i) => (
          <div key={i} className="mb-0.5 leading-tight">
            <span className="opacity-40 mr-1.5">&gt;</span>
            <span className="text-slate-300 break-words">{l.message?.substring(0, 80)}{l.message?.length > 80 ? '...' : ''}</span>
          </div>
        ))}
        {filteredLogs.length === 0 && <div className="text-slate-600 italic mt-4 text-center text-[9px]">Warte auf Aufgabe...</div>}
      </div>
    </motion.div>
  );
};

export default AgentCard;
