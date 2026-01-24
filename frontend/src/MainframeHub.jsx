import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
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
  DollarSign
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const MainframeHub = () => {
  const [config, setConfig] = useState(null);
  const [agents, setAgents] = useState([]);
  const [availableModels, setAvailableModels] = useState({ free_models: [], paid_models: [] });
  const [routerStatus, setRouterStatus] = useState({ rate_limited_models: {}, usage_stats: {} });
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [serverTime, setServerTime] = useState(new Date());
  const [maxRetries, setMaxRetries] = useState(5);

  // Fetch all data on mount
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => setServerTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    setLoading(true);
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
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = async () => {
    if (!config) return;
    const newMode = config.mode === 'test' ? 'production' : 'test';
    try {
      await axios.put(`${API_BASE}/config/mode`, { mode: newMode });
      setConfig({ ...config, mode: newMode });
      fetchData(); // Refresh agents with new mode's models
    } catch (err) {
      console.error('Failed to toggle mode:', err);
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

  const clearRateLimits = async () => {
    try {
      await axios.post(`${API_BASE}/models/clear-rate-limits`);
      fetchData();
    } catch (err) {
      console.error('Failed to clear rate limits:', err);
    }
  };

  const updateMaxRetries = async (value) => {
    setMaxRetries(value);
    try {
      await axios.put(`${API_BASE}/config/max-retries`, { max_retries: value });
    } catch (err) {
      console.error('Failed to update max retries:', err);
    }
  };

  const getModelDisplayName = (modelId) => {
    // Handle case where modelId is an object (nested config with primary/fallback)
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

      {/* Main Content */}
      <main className="flex-1 overflow-hidden p-4 md:p-6 lg:p-8">
        <div className="h-full grid grid-cols-1 xl:grid-cols-12 gap-6">

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
                    }}
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
                    <div className={`text-xl font-bold ${config?.mode === 'production' ? 'text-yellow-400' : 'text-primary'}`}>
                      {config?.mode?.toUpperCase()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Environment Control */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-6">
                <div className="flex justify-between items-center mb-4">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest">Environment Control</h4>
                  <div className="flex gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'test' ? 'bg-primary' : 'bg-primary/20'}`} />
                    <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'production' ? 'bg-yellow-500' : 'bg-yellow-500/20'}`} />
                  </div>
                </div>

                <div className="flex items-center justify-between gap-4 bg-[#1b271f] p-4 rounded-lg border border-[#28392e]">
                  <div className={`text-center w-1/3 transition-opacity ${config?.mode !== 'test' ? 'opacity-40' : ''}`}>
                    <div className="text-white font-bold text-sm mb-1">TEST</div>
                    <div className="text-[10px] text-[#9cbaa6] uppercase">Free Models</div>
                  </div>

                  {/* Industrial Switch */}
                  <button
                    onClick={toggleMode}
                    className="relative w-24 h-12 bg-black rounded-full border-2 border-[#3b5443] shadow-inner flex items-center p-1 cursor-pointer"
                  >
                    <motion.div
                      animate={{ x: config?.mode === 'production' ? 48 : 0 }}
                      transition={{ type: "spring", stiffness: 500, damping: 30 }}
                      className={`w-10 h-10 rounded-full shadow-lg border ${
                        config?.mode === 'production'
                          ? 'bg-gradient-to-br from-yellow-600 to-yellow-800 border-yellow-500'
                          : 'bg-gradient-to-br from-[#4a6b56] to-[#28392e] border-[#5c856b]'
                      }`}
                    />
                  </button>

                  <div className={`text-center w-1/3 transition-opacity ${config?.mode !== 'production' ? 'opacity-40' : ''}`}>
                    <div className={`font-bold text-sm mb-1 ${config?.mode === 'production' ? 'text-yellow-400' : 'text-white'}`}>PROD</div>
                    <div className="text-[10px] text-[#9cbaa6] uppercase">Premium</div>
                  </div>
                </div>
              </div>

              {/* System Settings - Max Retries */}
              <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                    <RefreshCw size={14} className="text-primary" />
                    Retry Configuration
                  </h4>
                  <span className="text-primary font-mono font-bold text-lg">{maxRetries}</span>
                </div>

                <div className="bg-[#1b271f] p-3 rounded-lg border border-[#28392e]">
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-6">1</span>
                    <input
                      type="range"
                      min="1"
                      max="100"
                      value={maxRetries}
                      onChange={(e) => updateMaxRetries(parseInt(e.target.value))}
                      className="flex-1 mainframe-slider"
                    />
                    <span className="text-[10px] text-[#9cbaa6] font-mono w-8">100</span>
                  </div>
                  <p className="text-[10px] text-[#5c856b] mt-2 text-center">
                    Maximum retry attempts for agent operations
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Available Models */}
          <div className="xl:col-span-4 flex flex-col gap-4">
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex-1 flex flex-col shadow-2xl">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Database size={16} className="text-primary" />
                  Model Registry
                </h3>
                <div className="px-2 py-0.5 bg-primary/20 text-primary text-[10px] font-mono rounded border border-primary/30">
                  {availableModels.free_models.length + availableModels.paid_models.length} MODELS
                </div>
              </div>

              <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
                {/* Free Models */}
                <div className="mb-4">
                  <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
                    <Zap size={12} />
                    Free Tier
                  </div>
                  <div className="space-y-2">
                    {availableModels.free_models.map((model) => (
                      <div
                        key={model.id}
                        className="bg-[#1b271f] border border-[#28392e] rounded-lg p-3 hover:border-primary/30 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="text-white font-bold text-sm">{model.name}</span>
                          <span className="text-[10px] text-primary bg-primary/10 px-2 py-0.5 rounded">{model.strength}</span>
                        </div>
                        <div className="text-[10px] text-[#9cbaa6]">{model.provider}</div>
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
                    {availableModels.paid_models.map((model) => (
                      <div
                        key={model.id}
                        className="bg-[#1b271f] border border-[#28392e] rounded-lg p-3 hover:border-yellow-500/30 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="text-white font-bold text-sm">{model.name}</span>
                          <span className="text-[10px] text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded">{model.strength}</span>
                        </div>
                        <div className="text-[10px] text-[#9cbaa6]">{model.provider}</div>
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

      {/* Model Selector Modal */}
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
              className="bg-[#111813] border border-[#28392e] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl"
            >
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-[#28392e] bg-[#16211a]">
                <h3 className="text-white font-bold text-lg">Select Model for {selectedAgent.name}</h3>
                <p className="text-[#9cbaa6] text-sm mt-1">{selectedAgent.description}</p>
              </div>

              {/* Model Options */}
              <div className="p-4 max-h-96 overflow-y-auto custom-scrollbar">
                <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2">Free Models</div>
                <div className="space-y-2 mb-4">
                  {availableModels.free_models.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => updateAgentModel(selectedAgent.role, model.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        selectedAgent.model === model.id
                          ? 'bg-primary/20 border-primary'
                          : 'bg-[#1b271f] border-[#28392e] hover:border-primary/50'
                      }`}
                    >
                      <div className="flex justify-between items-center">
                        <div>
                          <span className="text-white font-bold">{model.name}</span>
                          <span className="text-[#9cbaa6] text-sm ml-2">({model.provider})</span>
                        </div>
                        {selectedAgent.model === model.id && (
                          <Check size={18} className="text-primary" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>

                {config?.mode === 'production' && (
                  <>
                    <div className="text-[10px] text-yellow-400 uppercase tracking-widest font-bold mb-2">Premium Models</div>
                    <div className="space-y-2">
                      {availableModels.paid_models.map((model) => (
                        <button
                          key={model.id}
                          onClick={() => updateAgentModel(selectedAgent.role, model.id)}
                          className={`w-full text-left p-3 rounded-lg border transition-all ${
                            selectedAgent.model === model.id
                              ? 'bg-yellow-400/20 border-yellow-400'
                              : 'bg-[#1b271f] border-[#28392e] hover:border-yellow-400/50'
                          }`}
                        >
                          <div className="flex justify-between items-center">
                            <div>
                              <span className="text-white font-bold">{model.name}</span>
                              <span className="text-[#9cbaa6] text-sm ml-2">({model.provider})</span>
                            </div>
                            {selectedAgent.model === model.id && (
                              <Check size={18} className="text-yellow-400" />
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-4 border-t border-[#28392e] bg-[#0d120f] flex justify-end">
                <button
                  onClick={() => setShowModelSelector(false)}
                  className="px-4 py-2 rounded-lg border border-[#28392e] text-[#9cbaa6] hover:text-white hover:border-white/20 transition-colors"
                >
                  Cancel
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
