/**
 * Author: rahn
 * Datum: 13.02.2026
 * Version: 1.0
 * Beschreibung: Feature-Karte fuer das Kanban-Board.
 *               Zeigt Titel, Beschreibung, Priority-Badge, Agent-Avatar und Status.
 *               Klick expandiert Details (Dateipfad, Fehler, Iterationen).
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { Draggable } from '@hello-pangea/dnd';
import { ChevronDown, ChevronUp, AlertCircle, GitBranch, FileCode } from 'lucide-react';
import { COLORS } from '../constants/config';

// AENDERUNG 13.02.2026: Priority → Farb-Mapping
const PRIORITY_COLORS = {
  1: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Kritisch' },
  2: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Hoch' },
  3: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Mittel' },
  4: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Normal' },
  5: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'Normal' },
};

// AENDERUNG 13.02.2026: Kategorie → Icon-Mapping
const CATEGORY_ICONS = {
  feature: '⚡',
  file: '📄',
  config: '⚙️',
  test: '🧪',
};

const FeatureCard = ({ feature, index }) => {
  const [expanded, setExpanded] = useState(false);

  const priority = feature.priority || 5;
  const prioConfig = PRIORITY_COLORS[Math.min(priority, 5)] || PRIORITY_COLORS[5];
  const categoryIcon = CATEGORY_ICONS[feature.category] || '📄';
  const hasDeps = Array.isArray(feature.depends_on) && feature.depends_on.length > 0;
  const hasError = feature.status === 'failed' && feature.error_message;
  const isActive = feature.status === 'in_progress';

  return (
    <Draggable draggableId={String(feature.id)} index={index}>
      {(provided, snapshot) => (
        <motion.div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className={`
            relative rounded-lg border p-3 mb-2 cursor-grab
            transition-all duration-200
            ${snapshot.isDragging
              ? 'border-cyan-400/60 bg-gray-800/90 shadow-lg shadow-cyan-500/20 scale-[1.02]'
              : 'border-gray-700/50 bg-gray-800/60 hover:border-gray-600/70'}
            ${hasError ? 'border-red-500/40' : ''}
            ${isActive ? 'ring-1 ring-blue-500/30' : ''}
          `}
          onClick={() => setExpanded(!expanded)}
        >
          {/* Puls-Animation bei in_progress */}
          {isActive && (
            <div className="absolute top-2 right-2 h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
            </div>
          )}

          {/* Header: Icon + Titel */}
          <div className="flex items-start gap-2">
            <span className="text-sm mt-0.5 shrink-0">{categoryIcon}</span>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-gray-200 truncate">
                {feature.title}
              </h4>
              {feature.description && !expanded && (
                <p className="text-xs text-gray-500 truncate mt-0.5">
                  {feature.description}
                </p>
              )}
            </div>
          </div>

          {/* Badges */}
          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
            {/* Priority Badge */}
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${prioConfig.bg} ${prioConfig.text}`}>
              P{priority}
            </span>

            {/* Agent Badge */}
            {feature.assigned_agent && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400">
                {feature.assigned_agent}
              </span>
            )}

            {/* Dependency Badge */}
            {hasDeps && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 flex items-center gap-0.5">
                <GitBranch className="w-2.5 h-2.5" />
                {feature.depends_on.length}
              </span>
            )}

            {/* Iterations Badge */}
            {feature.iteration_count > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-600/40 text-gray-400">
                ×{feature.iteration_count}
              </span>
            )}

            {/* Expand/Collapse Icon */}
            <button className="ml-auto text-gray-500 hover:text-gray-300" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          {/* Expandierte Details */}
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              className="mt-2 pt-2 border-t border-gray-700/50 text-xs space-y-1"
            >
              {feature.description && (
                <p className="text-gray-400">{feature.description}</p>
              )}

              {feature.file_path && (
                <div className="flex items-center gap-1 text-gray-500">
                  <FileCode className="w-3 h-3" />
                  <span className="font-mono">{feature.file_path}</span>
                </div>
              )}

              {feature.estimated_lines > 0 && (
                <div className="text-gray-500">
                  Geschaetzt: ~{feature.estimated_lines} Zeilen
                  {feature.actual_lines > 0 && ` | Tatsaechlich: ${feature.actual_lines}`}
                </div>
              )}

              {hasDeps && (
                <div className="text-gray-500">
                  Abhaengig von: {feature.depends_on.join(', ')}
                </div>
              )}

              {hasError && (
                <div className="flex items-start gap-1 text-red-400 bg-red-500/10 rounded p-1.5">
                  <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                  <span>{feature.error_message}</span>
                </div>
              )}
            </motion.div>
          )}
        </motion.div>
      )}
    </Draggable>
  );
};

FeatureCard.propTypes = {
  feature: PropTypes.shape({
    id: PropTypes.number.isRequired,
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    file_path: PropTypes.string,
    category: PropTypes.string,
    status: PropTypes.string,
    priority: PropTypes.number,
    depends_on: PropTypes.array,
    assigned_agent: PropTypes.string,
    estimated_lines: PropTypes.number,
    actual_lines: PropTypes.number,
    error_message: PropTypes.string,
    iteration_count: PropTypes.number,
  }).isRequired,
  index: PropTypes.number.isRequired,
};

export default FeatureCard;
