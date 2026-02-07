/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Security Office Berechnungs-Funktionen.
 *               Extrahiert aus SecurityOffice.jsx (Regel 1: Max 500 Zeilen)
 */

/**
 * Berechnet Threat Intelligence Statistiken basierend auf Vulnerabilities.
 */
export const getThreatIntel = (vulnerabilities, overallStatus, scannedFiles, hasData, isScanning) => {
  if (!hasData) {
    return { activeThreats: 0, suspicious: 0, secured: 0, scanning: isScanning ? 1 : 0 };
  }
  const critical = vulnerabilities.filter(v => v.severity === 'critical').length;
  const high = vulnerabilities.filter(v => v.severity === 'high').length;
  const medium = vulnerabilities.filter(v => v.severity === 'medium').length;
  const low = vulnerabilities.filter(v => v.severity === 'low').length;

  return {
    activeThreats: critical + high,
    suspicious: medium,
    secured: overallStatus === 'SECURE' ? Math.max(scannedFiles, 1) : low,
    scanning: isScanning ? 1 : 0
  };
};

/**
 * Erstellt Defense-Log Einträge aus Logs.
 */
export const getDefenseEntries = (logs, hasData) => {
  if (logs.length === 0 && !hasData) return [];

  return logs.slice(-5).map((log) => {
    const ts = log.timestamp ? (typeof log.timestamp === 'string' ? new Date(log.timestamp) : log.timestamp) : new Date();
    const timeStr = (ts instanceof Date && !isNaN(ts.getTime()))
      ? ts.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return {
      time: timeStr,
      type: log.event === 'Error' ? 'alert' :
            log.event === 'Warning' ? 'warning' :
            log.event === 'Result' ? 'success' : 'info',
      message: log.message
    };
  });
};

/**
 * Gruppiert Vulnerabilities nach Severity für Mitigation-Targets.
 */
export const getMitigationTargets = (vulnerabilities, hasData) => {
  if (!hasData || vulnerabilities.length === 0) return [];

  const groups = {
    critical: { name: 'Critical Issues', patches: 0, critical: true },
    high: { name: 'High Priority', patches: 0, critical: true },
    medium: { name: 'Medium Priority', patches: 0, critical: false },
    low: { name: 'Low Priority', patches: 0, critical: false }
  };

  vulnerabilities.forEach(v => {
    if (groups[v.severity]) {
      groups[v.severity].patches++;
    }
  });

  return Object.values(groups).filter(g => g.patches > 0);
};

/**
 * Berechnet DEFCON-Level basierend auf Vulnerabilities.
 */
export const getDefconLevel = (vulnerabilities, hasData) => {
  if (!hasData) return { level: 5, text: 'STANDBY', color: 'slate', description: 'Warte auf Analyse...' };

  const critical = vulnerabilities.filter(v => v.severity === 'critical').length;
  const high = vulnerabilities.filter(v => v.severity === 'high').length;
  const medium = vulnerabilities.filter(v => v.severity === 'medium').length;

  if (critical > 0) return { level: 1, text: 'CRITICAL', color: 'red', description: 'Kritische Sicherheitslücken!' };
  if (high > 0) return { level: 2, text: 'HIGH ALERT', color: 'orange', description: 'Hohe Bedrohungsstufe' };
  if (medium > 0) return { level: 3, text: 'ELEVATED', color: 'amber', description: 'Erhöhte Wachsamkeit' };
  if (vulnerabilities.length > 0) return { level: 4, text: 'GUARDED', color: 'yellow', description: 'Geringe Bedrohungen' };
  return { level: 5, text: 'SECURE', color: 'green', description: 'System sicher' };
};

/**
 * Berechnet Node-Security Status basierend auf Overall-Status.
 */
export const getNodeStatus = (overallStatus, hasData) => {
  if (!hasData) {
    return [
      { name: 'DB', health: 0, status: 'unknown' },
      { name: 'API', health: 0, status: 'unknown' },
      { name: 'WEB', health: 0, status: 'unknown' },
      { name: 'CDN', health: 0, status: 'unknown' },
    ];
  }

  // Basiere Health auf overallStatus
  const baseHealth = overallStatus === 'SECURE' ? 100 :
                     overallStatus === 'WARNING' ? 85 :
                     overallStatus === 'CRITICAL' ? 60 : 70;

  return [
    { name: 'DB', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
    { name: 'API', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
    { name: 'WEB', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
    { name: 'CDN', health: Math.min(100, baseHealth + (Math.random() * 10 - 5)), status: overallStatus === 'SECURE' ? 'secured' : 'warning' },
  ];
};

/**
 * Gibt die passende Farb-Klasse für DEFCON-Level zurück.
 */
export const getDefconColorClass = (color, type = 'bg') => {
  const colorMap = {
    red: { bg: 'bg-red-950/30', border: 'border-red-500/30', text: 'text-red-400' },
    orange: { bg: 'bg-orange-950/30', border: 'border-orange-500/30', text: 'text-orange-400' },
    amber: { bg: 'bg-amber-950/30', border: 'border-amber-500/30', text: 'text-amber-400' },
    yellow: { bg: 'bg-yellow-950/30', border: 'border-yellow-500/30', text: 'text-yellow-400' },
    green: { bg: 'bg-green-950/30', border: 'border-green-500/30', text: 'text-green-400' },
    slate: { bg: 'bg-slate-800/50', border: 'border-slate-500/30', text: 'text-slate-400' }
  };
  return colorMap[color]?.[type] || colorMap.slate[type];
};
