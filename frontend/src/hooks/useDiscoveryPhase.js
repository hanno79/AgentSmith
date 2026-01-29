/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.0
 * Beschreibung: Hook für Discovery-Phasen und Ladezustände.
 */
// ÄNDERUNG 29.01.2026: Phase-Logik in Hook ausgelagert

import { useState, useCallback } from 'react';
import { PHASES } from '../constants/discoveryConstants';

export const useDiscoveryPhase = () => {
  const [phase, setPhase] = useState(PHASES.VISION);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');

  const startLoading = useCallback((message = '') => {
    setIsLoading(true);
    setLoadingMessage(message);
  }, []);

  const stopLoading = useCallback(() => {
    setIsLoading(false);
    setLoadingMessage('');
  }, []);

  return {
    phase,
    setPhase,
    isLoading,
    setIsLoading,
    loadingMessage,
    setLoadingMessage,
    startLoading,
    stopLoading
  };
};
