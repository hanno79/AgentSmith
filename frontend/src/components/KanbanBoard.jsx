/**
 * Author: rahn
 * Datum: 13.02.2026
 * Version: 1.0
 * Beschreibung: Kanban-Board Haupt-Container fuer Feature-Tracking.
 *               4 Spalten: Ausstehend | In Arbeit | Review | Fertig
 *               Drag-and-Drop via @hello-pangea/dnd (bereits installiert).
 *               Echtzeit-Updates via WebSocket (FeatureUpdate Events).
 *               Progress-Bar oben mit Fortschrittsanzeige.
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { DragDropContext } from '@hello-pangea/dnd';
import { BarChart3, RefreshCw, PartyPopper } from 'lucide-react';
import KanbanColumn from './KanbanColumn';
import { API_BASE } from '../constants/config';

// AENDERUNG 13.02.2026: Spalten-Reihenfolge
const COLUMNS = ['pending', 'in_progress', 'review', 'done'];

const KanbanBoard = ({ runId, featureData, onFeatureDataChange }) => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ pending: 0, in_progress: 0, review: 0, done: 0, failed: 0, total: 0, percentage: 0 });

  // Features nach Status gruppieren
  const grouped = {
    pending: [],
    in_progress: [],
    review: [],
    done: [],
  };

  if (Array.isArray(featureData)) {
    for (const f of featureData) {
      const s = f.status || 'pending';
      if (grouped[s]) {
        grouped[s].push(f);
      } else if (s === 'failed') {
        // Failed Features in "Ausstehend" anzeigen mit Fehler-Markierung
        grouped.pending.push(f);
      }
    }
  }

  // Stats berechnen
  useEffect(() => {
    if (!Array.isArray(featureData) || featureData.length === 0) return;
    const newStats = { pending: 0, in_progress: 0, review: 0, done: 0, failed: 0, total: featureData.length, percentage: 0 };
    for (const f of featureData) {
      const s = f.status || 'pending';
      if (newStats[s] !== undefined) newStats[s]++;
    }
    newStats.percentage = newStats.total > 0 ? Math.round((newStats.done / newStats.total) * 100) : 0;
    setStats(newStats);
  }, [featureData]);

  // Initiales Laden der Features
  const fetchFeatures = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/features/${runId}`);
      const data = await res.json();
      if (data.status === 'ok' && Array.isArray(data.features)) {
        onFeatureDataChange(data.features);
      }
    } catch (err) {
      console.warn('Feature-Fetch fehlgeschlagen:', err);
    } finally {
      setLoading(false);
    }
  }, [runId, onFeatureDataChange]);

  useEffect(() => {
    fetchFeatures();
  }, [fetchFeatures]);

  // Drag-and-Drop Handler
  const handleDragEnd = useCallback(async (result) => {
    if (!result.destination) return;

    const { source, destination, draggableId } = result;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    const featureId = parseInt(draggableId, 10);
    const newStatus = destination.droppableId;

    // Optimistisches Update
    const updatedFeatures = (featureData || []).map(f =>
      f.id === featureId ? { ...f, status: newStatus } : f
    );
    onFeatureDataChange(updatedFeatures);

    // Backend-Update
    try {
      await fetch(`${API_BASE}/features/${featureId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
    } catch (err) {
      console.warn('Feature-Status-Update fehlgeschlagen:', err);
      // Rollback bei Fehler
      fetchFeatures();
    }
  }, [featureData, onFeatureDataChange, fetchFeatures]);

  // Kein runId = keine Features
  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Kein aktiver Run - starte ein Projekt um Features zu sehen
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      {/* Header mit Progress-Bar */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-gray-200">Feature-Board</h2>
        </div>

        {/* Progress-Bar */}
        <div className="flex-1 max-w-md">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden relative">
              <div
                className={`h-full bg-gradient-to-r from-cyan-500 to-green-500 rounded-full transition-all duration-500 ${stats.percentage === 100 ? 'animate-pulse' : ''}`}
                style={{ width: `${stats.percentage}%` }}
              />
              {/* AENDERUNG 14.02.2026: Glow bei 100% */}
              {stats.percentage === 100 && (
                <div className="absolute inset-0 rounded-full" style={{ boxShadow: '0 0 12px rgba(34, 197, 94, 0.5)' }} />
              )}
            </div>
            <span className="text-sm font-mono text-gray-400 min-w-[3rem] text-right">
              {stats.percentage}%
            </span>
          </div>
        </div>

        {/* AENDERUNG 14.02.2026: 100%-Celebration Badge */}
        {stats.percentage === 100 && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 12 }}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-green-500/20 border border-green-500/30 text-green-400 text-xs font-medium"
          >
            <PartyPopper className="w-3.5 h-3.5" />
            Alle Features abgeschlossen!
          </motion.div>
        )}

        {/* Stats-Badges */}
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded bg-gray-700/50 text-gray-400">{stats.pending} Offen</span>
          <span className="px-2 py-1 rounded bg-blue-500/20 text-blue-400">{stats.in_progress} Aktiv</span>
          <span className="px-2 py-1 rounded bg-yellow-500/20 text-yellow-400">{stats.review} Review</span>
          <span className="px-2 py-1 rounded bg-green-500/20 text-green-400">{stats.done} Fertig</span>
          {stats.failed > 0 && (
            <span className="px-2 py-1 rounded bg-red-500/20 text-red-400">{stats.failed} Fehler</span>
          )}
        </div>

        {/* Refresh */}
        <button
          onClick={fetchFeatures}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          title="Features neu laden"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Kanban-Spalten */}
      <DragDropContext onDragEnd={handleDragEnd}>
        <div className="flex gap-3 flex-1 overflow-x-auto pb-2">
          {COLUMNS.map(status => (
            <KanbanColumn
              key={status}
              status={status}
              features={grouped[status]}
            />
          ))}
        </div>
      </DragDropContext>
    </div>
  );
};

KanbanBoard.propTypes = {
  runId: PropTypes.string,
  featureData: PropTypes.array,
  onFeatureDataChange: PropTypes.func.isRequired,
};

KanbanBoard.defaultProps = {
  featureData: [],
  runId: null,
};

export default KanbanBoard;
