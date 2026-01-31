/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Mainframe Hub - Zentrale Steuerung für Konfiguration, Modelle und System-Status.
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
// ÄNDERUNG 29.01.2026: Import SortableModelList für Drag & Drop Prioritätslisten
import SortableModelList from './components/SortableModelList';
import {
  Terminal,
  Cpu,
  Server,
  Settings,
  RefreshCw,
  Zap,
  Database,
  Shield,
  Activity,
  ChevronDown,
  Check,
  X,
  Clock,
  DollarSign,
  AlertTriangle
} from 'lucide-react';

import { API_BASE, DEFAULTS } from './constants/config';

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
  const [agentTimeout, setAgentTimeout] = useState(300);
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
      setAgentTimeout(configRes.data.agent_timeout_seconds || 300);
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

      {/* Main Content - ÄNDERUNG 25.01.2026: Feste Höhe für besseres Layout */}
      <main className="flex-1 overflow-hidden p-4 md:p-6 lg:p-8">
        <div className="h-[calc(100vh-140px)] grid grid-cols-1 xl:grid-cols-12 gap-6">

          {/* Left Panel: LLM Gateway */}
          <div className="xl:col-span-4 flex flex-col gap-4">
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex-1 flex flex-col shadow-2xl">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Server size={16} className="text-primary" />
                  LLM Gateway [Agents]
                </h3>
                <div className="flex gap-1">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                  <div className="w-2 h-2 rounded-full bg-primary/30" />
                </div>
              </div>

              <div className="p-4 flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-3">
                {/* Header Row */}
                <div className="grid grid-cols-12 gap-2 text-[10px] text-[#9cbaa6] font-mono uppercase px-3 mb-1">
                  <div className="col-span-5">Agent</div>
                  <div className="col-span-4">Model</div>
                  <div className="col-span-3 text-right">Status</div>
                </div>

                {/* Agent Cards */}
                {agents.map((agent) => (
                  <motion.div
                    key={agent.role}
                    whileHover={{ scale: 1.01 }}
                    onClick={() => {
                      setSelectedAgent(agent);
                      setShowModelSelector(true);
                      // Modal-Filter zurücksetzen
                      setModalModelFilter('');
                      setModalProviderFilter('all');
                      // ÄNDERUNG 29.01.2026: Lade Prioritätsliste beim Öffnen
                      loadModelPriority(agent.role);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedAgent(agent);
                        setShowModelSelector(true);
                        setModalModelFilter('');
                        setModalProviderFilter('all');
                        // ÄNDERUNG 29.01.2026: Lade Prioritätsliste beim Öffnen
                        loadModelPriority(agent.role);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-label={`${agent.name} - ${agent.role} - ${isModelRateLimited(agent.model) ? 'Rate Limited' : 'Ready'}`}
                    className={`group relative bg-[#1b271f] hover:bg-[#233328] border border-[#28392e] hover:border-primary/50 rounded-lg p-3 transition-all cursor-pointer ${
                      isModelRateLimited(agent.model) ? 'opacity-60' : ''
                    }`}
                  >
                    <div className="grid grid-cols-12 gap-2 items-center">
                      <div className="col-span-5 flex flex-col">
                        <span className="text-white font-bold text-sm">{agent.name}</span>
                        <span className="text-[#9cbaa6] text-[10px] uppercase tracking-wider">{agent.role}</span>
                      </div>
                      <div className="col-span-4">
                        <span className="text-primary text-xs font-mono truncate block">
                          {getModelDisplayName(agent.model)}
                        </span>
                      </div>
                      <div className="col-span-3 text-right">
                        {isModelRateLimited(agent.model) ? (
                          <span className="text-[10px] text-red-400 font-bold">RATE LIMITED</span>
                        ) : (
                          <span className="text-[10px] text-primary font-bold">READY</span>
                        )}
                      </div>
                    </div>
                    {/* Status Indicator */}
                    <div className={`absolute right-0 top-0 bottom-0 w-1 rounded-r-lg ${
                      isModelRateLimited(agent.model) ? 'bg-red-500/50' : 'bg-primary shadow-[0_0_10px_rgba(13,242,89,0.5)]'
                    }`} />
                  </motion.div>
                ))}
              </div>

              {/* Rate Limited Info */}
              {Object.keys(routerStatus.rate_limited_models || {}).length > 0 && (
                <div className="p-4 border-t border-[#28392e] bg-[#0d120f]">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[10px] text-red-400 uppercase tracking-wider font-bold">Rate Limited Models</span>
                    <button
                      onClick={clearRateLimits}
                      className="text-[10px] text-primary hover:underline"
                    >
                      Clear All
                    </button>
                  </div>
                  {Object.entries(routerStatus.rate_limited_models).map(([model, info]) => (
                    <div key={model} className="flex justify-between text-xs text-[#9cbaa6]">
                      <span className="truncate">{model.split('/').pop()}</span>
                      <span className="flex items-center gap-1">
                        <Clock size={10} />
                        {info.remaining_seconds}s
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Center Panel: The Core */}
          <div className="xl:col-span-4 flex flex-col gap-6">
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex-1 relative flex flex-col items-center justify-end shadow-[0_0_30px_rgba(13,242,89,0.05)]">
              {/* Background Grid */}
              <div className="absolute inset-0 opacity-10 pointer-events-none"
                style={{ backgroundImage: 'radial-gradient(#0df259 1px, transparent 1px)', backgroundSize: '20px 20px' }}
              />
              {/* Core Glow */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 bg-primary/20 rounded-full blur-[60px] animate-pulse pointer-events-none" />

              {/* Core Visual */}
              <div className="relative z-10 w-full flex-1 flex flex-col items-center justify-center p-6">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                  className="w-32 h-32 rounded-full border-2 border-primary/30 flex items-center justify-center mb-6"
                >
                  <div className="w-24 h-24 rounded-full border border-primary/50 flex items-center justify-center">
                    <Cpu size={48} className="text-primary" />
                  </div>
                </motion.div>

                <h2 className="text-2xl text-white font-bold uppercase tracking-widest mb-1">The Core</h2>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-primary text-xs font-mono">INTEGRITY: 99.8%</span>
                </div>

                {/* Stats */}
                <div className="mt-6 grid grid-cols-2 gap-4 w-full max-w-xs">
                  <div className="bg-[#0d120f] rounded-lg p-3 border border-[#28392e]">
                    <div className="text-[10px] text-[#9cbaa6] uppercase mb-1">Active Agents</div>
                    <div className="text-xl font-bold text-white">{agents.length}</div>
                  </div>
                  <div className="bg-[#0d120f] rounded-lg p-3 border border-[#28392e]">
                    <div className="text-[10px] text-[#9cbaa6] uppercase mb-1">Mode</div>
                    <div className={`text-xl font-bold ${
                      config?.mode === 'premium' ? 'text-amber-300' :
                      config?.mode === 'production' ? 'text-yellow-400' : 'text-primary'
                    }`}>
                      {config?.mode?.toUpperCase()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Environment Control - ÄNDERUNG 30.01.2026: 3-Tier-Selector (Test/Production/Premium) */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-6">
                <div className="flex justify-between items-center mb-4">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest">Environment Control</h4>
                  <div className="flex gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'test' ? 'bg-primary' : 'bg-primary/20'}`} />
                    <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'production' ? 'bg-yellow-500' : 'bg-yellow-500/20'}`} />
                    <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'premium' ? 'bg-amber-300' : 'bg-amber-300/20'}`} />
                  </div>
                </div>

                {/* 3-Tier Selector */}
                <div className="relative bg-[#1b271f] p-2 rounded-lg border border-[#28392e]">
                  {/* Sliding Indicator */}
                  <motion.div
                    className={`absolute top-2 bottom-2 rounded-md ${
                      config?.mode === 'premium'
                        ? 'bg-gradient-to-br from-amber-500/30 to-amber-700/30 border border-amber-400/50'
                        : config?.mode === 'production'
                          ? 'bg-gradient-to-br from-yellow-600/30 to-yellow-800/30 border border-yellow-500/50'
                          : 'bg-gradient-to-br from-[#4a6b56]/50 to-[#28392e]/50 border border-[#5c856b]/50'
                    }`}
                    initial={false}
                    animate={{
                      left: config?.mode === 'test' ? '8px' : config?.mode === 'production' ? 'calc(33.33% + 4px)' : 'calc(66.66% + 0px)',
                      width: 'calc(33.33% - 8px)'
                    }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />

                  <div className="relative flex">
                    {/* TEST */}
                    <button
                      onClick={() => setMode('test')}
                      className={`flex-1 py-3 px-2 text-center transition-all z-10 rounded-md ${
                        config?.mode === 'test' ? '' : 'hover:bg-white/5'
                      }`}
                    >
                      <div className={`font-bold text-sm mb-0.5 transition-colors ${
                        config?.mode === 'test' ? 'text-primary' : 'text-white/60'
                      }`}>TEST</div>
                      <div className="text-[9px] text-[#9cbaa6] uppercase">Free</div>
                    </button>

                    {/* PRODUCTION */}
                    <button
                      onClick={() => setMode('production')}
                      className={`flex-1 py-3 px-2 text-center transition-all z-10 rounded-md ${
                        config?.mode === 'production' ? '' : 'hover:bg-white/5'
                      }`}
                    >
                      <div className={`font-bold text-sm mb-0.5 transition-colors ${
                        config?.mode === 'production' ? 'text-yellow-400' : 'text-white/60'
                      }`}>PROD</div>
                      <div className="text-[9px] text-[#9cbaa6] uppercase">Value</div>
                    </button>

                    {/* PREMIUM */}
                    <button
                      onClick={() => setMode('premium')}
                      className={`flex-1 py-3 px-2 text-center transition-all z-10 rounded-md ${
                        config?.mode === 'premium' ? '' : 'hover:bg-white/5'
                      }`}
                    >
                      <div className={`font-bold text-sm mb-0.5 transition-colors ${
                        config?.mode === 'premium' ? 'text-amber-300' : 'text-white/60'
                      }`}>PREMIUM</div>
                      <div className="text-[9px] text-[#9cbaa6] uppercase">Best</div>
                    </button>
                  </div>
                </div>

                {/* Mode Description */}
                <div className="mt-3 text-center text-[10px] text-[#9cbaa6]">
                  {config?.mode === 'test' && 'Kostenlose Modelle - Ideal für Tests und Entwicklung'}
                  {config?.mode === 'production' && 'Preis-Leistungs-Sieger - Beste Balance für den Alltag'}
                  {config?.mode === 'premium' && 'Top-Premium-Modelle - Höchste Qualität ohne Kompromisse'}
                </div>
              </div>

              {/* ÄNDERUNG 25.01.2026: Dual-Slider für Iterationen & Modellwechsel */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                    <RefreshCw size={14} className="text-primary" />
                    Coder Konfiguration
                  </h4>
                </div>

                {/* Werte-Anzeige */}
                <div className="flex justify-between mb-3">
                  <div className="text-center">
                    <span className="text-amber-400 font-mono font-bold text-xl">{effectiveModelAttempts}</span>
                    <p className="text-[9px] text-amber-400/70 uppercase">Modellwechsel</p>
                  </div>
                  <div className="text-center">
                    <span className="text-primary font-mono font-bold text-xl">{effectiveMaxRetries}</span>
                    <p className="text-[9px] text-primary/70 uppercase">Iterationen</p>
                  </div>
                </div>

                <div className="bg-[#1b271f] p-3 rounded-lg border border-[#28392e]">
                  {/* Dual Range Slider */}
                  <div className="relative h-10 flex items-center px-2">
                    {/* Track Hintergrund */}
                    <div className="absolute left-2 right-2 h-2 bg-[#28392e] rounded-full" />

                    {/* Aktiver Bereich zwischen den Punkten */}
                    {/* ÄNDERUNG 25.01.2026: Edge Case Handling für effectiveMaxRetries <= 1 */}
                    {(() => {
                      const upperBound = effectiveMaxRetries - 1;
                      const safeModelAttempts = effectiveModelAttempts < 1 ? 0 : effectiveModelAttempts;
                      const safeUpperBound = Math.max(1, upperBound);
                      const leftPercent = upperBound < 1 ? 0 : ((safeModelAttempts - 1) / safeUpperBound) * 100;
                      return (
                        <div
                          className="absolute h-2 bg-gradient-to-r from-amber-500/60 to-primary/60 rounded-full"
                          style={{
                            left: `calc(${leftPercent}% + 8px)`,
                            right: `calc(${(100 - leftPercent)}% + 8px)`
                          }}
                        />
                      );
                    })()}

                    {/* Modellwechsel Slider (links, amber) */}
                    {/* ÄNDERUNG 25.01.2026: Edge Case Handling für effectiveMaxRetries <= 1 */}
                    {(() => {
                      const upperBound = effectiveMaxRetries - 1;
                      const sliderMax = Math.max(1, upperBound);
                      const sliderValue = effectiveModelAttempts < 1 ? 1 : Math.max(1, Math.min(effectiveModelAttempts, sliderMax));
                      const isDisabled = upperBound < 1;
                      return (
                        <input
                          type="range"
                          min="1"
                          max={sliderMax}
                          value={sliderValue}
                          disabled={isDisabled}
                          onChange={(e) => {
                            const val = parseInt(e.target.value);
                            updateModelAttempts(Math.min(val, upperBound));
                          }}
                          className="absolute inset-x-2 w-[calc(100%-16px)] dual-slider-left"
                          style={{ zIndex: effectiveModelAttempts > effectiveMaxRetries - 10 ? 3 : 1, opacity: isDisabled ? 0.5 : 1 }}
                        />
                      );
                    })()}

                    {/* Iterationen Slider (rechts, primary) */}
                    <input
                      type="range"
                      min="2"
                      max="100"
                      value={effectiveMaxRetries}
                      onChange={(e) => {
                        const newVal = Math.max(2, parseInt(e.target.value));
                        updateMaxRetries(newVal);
                        // ÄNDERUNG 25.01.2026: Edge Case Handling - Wenn Iterationen unter Modellwechsel fällt, anpassen
                        const newUpperBound = newVal - 1;
                        if (effectiveModelAttempts > 0 && effectiveModelAttempts >= newVal) {
                          // Setze auf neuen upperBound, oder 0 wenn upperBound < 1
                          updateModelAttempts(newUpperBound < 1 ? 0 : newUpperBound);
                        } else if (effectiveModelAttempts === 0 && newUpperBound >= 1) {
                          // Wenn Modellwechsel deaktiviert war aber jetzt wieder möglich, auf 1 setzen
                          updateModelAttempts(1);
                        }
                      }}
                      className="absolute inset-x-2 w-[calc(100%-16px)] dual-slider-right"
                      style={{ zIndex: effectiveModelAttempts > effectiveMaxRetries - 10 ? 1 : 3 }}
                    />
                  </div>

                  {/* Skala */}
                  <div className="flex justify-between mt-1 px-2">
                    <span className="text-[10px] text-[#9cbaa6] font-mono">1</span>
                    <span className="text-[10px] text-[#9cbaa6] font-mono">100</span>
                  </div>

                  {/* Erklärung */}
                  <div className="mt-3 p-2 bg-[#0d120f] rounded border border-[#28392e] space-y-1">
                    <p className="text-[10px] text-[#5c856b]">
                      <span className="text-amber-400 font-bold">Modellwechsel:</span> Nach X Fehlversuchen wird ein anderes KI-Modell verwendet ("Kollegen fragen").
                    </p>
                    <p className="text-[10px] text-[#5c856b]">
                      <span className="text-primary font-bold">Iterationen:</span> Maximale Gesamtversuche für den Coder-Agenten.
                    </p>
                  </div>
                </div>
              </div>

              {/* System Settings - Research Timeout */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                    <Clock size={14} className="text-primary" />
                    Research Timeout
                  </h4>
                  <span className="text-primary font-mono font-bold text-lg">{effectiveResearchTimeout} min</span>
                </div>

                <div className="bg-[#1b271f] p-3 rounded-lg border border-[#28392e]">
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-6">1</span>
                    <input
                      type="range"
                      min="1"
                      max="60"
                      value={effectiveResearchTimeout}
                      onChange={(e) => updateResearchTimeout(parseInt(e.target.value))}
                      className="flex-1 mainframe-slider"
                    />
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-8">60</span>
                  </div>
                  <p className="text-[10px] text-[#5c856b] mt-2 text-center">
                    Maximale Zeit für Web-Recherche (in Minuten)
                  </p>
                </div>
              </div>

              {/* ÄNDERUNG 30.01.2026: Agent Timeout Slider */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                    <Clock size={14} className="text-primary" />
                    Agent Timeout
                  </h4>
                  <span className="text-primary font-mono font-bold text-lg">{Math.floor(agentTimeout / 60)} min</span>
                </div>

                <div className="bg-[#1b271f] p-3 rounded-lg border border-[#28392e]">
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-6">1</span>
                    <input
                      type="range"
                      min="60"
                      max="600"
                      step="30"
                      value={agentTimeout}
                      onChange={(e) => updateAgentTimeout(parseInt(e.target.value))}
                      className="flex-1 mainframe-slider"
                    />
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-8">10</span>
                  </div>
                  <p className="text-[10px] text-[#5c856b] mt-2 text-center">
                    Maximale Zeit pro Agent-Operation (in Minuten)
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Available Models - ÄNDERUNG 25.01.2026: Mit Filter und begrenzter Höhe */}
          <div className="xl:col-span-4 flex flex-col gap-4 max-h-full">
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex flex-col shadow-2xl max-h-full">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Database size={16} className="text-primary" />
                  Model Registry
                </h3>
                <div className="px-2 py-0.5 bg-primary/20 text-primary text-[10px] font-mono rounded border border-primary/30">
                  {availableModels.free_models.filter(m => {
                    const matchesSearch = m.name.toLowerCase().includes(modelFilter.toLowerCase());
                    const matchesProvider = providerFilter === 'all' || m.id.toLowerCase().includes(providerFilter);
                    return matchesSearch && matchesProvider;
                  }).length + availableModels.paid_models.filter(m => {
                    const matchesSearch = m.name.toLowerCase().includes(modelFilter.toLowerCase());
                    const matchesProvider = providerFilter === 'all' || m.id.toLowerCase().includes(providerFilter);
                    return matchesSearch && matchesProvider;
                  }).length} / {availableModels.free_models.length + availableModels.paid_models.length}
                </div>
              </div>

              {/* Filter - ÄNDERUNG 25.01.2026 */}
              <div className="p-3 border-b border-[#28392e] space-y-2 bg-[#0d120f]">
                <input
                  type="text"
                  placeholder="Search models..."
                  value={modelFilter}
                  onChange={(e) => setModelFilter(e.target.value)}
                  className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white placeholder-[#6b8f71] focus:outline-none focus:border-primary"
                />
                <select
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary"
                >
                  <option value="all">All Providers</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="google">Google</option>
                  <option value="meta-llama">Meta</option>
                  <option value="mistralai">Mistral</option>
                  <option value="qwen">Qwen</option>
                  <option value="nvidia">NVIDIA</option>
                  <option value="deepseek">DeepSeek</option>
                </select>
              </div>

              <div className="p-4 overflow-y-auto custom-scrollbar" style={{maxHeight: 'calc(100vh - 380px)'}}>
                {/* Free Models */}
                <div className="mb-4">
                  <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
                    <Zap size={12} />
                    Free Tier
                  </div>
                  <div className="space-y-2">
                    {availableModels.free_models
                      .filter(m => {
                        const matchesSearch = m.name.toLowerCase().includes(modelFilter.toLowerCase());
                        const matchesProvider = providerFilter === 'all' || m.id.toLowerCase().includes(providerFilter);
                        return matchesSearch && matchesProvider;
                      })
                      .slice(0, 50)
                      .map((model) => (
                      <div
                        key={model.id}
                        className="bg-[#1b271f] border border-[#28392e] rounded-lg p-3 hover:border-primary/30 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="text-white font-bold text-sm">{model.name}</span>
                          <span className="text-[10px] text-primary bg-primary/10 px-2 py-0.5 rounded">{model.provider}</span>
                        </div>
                        <div className="text-[10px] text-[#9cbaa6] truncate">{model.id}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Paid Models */}
                <div>
                  <div className="text-[10px] text-yellow-400 uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
                    <DollarSign size={12} />
                    Premium Tier
                  </div>
                  <div className="space-y-2">
                    {availableModels.paid_models
                      .filter(m => {
                        const matchesSearch = m.name.toLowerCase().includes(modelFilter.toLowerCase());
                        const matchesProvider = providerFilter === 'all' || m.id.toLowerCase().includes(providerFilter);
                        return matchesSearch && matchesProvider;
                      })
                      .slice(0, 50)
                      .map((model) => (
                      <div
                        key={model.id}
                        className="bg-[#1b271f] border border-[#28392e] rounded-lg p-3 hover:border-yellow-500/30 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="text-white font-bold text-sm">{model.name}</span>
                          <span className="text-[10px] text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">{model.provider}</span>
                        </div>
                        <div className="text-[10px] text-[#9cbaa6] truncate">{model.id}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer Stats */}
              <div className="border-t border-[#28392e] bg-[#0d120f] p-3 flex justify-end items-center text-[10px] font-mono text-[#5c856b]">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                  <span>LIVE_SYNC</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Model Selector Modal - ÄNDERUNG 29.01.2026: Erweitert um sortierbare Prioritätsliste */}
      <AnimatePresence>
        {showModelSelector && selectedAgent && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowModelSelector(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-[#111813] border border-[#28392e] rounded-xl w-full max-w-4xl overflow-hidden shadow-2xl"
            >
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-[#28392e] bg-[#16211a]">
                <h3 className="text-white font-bold text-lg">Modell-Priorität für {selectedAgent.name}</h3>
                <p className="text-[#9cbaa6] text-sm mt-1">Ziehe Modelle per Drag & Drop um die Reihenfolge zu ändern. Das erste Modell ist Primary.</p>
              </div>

              {/* Two Column Layout */}
              <div className="flex flex-col md:flex-row">
                {/* Left: Sortable Priority List */}
                <div className="md:w-1/2 border-b md:border-b-0 md:border-r border-[#28392e] p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="text-[10px] text-primary uppercase tracking-widest font-bold">Modell-Priorität (1-5)</h4>
                    <span className="text-[10px] text-[#9cbaa6]">{agentModelPriority.length}/5 Modelle</span>
                  </div>

                  <div className="min-h-[200px]">
                    <SortableModelList
                      models={agentModelPriority}
                      onReorder={setAgentModelPriority}
                      onRemove={removeModelFromPriority}
                      maxModels={5}
                      disabled={savingPriority}
                    />
                  </div>

                  {/* Info Box */}
                  <div className="mt-4 p-3 bg-[#0d120f] rounded-lg border border-[#28392e]">
                    <p className="text-[10px] text-[#5c856b]">
                      <span className="text-primary font-bold">Primary:</span> Wird zuerst verwendet
                    </p>
                    <p className="text-[10px] text-[#5c856b] mt-1">
                      <span className="text-[#9cbaa6] font-bold">Fallback 1-4:</span> Bei Fehler/Rate-Limit der Reihe nach
                    </p>
                  </div>
                </div>

                {/* Right: Available Models to Add */}
                <div className="md:w-1/2 flex flex-col">
                  {/* Filter */}
                  <div className="p-4 border-b border-[#28392e] space-y-2 bg-[#0d120f]">
                    <input
                      type="text"
                      placeholder="Search models..."
                      value={modalModelFilter}
                      onChange={(e) => setModalModelFilter(e.target.value)}
                      className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white placeholder-[#6b8f71] focus:outline-none focus:border-primary"
                    />
                    <select
                      value={modalProviderFilter}
                      onChange={(e) => setModalProviderFilter(e.target.value)}
                      className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary"
                    >
                      <option value="all">All Providers</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="openai">OpenAI</option>
                      <option value="google">Google</option>
                      <option value="meta-llama">Meta</option>
                      <option value="mistralai">Mistral</option>
                      <option value="qwen">Qwen</option>
                      <option value="nvidia">NVIDIA</option>
                      <option value="deepseek">DeepSeek</option>
                    </select>
                  </div>

                  {/* Model List */}
                  <div className="p-4 max-h-80 overflow-y-auto custom-scrollbar flex-1">
                    <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2">Free Models</div>
                    <div className="space-y-2 mb-4">
                      {availableModels.free_models
                        .filter(m => {
                          const matchesSearch = m.name.toLowerCase().includes(modalModelFilter.toLowerCase());
                          const matchesProvider = modalProviderFilter === 'all' || m.id.toLowerCase().includes(modalProviderFilter);
                          return matchesSearch && matchesProvider;
                        })
                        .slice(0, 30)
                        .map((model) => {
                          const isInList = agentModelPriority.includes(model.id);
                          return (
                            <button
                              key={model.id}
                              onClick={() => !isInList && addModelToPriority(model.id)}
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

                    {/* # ÄNDERUNG [31.01.2026]: Premium-Models auch im Premium-Modus anzeigen */}
                    {(config?.mode === 'production' || config?.mode === 'premium') && (
                      <>
                        <div className="text-[10px] text-yellow-400 uppercase tracking-widest font-bold mb-2">Premium Models</div>
                        <div className="space-y-2">
                          {availableModels.paid_models
                            .filter(m => {
                              const matchesSearch = m.name.toLowerCase().includes(modalModelFilter.toLowerCase());
                              const matchesProvider = modalProviderFilter === 'all' || m.id.toLowerCase().includes(modalProviderFilter);
                              return matchesSearch && matchesProvider;
                            })
                            .slice(0, 30)
                            .map((model) => {
                              const isInList = agentModelPriority.includes(model.id);
                              return (
                                <button
                                  key={model.id}
                                  onClick={() => !isInList && addModelToPriority(model.id)}
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
              <div className="px-6 py-4 border-t border-[#28392e] bg-[#0d120f] flex justify-between">
                <button
                  onClick={() => setShowModelSelector(false)}
                  className="px-4 py-2 rounded-lg border border-[#28392e] text-[#9cbaa6] hover:text-white hover:border-white/20 transition-colors"
                >
                  Abbrechen
                </button>
                <button
                  onClick={saveModelPriority}
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
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default MainframeHub;
