import { useEffect, useRef, useCallback } from 'react';

/**
 * Gemeinsame Funktionen für alle Office-Komponenten
 *
 * Dieser Hook konsolidiert duplizierte Logik aus allen *Office.jsx Komponenten:
 * - Auto-scroll für Logs
 * - Status Badge Generator
 * - Zeit-Formatierung für Logs
 *
 * @param {Array} logs - Array von Log-Einträgen
 * @returns {Object} - { logRef, getStatusBadge, formatTime }
 */
export const useOfficeCommon = (logs = []) => {
  const logRef = useRef(null);

  // Auto-scroll bei neuen Logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  /**
   * Generiert Status Badge Daten basierend auf Status
   *
   * @param {string} status - Aktueller Status ('Idle', 'Working', 'Success', etc.)
   * @param {string} activeColorClass - CSS Klassen für aktiven Zustand (z.B. 'bg-blue-500/20 text-blue-400 border-blue-500/20')
   * @returns {Object} - { className, text, isActive }
   */
  const getStatusBadge = useCallback((status, activeColorClass = '') => {
    const isActive = status !== 'Idle' && status !== 'Success' && status !== 'Failure' && status !== 'Error';

    if (isActive) {
      return {
        className: `px-1.5 py-0.5 rounded text-[10px] ${activeColorClass} border uppercase tracking-wide`,
        text: status,
        isActive: true,
      };
    }

    return {
      className: 'px-1.5 py-0.5 rounded text-[10px] bg-slate-500/20 text-slate-400 border border-slate-500/20 uppercase tracking-wide',
      text: status,
      isActive: false,
    };
  }, []);

  /**
   * Formatiert Zeit für Log-Einträge
   *
   * @param {number} index - Index des Log-Eintrags im Array
   * @param {number} multiplier - Sekunden-Multiplikator für Zeit-Offset (default: 2)
   * @returns {string} - Formatierte Zeit im Format "HH:MM:SS"
   */
  const formatTime = useCallback((index, multiplier = 2) => {
    const now = new Date();
    now.setSeconds(now.getSeconds() - (logs.length - index) * multiplier);
    return now.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }, [logs.length]);

  return {
    logRef,
    getStatusBadge,
    formatTime,
  };
};

export default useOfficeCommon;
