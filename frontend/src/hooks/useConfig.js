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
const useConfig = (setAgentData) => {
  const [researchTimeoutMinutes, setResearchTimeoutMinutes] = useState(5);
  const [maxRetriesConfig, setMaxRetriesConfig] = useState(15);
  // ÄNDERUNG 25.01.2026: State für Modellwechsel (Dual-Slider)
  const [maxModelAttempts, setMaxModelAttempts] = useState(3);

  // Konfiguration beim Start laden
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config`);
        setResearchTimeoutMinutes(response.data.research_timeout_minutes || 5);

        // Max Retries initial setzen
        const maxRetries = response.data.max_retries || 15;
        setMaxRetriesConfig(maxRetries);

        // ÄNDERUNG 25.01.2026: Max Model Attempts laden
        const modelAttempts = response.data.max_model_attempts || 3;
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

  /**
   * Handler für Research Timeout Änderungen.
   * Synchronisiert MainframeHub und ResearcherOffice.
   */
  const handleResearchTimeoutChange = async (value) => {
    setResearchTimeoutMinutes(value);
    try {
      await axios.put(`${API_BASE}/config/research-timeout`, { research_timeout_minutes: value });
    } catch (err) {
      console.error('Research Timeout Update fehlgeschlagen:', err);
    }
  };

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
    // Validierung: max = maxRetries - 1
    const validValue = Math.min(value, maxRetriesConfig - 1);
    setMaxModelAttempts(validValue);
    try {
      await axios.put(`${API_BASE}/config/max-model-attempts`, { max_model_attempts: validValue });
    } catch (err) {
      console.error('Max Model Attempts Update fehlgeschlagen:', err);
    }
  };

  return {
    researchTimeoutMinutes,
    maxRetriesConfig,
    maxModelAttempts,
    handleResearchTimeoutChange,
    handleMaxRetriesChange,
    handleMaxModelAttemptsChange
  };
};

export default useConfig;
