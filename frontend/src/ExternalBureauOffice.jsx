/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.1
 * Beschreibung: External Bureau UI - Matrix-inspirierte Stasis Pod Array
 *               Verwaltung externer Fachkraefte (CodeRabbit, EXA Search, etc.)
 * # ÄNDERUNG [01.02.2026]: Refaktor in Module – Styles/Komponenten/Hooks ausgelagert
 *               - constants/ExternalBureauConstants.js, styles/ExternalBureauStyles.js
 *               - components/SpecialistPod.jsx, FindingItem.jsx, hooks/useExternalBureau.js
 */

import React, { useState, useEffect } from 'react';

// Konstanten
import {
  MATRIX_GREEN,
  MATRIX_BG
} from './constants/ExternalBureauConstants';

// Styles
import {
  styles,
  initializePulseAnimation
} from './styles/ExternalBureauStyles';

// Komponenten
import SpecialistPod from './components/SpecialistPod';
import FindingItem from './components/FindingItem';

// Hook
import { useExternalBureau } from './hooks/useExternalBureau';

function ExternalBureauOffice({ onBack }) {
  const [filter, setFilter] = useState('all');
  const [selectedPod, setSelectedPod] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // API Hook
  const {
    specialists,
    findings,
    loading,
    error,
    searchLoading,
    handleActivate,
    handleDeactivate,
    handleSearch,
  } = useExternalBureau();

  // Pulse Animation initialisieren
  useEffect(() => {
    initializePulseAnimation();
  }, []);

  // Such-Handler
  const onSearchSubmit = async () => {
    try {
      const success = await handleSearch(searchQuery);
      if (success) {
        // Optionale Aktionen nach erfolgreicher Suche
      }
    } catch (err) {
      const ts = new Date().toISOString();
      console.error(`[${ts}] [ERROR] [onSearchSubmit] - Suchfehler: ${err?.message ?? err}`);
    }
  };

  const filteredSpecs = specialists.filter(s =>
    filter === 'all' || s.category === filter
  );

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingText}>INITIALISIERE EXTERNAL BUREAU...</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Scan-Linien Overlay */}
      <div style={styles.scanLines} />

      {/* Kopfzeile */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <button onClick={onBack} style={styles.backButton}>
            <span className="material-icons">arrow_back</span>
            ZURUECK
          </button>
        </div>
        <div style={styles.headerCenter}>
          <h1 style={styles.title}>EXTERNAL BUREAU</h1>
          <p style={styles.subtitle}>// STASIS POD ARRAY</p>
        </div>
        <div style={styles.headerRight}>
          <span style={styles.statusIndicator}>
            <span style={{ ...styles.statusDot, backgroundColor: specialists.length > 0 ? MATRIX_GREEN : '#555' }} />
            {specialists.filter(s => s.status === 'READY').length} ACTIVE
          </span>
        </div>
      </header>

      {/* Hauptbereich */}
      <div style={styles.mainContent}>
        {/* Linkes Panel – Spezialisten */}
        <div style={styles.leftPanel}>
          {/* Filter-Leiste */}
          <div style={styles.filterBar}>
            {['all', 'combat', 'intelligence', 'creative'].map(cat => (
              <button
                key={cat}
                onClick={() => setFilter(cat)}
                style={{
                  ...styles.filterButton,
                  background: filter === cat ? MATRIX_GREEN : 'transparent',
                  color: filter === cat ? MATRIX_BG : MATRIX_GREEN,
                }}
              >
                {cat === 'all' ? 'ALL UNITS' : cat.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Spezialisten-Gitter */}
          <div style={styles.podsGrid}>
            {filteredSpecs.map(spec => (
              <SpecialistPod
                key={spec.id}
                specialist={spec}
                isSelected={selectedPod === spec.id}
                onSelect={() => setSelectedPod(selectedPod === spec.id ? null : spec.id)}
                onActivate={() => handleActivate(spec.id)}
                onDeactivate={() => handleDeactivate(spec.id)}
              />
            ))}
            {filteredSpecs.length === 0 && (
              <div style={styles.emptyState}>
                <span className="material-icons" style={{ fontSize: '48px', opacity: 0.3 }}>
                  extension_off
                </span>
                <p>Keine Spezialisten in dieser Kategorie</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Console */}
        <div style={styles.rightPanel}>
          {/* Search Section */}
          <div style={styles.consoleSection}>
            <h3 style={styles.consoleSectionTitle}>
              <span className="material-icons" style={styles.sectionIcon}>search</span>
              INTELLIGENCE SEARCH
            </h3>
            <div style={styles.searchBox}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && onSearchSubmit()}
                placeholder="Suchanfrage eingeben..."
                style={styles.searchInput}
              />
              <button
                onClick={onSearchSubmit}
                disabled={searchLoading || !searchQuery.trim()}
                style={{
                  ...styles.searchButton,
                  opacity: searchLoading || !searchQuery.trim() ? 0.5 : 1
                }}
              >
                {searchLoading ? 'SCANNING...' : 'EXECUTE'}
              </button>
            </div>
          </div>

          {/* Findings-Bereich */}
          <div style={styles.consoleSection}>
            <h3 style={styles.consoleSectionTitle}>
              <span className="material-icons" style={styles.sectionIcon}>report</span>
              LATEST FINDINGS
              <span style={styles.badge}>{findings.length}</span>
            </h3>
            <div style={styles.findingsList}>
              {findings.slice(0, 10).map((finding, idx) => (
                <FindingItem key={idx} finding={finding} />
              ))}
              {findings.length === 0 && (
                <div style={styles.noFindings}>
                  Keine Findings vorhanden
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Fußzeile */}
      <footer style={styles.footer}>
        <span>SYS.VER.1.0.0</span>
        <span>EXTERNAL BUREAU // ACTIVE</span>
        <span>{new Date().toLocaleTimeString()}</span>
      </footer>
    </div>
  );
}

export default ExternalBureauOffice;
