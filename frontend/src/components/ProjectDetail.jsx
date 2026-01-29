/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.1
 * Beschreibung: ProjectDetail Komponente - Zeigt Projekt-Header und beteiligte Agenten.
 *               Teil der Bibliothek-Ansicht. Keine Dummy-Daten.
 *               ÄNDERUNG 29.01.2026: Register-Ansicht für Aufgabe/Briefing Umschaltung.
 */

import React, { useState } from 'react';
import {
  BookOpen,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  FileText,
  Users,
  Hash,
  RefreshCw,
  Clipboard,
  Target,
  Settings,
  MessageSquare,
  HelpCircle
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
 * BriefingView - Zeigt das Discovery Briefing an
 */
const BriefingView = ({ briefing }) => {
  if (!briefing) {
    return (
      <div className="text-center py-8 text-amber-200/30">
        <Clipboard size={32} className="mx-auto mb-2" />
        <p>Kein Discovery Briefing vorhanden</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Projektziel */}
      {briefing.goal && (
        <div>
          <h4 className="text-xs uppercase text-amber-200/50 mb-1 flex items-center gap-1">
            <Target size={12} />
            Projektziel
          </h4>
          <p className="text-amber-100 text-sm">{briefing.goal}</p>
        </div>
      )}

      {/* Technische Anforderungen */}
      {briefing.techRequirements && (
        <div>
          <h4 className="text-xs uppercase text-amber-200/50 mb-1 flex items-center gap-1">
            <Settings size={12} />
            Technische Anforderungen
          </h4>
          <div className="text-sm text-amber-100 space-y-1">
            {briefing.techRequirements.language && (
              <p>Sprache: <span className="text-amber-200/70">{briefing.techRequirements.language}</span></p>
            )}
            {briefing.techRequirements.deployment && (
              <p>Deployment: <span className="text-amber-200/70">{briefing.techRequirements.deployment}</span></p>
            )}
          </div>
        </div>
      )}

      {/* Beteiligte Agenten im Briefing */}
      {briefing.agents?.length > 0 && (
        <div>
          <h4 className="text-xs uppercase text-amber-200/50 mb-1 flex items-center gap-1">
            <Users size={12} />
            Geplante Agenten
          </h4>
          <div className="flex flex-wrap gap-1">
            {briefing.agents.map((agent, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-0.5 rounded"
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
      )}

      {/* Entscheidungen aus Discovery */}
      {briefing.answers?.length > 0 && (
        <div>
          <h4 className="text-xs uppercase text-amber-200/50 mb-2 flex items-center gap-1">
            <MessageSquare size={12} />
            Entscheidungen aus Discovery
          </h4>
          <div className="space-y-2">
            {briefing.answers
              .filter(a => !a.skipped)
              .map((answer, i) => (
                <div
                  key={i}
                  className="text-sm p-2 rounded"
                  style={{ backgroundColor: COLORS.glass }}
                >
                  <span className="text-amber-200/70 text-xs">
                    {Array.isArray(answer.agents) && answer.agents.length > 0
                      ? answer.agents.join(', ')
                      : answer.agents || answer.agent || '—'}:
                  </span>
                  <p className="text-amber-100">
                    {answer.selectedValues?.join(', ') || answer.customText || '-'}
                  </p>
                </div>
              ))
            }
          </div>
        </div>
      )}

      {/* Offene Punkte */}
      {briefing.openPoints?.length > 0 && (
        <div>
          <h4 className="text-xs uppercase text-amber-200/50 mb-1 flex items-center gap-1">
            <HelpCircle size={12} />
            Offene Punkte
          </h4>
          <ul className="list-disc pl-4 text-amber-100 text-sm space-y-1">
            {briefing.openPoints.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/**
 * ProjectDetail - Zeigt den Projekt-Header und die beteiligten Agenten
 *
 * @param {Object} project - Projekt-Daten (aktuell oder archiviert)
 */
const ProjectDetail = ({ project }) => {
  const [activeTab, setActiveTab] = useState('aufgabe');

  // Prüfe ob Briefing vorhanden ist
  const hasBriefing = project?.briefing && Object.keys(project.briefing).length > 0;

  if (!project) {
    return (
      <div className="h-full flex flex-col">
        <div
          className="flex-1 px-6 py-4"
          style={{
            backgroundColor: COLORS.woodDark + '80'
          }}
        >
          <div className="text-center py-4 text-amber-200/30">
            <BookOpen size={32} className="mx-auto mb-2" />
            <p>Wähle ein Projekt aus dem Archiv oder starte ein neues</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Tabs Header */}
      <div
        className="flex border-b shrink-0"
        style={{
          backgroundColor: COLORS.woodDark,
          borderColor: COLORS.glassBorder
        }}
      >
        <button
          onClick={() => setActiveTab('aufgabe')}
          className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'aufgabe'
              ? 'text-amber-100 border-b-2'
              : 'text-amber-200/50 hover:text-amber-200/70'
          }`}
          style={{
            borderColor: activeTab === 'aufgabe' ? COLORS.primary : 'transparent',
            marginBottom: '-1px'
          }}
        >
          <FileText size={14} />
          Aufgabe
        </button>
        {hasBriefing && (
          <button
            onClick={() => setActiveTab('briefing')}
            className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
              activeTab === 'briefing'
                ? 'text-amber-100 border-b-2'
                : 'text-amber-200/50 hover:text-amber-200/70'
            }`}
            style={{
              borderColor: activeTab === 'briefing' ? COLORS.primary : 'transparent',
              marginBottom: '-1px'
            }}
          >
            <Clipboard size={14} />
            Briefing
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div
        className="flex-1 overflow-auto px-6 py-4"
        style={{
          backgroundColor: COLORS.woodDark + '80'
        }}
      >
        {activeTab === 'aufgabe' ? (
          /* Aufgabe Tab - Zeigt Projekt-Details */
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FileText size={20} style={{ color: COLORS.primary }} />
              <h3 className="text-lg font-bold text-amber-100">{project.name}</h3>
              {renderStatusBadge(project.status)}
            </div>
            <p className="text-sm text-amber-200/50 mb-3">{project.goal}</p>
            <div className="flex items-center gap-6 text-xs text-amber-200/40 flex-wrap">
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
        ) : (
          /* Briefing Tab - Zeigt Discovery Briefing */
          <BriefingView briefing={project.briefing} />
        )}
      </div>

      {/* Agent Footer - bleibt immer unten */}
      {(project.agents_involved?.length > 0) && (
        <div
          className="px-4 py-3 border-t shrink-0"
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
            <div className="flex items-center gap-2 flex-wrap">
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
    </div>
  );
};

export { renderStatusBadge, formatTime, formatCost };
export default ProjectDetail;
