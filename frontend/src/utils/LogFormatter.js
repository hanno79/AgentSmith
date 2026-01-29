/**
 * Author: rahn
 * Datum: 28.01.2026
 * Version: 1.4
 * Beschreibung: Log-Formatierung fuer benutzerfreundliche Ausgabe im Global Output Loop.
 *               Wandelt JSON-Events in Klartext-Zusammenfassungen um.
 *               AENDERUNG 25.01.2026: Researcher zeigt status-basierten Titel.
 *               AENDERUNG 25.01.2026: Text-Truncation mit "..." am Ende.
 *               AENDERUNG 25.01.2026: Researcher ohne Query-Duplikat bei Abschluss.
 *               AENDERUNG 28.01.2026: Robuste Message-Typen-Behandlung fuer Session-Recovery.
 */

/**
 * Kuerzt Text auf maxLength und fuegt "..." hinzu wenn gekuerzt.
 * Versucht an Wortgrenzen zu kuerzen.
 * AENDERUNG 25.01.2026: Limits stark erhoeht - User muss Inhalt verstehen koennen.
 */
const truncateText = (text, maxLength = 500) => {
  if (!text || text.length <= maxLength) return text;

  // Kuerze auf maxLength - 3 (fuer "...")
  let truncated = text.substring(0, maxLength - 3);

  // Versuche an Wortgrenze zu kuerzen (letztes Leerzeichen finden)
  const lastSpace = truncated.lastIndexOf(' ');
  if (lastSpace > maxLength * 0.7) {
    truncated = truncated.substring(0, lastSpace);
  }

  return truncated + '...';
};

// Events die in der Benutzer-Ansicht ausgeblendet werden (technische/interne Events)
export const HIDDEN_USER_EVENTS = [
  'WorkerStatus',
  'TokenMetrics',
  'LoopDecision',
  'Status',
  'Iteration',
  'CoderTasksOutput'  // Security-Tasks werden separat angezeigt
];

// Formatiert TechStack-Entscheidungen
const formatTechStack = (data) => {
  if (!data) return null;
  const bp = data.blueprint || data;
  const reasoning = data.reasoning || bp.reasoning || '';

  return {
    icon: '\u{1F6E0}\uFE0F',  // Hammer und Schraubenschluessel
    title: 'TechStack entschieden',
    summary: `${bp.project_type || 'App'} mit ${bp.language || 'JavaScript'}` +
             (bp.database ? `, ${bp.database}` : ''),
    detail: reasoning ? reasoning : null
  };
};

// Formatiert Code-Generierung
const formatCodeOutput = (data) => {
  if (!data) return null;
  const fileCount = Array.isArray(data.files) && data.files.length > 0 ? data.files.length : 0;
  const iteration = data.iteration || 1;
  const maxIter = data.max_iterations || 3;

  return {
    icon: '\u{1F4BB}',  // Laptop
    title: 'Code generiert',
    summary: `${fileCount} Datei(en) erstellt - Iteration ${iteration}/${maxIter}`,
    detail: fileCount > 0 ? `Dateien: ${data.files.join(', ')}` : null
  };
};

// Formatiert Review-Ergebnisse
const formatReview = (data) => {
  if (!data) return null;
  const approved = data.isApproved;
  const verdict = data.verdict || '';

  return {
    icon: approved ? '\u2705' : '\u26A0\uFE0F',  // Haekchen oder Warnung
    title: approved ? 'Review bestanden' : 'Review: Nacharbeit noetig',
    summary: data.humanSummary || truncateText(verdict, 400),
    detail: null
  };
};

