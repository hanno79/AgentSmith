/**
 * Author: rahn
 * Datum: 30.01.2026
 * Version: 1.0
 * Beschreibung: HelpPanel Komponente - Zeigt HELP_NEEDED Events von blockierten Agenten.
 *               Gemäß Kommunikationsprotokoll v1.0 zeigt dieses Panel Situationen an,
 *               in denen Agenten auf Probleme stoßen und Unterstützung benötigen.
 *               # ÄNDERUNG [31.01.2026]: Guards für optionale Callback-Props.
 */

import React from 'react';
import { AlertTriangle, X, RefreshCw, Shield, TestTube, Bot } from 'lucide-react';

// Icon-Mapping für verschiedene Agenten
const agentIcons = {
  security: Shield,
  tester: TestTube,
  default: Bot
};

// Farb-Mapping für Prioritäten
const priorityColors = {
  critical: 'border-red-500/50 bg-red-500/10',
  high: 'border-orange-500/50 bg-orange-500/10',
  normal: 'border-yellow-500/50 bg-yellow-500/10',
  low: 'border-blue-500/50 bg-blue-500/10'
};

// Text-Mapping für Prioritäten
const priorityText = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  normal: 'text-yellow-400',
  low: 'text-blue-400'
};

// Beschreibungen für bekannte Gründe
const reasonDescriptions = {
  critical_vulnerabilities: 'Kritische Sicherheitslücken gefunden',
  no_unit_tests: 'Unit-Tests fehlen im Projekt',
  no_orchestration_plan: 'Kein Ausführungsplan erstellt',
  security_review_required: 'Manuelle Sicherheitsprüfung erforderlich',
  clarify_requirements: 'Anforderungen unklar',
  create_test_files: 'Test-Dateien müssen erstellt werden'
};

/**
 * HelpPanel Komponente - Zeigt HELP_NEEDED Events als Notification-Panel.
 *
 * @param {Array} helpRequests - Liste der aktiven HELP_NEEDED Requests
 * @param {Function} onDismiss - Callback zum Entfernen eines Requests
 * @param {Function} onDismissAll - Callback zum Entfernen aller Requests
 */
const HelpPanel = ({ helpRequests = [], onDismiss, onDismissAll }) => {
  // # ÄNDERUNG [31.01.2026]: Callback-Guards für optionale Handler
  const handleDismissAll = () => {
    if (typeof onDismissAll === 'function') {
      onDismissAll();
    }
  };

  const handleDismiss = (requestId) => {
    if (typeof onDismiss === 'function') {
      onDismiss(requestId);
    }
  };

  if (!helpRequests || helpRequests.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-md space-y-2">
      {/* Header mit "Alle schließen" Button */}
      {helpRequests.length > 1 && (
        <div className="flex justify-end mb-1">
          <button
            onClick={handleDismissAll}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1 px-2 py-1 rounded bg-slate-800/50 hover:bg-slate-700/50 transition-colors"
          >
            <RefreshCw size={12} />
            Alle schließen ({helpRequests.length})
          </button>
        </div>
      )}

      {/* Help Request Cards */}
      {helpRequests.map((request) => {
        const agentKey = request.agent?.toLowerCase().replace(/[\s-]/g, '') || 'default';
        const IconComponent = agentIcons[agentKey] || agentIcons.default;
        const priority = request.context?.priority || 'normal';
        const colorClass = priorityColors[priority] || priorityColors.normal;
        const textClass = priorityText[priority] || priorityText.normal;

        return (
          <div
            key={request.id}
            className={`p-4 rounded-lg border backdrop-blur-sm shadow-lg animate-slide-in ${colorClass}`}
          >
            <div className="flex items-start gap-3">
              {/* Icon */}
              <div className={`p-2 rounded-lg bg-slate-800/50 ${textClass}`}>
                {priority === 'critical' || priority === 'high' ? (
                  <AlertTriangle className="w-5 h-5" />
                ) : (
                  <IconComponent className="w-5 h-5" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className={`font-medium text-sm ${textClass}`}>
                  {request.agent} benötigt Unterstützung
                </p>
                <p className="text-slate-300 text-xs mt-1">
                  {reasonDescriptions[request.reason] || request.reason}
                </p>

                {/* Context Details */}
                {request.context && (
                  <div className="mt-2 text-xs text-slate-400 space-y-1">
                    {request.context.count && (
                      <p>Anzahl: {request.context.count} {request.context.total_vulns ? `von ${request.context.total_vulns}` : ''}</p>
                    )}
                    {request.context.iteration !== undefined && (
                      <p>Iteration: {request.context.iteration + 1}</p>
                    )}
                    {request.context.project_type && (
                      <p>Projekttyp: {request.context.project_type}</p>
                    )}
                  </div>
                )}

                {/* Action Required */}
                {request.actionRequired && (
                  <div className="mt-2 pt-2 border-t border-white/10">
                    <p className="text-slate-400 text-xs">
                      Aktion: <span className="text-slate-300">{reasonDescriptions[request.actionRequired] || request.actionRequired}</span>
                    </p>
                  </div>
                )}

                {/* Timestamp */}
                <p className="text-slate-500 text-[10px] mt-2">
                  {new Date(request.timestamp).toLocaleTimeString('de-DE')}
                </p>
              </div>

              {/* Close Button */}
              <button
                onClick={() => handleDismiss(request.id)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/10 transition-colors"
                title="Schließen"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        );
      })}

      {/* CSS für Slide-in Animation */}
      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default HelpPanel;
