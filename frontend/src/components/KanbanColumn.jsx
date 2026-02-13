/**
 * Author: rahn
 * Datum: 13.02.2026
 * Version: 1.0
 * Beschreibung: Einzelne Spalte im Kanban-Board.
 *               Zeigt Header mit Titel + Count-Badge und eine scrollbare Liste von FeatureCards.
 *               Fungiert als Droppable-Zone fuer Drag-and-Drop.
 */

import React from 'react';
import PropTypes from 'prop-types';
import { Droppable } from '@hello-pangea/dnd';
import FeatureCard from './FeatureCard';

// AENDERUNG 13.02.2026: Status → Spalten-Konfiguration
const COLUMN_CONFIG = {
  pending: {
    title: 'Ausstehend',
    borderColor: 'border-gray-600/50',
    badgeBg: 'bg-gray-600/30',
    badgeText: 'text-gray-400',
    headerBg: 'bg-gray-800/40',
  },
  in_progress: {
    title: 'In Arbeit',
    borderColor: 'border-blue-500/40',
    badgeBg: 'bg-blue-500/20',
    badgeText: 'text-blue-400',
    headerBg: 'bg-blue-900/20',
  },
  review: {
    title: 'Review',
    borderColor: 'border-yellow-500/40',
    badgeBg: 'bg-yellow-500/20',
    badgeText: 'text-yellow-400',
    headerBg: 'bg-yellow-900/20',
  },
  done: {
    title: 'Fertig',
    borderColor: 'border-green-500/40',
    badgeBg: 'bg-green-500/20',
    badgeText: 'text-green-400',
    headerBg: 'bg-green-900/20',
  },
};

const KanbanColumn = ({ status, features = [] }) => {
  const config = COLUMN_CONFIG[status] || COLUMN_CONFIG.pending;

  return (
    <div className={`flex flex-col rounded-xl border ${config.borderColor} bg-gray-900/50 min-w-[240px] max-w-[300px] flex-1`}>
      {/* Spalten-Header */}
      <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-xl ${config.headerBg}`}>
        <h3 className="text-sm font-semibold text-gray-200">{config.title}</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${config.badgeBg} ${config.badgeText} font-medium`}>
          {features.length}
        </span>
      </div>

      {/* Droppable-Zone mit Karten */}
      <Droppable droppableId={status}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={`
              flex-1 p-2 overflow-y-auto min-h-[100px] max-h-[600px]
              transition-colors duration-200
              ${snapshot.isDraggingOver ? 'bg-gray-800/40' : ''}
            `}
          >
            {features.length === 0 ? (
              <div className="text-xs text-gray-600 text-center py-6">
                Keine Features
              </div>
            ) : (
              features.map((feature, index) => (
                <FeatureCard key={feature.id} feature={feature} index={index} />
              ))
            )}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  );
};

KanbanColumn.propTypes = {
  status: PropTypes.oneOf(['pending', 'in_progress', 'review', 'done']).isRequired,
  features: PropTypes.array,
};

export default KanbanColumn;
