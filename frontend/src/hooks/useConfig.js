/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Custom Hook für Konfigurationsverwaltung.
 *               Lädt und aktualisiert Einstellungen vom Backend.
 */

import { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../constants/config';

/**
 * Konfigurations-Hook für Backend-Einstellungen.
 *
 * @param {Function} setAgentData - Setter für Agenten-Daten (für maxIterations)
 * @returns {Object} Konfigurationswerte und Handler
 */
// ÄNDERUNG 08.02.2026: researchTimeoutMinutes entfernt - pro Agent im ModelModal
const useConfig = (setAgentData) => {
  const [maxRetriesConfig, setMaxRetriesConfig] = useState(15);
  // ÄNDERUNG 25.01.2026: State für Modellwechsel (Dual-Slider)
  const [maxModelAttempts, setMaxModelAttempts] = useState(3);

  // Konfiguration beim Start laden
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config`);
        // ÄNDERUNG 08.02.2026: research_timeout_minutes nicht mehr geladen (pro Agent im ModelModal)

        // Max Retries initial setzen
        const maxRetries = response.data.max_retries || 15;
        setMaxRetriesConfig(maxRetries);

        // ÄNDERUNG 25.01.2026: Max Model Attempts laden und validieren
        const rawModelAttempts = response.data.max_model_attempts || 3;
        // Validierung: Edge Case Handling für maxRetries <= 1
        const upperBound = maxRetries - 1;
        const modelAttempts = upperBound < 1 ? 0 : Math.max(1, Math.min(rawModelAttempts, upperBound));
        setMaxModelAttempts(modelAttempts);

        setAgentData(prev => ({
          ...prev,
          coder: {
            ...prev.coder,
            maxIterations: maxRetries
          }
        }));
      } catch (err) {
        console.error('Konfiguration laden fehlgeschlagen:', err);
      }
    };
    fetchConfig();
  }, []);

  // ÄNDERUNG 08.02.2026: handleResearchTimeoutChange entfernt (pro Agent im ModelModal)

  /**
   * Handler für Max Retries Änderungen.
   * Synchronisiert MainframeHub und CoderOffice.
   */
  const handleMaxRetriesChange = async (value) => {
    setMaxRetriesConfig(value);
    // Auch agentData.coder.maxIterations sofort aktualisieren
    setAgentData(prev => ({
      ...prev,
      coder: {
        ...prev.coder,
        maxIterations: value
      }
    }));
    try {
      await axios.put(`${API_BASE}/config/max-retries`, { max_retries: value });
    } catch (err) {
      console.error('Max Retries Update fehlgeschlagen:', err);
    }
  };

  /**
   * ÄNDERUNG 25.01.2026: Handler für Max Model Attempts Änderungen.
   * Für Dual-Slider: Modellwechsel nach X Fehlversuchen.
   */
  const handleMaxModelAttemptsChange = async (value) => {
    // Validierung: min = 1, max = maxRetries - 1
    // ÄNDERUNG 25.01.2026: Edge Case Handling für maxRetriesConfig <= 1
    const upperBound = maxRetriesConfig - 1;
    const validValue = upperBound < 1 ? 0 : Math.max(1, Math.min(value, upperBound));
    setMaxModelAttempts(validValue);
    try {
      await axios.put(`${API_BASE}/config/max-model-attempts`, { max_model_attempts: validValue });
    } catch (err) {
      console.error('Max Model Attempts Update fehlgeschlagen:', err);
    }
  };

  return {
    maxRetriesConfig,
    maxModelAttempts,
    handleMaxRetriesChange,
    handleMaxModelAttemptsChange
  };
};

export default useConfig;
