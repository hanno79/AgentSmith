/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Finding Item Komponente für External Bureau.
 *               Extrahiert aus ExternalBureauOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import React from 'react';
import { SEVERITY_COLORS } from '../constants/ExternalBureauConstants';
import { findingStyles as styles } from '../styles/ExternalBureauStyles';

const FindingItem = ({ finding }) => {
  return (
    <div style={styles.findingItem}>
      <div style={styles.findingHeader}>
        <span style={{
          ...styles.severityBadge,
          backgroundColor: SEVERITY_COLORS[finding.severity] || '#888'
        }}>
          {finding.severity}
        </span>
        <span style={styles.findingSpecialist}>{finding.specialist}</span>
      </div>
      <p style={styles.findingDescription}>
        {finding.description?.substring(0, 150)}
        {finding.description?.length > 150 ? '...' : ''}
      </p>
      {finding.file && (
        <span style={styles.findingFile}>
          <span className="material-icons" style={{ fontSize: '12px' }}>folder</span>
          {finding.file}
          {finding.line > 0 && `:${finding.line}`}
        </span>
      )}
    </div>
  );
};

export default FindingItem;
