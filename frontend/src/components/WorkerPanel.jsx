/**
 * Author: rahn
 * Datum: 25.01.2026
 * Version: 1.0
 * Beschreibung: WorkerPanel Komponente - Zeigt Worker-Status in Agent Offices.
 *               Für parallele Verarbeitung mit mehreren Workern pro Office.
 */

import React from 'react';
import { Users, Circle, Cpu, CheckCircle, Clock } from 'lucide-react';

// Farben für verschiedene Worker-Status
const statusColors = {
  idle: 'text-slate-400 bg-slate-800/50',
  working: 'text-green-400 bg-green-500/20',
  error: 'text-red-400 bg-red-500/20',
  offline: 'text-slate-600 bg-slate-900/50'
};

// Status-Icons
const StatusIcon = ({ status }) => {
  switch (status) {
    case 'working':
      return <Circle size={8} className="text-green-400 animate-pulse fill-green-400" />;
    case 'error':
      return <Circle size={8} className="text-red-400 fill-red-400" />;
    case 'offline':
      return <Circle size={8} className="text-slate-600 fill-slate-600" />;
    default: // idle
      return <Circle size={8} className="text-slate-400" />;
  }
};

/**
 * WorkerPanel Komponente - Zeigt alle Worker eines Office mit Status.
 *
 * @param {Array} workers - Array von Worker-Objekten
 * @param {string} color - Farbschema des Office (blue, green, etc.)
 * @param {boolean} compact - Kompakte Ansicht (nur Icons)
 */
const WorkerPanel = ({ workers = [], color = 'blue', compact = false }) => {
  // Wenn keine Worker, nichts anzeigen
  if (!workers || workers.length === 0) {
    return null;
  }

  // Statistiken berechnen
  const activeWorkers = workers.filter(w => w.status === 'working').length;
  const totalWorkers = workers.length;

  // Nur anzeigen wenn mehr als 1 Worker (sonst nicht relevant)
  if (totalWorkers <= 1 && !compact) {
    return null;
  }

  // Kompakte Ansicht für Header
  if (compact) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-slate-800/50 border border-slate-700/50">
        <Users size={12} className="text-slate-400" />
        <div className="flex gap-1">
          {workers.map((worker, idx) => (
            <div
              key={worker.id || idx}
              className={`w-2 h-2 rounded-full ${
                worker.status === 'working' ? 'bg-green-400 animate-pulse' : 'bg-slate-600'
              }`}
              title={`${worker.name}: ${worker.status}`}
            />
          ))}
        </div>
        <span className="text-[10px] text-slate-400 font-mono">
          {activeWorkers}/{totalWorkers}
        </span>
      </div>
    );
  }

  // Vollständige Ansicht
  return (
    <div className="bg-[#1e293b]/50 rounded-lg border border-[#334155] overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[#334155] bg-[#1e293b]/80 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Users size={14} className="text-slate-400" />
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Worker Pool
          </span>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full ${
          activeWorkers > 0
            ? 'bg-green-500/20 text-green-300 border border-green-500/30'
            : 'bg-slate-800 text-slate-400'
        }`}>
          {activeWorkers} / {totalWorkers} aktiv
        </span>
      </div>

      {/* Worker Liste */}
      <div className="divide-y divide-[#334155]/50">
        {workers.map((worker, idx) => (
          <div
            key={worker.id || idx}
            className={`px-3 py-2 flex items-center gap-3 transition-colors ${
              worker.status === 'working' ? 'bg-green-500/5' : ''
            }`}
          >
            {/* Status Indicator */}
            <StatusIcon status={worker.status} />

            {/* Worker Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-200">
                  {worker.name}
                </span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded uppercase font-bold ${
                  statusColors[worker.status] || statusColors.idle
                }`}>
                  {worker.status}
                </span>
              </div>

              {/* Task Description (wenn working) */}
              {worker.status === 'working' && worker.current_task_description && (
                <p className="text-[10px] text-slate-400 truncate mt-0.5">
                  {worker.current_task_description}
                </p>
              )}
            </div>

            {/* Zusätzliche Info */}
            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              {/* Modell (wenn vorhanden) */}
              {worker.model && worker.status === 'working' && (
                <div className="flex items-center gap-1" title="Modell">
                  <Cpu size={10} />
                  <span className="max-w-[80px] truncate">{worker.model.split('/').pop()}</span>
                </div>
              )}

              {/* Tasks Completed */}
              {worker.tasks_completed > 0 && (
                <div className="flex items-center gap-1" title="Abgeschlossene Tasks">
                  <CheckCircle size={10} className="text-green-500" />
                  <span>{worker.tasks_completed}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Queue Info (wenn Tasks warten) */}
      {workers.some(w => w.queue_size > 0) && (
        <div className="px-3 py-2 border-t border-[#334155] bg-amber-500/5 flex items-center gap-2">
          <Clock size={12} className="text-amber-400" />
          <span className="text-[10px] text-amber-300">
            Tasks in Queue warten auf freie Worker
          </span>
        </div>
      )}
    </div>
  );
};

export default WorkerPanel;