// Formatiert Security-Scan
const formatSecurity = (data) => {
  if (!data) return null;
  const vulnCount = data.vulnerabilities?.length || 0;

  if (vulnCount === 0) {
    return {
      icon: '\u2705',
      title: 'Security: OK',
      summary: 'Keine kritischen Sicherheitsprobleme gefunden',
      detail: null
    };
  }

  // Vulnerabilities nach Severity gruppieren
  const critical = data.vulnerabilities.filter(v => v.severity === 'critical').length;
  const high = data.vulnerabilities.filter(v => v.severity === 'high').length;

  return {
    icon: '\u{1F6E1}\uFE0F',  // Schild
    title: `Security: ${vulnCount} Issue${vulnCount > 1 ? 's' : ''}`,
    summary: `${critical > 0 ? `${critical} kritisch` : ''}${critical > 0 && high > 0 ? ', ' : ''}${high > 0 ? `${high} hoch` : ''}`.trim() || `${vulnCount} gefunden`,
    detail: data.vulnerabilities.slice(0, 3).map(v => truncateText(v.description, 150)).join(' | ')
  };
};

// Formatiert Researcher-Ergebnisse
// AENDERUNG 25.01.2026: Status-basierte Titel (laueft/abgeschlossen/fehlgeschlagen)
// AENDERUNG 25.01.2026: Kein Duplikat - Query nur bei "laeuft", Ergebnis bei "abgeschlossen"
const formatResearch = (data) => {
  if (!data) return null;

  // Status-basierte Titel
  const isComplete = data.status === 'completed' || data.status === 'success' || data.result;
  const hasError = data.status === 'error' || data.error;

  let title = 'Recherche laeuft...';
  let icon = '\u{1F50D}';  // Lupe
  let summary = data.query || 'Web-Recherche';

  if (hasError) {
    title = 'Recherche fehlgeschlagen';
    icon = '\u274C';  // Rotes X
    summary = data.error || 'Ein Fehler ist aufgetreten';
  } else if (isComplete) {
    title = 'Recherche abgeschlossen';
    icon = '\u2705';  // Gruener Haken
    // Bei abgeschlossener Recherche: Ergebnis anzeigen (Query war schon vorher sichtbar)
    summary = truncateText(data.result, 500) || 'Keine Ergebnisse';
  }

  return {
    icon: icon,
    title: title,
    summary: summary,
    detail: null  // Kein Detail mehr noetig - alles in summary
  };
};

// Formatiert Designer-Output
// AENDERUNG 25.01.2026: Laengere Ausgabe (800 statt 400) damit Konzept lesbar bleibt
const formatDesigner = (data) => {
  if (!data) return null;
  return {
    icon: '\u{1F3A8}',  // Palette
    title: 'Design erstellt',
    summary: truncateText(data.concept, 800) || 'Design-Konzept generiert',
    detail: data.colorPalette?.length ? `${data.colorPalette.length} Farben definiert` : null
  };
};

// Formatiert DB-Designer-Output
const formatDBDesigner = (data) => {
  if (!data) return null;
  const tableCount = data.tables?.length || 0;
  return {
    icon: '\u{1F5C3}\uFE0F',  // Karteikasten
    title: 'Datenbank-Schema erstellt',
    summary: tableCount > 0 ? `${tableCount} Tabelle(n) definiert` : 'Schema generiert',
    detail: data.tables?.slice(0, 5).map(t => t.name || t).join(', ')
  };
};

// Formatiert Tester-Output
const formatTester = (data) => {
  if (!data) return null;
  const defectCount = data.defects?.length || data.issues?.length || 0;

  if (defectCount === 0) {
    return {
      icon: '\u2705',
      title: 'Test: Erfolgreich',
      summary: 'Keine visuellen Probleme gefunden',
      detail: null
    };
  }

  return {
    icon: '\u{1F41B}',  // Kaefer
    title: `Test: ${defectCount} Fehler`,
    summary: 'Visuelle Probleme gefunden, Nacharbeit erforderlich',
    detail: null
  };
};

// Formatiert Model-Switch
const formatModelSwitch = (data) => {
  if (!data) return null;
  const oldModel = data.old_model?.split('/').pop() || 'Unbekannt';
  const newModel = data.new_model?.split('/').pop() || 'Unbekannt';

  return {
    icon: '\u{1F504}',  // Pfeile im Kreis
    title: 'Modellwechsel',
    summary: `${oldModel} -> ${newModel}`,
    detail: data.reason ? `Grund: ${data.reason}` : null
  };
};

