/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Specialist Pod Komponente für External Bureau.
 *               Extrahiert aus ExternalBureauOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import React from 'react';
import { MATRIX_GREEN, MATRIX_BORDER, STATUS_COLORS } from '../constants/ExternalBureauConstants';
import { podStyles as styles } from '../styles/ExternalBureauStyles';

const SpecialistPod = ({
  specialist,
  isSelected,
  onSelect,
  onActivate,
  onDeactivate
}) => {
  const { name, status, stats, available, description, cooldown_remaining, run_count } = specialist;
  const statusColor = STATUS_COLORS[status] || '#555';

  return (
    <div
      onClick={onSelect}
      style={{
        ...styles.pod,
        borderColor: isSelected ? MATRIX_GREEN : MATRIX_BORDER,
        background: isSelected ? 'rgba(13, 242, 89, 0.05)' : 'rgba(255,255,255,0.02)',
      }}
    >
      {/* Status Header */}
      <div style={styles.podHeader}>
        <span style={{ ...styles.statusBadge, backgroundColor: statusColor }}>
          {status}
        </span>
        {cooldown_remaining > 0 && (
          <span style={styles.cooldownBadge}>
            {cooldown_remaining}s
          </span>
        )}
      </div>

      {/* Name */}
      <h3 style={styles.podName}>{name}</h3>
      {description && <p style={styles.podDescription}>{description}</p>}

      {/* Stats Bars */}
      <div style={styles.statsContainer}>
        {Object.entries(stats || {}).map(([key, value]) => (
          <div key={key} style={styles.statRow}>
            <div style={styles.statLabel}>
              <span>{key}</span>
              <span>{value}</span>
            </div>
            <div style={styles.statBarBg}>
              <div style={{
                ...styles.statBarFill,
                width: `${value}%`,
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* Run Count */}
      <div style={styles.runCount}>
        <span className="material-icons" style={{ fontSize: '14px' }}>play_arrow</span>
        {run_count || 0} Runs
      </div>

      {/* Action Button */}
      {isSelected && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            status === 'READY' ? onDeactivate() : onActivate();
          }}
          disabled={!available && status !== 'READY'}
          style={{
            ...styles.actionButton,
            background: status === 'READY' ? '#ff3333' : MATRIX_GREEN,
            opacity: (!available && status !== 'READY') ? 0.5 : 1,
            cursor: (!available && status !== 'READY') ? 'not-allowed' : 'pointer',
          }}
        >
          {status === 'READY' ? 'DEACTIVATE' : 'ACTIVATE'}
        </button>
      )}

      {/* Availability Warning */}
      {!available && status !== 'READY' && (
        <p style={styles.unavailableWarning}>
          CLI/API nicht konfiguriert
        </p>
      )}
    </div>
  );
};

export default SpecialistPod;
