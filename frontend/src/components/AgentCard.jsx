/**
 * Author: rahn
 * Datum: 03.02.2026
 * Version: 1.7
 * Beschreibung: AgentCard Komponente - Zeigt Status und Logs eines einzelnen Agenten.
 *               Mit farbigem Glow-Effekt bei aktiven Agenten.
 *               ÄNDERUNG 25.01.2026: Bug Fix - Glow nur bei explizit aktiven Status (nicht bei *Output).
 *               ÄNDERUNG 25.01.2026: Worker-Anzeige für parallele Verarbeitung (Badge mit aktiv/total).
 *               ÄNDERUNG 25.01.2026: Kompaktere Status-Badges und gefilterte Logs.
 *               ÄNDERUNG 31.01.2026: Refactoring - Nutzt zentrale COLORS aus config.js (Single Source of Truth)
 *               ÄNDERUNG 31.01.2026: PropTypes für name, icon, color (oneOf COLORS), status, logs, onOpenOffice, workers
 *               ÄNDERUNG 31.01.2026: Explizite Fallbacks bei ungültigem color-Prop (DEFAULT_COLOR, keine undefined-Werte)
 *               ÄNDERUNG 03.02.2026: ROOT-CAUSE-FIX - "|| activeWorkers > 0" entfernt aus isActive Logik.
 *                                    Agent-Status hat Vorrang, Worker nur fuer Badge relevant.
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { ExternalLink, Users } from 'lucide-react';
// ÄNDERUNG 31.01.2026: Import aus zentraler Konfiguration statt lokaler Duplikate
import { COLORS, DEFAULT_COLOR, getColorClasses } from '../constants/config';

// Gültige color-Werte für PropTypes (Single Source of Truth aus COLORS)
const COLOR_KEYS = Object.keys(COLORS);

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
  // ÄNDERUNG 31.01.2026: Sichere Farbauflösung – bei ungültigem color Fallback auf DEFAULT_COLOR
  const colorDef = COLORS[color] ?? COLORS[DEFAULT_COLOR];
  // ÄNDERUNG 25.01.2026: Worker-Statistiken berechnen (für Badge-Anzeige)
  const activeWorkers = workers.filter(w => w.status === 'working').length;
  const totalWorkers = workers.length;
  // ÄNDERUNG 03.02.2026: ROOT-CAUSE-FIX - Agent-Status hat Vorrang
  // Symptom: Glow-Effekt stoppte nicht wenn Agent fertig war
  // Ursache: "|| activeWorkers > 0" liess Glow weiterlaufen wenn Worker-Daten veraltet waren
  // Loesung: Nur Agent-Status entscheidet ueber Glow, Worker nur fuer Badge relevant
  const isActive = status && (activeStates.includes(status) || status === 'Status');
  // ÄNDERUNG 25.01.2026: Gefilterte Logs einmal berechnen statt zweimal
  const filteredLogs = useMemo(() => filterLogs(logs), [logs]);

  // ÄNDERUNG 02.02.2026: Key basierend auf isActive für korrektes Animations-Stoppen
  // Framer Motion stoppt repeat:Infinity nicht automatisch bei Prop-Änderungen
  // Der key zwingt ein Neu-Rendern bei Status-Wechsel
  return (
    <motion.div
      key={`${name}-${isActive ? 'active' : 'idle'}`}
      initial={{ boxShadow: 'none', borderColor: 'transparent' }}
      animate={{
        boxShadow: isActive ? colorDef.glow : 'none',
        borderColor: isActive ? colorDef.hex : 'transparent',
      }}
      transition={{ duration: 0.6, repeat: isActive ? Infinity : 0, repeatType: 'reverse', ease: 'easeInOut' }}
      className={`p-4 rounded-xl border ${colorDef.border} bg-[#1c2127] transition-all relative overflow-hidden group ${isActive ? 'ring-1 ring-white/10' : ''}`}
    >
      {/* Hintergrund-Icon */}
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        {React.cloneElement(icon, { size: 64 })}
      </div>

      {/* Header mit Name und Status - ÄNDERUNG 25.01.2026: Kompakteres Layout */}
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg bg-slate-800 border border-border-dark ${colorDef.text}`}>
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
              activeWorkers > 0 ? getColorClasses(color) : 'bg-[#283039] border-border-dark text-slate-500'
            }`} title={`${activeWorkers} von ${totalWorkers} Worker aktiv`}>
              <Users size={9} />
              <span>{activeWorkers}/{totalWorkers}</span>
            </div>
          )}
          {/* Status-Badge: gekürzt */}
          <div className={`px-1.5 py-0.5 rounded-full border text-[8px] font-bold uppercase transition-all max-w-[60px] truncate ${
            status !== 'Idle' ? getColorClasses(color) : 'bg-[#283039] border-border-dark text-slate-500'
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
              className={`p-1 rounded-lg border transition-all hover:scale-105 ${getColorClasses(color)}`}
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

AgentCard.propTypes = {
  name: PropTypes.string.isRequired,
  icon: PropTypes.element.isRequired,
  color: PropTypes.oneOf(COLOR_KEYS).isRequired,
  status: PropTypes.string,
  logs: PropTypes.arrayOf(
    PropTypes.shape({
      event: PropTypes.string,
      message: PropTypes.string,
    })
  ),
  onOpenOffice: PropTypes.func,
  workers: PropTypes.arrayOf(
    PropTypes.shape({
      status: PropTypes.string,
    })
  ),
};

AgentCard.defaultProps = {
  status: 'Idle',
  logs: [],
  workers: [],
};

export default AgentCard;
