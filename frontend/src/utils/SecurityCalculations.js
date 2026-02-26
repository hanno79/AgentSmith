/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Security Office Berechnungs-Funktionen.
 *               Extrahiert aus SecurityOffice.jsx (Regel 1: Max 500 Zeilen)
 */

const asVulnerabilityArray = (value) => (Array.isArray(value) ? value : []);

/**
 * Berechnet Threat Intelligence Statistiken basierend auf Vulnerabilities.
 */
export const getThreatIntel = ({
  vulnerabilities = [],
  overallStatus = '',
  scannedFiles = 0,
  hasData = false,
  isScanning = false
} = {}) => {
  const vulnerabilityList = asVulnerabilityArray(vulnerabilities);
  const effectiveHasData = Boolean(hasData) || overallStatus !== '' || vulnerabilityList.length > 0;

  if (!effectiveHasData) {
    return { activeThreats: 0, suspicious: 0, secured: 0, scanning: isScanning ? 1 : 0 };
  }
  const critical = vulnerabilityList.filter(v => v.severity === 'critical').length;
  const high = vulnerabilityList.filter(v => v.severity === 'high').length;
  const medium = vulnerabilityList.filter(v => v.severity === 'medium').length;
  const low = vulnerabilityList.filter(v => v.severity === 'low').length;

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
export const getMitigationTargets = ({
  vulnerabilities = [],
  hasData = false
} = {}) => {
  const vulnerabilityList = asVulnerabilityArray(vulnerabilities);
  const effectiveHasData = Boolean(hasData) || vulnerabilityList.length > 0;
  if (!effectiveHasData || vulnerabilityList.length === 0) return [];

  const groups = {
    critical: { name: 'Critical Issues', patches: 0, critical: true },
    high: { name: 'High Priority', patches: 0, critical: true },
    medium: { name: 'Medium Priority', patches: 0, critical: false },
    low: { name: 'Low Priority', patches: 0, critical: false }
  };

  vulnerabilityList.forEach(v => {
    if (groups[v.severity]) {
      groups[v.severity].patches++;
    }
  });

  return Object.values(groups).filter(g => g.patches > 0);
};

/**
 * Berechnet DEFCON-Level basierend auf Vulnerabilities.
 */
export const getDefconLevel = ({
  vulnerabilities = [],
  hasData = false
} = {}) => {
  const vulnerabilityList = asVulnerabilityArray(vulnerabilities);
  const effectiveHasData = Boolean(hasData) || vulnerabilityList.length > 0;
  if (!effectiveHasData) return { level: 5, text: 'STANDBY', color: 'slate', description: 'Warte auf Analyse...' };

  const critical = vulnerabilityList.filter(v => v.severity === 'critical').length;
  const high = vulnerabilityList.filter(v => v.severity === 'high').length;
  const medium = vulnerabilityList.filter(v => v.severity === 'medium').length;

  if (critical > 0) return { level: 1, text: 'CRITICAL', color: 'red', description: 'Kritische Sicherheitslücken!' };
  if (high > 0) return { level: 2, text: 'HIGH ALERT', color: 'orange', description: 'Hohe Bedrohungsstufe' };
  if (medium > 0) return { level: 3, text: 'ELEVATED', color: 'amber', description: 'Erhöhte Wachsamkeit' };
  if (vulnerabilityList.length > 0) return { level: 4, text: 'GUARDED', color: 'yellow', description: 'Geringe Bedrohungen' };
  return { level: 5, text: 'SECURE', color: 'green', description: 'System sicher' };
};

/**
 * Berechnet Node-Security Status basierend auf Overall-Status.
 */
export const getNodeStatus = ({
  overallStatus = '',
  hasData = false
} = {}) => {
  const effectiveHasData = Boolean(hasData) || overallStatus !== '';
  if (!effectiveHasData) {
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
    red: {
      bg: 'bg-red-950/30',
      border: 'border-red-500/30',
      text: 'text-red-400',
      icon: 'text-red-400',
      ping: 'bg-red-400',
      dot: 'bg-red-500'
    },
    orange: {
      bg: 'bg-orange-950/30',
      border: 'border-orange-500/30',
      text: 'text-orange-400',
      icon: 'text-orange-400',
      ping: 'bg-orange-400',
      dot: 'bg-orange-500'
    },
    amber: {
      bg: 'bg-amber-950/30',
      border: 'border-amber-500/30',
      text: 'text-amber-400',
      icon: 'text-amber-400',
      ping: 'bg-amber-400',
      dot: 'bg-amber-500'
    },
    yellow: {
      bg: 'bg-yellow-950/30',
      border: 'border-yellow-500/30',
      text: 'text-yellow-400',
      icon: 'text-yellow-400',
      ping: 'bg-yellow-400',
      dot: 'bg-yellow-500'
    },
    green: {
      bg: 'bg-green-950/30',
      border: 'border-green-500/30',
      text: 'text-green-400',
      icon: 'text-green-400',
      ping: 'bg-green-400',
      dot: 'bg-green-500'
    },
    slate: {
      bg: 'bg-slate-800/50',
      border: 'border-slate-500/30',
      text: 'text-slate-400',
      icon: 'text-slate-400',
      ping: 'bg-slate-400',
      dot: 'bg-slate-500'
    }
  };
  return colorMap[color]?.[type] || colorMap.slate[type];
};
