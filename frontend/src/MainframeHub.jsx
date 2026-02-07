/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.2
 * Beschreibung: Mainframe Hub - Zentrale Steuerung für Konfiguration, Modelle und System-Status.
 *               ÄNDERUNG 31.01.2026: Refactoring - Panels/Modal/Slider in eigene Komponenten (Regel 1).
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useModelFilter } from './hooks/useModelFilter';
import { Terminal, RefreshCw, AlertTriangle } from 'lucide-react';
import { API_BASE } from './constants/config';

import LLMGatewayPanel from './components/LLMGatewayPanel';
import CorePanel from './components/CorePanel';
import ModelListPanel from './components/ModelListPanel';
import ModelModal from './components/ModelModal';

const MainframeHub = ({
  maxRetries: propMaxRetries,
  onMaxRetriesChange,
  researchTimeout: propResearchTimeout,
  onResearchTimeoutChange,
  // ÄNDERUNG 25.01.2026: Props für Modellwechsel (Dual-Slider)
  maxModelAttempts: propMaxModelAttempts,
  onMaxModelAttemptsChange
}) => {
  const [config, setConfig] = useState(null);
  const [agents, setAgents] = useState([]);
  const [availableModels, setAvailableModels] = useState({ free_models: [], paid_models: [] });
  const [routerStatus, setRouterStatus] = useState({ rate_limited_models: {}, usage_stats: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [serverTime, setServerTime] = useState(new Date());
  const [maxRetries, setMaxRetries] = useState(5);
  const [researchTimeout, setResearchTimeout] = useState(5);
  // ÄNDERUNG 30.01.2026: Globaler Agent-Timeout in Sekunden
  // ÄNDERUNG 02.02.2026: Default von 300s (5 min) auf 900s (15 min) erhöht für langsame Free-Modelle
  const [agentTimeout, setAgentTimeout] = useState(900);
  // ÄNDERUNG 07.02.2026: Token-Limits als Dict für alle Agents (statt nur Coder)
  const [tokenLimits, setTokenLimits] = useState({});
  // ÄNDERUNG 07.02.2026: Agent-Timeouts als Dict pro Agent (analog zu tokenLimits)
  const [agentTimeouts, setAgentTimeouts] = useState({});
  // AENDERUNG 06.02.2026: Docker-Toggle
  const [dockerEnabled, setDockerEnabled] = useState(false);
  // ÄNDERUNG 25.01.2026: Lokaler State für Modellwechsel
  const [maxModelAttempts, setMaxModelAttempts] = useState(3);
  // ÄNDERUNG 25.01.2026: Filter für Modell-Listen
  const [modelFilter, setModelFilter] = useState('');
  const [providerFilter, setProviderFilter] = useState('all');
  // ÄNDERUNG 25.01.2026: Separate Filter für Modal
  const [modalModelFilter, setModalModelFilter] = useState('');
  const [modalProviderFilter, setModalProviderFilter] = useState('all');
  // ÄNDERUNG 29.01.2026: State für sortierbare Modell-Prioritätsliste
  const [agentModelPriority, setAgentModelPriority] = useState([]);
  const [savingPriority, setSavingPriority] = useState(false);

  // Verwende Props wenn vorhanden, sonst lokalen State (für Abwärtskompatibilität)
  const effectiveMaxRetries = propMaxRetries !== undefined ? propMaxRetries : maxRetries;
  const effectiveResearchTimeout = propResearchTimeout !== undefined ? propResearchTimeout : researchTimeout;
  // ÄNDERUNG 25.01.2026: Effektiver Wert für Modellwechsel
  const effectiveModelAttempts = propMaxModelAttempts !== undefined ? propMaxModelAttempts : maxModelAttempts;

  // ÄNDERUNG 31.01.2026: Memoized gefilterte Modell-Listen (eliminiert 4x Code-Duplikation)
  const filteredFreeModels = useModelFilter(availableModels.free_models, modelFilter, providerFilter);
  const filteredPaidModels = useModelFilter(availableModels.paid_models, modelFilter, providerFilter);
  const filteredModalFreeModels = useModelFilter(availableModels.free_models, modalModelFilter, modalProviderFilter);
  const filteredModalPaidModels = useModelFilter(availableModels.paid_models, modalModelFilter, modalProviderFilter);

  // Alle Daten beim Laden abrufen
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => setServerTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Daten neu laden wenn config.mode sich ändert
  useEffect(() => {
    if (config?.mode) {
      fetchData();
    }
  }, [config?.mode]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [configRes, agentsRes, modelsRes, routerRes] = await Promise.all([
        axios.get(`${API_BASE}/config`),
        axios.get(`${API_BASE}/agents`),
        axios.get(`${API_BASE}/models/available`),
        axios.get(`${API_BASE}/models/router-status`)
      ]);
      setConfig(configRes.data);
      setAgents(agentsRes.data.agents);
      setAvailableModels(modelsRes.data);
      setRouterStatus(routerRes.data);
      setMaxRetries(configRes.data.max_retries || 5);
      setResearchTimeout(configRes.data.research_timeout_minutes || 5);
      // ÄNDERUNG 30.01.2026: Globaler Agent-Timeout
      // ÄNDERUNG 02.02.2026: Fallback von 300s auf 900s (15 min) erhöht
      setAgentTimeout(configRes.data.agent_timeout_seconds || 900);
      // ÄNDERUNG 07.02.2026: Alle Token-Limits laden (Dict für alle Agents)
      setTokenLimits(configRes.data.token_limits || {});
      // ÄNDERUNG 07.02.2026: Agent-Timeouts pro Agent laden (analog zu tokenLimits)
      setAgentTimeouts(configRes.data.agent_timeouts || {});
      // AENDERUNG 06.02.2026: Docker-Status laden
      setDockerEnabled(configRes.data.docker_enabled || false);
    } catch (err) {
      console.error('Failed to fetch data:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  // ÄNDERUNG 30.01.2026: setMode ersetzt toggleMode für 3-Tier-Auswahl (Test/Production/Premium)
  const setMode = async (newMode) => {
    if (!config || config.mode === newMode) return;
    try {
      await axios.put(`${API_BASE}/config/mode`, { mode: newMode });
      // Reine State-Update ohne Side-Effects
      setConfig(prevConfig => ({ ...prevConfig, mode: newMode }));
      // fetchData wird automatisch durch useEffect ausgelöst wenn config.mode sich ändert
    } catch (err) {
      console.error('Failed to set mode:', err);
    }
  };

  const updateAgentModel = async (agentRole, newModel) => {
    try {
      await axios.put(`${API_BASE}/config/model/${agentRole}`, { model: newModel });
      fetchData();
      setShowModelSelector(false);
      setSelectedAgent(null);
    } catch (err) {
      console.error('Failed to update model:', err);
    }
  };

  // ÄNDERUNG 29.01.2026: Lade Modell-Prioritätsliste beim Öffnen des Modals
  const loadModelPriority = async (agentRole) => {
    try {
      const res = await axios.get(`${API_BASE}/config/model-priority/${agentRole}`);
      setAgentModelPriority(res.data.models || []);
    } catch (err) {
      console.error('Failed to load model priority:', err);
      setAgentModelPriority([]);
    }
  };

  // ÄNDERUNG 29.01.2026: Speichere Modell-Prioritätsliste
  const saveModelPriority = async () => {
    if (!selectedAgent || agentModelPriority.length === 0) {
      alert('Mindestens 1 Modell auswählen');
      return;
    }
    setSavingPriority(true);
    try {
      await axios.put(`${API_BASE}/config/model-priority/${selectedAgent.role}`, {
        models: agentModelPriority
      });
      fetchData();
      setShowModelSelector(false);
      setSelectedAgent(null);
    } catch (err) {
      console.error('Failed to save model priority:', err);
      alert('Fehler beim Speichern: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSavingPriority(false);
    }
  };

  // ÄNDERUNG 29.01.2026: Modell zur Prioritätsliste hinzufügen
  const addModelToPriority = (modelId) => {
    if (agentModelPriority.length >= 5) {
      alert('Maximal 5 Modelle pro Agent');
      return;
    }
    if (!agentModelPriority.includes(modelId)) {
      setAgentModelPriority([...agentModelPriority, modelId]);
    }
  };

  // ÄNDERUNG 29.01.2026: Modell aus Prioritätsliste entfernen
  const removeModelFromPriority = (modelId) => {
    setAgentModelPriority(agentModelPriority.filter(m => m !== modelId));
  };

  const clearRateLimits = async () => {
    try {
      await axios.post(`${API_BASE}/models/clear-rate-limits`);
      fetchData();
    } catch (err) {
      console.error('Failed to clear rate limits:', err);
    }
  };

  const updateMaxRetries = async (value) => {
    if (onMaxRetriesChange) {
      // Wenn Callback vorhanden, delegiere an Parent (App.jsx)
      onMaxRetriesChange(value);
    } else {
      // Fallback: Lokaler State + API-Call
      setMaxRetries(value);
      try {
        await axios.put(`${API_BASE}/config/max-retries`, { max_retries: value });
      } catch (err) {
        console.error('Failed to update max retries:', err);
      }
    }
  };

  const updateResearchTimeout = async (value) => {
    if (onResearchTimeoutChange) {
      // Wenn Callback vorhanden, delegiere an Parent (App.jsx)
      onResearchTimeoutChange(value);
    } else {
      // Fallback: Lokaler State + API-Call
      setResearchTimeout(value);
      try {
        await axios.put(`${API_BASE}/config/research-timeout`, { research_timeout_minutes: value });
      } catch (err) {
        console.error('Failed to update research timeout:', err);
      }
    }
  };

  // ÄNDERUNG 30.01.2026: Handler für globalen Agent-Timeout
  const updateAgentTimeout = async (value) => {
    // ÄNDERUNG [31.01.2026]: Optimistisches Update mit Rollback bei Fehler
    const previousValue = agentTimeout;
    setAgentTimeout(value);
    try {
      await axios.put(`${API_BASE}/config/agent-timeout`, { agent_timeout_seconds: value });
    } catch (err) {
      console.error('Failed to update agent timeout:', err);
      setAgentTimeout(previousValue);
      alert('Agent-Timeout konnte nicht gespeichert werden.');
    }
  };

  // ÄNDERUNG 07.02.2026: Generischer Handler für Token-Limits pro Agent
  const updateTokenLimit = async (agentRole, value) => {
    const previousLimits = { ...tokenLimits };
    setTokenLimits(prev => ({ ...prev, [agentRole]: value }));
    try {
      await axios.put(`${API_BASE}/config/token-limit/${agentRole}`, { max_tokens: value });
    } catch (err) {
      console.error(`Token-Limit für ${agentRole} fehlgeschlagen:`, err);
      setTokenLimits(previousLimits);
    }
  };

  // ÄNDERUNG 07.02.2026: Handler fuer Agent-Timeout pro Agent (analog zu updateTokenLimit)
  const updateAgentTimeoutPerAgent = async (agentRole, seconds) => {
    const previousTimeouts = { ...agentTimeouts };
    setAgentTimeouts(prev => ({ ...prev, [agentRole]: seconds }));
    try {
      await axios.put(`${API_BASE}/config/agent-timeout/${agentRole}`, { agent_timeout_seconds: seconds });
    } catch (err) {
      console.error(`Timeout für ${agentRole} fehlgeschlagen:`, err);
      setAgentTimeouts(previousTimeouts);
    }
  };

  // AENDERUNG 06.02.2026: Handler fuer Docker-Toggle mit Rollback
  const updateDockerEnabled = async (value) => {
    const previousValue = dockerEnabled;
    setDockerEnabled(value);
    try {
      await axios.put(`${API_BASE}/config/docker`, { enabled: value });
    } catch (err) {
      console.error('Docker-Toggle fehlgeschlagen:', err);
      setDockerEnabled(previousValue);
    }
  };

  // ÄNDERUNG 25.01.2026: Handler für Modellwechsel (Dual-Slider)
  const updateModelAttempts = async (value) => {
    // Validierung: max = effectiveMaxRetries - 1
    // ÄNDERUNG 25.01.2026: Edge Case Handling für effectiveMaxRetries <= 1
    const upperBound = effectiveMaxRetries - 1;
    const validValue = upperBound < 1 ? 0 : Math.max(1, Math.min(value, upperBound));
    if (onMaxModelAttemptsChange) {
      onMaxModelAttemptsChange(validValue);
    } else {
      setMaxModelAttempts(validValue);
      try {
        await axios.put(`${API_BASE}/config/max-model-attempts`, { max_model_attempts: validValue });
      } catch (err) {
        console.error('Failed to update model attempts:', err);
      }
    }
  };

  const getModelDisplayName = (modelId) => {
    // Behandle Fall wo modelId ein Objekt ist (verschachtelte Config mit primary/fallback)
    if (typeof modelId === 'object' && modelId !== null) {
      modelId = modelId.primary || JSON.stringify(modelId);
    }
    const allModels = [...availableModels.free_models, ...availableModels.paid_models];
    const model = allModels.find(m => m.id === modelId);
    if (model) return model.name;
    if (typeof modelId === 'string') {
      return modelId.split('/').pop() || 'Unknown';
    }
    return 'Unknown';
  };

  const isModelRateLimited = (modelId) => {
    return routerStatus.rate_limited_models && modelId in routerStatus.rate_limited_models;
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0a0a0a]">
        <RefreshCw className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-red-500" />
          <span className="text-white font-bold text-lg">Connection Error</span>
          <span className="text-[#9cbaa6] text-sm">Failed to load configuration. Please check if the server is running.</span>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-primary/20 border border-primary/30 rounded text-primary font-bold uppercase tracking-wider hover:bg-primary/30 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-[#0a0a0a] text-white font-display overflow-y-auto overflow-x-hidden page-scrollbar flex flex-col">
      {/* Scanline Effect */}
      <div className="fixed inset-0 pointer-events-none z-50 opacity-[0.03]"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 4px)'
        }}
      />

      {/* Header */}
      <header className="flex-none flex items-center justify-between border-b border-[#28392e] px-6 py-3 bg-[#111813]">
        <div className="flex items-center gap-4">
          <div className="p-2 rounded bg-primary/20 text-primary">
            <Terminal size={24} />
          </div>
          <div>
            <h2 className="text-lg font-bold leading-tight tracking-wider uppercase">Agent Smith // Mainframe</h2>
            <div className="text-xs text-[#9cbaa6] font-medium tracking-widest">INFRASTRUCTURE CONTROL</div>
          </div>
        </div>

        <div className="flex gap-4 items-center">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1b271f] border border-[#28392e]">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-xs font-semibold text-primary">SYSTEM ONLINE</span>
          </div>
          <div className="text-right hidden lg:block">
            <div className="text-[10px] text-[#9cbaa6] uppercase tracking-wider">SERVER_TIME</div>
            <div className="text-sm font-mono text-white">{serverTime.toLocaleTimeString()}</div>
          </div>
          <button
            onClick={fetchData}
            className="p-2 rounded-lg border border-[#28392e] hover:border-primary/50 hover:bg-primary/10 transition-all"
          >
            <RefreshCw size={18} className="text-[#9cbaa6] hover:text-primary" />
          </button>
        </div>
      </header>

      {/* Main Content - ÄNDERUNG 01.02.2026: overflow-y-auto für Scroll, min-h-fit für variable Höhe */}
      <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto page-scrollbar">
        <div className="min-h-fit grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">

          <LLMGatewayPanel
            agents={agents}
            routerStatus={routerStatus}
            onAgentClick={(agent) => {
              setSelectedAgent(agent);
              setShowModelSelector(true);
              setModalModelFilter('');
              setModalProviderFilter('all');
              loadModelPriority(agent.role);
            }}
            getModelDisplayName={getModelDisplayName}
            isModelRateLimited={isModelRateLimited}
            onClearRateLimits={clearRateLimits}
          />

          <CorePanel
            config={config}
            agents={agents}
            setMode={setMode}
            effectiveModelAttempts={effectiveModelAttempts}
            effectiveMaxRetries={effectiveMaxRetries}
            effectiveResearchTimeout={effectiveResearchTimeout}
            agentTimeout={agentTimeout}
            onModelAttemptsChange={updateModelAttempts}
            onMaxRetriesChange={updateMaxRetries}
            onResearchTimeoutChange={updateResearchTimeout}
            onAgentTimeoutChange={updateAgentTimeout}
            dockerEnabled={dockerEnabled}
            onDockerToggle={updateDockerEnabled}
          />

          <ModelListPanel
            modelFilter={modelFilter}
            onModelFilterChange={setModelFilter}
            providerFilter={providerFilter}
            onProviderFilterChange={setProviderFilter}
            filteredFreeModels={filteredFreeModels}
            filteredPaidModels={filteredPaidModels}
            availableModels={availableModels}
          />
        </div>
      </main>

      <ModelModal
        open={showModelSelector && !!selectedAgent}
        onClose={() => setShowModelSelector(false)}
        selectedAgent={selectedAgent}
        agentModelPriority={agentModelPriority}
        onReorder={setAgentModelPriority}
        onRemove={removeModelFromPriority}
        onAdd={addModelToPriority}
        onSave={saveModelPriority}
        savingPriority={savingPriority}
        modalModelFilter={modalModelFilter}
        onModalModelFilterChange={setModalModelFilter}
        modalProviderFilter={modalProviderFilter}
        onModalProviderFilterChange={setModalProviderFilter}
        filteredModalFreeModels={filteredModalFreeModels}
        filteredModalPaidModels={filteredModalPaidModels}
        configMode={config?.mode}
        tokenLimits={tokenLimits}
        onTokenLimitChange={updateTokenLimit}
        agentTimeouts={agentTimeouts}
        onAgentTimeoutChange={updateAgentTimeoutPerAgent}
      />

    </div>
  );
};

export default MainframeHub;
