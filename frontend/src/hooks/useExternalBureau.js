/**
 * Author: rahn
 * Datum: 01.02.2026
 * Version: 1.0
 * Beschreibung: Custom Hook für External Bureau API-Interaktionen.
 *               Extrahiert aus ExternalBureauOffice.jsx (Regel 1: Max 500 Zeilen)
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '../constants/ExternalBureauConstants';

export const useExternalBureau = () => {
  const [specialists, setSpecialists] = useState([]);
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);

  // Lade Specialists
  const fetchSpecialists = useCallback(async () => {
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
  }, []);

  // Lade Findings
  const fetchFindings = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/external-bureau/findings`);
      const data = await response.json();
      setFindings(data.findings || []);
    } catch (err) {
      console.error('Fehler beim Laden der Findings:', err);
    }
  }, []);

  // Aktiviere Specialist
  const handleActivate = useCallback(async (specialistId) => {
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
  }, [fetchSpecialists]);

  // Deaktiviere Specialist
  const handleDeactivate = useCallback(async (specialistId) => {
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
  }, [fetchSpecialists]);

  // Suche durchführen
  const handleSearch = useCallback(async (searchQuery) => {
    if (!searchQuery.trim()) return false;
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
        return true;
      } else {
        alert(data.error || 'Suche fehlgeschlagen');
        return false;
      }
    } catch (err) {
      console.error('Suche fehlgeschlagen:', err);
      return false;
    } finally {
      setSearchLoading(false);
    }
  }, [fetchFindings]);

  // Initial laden und Interval einrichten
  useEffect(() => {
    fetchSpecialists();
    fetchFindings();
    const interval = setInterval(fetchSpecialists, 5000); // Refresh alle 5s
    return () => clearInterval(interval);
  }, [fetchSpecialists, fetchFindings]);

  return {
    specialists,
    findings,
    loading,
    error,
    searchLoading,
    handleActivate,
    handleDeactivate,
    handleSearch,
    fetchSpecialists,
    fetchFindings,
  };
};

export default useExternalBureau;
