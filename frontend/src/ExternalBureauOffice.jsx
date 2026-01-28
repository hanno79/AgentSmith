/**
 * Author: rahn
 * Datum: 28.01.2026
 * Version: 1.0
 * Beschreibung: External Bureau UI - Matrix-inspirierte Stasis Pod Array
 *               Verwaltung externer Fachkraefte (CodeRabbit, EXA Search, etc.)
 */

import React, { useState, useEffect, useCallback } from 'react';

// Matrix-Design Farben
const MATRIX_GREEN = '#0df259';
const MATRIX_GREEN_DIM = 'rgba(13, 242, 89, 0.5)';
const MATRIX_BG = '#0a0a0a';
const MATRIX_BG_LIGHT = '#111';
const MATRIX_BORDER = 'rgba(13, 242, 89, 0.3)';

// Status-Farben
const STATUS_COLORS = {
    'DORMANT': '#555',
    'READY': MATRIX_GREEN,
    'COMPILING': '#ffcc00',
    'ERROR': '#ff3333',
    'RATE_LIMITED': '#ff9900'
};

// Kategorie-Icons
const CATEGORY_ICONS = {
    'combat': 'shield',
    'intelligence': 'search',
    'creative': 'palette'
};

// API Base URL
const API_BASE = 'http://localhost:8000';

function ExternalBureauOffice({ onBack }) {
    const [specialists, setSpecialists] = useState([]);
    const [filter, setFilter] = useState('all');
    const [selectedPod, setSelectedPod] = useState(null);
    const [findings, setFindings] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchLoading, setSearchLoading] = useState(false);

    // Lade Specialists beim Mount
    useEffect(() => {
        fetchSpecialists();
        fetchFindings();
        const interval = setInterval(fetchSpecialists, 5000); // Refresh alle 5s
        return () => clearInterval(interval);
    }, []);

    const fetchSpecialists = async () => {
        try {
            const response = await fetch(`${API_BASE}/external-bureau/specialists`);
            const data = await response.json();
            setSpecialists(data.specialists || []);
            setLoading(false);
        } catch (err) {
            console.error('Fehler beim Laden der Specialists:', err);
            setError('Verbindung zum Server fehlgeschlagen');
            setLoading(false);
        }
    };

    const fetchFindings = async () => {
        try {
            const response = await fetch(`${API_BASE}/external-bureau/findings`);
            const data = await response.json();
            setFindings(data.findings || []);
        } catch (err) {
            console.error('Fehler beim Laden der Findings:', err);
        }
    };

    const handleActivate = async (specialistId) => {
        try {
            const response = await fetch(`${API_BASE}/external-bureau/specialists/${specialistId}/activate`, {
                method: 'POST'
            });
            if (response.ok) {
                fetchSpecialists();
            } else {
                const data = await response.json();
                alert(data.detail || 'Aktivierung fehlgeschlagen');
            }
        } catch (err) {
            console.error('Aktivierung fehlgeschlagen:', err);
        }
    };

    const handleDeactivate = async (specialistId) => {
        try {
            const response = await fetch(`${API_BASE}/external-bureau/specialists/${specialistId}/deactivate`, {
                method: 'POST'
            });
            if (response.ok) {
                fetchSpecialists();
            }
        } catch (err) {
            console.error('Deaktivierung fehlgeschlagen:', err);
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;
        setSearchLoading(true);
        try {
            const response = await fetch(`${API_BASE}/external-bureau/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: searchQuery, num_results: 10 })
            });
            const data = await response.json();
            if (data.success) {
                fetchFindings(); // Refresh Findings
            } else {
                alert(data.error || 'Suche fehlgeschlagen');
            }
        } catch (err) {
            console.error('Suche fehlgeschlagen:', err);
        } finally {
            setSearchLoading(false);
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
            {/* Scan Lines Overlay */}
            <div style={styles.scanLines} />

            {/* Header */}
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
                        <span style={{...styles.statusDot, backgroundColor: specialists.length > 0 ? MATRIX_GREEN : '#555'}} />
                        {specialists.filter(s => s.status === 'READY').length} ACTIVE
                    </span>
                </div>
            </header>

            {/* Main Content */}
            <div style={styles.mainContent}>
                {/* Left Panel - Specialists */}
                <div style={styles.leftPanel}>
                    {/* Filter Buttons */}
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

                    {/* Specialists Grid */}
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
                                <span className="material-icons" style={{fontSize: '48px', opacity: 0.3}}>
                                    extension_off
                                </span>
                                <p>Keine Specialists in dieser Kategorie</p>
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
                                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                                placeholder="Suchanfrage eingeben..."
                                style={styles.searchInput}
                            />
                            <button
                                onClick={handleSearch}
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

                    {/* Findings Section */}
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

            {/* Footer */}
            <footer style={styles.footer}>
                <span>SYS.VER.1.0.0</span>
                <span>EXTERNAL BUREAU // ACTIVE</span>
                <span>{new Date().toLocaleTimeString()}</span>
            </footer>
        </div>
    );
}

// Specialist Pod Komponente
function SpecialistPod({ specialist, isSelected, onSelect, onActivate, onDeactivate }) {
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
                <span style={{...styles.statusBadge, backgroundColor: statusColor}}>
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
                <span className="material-icons" style={{fontSize: '14px'}}>play_arrow</span>
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
}

// Finding Item Komponente
function FindingItem({ finding }) {
    const severityColors = {
        'CRITICAL': '#ff0000',
        'HIGH': '#ff6600',
        'MEDIUM': '#ffcc00',
        'LOW': '#00ccff',
        'INFO': '#888'
    };

    return (
        <div style={styles.findingItem}>
            <div style={styles.findingHeader}>
                <span style={{
                    ...styles.severityBadge,
                    backgroundColor: severityColors[finding.severity] || '#888'
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
                    <span className="material-icons" style={{fontSize: '12px'}}>folder</span>
                    {finding.file}
                    {finding.line > 0 && `:${finding.line}`}
                </span>
            )}
        </div>
    );
}

// Styles
const styles = {
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
    emptyState: {
        gridColumn: '1 / -1',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px',
        opacity: 0.5,
    },
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

// CSS Animation fuer Pulse-Effekt
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
`;
document.head.appendChild(styleSheet);

export default ExternalBureauOffice;