// Agent-Icons Mapping
const getAgentIcon = (agent) => {
  const icons = {
    'Coder': '\u{1F4BB}',
    'Researcher': '\u{1F50D}',
    'Designer': '\u{1F3A8}',
    'Reviewer': '\u2705',
    'Tester': '\u{1F41B}',
    'TechArchitect': '\u{1F6E0}\uFE0F',
    'DBDesigner': '\u{1F5C3}\uFE0F',
    'Security': '\u{1F6E1}\uFE0F',
    'Orchestrator': '\u{1F3AF}',
    'System': '\u2699\uFE0F'
  };
  return icons[agent] || '\u{1F4DD}';
};

/**
 * Haupt-Formatierungs-Funktion
 * Wandelt ein Log-Objekt in ein benutzerfreundliches Format um.
 * AENDERUNG 28.01.2026: Robuste Behandlung von nicht-String messages (Session-Recovery).
 *
 * @param {Object} log - Log-Objekt mit agent, event, message
 * @returns {Object} Formatiertes Objekt mit icon, title, summary, detail
 */
export const formatLogForUser = (log) => {
  const { agent, event, message } = log;

  // AENDERUNG 28.01.2026: Message zu String konvertieren falls noetig (Session-Recovery)
  let messageStr = message;
  if (message === null || message === undefined) {
    messageStr = '';
  } else if (typeof message === 'object') {
    // Objekt zu JSON-String konvertieren
    try {
      messageStr = JSON.stringify(message);
    } catch {
      messageStr = String(message);
    }
  } else if (typeof message !== 'string') {
    messageStr = String(message);
  }

  // ÄNDERUNG 28.01.2026: Nicht-JSON Nachrichten - leere überspringen
  if (!messageStr || !messageStr.startsWith('{')) {
    // Leere Nachrichten überspringen (verhindert leere </> Zeilen)
    if (!messageStr || messageStr.trim() === '') {
      return null;
    }
    return {
      icon: getAgentIcon(agent),
      title: agent,
      summary: messageStr,
      detail: null
    };
  }

  // JSON parsen
  let data = null;
  try {
    data = JSON.parse(messageStr);
  } catch {
    return {
      icon: getAgentIcon(agent),
      title: agent,
      summary: truncateText(messageStr, 500),
      detail: null
    };
  }

  // Event-spezifische Formatierung
  let result = null;
  switch (event) {
    case 'TechStackOutput':
      result = formatTechStack(data);
      break;
    case 'CodeOutput':
      result = formatCodeOutput(data);
      break;
    case 'ReviewOutput':
      result = formatReview(data);
      break;
    case 'SecurityOutput':
    case 'SecurityRescanOutput':
      result = formatSecurity(data);
      break;
    case 'ResearchOutput':
      result = formatResearch(data);
      break;
    case 'DesignerOutput':
      result = formatDesigner(data);
      break;
    case 'DBDesignerOutput':
      result = formatDBDesigner(data);
      break;
    case 'UITestResult':
      result = formatTester(data);
      break;
    case 'ModelSwitch':
      result = formatModelSwitch(data);
      break;
    default:
      result = {
        icon: getAgentIcon(agent),
        title: agent,
        summary: truncateText(messageStr, 500),
        detail: null
      };
  }

  // Fallback wenn format-Funktion null zurückgibt
  if (!result) {
    return {
      icon: getAgentIcon(agent),
      title: agent,
      summary: truncateText(messageStr, 500),
      detail: null
    };
  }

  // ÄNDERUNG 28.01.2026: Nur zurückgeben wenn summary nicht leer ist
  if (!result.summary || result.summary.trim() === '') {
    return null;
  }

  return result;
};

export default formatLogForUser;
