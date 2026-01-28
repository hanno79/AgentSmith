/**
 * Author: rahn
 * Datum: 28.01.2026
 * Version: 1.0
 * Beschreibung: ProjectDetail Komponente - Zeigt Projekt-Header und beteiligte Agenten.
 *               Teil der Bibliothek-Ansicht. Keine Dummy-Daten.
 */

import React from 'react';
import {
  BookOpen,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  FileText,
  Users,
  Hash,
  RefreshCw
} from 'lucide-react';

// Farbpalette passend zu LibraryOffice
const COLORS = {
  primary: '#ec9c13',
  woodDark: '#2c241b',
  glass: 'rgba(44, 36, 27, 0.7)',
  glassBorder: 'rgba(236, 156, 19, 0.2)'
};

// Zeitformat
const formatTime = (isoString) => {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Kosten formatieren
const formatCost = (cost) => {
  if (!cost && cost !== 0) return '-';
  return `$${cost.toFixed(4)}`;
};

// Status-Badge rendern
const renderStatusBadge = (status) => {
  const configs = {
    running: { icon: RefreshCw, color: 'text-amber-400', bg: 'bg-amber-900/30', text: 'Läuft' },
    success: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-900/30', text: 'Erfolgreich' },
    failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/30', text: 'Fehlgeschlagen' },
    error: { icon: AlertCircle, color: 'text-orange-400', bg: 'bg-orange-900/30', text: 'Fehler' }
  };
  const config = configs[status] || configs.running;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color}`}>
      <Icon size={12} className={status === 'running' ? 'animate-spin' : ''} />
      {config.text}
    </span>
  );
};

/**
 * ProjectDetail - Zeigt den Projekt-Header und die beteiligten Agenten
 *
 * @param {Object} project - Projekt-Daten (aktuell oder archiviert)
 */
const ProjectDetail = ({ project }) => {
  if (!project) {
    return (
      <>
        <div
          className="px-6 py-4 border-b"
          style={{
            backgroundColor: COLORS.woodDark + '80',
            borderColor: COLORS.glassBorder
          }}
        >
          <div className="text-center py-4 text-amber-200/30">
            <BookOpen size={32} className="mx-auto mb-2" />
            <p>Wähle ein Projekt aus dem Archiv oder starte ein neues</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      {/* Project Header */}
      <div
        className="px-6 py-4 border-b"
        style={{
          backgroundColor: COLORS.woodDark + '80',
          borderColor: COLORS.glassBorder
        }}
      >
        <div className="flex items-center gap-3 mb-2">
          <FileText size={20} style={{ color: COLORS.primary }} />
          <h3 className="text-lg font-bold text-amber-100">{project.name}</h3>
          {renderStatusBadge(project.status)}
        </div>
        <p className="text-sm text-amber-200/50 mb-3">{project.goal}</p>
        <div className="flex items-center gap-6 text-xs text-amber-200/40">
          <span className="flex items-center gap-1">
            <Clock size={12} />
            Start: {formatTime(project.started_at)}
          </span>
          {project.completed_at && (
            <span className="flex items-center gap-1">
              <CheckCircle size={12} />
              Ende: {formatTime(project.completed_at)}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Hash size={12} />
            {project.iterations || 0} Iterationen
          </span>
          <span className="flex items-center gap-1" style={{ color: COLORS.primary }}>
            Kosten: {formatCost(project.total_cost)}
          </span>
        </div>
      </div>

      {/* Agent Footer */}
      {(project.agents_involved?.length > 0) && (
        <div
          className="px-4 py-3 border-t"
          style={{
            backgroundColor: COLORS.woodDark,
            borderColor: COLORS.glassBorder
          }}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-200/70 uppercase tracking-wider flex items-center gap-2">
              <Users size={14} style={{ color: COLORS.primary }} />
              Beteiligte Agenten
            </span>
            <div className="flex items-center gap-2">
              {project.agents_involved.map((agent, i) => (
                <span
                  key={i}
                  className="text-[10px] px-2 py-1 rounded"
                  style={{
                    backgroundColor: COLORS.glass,
                    color: COLORS.primary
                  }}
                >
                  {agent}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export { renderStatusBadge, formatTime, formatCost };
export default ProjectDetail;
