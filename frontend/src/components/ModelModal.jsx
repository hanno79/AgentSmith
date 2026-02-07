/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Modal für Modell-Priorität pro Agent (Drag & Drop, Filter).
 *               Aus MainframeHub.jsx extrahiert (Regel 1).
 * # ÄNDERUNG [02.02.2026]: Extraktion aus MainframeHub – Modell-Priorität pro Agent
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Zap, Clock } from 'lucide-react';
import SortableModelList from './SortableModelList';
import { PROVIDER_OPTIONS } from '../hooks/useModelFilter';

const ModelModal = ({
  open,
  onClose,
  selectedAgent,
  agentModelPriority,
  onReorder,
  onRemove,
  onAdd,
  onSave,
  savingPriority,
  modalModelFilter,
  onModalModelFilterChange,
  modalProviderFilter,
  onModalProviderFilterChange,
  filteredModalFreeModels,
  filteredModalPaidModels,
  configMode,
  providerOptions = PROVIDER_OPTIONS,
  tokenLimits = {},
  onTokenLimitChange,
  // ÄNDERUNG 07.02.2026: Agent-Timeout pro Agent (analog zu tokenLimits)
  agentTimeouts = {},
  onAgentTimeoutChange
}) => {
  // ÄNDERUNG 07.02.2026: Token-Limit-Slider pro Agent im Modal
  const [localTokenLimit, setLocalTokenLimit] = React.useState(8192);

  React.useEffect(() => {
    if (selectedAgent && tokenLimits) {
      setLocalTokenLimit(tokenLimits[selectedAgent.role] || tokenLimits.default || 8192);
    }
  }, [selectedAgent, tokenLimits]);

  // ÄNDERUNG 07.02.2026: Timeout-Slider pro Agent im Modal (analog zu Token-Limit)
  const [localTimeout, setLocalTimeout] = React.useState(750);

  React.useEffect(() => {
    if (selectedAgent && agentTimeouts) {
      setLocalTimeout(agentTimeouts[selectedAgent.role] || agentTimeouts.default || 750);
    }
  }, [selectedAgent, agentTimeouts]);

  // Diskrete Timeout-Steps in Sekunden (60s bis 1800s / 1 bis 30 Minuten)
  const TIMEOUT_STEPS = [60, 90, 120, 180, 240, 300, 360, 420, 480, 540, 600, 750, 900, 1200, 1500, 1800];

  const timeoutStepIndex = TIMEOUT_STEPS.reduce((best, s, i) =>
    Math.abs(s - localTimeout) < Math.abs(TIMEOUT_STEPS[best] - localTimeout) ? i : best, 0);

  // Formatierung: Minuten + Sekunden in Klammern
  const formatTimeout = (seconds) => {
    const min = Math.floor(seconds / 60);
    return `${min} Min (${seconds}s)`;
  };

  const formatTokens = (v) => v >= 1024 ? `${Math.round(v / 1024)}K` : String(v);

  // Diskrete Steps: 1K-16K (1K), dann 24K, 32K, 48K, 64K, 96K, 128K
  const STEPS = [
    1024, 2048, 3072, 4096, 5120, 6144, 7168, 8192,
    9216, 10240, 11264, 12288, 13312, 14336, 15360, 16384,
    24576, 32768, 49152, 65536, 98304, 131072
  ];

  const stepIndex = STEPS.reduce((best, s, i) =>
    Math.abs(s - localTokenLimit) < Math.abs(STEPS[best] - localTokenLimit) ? i : best, 0);

  const handleSaveAll = async () => {
    if (onTokenLimitChange && selectedAgent) {
      await onTokenLimitChange(selectedAgent.role, localTokenLimit);
    }
    // ÄNDERUNG 07.02.2026: Timeout ebenfalls speichern beim Save
    if (onAgentTimeoutChange && selectedAgent) {
      await onAgentTimeoutChange(selectedAgent.role, localTimeout);
    }
    onSave();
  };

  return (
    <AnimatePresence>
      {open && selectedAgent ? (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-[#111813] border border-[#28392e] rounded-xl w-full max-w-4xl overflow-hidden shadow-2xl"
        >
          {/* Modal-Header */}
          <div className="px-6 py-4 border-b border-[#28392e] bg-[#16211a]">
            <h3 className="text-white font-bold text-lg">Modell-Priorität für {selectedAgent.name}</h3>
            <p className="text-[#9cbaa6] text-sm mt-1">Ziehe Modelle per Drag & Drop um die Reihenfolge zu ändern. Das erste Modell ist Primary.</p>
          </div>

          {/* Zweispaltiges Layout */}
          <div className="flex flex-col md:flex-row">
            {/* Links: Sortierbare Prioritätenliste */}
            <div className="md:w-1/2 border-b md:border-b-0 md:border-r border-[#28392e] p-4">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-[10px] text-primary uppercase tracking-widest font-bold">Modell-Priorität (1-5)</h4>
                <span className="text-[10px] text-[#9cbaa6]">{agentModelPriority.length}/5 Modelle</span>
              </div>

              <div className="min-h-[200px]">
                <SortableModelList
                  models={agentModelPriority}
                  onReorder={onReorder}
                  onRemove={onRemove}
                  maxModels={5}
                  disabled={savingPriority}
                />
              </div>

              {/* Info-Box */}
              <div className="mt-4 p-3 bg-[#0d120f] rounded-lg border border-[#28392e]">
                <p className="text-[10px] text-[#5c856b]">
                  <span className="text-primary font-bold">Primary:</span> Wird zuerst verwendet
                </p>
                <p className="text-[10px] text-[#5c856b] mt-1">
                  <span className="text-[#9cbaa6] font-bold">Fallback 1-4:</span> Bei Fehler/Rate-Limit der Reihe nach
                </p>
              </div>
            </div>

            {/* Rechts: Verfügbare Modelle zum Hinzufügen */}
            <div className="md:w-1/2 flex flex-col">
              {/* Filter */}
              <div className="p-4 border-b border-[#28392e] space-y-2 bg-[#0d120f]">
                <input
                  type="text"
                  placeholder="Search models..."
                  value={modalModelFilter}
                  onChange={(e) => onModalModelFilterChange(e.target.value)}
                  className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white placeholder-[#6b8f71] focus:outline-none focus:border-primary"
                />
                <select
                  value={modalProviderFilter}
                  onChange={(e) => onModalProviderFilterChange(e.target.value)}
                  className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary"
                >
                  {providerOptions.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Modellliste */}
              <div className="p-4 max-h-80 overflow-y-auto custom-scrollbar flex-1">
                <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2">Free Models</div>
                <div className="space-y-2 mb-4">
                  {filteredModalFreeModels.slice(0, 30).map((model) => {
                    const isInList = agentModelPriority.includes(model.id);
                    return (
                      <button
                        key={model.id}
                        onClick={() => !isInList && onAdd(model.id)}
                        disabled={isInList || agentModelPriority.length >= 5}
                        className={`w-full text-left p-2 rounded-lg border transition-all ${
                          isInList
                            ? 'bg-primary/20 border-primary opacity-50 cursor-not-allowed'
                            : agentModelPriority.length >= 5
                              ? 'bg-[#1b271f] border-[#28392e] opacity-50 cursor-not-allowed'
                              : 'bg-[#1b271f] border-[#28392e] hover:border-primary/50 cursor-pointer'
                        }`}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="text-white font-bold text-sm">{model.name}</span>
                            <span className="text-[#9cbaa6] text-xs ml-2">({model.provider})</span>
                          </div>
                          {isInList ? (
                            <Check size={14} className="text-primary" />
                          ) : agentModelPriority.length < 5 ? (
                            <span className="text-[10px] text-primary">+ Add</span>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {(configMode === 'production' || configMode === 'premium') && (
                  <>
                    <div className="text-[10px] text-yellow-400 uppercase tracking-widest font-bold mb-2">Premium Models</div>
                    <div className="space-y-2">
                      {filteredModalPaidModels.slice(0, 30).map((model) => {
                        const isInList = agentModelPriority.includes(model.id);
                        return (
                          <button
                            key={model.id}
                            onClick={() => !isInList && onAdd(model.id)}
                            disabled={isInList || agentModelPriority.length >= 5}
                            className={`w-full text-left p-2 rounded-lg border transition-all ${
                              isInList
                                ? 'bg-yellow-400/20 border-yellow-400 opacity-50 cursor-not-allowed'
                                : agentModelPriority.length >= 5
                                  ? 'bg-[#1b271f] border-[#28392e] opacity-50 cursor-not-allowed'
                                  : 'bg-[#1b271f] border-[#28392e] hover:border-yellow-400/50 cursor-pointer'
                            }`}
                          >
                            <div className="flex justify-between items-center">
                              <div>
                                <span className="text-white font-bold text-sm">{model.name}</span>
                                <span className="text-[#9cbaa6] text-xs ml-2">({model.provider})</span>
                              </div>
                              {isInList ? (
                                <Check size={14} className="text-yellow-400" />
                              ) : agentModelPriority.length < 5 ? (
                                <span className="text-[10px] text-yellow-400">+ Add</span>
                              ) : null}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="border-t border-[#28392e] bg-[#0d120f]">
            {/* Token-Limit Slider */}
            <div className="px-6 py-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                  <Zap size={14} className="text-amber-400" />
                  Token Limit
                </span>
                <span className="text-amber-400 font-mono font-bold text-lg">
                  {formatTokens(localTokenLimit)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-[#9cbaa6] font-mono">1K</span>
                <input
                  type="range"
                  min="0"
                  max={STEPS.length - 1}
                  value={stepIndex}
                  onChange={(e) => setLocalTokenLimit(STEPS[parseInt(e.target.value)])}
                  className="flex-1 mainframe-slider token-slider"
                  style={{
                    background: `linear-gradient(to right, #f59e0b 0%, #f59e0b ${(stepIndex / (STEPS.length - 1)) * 100}%, #28392e ${(stepIndex / (STEPS.length - 1)) * 100}%, #28392e 100%)`
                  }}
                />
                <span className="text-[10px] text-[#9cbaa6] font-mono">128K</span>
              </div>
            </div>

            {/* ÄNDERUNG 07.02.2026: Timeout-Slider pro Agent (analog zu Token-Limit) */}
            <div className="px-6 py-3 border-t border-[#28392e]">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                  <Clock size={14} className="text-amber-400" />
                  Agent Timeout
                </span>
                <span className="text-amber-400 font-mono font-bold text-lg">
                  {formatTimeout(localTimeout)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-[#9cbaa6] font-mono">1 Min</span>
                <input
                  type="range"
                  min="0"
                  max={TIMEOUT_STEPS.length - 1}
                  value={timeoutStepIndex}
                  onChange={(e) => setLocalTimeout(TIMEOUT_STEPS[parseInt(e.target.value)])}
                  className="flex-1 mainframe-slider token-slider"
                  style={{
                    background: `linear-gradient(to right, #f59e0b 0%, #f59e0b ${(timeoutStepIndex / (TIMEOUT_STEPS.length - 1)) * 100}%, #28392e ${(timeoutStepIndex / (TIMEOUT_STEPS.length - 1)) * 100}%, #28392e 100%)`
                  }}
                />
                <span className="text-[10px] text-[#9cbaa6] font-mono">30 Min</span>
              </div>
            </div>

            {/* Buttons */}
            <div className="px-6 py-3 border-t border-[#28392e] flex justify-between">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-[#28392e] text-[#9cbaa6] hover:text-white hover:border-white/20 transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={handleSaveAll}
                disabled={savingPriority || agentModelPriority.length === 0}
                className={`px-6 py-2 rounded-lg font-bold transition-all ${
                  savingPriority || agentModelPriority.length === 0
                    ? 'bg-[#28392e] text-[#5c856b] cursor-not-allowed'
                    : 'bg-primary text-black hover:bg-primary/80'
                }`}
              >
                {savingPriority ? 'Speichern...' : 'Priorität speichern'}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default ModelModal;
