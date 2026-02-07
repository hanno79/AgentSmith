/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Styles für External Bureau UI.
 *               Extrahiert aus ExternalBureauOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import { MATRIX_GREEN, MATRIX_BG, MATRIX_BORDER } from '../constants/ExternalBureauConstants';

// Container & Layout Styles
export const containerStyles = {
  container: {
    minHeight: '100vh',
    background: MATRIX_BG,
    color: MATRIX_GREEN,
    fontFamily: "'Space Mono', 'Courier New', monospace",
    position: 'relative',
    overflow: 'hidden',
  },
  scanLines: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.1) 0px, rgba(0,0,0,0.1) 1px, transparent 1px, transparent 2px)',
    pointerEvents: 'none',
    zIndex: 1000,
  },
  loadingText: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    fontSize: '18px',
    letterSpacing: '4px',
  },
  mainContent: {
    display: 'flex',
    padding: '20px',
    gap: '20px',
    height: 'calc(100vh - 140px)',
  },
  leftPanel: {
    flex: 2,
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  rightPanel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    minWidth: '350px',
  },
};

// Header Styles
export const headerStyles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '20px 30px',
    borderBottom: `1px solid ${MATRIX_BORDER}`,
    background: 'rgba(10, 10, 10, 0.9)',
  },
  headerLeft: {},
  headerCenter: {
    textAlign: 'center',
  },
  headerRight: {},
  backButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'transparent',
    border: `1px solid ${MATRIX_BORDER}`,
    color: MATRIX_GREEN,
    padding: '8px 16px',
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: '12px',
    transition: 'all 0.3s',
  },
  title: {
    fontSize: '28px',
    fontWeight: 'normal',
    letterSpacing: '6px',
    margin: 0,
  },
  subtitle: {
    fontSize: '12px',
    opacity: 0.6,
    margin: '5px 0 0 0',
    letterSpacing: '3px',
  },
  statusIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
    letterSpacing: '2px',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    animation: 'pulse 2s infinite',
  },
};

// Filter & Grid Styles
export const filterStyles = {
  filterBar: {
    display: 'flex',
    gap: '10px',
  },
  filterButton: {
    padding: '10px 20px',
    border: `1px solid ${MATRIX_GREEN}`,
    fontFamily: 'inherit',
    fontSize: '11px',
    letterSpacing: '2px',
    cursor: 'pointer',
    transition: 'all 0.3s',
  },
  podsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '20px',
    overflow: 'auto',
    flex: 1,
  },
  emptyState: {
    gridColumn: '1 / -1',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px',
    opacity: 0.5,
  },
};

// Pod Styles
export const podStyles = {
  pod: {
    border: `1px solid ${MATRIX_BORDER}`,
    padding: '20px',
    cursor: 'pointer',
    transition: 'all 0.3s',
    position: 'relative',
  },
  podHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '15px',
  },
  statusBadge: {
    padding: '4px 8px',
    fontSize: '10px',
    letterSpacing: '1px',
    color: '#000',
    fontWeight: 'bold',
  },
  cooldownBadge: {
    background: '#ff9900',
    color: '#000',
    padding: '2px 6px',
    fontSize: '10px',
  },
  podName: {
    fontSize: '18px',
    fontWeight: 'normal',
    margin: '0 0 8px 0',
    letterSpacing: '2px',
  },
  podDescription: {
    fontSize: '11px',
    opacity: 0.6,
    margin: '0 0 15px 0',
    lineHeight: 1.4,
  },
  statsContainer: {
    marginBottom: '15px',
  },
  statRow: {
    marginBottom: '8px',
  },
  statLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    marginBottom: '4px',
    opacity: 0.8,
  },
  statBarBg: {
    background: '#222',
    height: '4px',
    borderRadius: '2px',
  },
  statBarFill: {
    height: '100%',
    background: MATRIX_GREEN,
    borderRadius: '2px',
    transition: 'width 0.3s',
  },
  runCount: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '11px',
    opacity: 0.6,
    marginBottom: '10px',
  },
  actionButton: {
    width: '100%',
    padding: '12px',
    border: 'none',
    fontFamily: 'inherit',
    fontSize: '12px',
    fontWeight: 'bold',
    letterSpacing: '2px',
    color: '#000',
    marginTop: '10px',
    transition: 'all 0.3s',
  },
  unavailableWarning: {
    fontSize: '10px',
    color: '#ff6600',
    marginTop: '10px',
    textAlign: 'center',
  },
};

// Console Styles
export const consoleStyles = {
  consoleSection: {
    background: 'rgba(17, 17, 17, 0.8)',
    border: `1px solid ${MATRIX_BORDER}`,
    padding: '20px',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  consoleSectionTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '13px',
    fontWeight: 'normal',
    letterSpacing: '2px',
    marginBottom: '15px',
    paddingBottom: '10px',
    borderBottom: `1px solid ${MATRIX_BORDER}`,
  },
  sectionIcon: {
    fontSize: '18px',
    opacity: 0.8,
  },
  badge: {
    background: MATRIX_GREEN,
    color: '#000',
    padding: '2px 8px',
    fontSize: '10px',
    marginLeft: 'auto',
  },
  searchBox: {
    display: 'flex',
    gap: '10px',
  },
  searchInput: {
    flex: 1,
    background: 'rgba(0,0,0,0.5)',
    border: `1px solid ${MATRIX_BORDER}`,
    color: MATRIX_GREEN,
    padding: '12px',
    fontFamily: 'inherit',
    fontSize: '12px',
  },
  searchButton: {
    background: MATRIX_GREEN,
    border: 'none',
    color: '#000',
    padding: '12px 20px',
    fontFamily: 'inherit',
    fontSize: '11px',
    fontWeight: 'bold',
    letterSpacing: '1px',
    cursor: 'pointer',
  },
};

// Finding Styles
export const findingStyles = {
  findingsList: {
    flex: 1,
    overflow: 'auto',
  },
  findingItem: {
    padding: '12px',
    borderBottom: `1px solid ${MATRIX_BORDER}`,
  },
  findingHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '8px',
  },
  severityBadge: {
    padding: '2px 6px',
    fontSize: '9px',
    color: '#000',
    fontWeight: 'bold',
  },
  findingSpecialist: {
    fontSize: '10px',
    opacity: 0.6,
  },
  findingDescription: {
    fontSize: '11px',
    lineHeight: 1.4,
    margin: '0 0 8px 0',
    opacity: 0.9,
  },
  findingFile: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '10px',
    opacity: 0.5,
  },
  noFindings: {
    padding: '20px',
    textAlign: 'center',
    opacity: 0.5,
    fontSize: '12px',
  },
};

// Footer Styles
export const footerStyles = {
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '10px 30px',
    borderTop: `1px solid ${MATRIX_BORDER}`,
    fontSize: '10px',
    opacity: 0.5,
    letterSpacing: '2px',
  },
};

// Combined styles for backwards compatibility
export const styles = {
  ...containerStyles,
  ...headerStyles,
  ...filterStyles,
  ...podStyles,
  ...consoleStyles,
  ...findingStyles,
  ...footerStyles,
};

// CSS Animation für Pulse-Effekt initialisieren
export const initializePulseAnimation = () => {
  if (typeof document !== 'undefined') {
    const existingStyle = document.getElementById('external-bureau-pulse');
    if (!existingStyle) {
      const styleSheet = document.createElement('style');
      styleSheet.id = 'external-bureau-pulse';
      styleSheet.textContent = `
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `;
      document.head.appendChild(styleSheet);
    }
  }
};
