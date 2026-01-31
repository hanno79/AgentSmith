/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Hook für Modell-Filterung (Search + Provider)
 *               Eliminiert Code-Duplikation in MainframeHub.jsx (Regel 13)
 */
import { useMemo } from 'react';

/**
 * Provider-Optionen für Dropdown-Filter
 * Single Source of Truth für alle Provider-Selects
 */
export const PROVIDER_OPTIONS = [
  { value: 'all', label: 'All Providers' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'google', label: 'Google' },
  { value: 'meta-llama', label: 'Meta' },
  { value: 'mistralai', label: 'Mistral' },
  { value: 'qwen', label: 'Qwen' },
  { value: 'nvidia', label: 'NVIDIA' },
  { value: 'deepseek', label: 'DeepSeek' },
];

/**
 * Hook zum Filtern von Modellen nach Suchbegriff und Provider
 *
 * @param {Array} models - Array von Modell-Objekten mit {id, name}
 * @param {string} searchFilter - Suchbegriff für Modellnamen
 * @param {string} providerFilter - Provider-ID oder 'all'
 * @returns {Array} Gefilterte Modelle
 *
 * @example
 * const filteredModels = useModelFilter(availableModels.free_models, modelFilter, providerFilter);
 */
export const useModelFilter = (models, searchFilter, providerFilter) => {
  return useMemo(() => {
    if (!models || !Array.isArray(models)) return [];

    return models.filter(m => {
      const matchesSearch = m.name.toLowerCase().includes(searchFilter.toLowerCase());
      const matchesProvider = providerFilter === 'all' || m.id.toLowerCase().includes(providerFilter);
      return matchesSearch && matchesProvider;
    });
  }, [models, searchFilter, providerFilter]);
};

export default useModelFilter;
