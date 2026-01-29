/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.0
 * Beschreibung: Fortschrittsanzeige für Discovery-Phasen.
 */
// ÄNDERUNG 29.01.2026: ProgressBar aus DiscoveryOffice ausgelagert

import React from 'react';
import { CheckCircle, MessageSquare, Users, FileText, Lightbulb } from 'lucide-react';
import { PHASES } from '../constants/discoveryConstants';

const ProgressBar = ({ phase }) => {
  const phases = [
    { key: PHASES.VISION, label: 'Vision', icon: Lightbulb },
    { key: PHASES.TEAM_SETUP, label: 'Team', icon: Users },
    { key: PHASES.DYNAMIC_QUESTIONS, label: 'Projekt-Fragen', icon: MessageSquare },
    { key: PHASES.GUIDED_QA, label: 'Tech-Fragen', icon: MessageSquare },
    { key: PHASES.SUMMARY, label: 'Zusammenfassung', icon: CheckCircle },
    { key: PHASES.BRIEFING, label: 'Briefing', icon: FileText }
  ];

  const currentIndex = phases.findIndex(p => p.key === phase);

  return (
    <div className="flex items-center justify-between mb-8 px-4">
      {phases.map((p, idx) => {
        const Icon = p.icon;
        const isActive = idx === currentIndex;
        const isComplete = idx < currentIndex;

        return (
          <React.Fragment key={p.key}>
            <div className={`flex flex-col items-center ${
              isActive ? 'text-cyan-400' : isComplete ? 'text-green-400' : 'text-slate-500'
            }`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                isActive ? 'bg-cyan-900/50 ring-2 ring-cyan-400' :
                isComplete ? 'bg-green-900/50' : 'bg-slate-800'
              }`}>
                <Icon size={20} />
              </div>
              <span className="text-xs mt-2">{p.label}</span>
            </div>
            {idx < phases.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 ${
                idx < currentIndex ? 'bg-green-400' : 'bg-slate-700'
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default ProgressBar;
