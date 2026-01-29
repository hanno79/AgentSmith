/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.0
 * Beschreibung: Hook für Discovery Session Persistenz in localStorage.
 */
// ÄNDERUNG 29.01.2026: Session-Persistenz für Pausieren/Fortsetzen

import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'agentsmith_discovery_session';

export const useSessionStorage = () => {
  const [hasSavedSession, setHasSavedSession] = useState(false);

  // Prüfe beim Start ob eine gespeicherte Session existiert
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      setHasSavedSession(!!saved);
    } catch (e) {
      console.warn('localStorage nicht verfügbar:', e);
      setHasSavedSession(false);
    }
  }, []);

  // Session speichern
  const saveSession = useCallback((sessionData) => {
    try {
      const dataWithTimestamp = {
        ...sessionData,
        savedAt: new Date().toISOString()
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(dataWithTimestamp));
      setHasSavedSession(true);
      return true;
    } catch (e) {
      console.error('Fehler beim Speichern der Session:', e);
      return false;
    }
  }, []);

  // Session laden
  const loadSession = useCallback(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
      return null;
    } catch (e) {
      console.error('Fehler beim Laden der Session:', e);
      return null;
    }
  }, []);

  // Session löschen
  const clearSession = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
      setHasSavedSession(false);
      return true;
    } catch (e) {
      console.error('Fehler beim Löschen der Session:', e);
      return false;
    }
  }, []);

  return {
    hasSavedSession,
    saveSession,
    loadSession,
    clearSession
  };
};
