/**
 * Author: rahn
 * Datum: 28.01.2026
 * Version: 1.1
 * Beschreibung: ProtocolFeed Komponente - Zeigt den Live-Protokoll-Feed aller Agent-Kommunikationen.
 *               Teil der Bibliothek-Ansicht. Keine Dummy-Daten.
 *               ÄNDERUNG 28.01.2026: Klappbare Einträge mit "Mehr anzeigen" Button statt Truncation.
 */

import React, { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  ChevronRight,
  ChevronDown,
  Brain
} from 'lucide-react';

// Farbpalette passend zu LibraryOffice
const COLORS = {
  primary: '#ec9c13',
  backgroundDark: '#1a1612',
  woodLight: '#3e3226',
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

/**
 * ProtocolFeed - Zeigt die Protokoll-Einträge eines Projekts
 *
 * @param {Array} entries - Protokoll-Einträge
 */
// ÄNDERUNG 28.01.2026: Zeichenlimit für Vorschau
const PREVIEW_LIMIT = 300;

const ProtocolFeed = ({ entries = [] }) => {
  const protocolRef = useRef(null);
  // ÄNDERUNG 28.01.2026: State für expandierte Einträge
  const [expandedEntries, setExpandedEntries] = useState({});

  const toggleEntry = (entryKey) => {
    setExpandedEntries(prev => ({
      ...prev,
      [entryKey]: !prev[entryKey]
    }));
  };

  // Auto-Scroll bei neuen Einträgen
  useEffect(() => {
    if (protocolRef.current) {
      protocolRef.current.scrollTop = protocolRef.current.scrollHeight;
    }
  }, [entries]);

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <div
        className="px-4 py-2 border-b flex items-center justify-between"
        style={{
          backgroundColor: COLORS.woodLight + '40',
          borderColor: COLORS.glassBorder
        }}
      >
        <span className="text-xs font-bold text-amber-200/70 uppercase tracking-wider flex items-center gap-2">
          <Brain size={14} style={{ color: COLORS.primary }} />
          Protokoll-Feed
        </span>
        <span className="text-[10px] text-amber-200/40 font-mono">
          {entries.length} Einträge
        </span>
      </div>

      <div
        ref={protocolRef}
        className="flex-1 overflow-y-auto p-4 space-y-2"
        style={{ scrollbarColor: `${COLORS.primary} ${COLORS.backgroundDark}` }}
      >
        {entries.length > 0 ? (
          entries.map((entry, i) => (
            <motion.div
              key={entry.id || i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.02, 0.5) }}
              className="p-3 rounded-lg border"
              style={{
                backgroundColor: COLORS.woodLight + '60',
                borderColor: COLORS.glassBorder
              }}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: COLORS.primary + '20',
                      color: COLORS.primary
                    }}
                  >
                    {entry.from_agent}
                  </span>
                  <ChevronRight size={10} className="text-amber-200/30" />
                  <span className="text-[10px] text-amber-200/50">
                    {entry.to_agent}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[9px] text-amber-200/30">
                  <span>Iter. {entry.iteration}</span>
                  <span>{formatTime(entry.timestamp)}</span>
                </div>
              </div>
              {(() => {
                const entryKey = entry.id || i;
                const isExpanded = expandedEntries[entryKey];
                const contentText = typeof entry.content === 'string'
                  ? entry.content
                  : JSON.stringify(entry.content);
                const isLong = contentText.length > PREVIEW_LIMIT;
                const displayText = isExpanded || !isLong
                  ? contentText
                  : contentText.substring(0, PREVIEW_LIMIT) + '...';

                return (
                  <>
                    <p className="text-xs text-amber-100/80 leading-relaxed whitespace-pre-wrap">
                      {displayText}
                    </p>
                    {isLong && (
                      <button
                        onClick={() => toggleEntry(entryKey)}
                        className="mt-1 text-[10px] flex items-center gap-1 transition-colors"
                        style={{ color: COLORS.primary }}
                      >
                        <ChevronDown
                          size={10}
                          className={`transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        />
                        {isExpanded ? 'Weniger anzeigen' : `Mehr anzeigen (${contentText.length} Zeichen)`}
                      </button>
                    )}
                  </>
                );
              })()}
              {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                <div className="mt-2 flex items-center gap-3 text-[9px] text-amber-200/30">
                  {entry.metadata.model && <span>Model: {entry.metadata.model}</span>}
                  {entry.metadata.tokens && <span>Tokens: {entry.metadata.tokens}</span>}
                  {entry.metadata.cost && <span>Kosten: {formatCost(entry.metadata.cost)}</span>}
                </div>
              )}
            </motion.div>
          ))
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-amber-200/30">
            <FileText size={48} />
            <span className="text-sm">Keine Protokoll-Einträge</span>
            <span className="text-xs">Einträge erscheinen hier sobald Agenten aktiv werden</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProtocolFeed;
