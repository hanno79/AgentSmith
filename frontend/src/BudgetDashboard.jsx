/**
 * Author: rahn
 * Datum: 24.01.2026
 * Version: 1.0
 * Beschreibung: Budget Dashboard - Übersicht über Kosten, Nutzung und Budgetstatus.
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import {
  Flame,
  Wallet,
  Calendar,
  BarChart3,
  Grid,
  Bell,
  Lock,
  TrendingUp,
  Download,
  Plus,
  CreditCard,
  Zap,
  Terminal,
  RefreshCw,
  Lightbulb,
  AlertTriangle,
  Info,
  Database
} from 'lucide-react';
import { API_BASE } from './constants/config';

// Leere Default-Zustände (KEINE Mock-Daten)
const EMPTY_BUDGET_STATS = {
  total_budget: 10000,
  remaining: 10000,
  burn_rate_daily: 0,
  burn_rate_change: 0,
  projected_runout: "N/A",
  days_remaining: 0,
  data_source: "no_data"
};

// ÄNDERUNG 03.02.2026: Konsistente Währungsformatierung mit Punkt als Dezimaltrenner
const formatCurrency = (value, decimals = 0) => {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
};

const BudgetDashboard = () => {
  const [budgetStats, setBudgetStats] = useState(EMPTY_BUDGET_STATS);
  const [agentCosts, setAgentCosts] = useState([]);
  const [agentCostsDataSource, setAgentCostsDataSource] = useState("no_data");
  const [heatmapData, setHeatmapData] = useState({ agents: [], hours: [], data: [], data_source: "no_data" });
  const [recommendations, setRecommendations] = useState([]);
  // ÄNDERUNG 03.02.2026: Neue Default-Werte für kleinere Budget-Bereiche
  const [budgetCaps, setBudgetCaps] = useState({ monthly: 100, daily: 20 });
  // ÄNDERUNG 03.02.2026: Project Budget State für Gesamtbudget-Einstellung
  const [projectBudget, setProjectBudget] = useState(1000);
  const [autoPause, setAutoPause] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Echte Daten von API abrufen (KEINE Mock-Daten als Fallback)
  useEffect(() => {
    fetchBudgetData();
  }, []);

  const fetchBudgetData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, costsRes, heatmapRes, capsRes, recsRes] = await Promise.all([
        axios.get(`${API_BASE}/budget/stats`),
        axios.get(`${API_BASE}/budget/costs/agents`),
        axios.get(`${API_BASE}/budget/heatmap`),
        axios.get(`${API_BASE}/budget/caps`),
        axios.get(`${API_BASE}/budget/recommendations`)
      ]);

      setBudgetStats(statsRes.data);
      setAgentCosts(costsRes.data.agents || []);
      setAgentCostsDataSource(costsRes.data.data_source || "no_data");
      setHeatmapData(heatmapRes.data);
      setBudgetCaps({ monthly: capsRes.data.monthly, daily: capsRes.data.daily });
      // ÄNDERUNG 03.02.2026: Project Budget aus API laden (total_budget = monthly_cap)
      setProjectBudget(capsRes.data.monthly);
      setAutoPause(capsRes.data.auto_pause);
      setRecommendations(recsRes.data.recommendations || []);
    } catch (err) {
      console.error('Failed to fetch budget data:', err);
      setError('Verbindung zum Backend fehlgeschlagen. Stellen Sie sicher, dass der Server läuft.');
    } finally {
      setLoading(false);
    }
  };

  const handleCapChange = async (type, value) => {
    const prevCaps = budgetCaps;
    const newCaps = { ...budgetCaps, [type]: value };
    setBudgetCaps(newCaps);
    try {
      await axios.put(`${API_BASE}/budget/caps`, { ...newCaps, auto_pause: autoPause });
    } catch (err) {
      console.error('Failed to update budget caps:', err);
      // Rollback bei Fehler
      setBudgetCaps(prevCaps);
    }
  };

  const handleAutoPauseToggle = async () => {
    const prevAutoPause = autoPause;
    const newValue = !autoPause;
    setAutoPause(newValue);
    try {
      await axios.put(`${API_BASE}/budget/caps`, { ...budgetCaps, auto_pause: newValue });
    } catch (err) {
      console.error('Failed to update auto-pause:', err);
      // Rollback bei Fehler
      setAutoPause(prevAutoPause);
    }
  };

  // ÄNDERUNG 03.02.2026: Handler für Project Budget Änderungen
  const handleProjectBudgetChange = async (value) => {
    const prevBudget = projectBudget;
    setProjectBudget(value);
    try {
      await axios.put(`${API_BASE}/budget/caps`, {
        monthly: value,  // total_budget = monthly_cap
        daily: budgetCaps.daily,
        auto_pause: autoPause
      });
      // Stats neu laden um "Remaining Budget" zu aktualisieren
      fetchBudgetData();
    } catch (err) {
      console.error('Fehler beim Setzen des Project Budgets:', err);
      // Rollback bei Fehler
      setProjectBudget(prevBudget);
    }
  };

  const budgetPercentage = budgetStats.total_budget > 0
    ? (budgetStats.remaining / budgetStats.total_budget) * 100
    : 100;

  const hasData = budgetStats.data_source === "real";

  // Loading State
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw size={48} className="text-[#0df259] animate-spin" />
          <span className="text-[#9cbaa6] font-mono uppercase tracking-wider">Loading Budget Data...</span>
        </div>
      </div>
    );
  }

  // Error State
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <AlertTriangle size={48} className="text-red-500" />
          <span className="text-white font-bold text-lg">Connection Error</span>
          <span className="text-[#9cbaa6] text-sm">{error}</span>
          <button
            onClick={fetchBudgetData}
            className="mt-4 px-4 py-2 bg-[#0df259]/20 border border-[#0df259]/30 rounded text-[#0df259] font-bold uppercase tracking-wider hover:bg-[#0df259]/30 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No Data Empty State Component
  const NoDataState = ({ icon: Icon, title, description }) => (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <Icon size={48} className="text-[#28392e] mb-4" />
      <span className="text-[#5c856b] font-bold uppercase tracking-wider text-sm">{title}</span>
      <span className="text-[#3d5445] text-xs mt-2 max-w-xs">{description}</span>
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto overflow-x-hidden page-scrollbar bg-[#0a0a0a] relative">
      {/* Scanlines Effect */}
      <div
        className="fixed inset-0 pointer-events-none z-50 opacity-[0.03]"
        style={{
          background: `linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1))`,
          backgroundSize: '100% 4px'
        }}
      />

      <main className="flex flex-col p-4 md:p-8 lg:p-10 max-w-[1600px] mx-auto w-full gap-6">
        {/* Header */}
        <div className="flex flex-wrap justify-between items-end gap-6 mb-2 border-b border-[#28392e] pb-6">
          <div className="flex min-w-72 flex-col gap-2">
            <div className="flex items-center gap-2 text-[#0df259] text-xs tracking-widest uppercase font-mono mb-1">
              <span className={`w-2 h-2 rounded-full ${hasData ? 'bg-[#0df259] animate-pulse' : 'bg-[#5c856b]'}`}></span>
              {hasData ? 'Finance Stream Active' : 'Awaiting Data'}
            </div>
            <h1 className="text-white text-4xl md:text-5xl font-black leading-tight tracking-[-0.033em] uppercase">
              Project Budget // <span className="text-[#0df259]/60">Dashboard</span>
            </h1>
            <p className="text-[#9cbaa6] text-base font-normal leading-normal max-w-2xl mt-2">
              {hasData
                ? 'Real-time cost analysis and burn rate tracking for multi-agent operations.'
                : 'Noch keine Nutzungsdaten. Daten werden nach Agent-Runs automatisch erfasst.'}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={fetchBudgetData}
              className="flex items-center gap-2 px-4 py-2 rounded border border-[#28392e] bg-[#16211a] hover:bg-[#1f2e24] transition-colors text-xs uppercase font-bold tracking-wider text-[#9cbaa6]"
            >
              <RefreshCw size={14} /> Refresh
            </button>
            <button className="flex items-center gap-2 px-4 py-2 rounded border border-[#28392e] bg-[#16211a] hover:bg-[#1f2e24] transition-colors text-xs uppercase font-bold tracking-wider text-[#9cbaa6]">
              <Download size={14} /> Export CSV
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Burn Rate Card */}
          <motion.div
            whileHover={{ scale: 1.01 }}
            className="bg-[#111813] rounded-xl border border-[#28392e] p-6 relative overflow-hidden group"
          >
            <div className="absolute right-0 top-0 p-4 opacity-20 group-hover:opacity-40 transition-opacity">
              <Flame size={64} className="text-[#0df259]" />
            </div>
            <h3 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest mb-2">Total Burn Rate</h3>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-4xl text-white font-mono font-bold">${formatCurrency(budgetStats.burn_rate_daily, 2)}</span>
              <span className="text-sm text-[#9cbaa6] font-mono">/ day</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${budgetStats.burn_rate_change > 0 ? 'text-red-400 bg-red-400/10' : 'text-green-400 bg-green-400/10'}`}>
                <TrendingUp size={12} /> {budgetStats.burn_rate_change > 0 ? '+' : ''}{budgetStats.burn_rate_change}%
              </span>
              <span className="text-[#5c856b]">vs last 24h</span>
            </div>
            <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500/50 to-transparent"></div>
          </motion.div>

          {/* Remaining Budget Card */}
          <motion.div
            whileHover={{ scale: 1.01 }}
            className="bg-[#111813] rounded-xl border border-[#28392e] p-6 relative overflow-hidden group"
          >
            <div className="absolute right-0 top-0 p-4 opacity-20 group-hover:opacity-40 transition-opacity">
              <Wallet size={64} className="text-[#0df259]" />
            </div>
            <h3 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest mb-2">Remaining Budget</h3>
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-4xl text-white font-mono font-bold">${formatCurrency(budgetStats.remaining, 2)}</span>
              <span className="text-sm text-[#5c856b] font-mono">/ ${formatCurrency(budgetStats.total_budget)}</span>
            </div>
            <div className="w-full bg-[#0a0a0a] rounded-full h-2 border border-[#28392e]">
              <div
                className="bg-[#0df259] h-1.5 rounded-full relative transition-all duration-500"
                style={{ width: `${budgetPercentage}%` }}
              >
                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full shadow-[0_0_10px_#fff]"></div>
              </div>
            </div>
          </motion.div>

          {/* Projected Runout Card */}
          <motion.div
            whileHover={{ scale: 1.01 }}
            className="bg-[#111813] rounded-xl border border-[#28392e] p-6 relative overflow-hidden group"
          >
            <div className="absolute right-0 top-0 p-4 opacity-20 group-hover:opacity-40 transition-opacity">
              <Calendar size={64} className="text-[#0df259]" />
            </div>
            <h3 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest mb-2">Projected Runout</h3>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-4xl text-white font-mono font-bold">
                {budgetStats.projected_runout && budgetStats.projected_runout !== "N/A"
                  ? new Date(budgetStats.projected_runout).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                  : 'N/A'}
              </span>
              <span className="text-sm text-[#9cbaa6] font-mono">
                {budgetStats.projected_runout && budgetStats.projected_runout !== "N/A"
                  ? new Date(budgetStats.projected_runout).getFullYear()
                  : ''}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center text-[#0df259] bg-[#0df259]/10 px-1.5 py-0.5 rounded border border-[#0df259]/20">
                {budgetStats.days_remaining} Days Remaining
              </span>
            </div>
            <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#0df259]/50 to-transparent"></div>
          </motion.div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Left Column - Charts */}
          <div className="xl:col-span-8 flex flex-col gap-6">
            {/* Cost by Agent */}
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden shadow-lg">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <BarChart3 size={16} className="text-[#0df259]" />
                  Cost by Agent
                </h3>
                <div className="flex gap-2 text-[10px] font-mono text-[#9cbaa6]">
                  <span className="px-2 py-1 rounded bg-black border border-[#28392e]">
                    {agentCostsDataSource === "real" ? "ECHTE DATEN" : "KEINE DATEN"}
                  </span>
                </div>
              </div>
              <div className="p-6 relative" style={{ backgroundImage: 'linear-gradient(rgba(40, 57, 46, 0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(40, 57, 46, 0.3) 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
                {agentCosts.length > 0 ? (
                  <div className="flex flex-col gap-5 font-mono text-sm">
                    {agentCosts.map((agent, index) => (
                      <div key={agent.name} className="flex items-center gap-4 group">
                        <div className="w-24 text-[#9cbaa6] text-xs uppercase tracking-wider text-right group-hover:text-white transition-colors">
                          {agent.name}
                        </div>
                        <div className="flex-1 h-8 bg-[#0a0f0c] rounded border border-[#28392e] relative overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${agent.percentage}%` }}
                            transition={{ duration: 0.8, delay: index * 0.1 }}
                            className="absolute top-0 left-0 bottom-0 bg-[#0df259]/80 group-hover:bg-[#0df259] transition-all duration-500 rounded-r flex items-center justify-end px-2"
                          >
                            <span className="text-[#0a0a0a] font-bold text-xs opacity-0 group-hover:opacity-100 transition-opacity">
                              ${formatCurrency(agent.cost, 2)}
                            </span>
                          </motion.div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <NoDataState
                    icon={BarChart3}
                    title="Keine Kosten-Daten"
                    description="Agent-Kosten werden nach der ersten Nutzung hier angezeigt."
                  />
                )}
              </div>
            </div>

            {/* Token Consumption Heatmap */}
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden shadow-lg flex-1">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Grid size={16} className="text-[#0df259]" />
                  Token Consumption Heatmap (24h)
                </h3>
                <div className="flex items-center gap-2 text-[10px] text-[#9cbaa6] uppercase">
                  {heatmapData.data_source === "real" ? (
                    <>
                      <span>Low</span>
                      <div className="flex gap-0.5">
                        <div className="w-3 h-3 bg-[#0df259]/10 rounded-sm"></div>
                        <div className="w-3 h-3 bg-[#0df259]/40 rounded-sm"></div>
                        <div className="w-3 h-3 bg-[#0df259]/70 rounded-sm"></div>
                        <div className="w-3 h-3 bg-[#0df259] rounded-sm"></div>
                      </div>
                      <span>High</span>
                    </>
                  ) : (
                    <span className="px-2 py-1 rounded bg-black border border-[#28392e]">KEINE DATEN</span>
                  )}
                </div>
              </div>
              <div className="p-6 overflow-x-auto">
                {heatmapData.agents && heatmapData.agents.length > 0 ? (
                  <div className="flex flex-col gap-1 min-w-[600px]">
                    {/* Time labels */}
                    <div className="grid grid-cols-12 gap-1 mb-1 text-[10px] font-mono text-[#5c856b] ml-20">
                      {['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'].map(time => (
                        <div key={time} className="text-center">{time}</div>
                      ))}
                    </div>

                    {/* Heatmap rows */}
                    {heatmapData.agents.map((agent, agentIdx) => (
                      <div key={agent} className="flex items-center gap-2 mt-2">
                        <span className="w-16 text-[10px] text-[#9cbaa6] font-mono uppercase text-right">{agent}</span>
                        <div className="flex-1 grid grid-cols-24 gap-1 h-8">
                          {heatmapData.data[agentIdx]?.map((intensity, hourIdx) => (
                            <div
                              key={hourIdx}
                              className="rounded-sm hover:ring-1 hover:ring-[#0df259] transition-all cursor-pointer"
                              style={{
                                backgroundColor: `rgba(13, 242, 89, ${intensity})`,
                                boxShadow: intensity > 0.8 ? '0 0 5px #0df259' : 'none'
                              }}
                              title={`${agent} - ${hourIdx}:00 - ${Math.round(intensity * 100)}% activity`}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <NoDataState
                    icon={Grid}
                    title="Keine Heatmap-Daten"
                    description="Token-Nutzung wird nach Agent-Aktivität in den letzten 24h angezeigt."
                  />
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Optimization & Caps */}
          <div className="xl:col-span-4 flex flex-col gap-6">
            {/* Smart Optimization */}
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden shadow-2xl">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Bell size={16} className="text-yellow-400" />
                  Smart Optimization
                </h3>
                {recommendations.length > 0 && recommendations.some(r => r.type !== 'info') && (
                  <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
                )}
              </div>
              <div className="p-4 flex flex-col gap-3">
                {recommendations.length > 0 ? (
                  recommendations.map((rec, idx) => (
                    <div
                      key={idx}
                      className={`bg-[#1b271f] border border-[#28392e] rounded-lg p-3 hover:border-[#0df259]/50 transition-colors cursor-pointer group ${rec.type === 'info' ? 'opacity-70' : ''}`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                          rec.type === 'recommendation' ? 'bg-[#0df259]/10 text-[#0df259] border-[#0df259]/20' :
                          rec.type === 'warning' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' :
                          rec.type === 'critical' ? 'bg-red-500/10 text-red-500 border-red-500/20' :
                          'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        }`}>
                          {rec.type === 'recommendation' ? 'Empfehlung' :
                           rec.type === 'warning' ? 'Warnung' :
                           rec.type === 'critical' ? 'Kritisch' : 'Info'}
                        </span>
                        {rec.title && <span className="text-white text-xs font-bold">{rec.title}</span>}
                      </div>
                      <p className="text-[#9cbaa6] text-xs leading-relaxed mb-3">
                        {rec.agent && <span className="text-white font-bold">{rec.agent}: </span>}{rec.description}
                      </p>
                      {rec.type === 'recommendation' && (
                        <button className="w-full py-1.5 bg-[#0a0f0c] border border-[#28392e] text-[#9cbaa6] text-xs uppercase font-bold hover:bg-[#0df259] hover:text-[#0a0a0a] transition-colors rounded">
                          Fix anwenden
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  <NoDataState
                    icon={Lightbulb}
                    title="Keine Empfehlungen"
                    description="Empfehlungen erscheinen basierend auf Nutzungsmustern nach einigen Agent-Runs."
                  />
                )}
              </div>
            </div>

            {/* Hard Budget Caps */}
            <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden shadow-2xl flex-1">
              <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a]">
                <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
                  <Lock size={16} className="text-red-500" />
                  Hard Budget Caps
                </h3>
              </div>
              <div className="p-6 flex flex-col gap-6">
                {/* Project Budget - ÄNDERUNG 03.02.2026: Neuer Slider für Gesamtbudget */}
                <div className="flex flex-col gap-2 pb-4 border-b border-[#28392e]">
                  <div className="flex justify-between text-xs font-mono uppercase text-[#9cbaa6] mb-1">
                    <span>Project Budget</span>
                    <span className="text-white font-bold">${formatCurrency(projectBudget)}</span>
                  </div>
                  <div className="relative w-full h-8 flex items-center">
                    <input
                      type="range"
                      min="10"
                      max="10000"
                      step="10"
                      value={projectBudget}
                      onChange={(e) => handleProjectBudgetChange(parseInt(e.target.value))}
                      className="w-full z-10 relative cursor-pointer"
                      style={{
                        WebkitAppearance: 'none',
                        background: 'transparent'
                      }}
                    />
                    <div className="absolute top-1/2 left-0 w-full h-1 bg-[#28392e] -translate-y-1/2 rounded pointer-events-none"></div>
                    <div
                      className="absolute top-1/2 left-0 h-1 bg-[#0df259]/50 -translate-y-1/2 rounded pointer-events-none transition-all"
                      style={{ width: `${((projectBudget - 10) / 9990) * 100}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-[10px] text-[#5c856b]">
                    <span>$10</span>
                    <span>$10k</span>
                  </div>
                </div>

                {/* Monthly Cap - ÄNDERUNG 03.02.2026: Angepasst für kleinere Budgets */}
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-mono uppercase text-[#9cbaa6] mb-1">
                    <span>Global Monthly Cap</span>
                    <span className="text-white font-bold">${formatCurrency(budgetCaps.monthly)}</span>
                  </div>
                  <div className="relative w-full h-8 flex items-center">
                    <input
                      type="range"
                      min="10"
                      max="1000"
                      step="10"
                      value={budgetCaps.monthly}
                      onChange={(e) => handleCapChange('monthly', parseInt(e.target.value))}
                      className="w-full z-10 relative cursor-pointer"
                      style={{
                        WebkitAppearance: 'none',
                        background: 'transparent'
                      }}
                    />
                    <div className="absolute top-1/2 left-0 w-full h-1 bg-[#28392e] -translate-y-1/2 rounded pointer-events-none"></div>
                    <div
                      className="absolute top-1/2 left-0 h-1 bg-[#0df259]/50 -translate-y-1/2 rounded pointer-events-none transition-all"
                      style={{ width: `${((budgetCaps.monthly - 10) / 990) * 100}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-[10px] text-[#5c856b]">
                    <span>$10</span>
                    <span>$1k</span>
                  </div>
                </div>

                {/* Daily Cap - ÄNDERUNG 03.02.2026: Angepasst für kleinere Budgets */}
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-mono uppercase text-[#9cbaa6] mb-1">
                    <span>Daily Burst Cap</span>
                    <span className="text-white font-bold">${formatCurrency(budgetCaps.daily)}</span>
                  </div>
                  <div className="relative w-full h-8 flex items-center">
                    <input
                      type="range"
                      min="5"
                      max="500"
                      step="5"
                      value={budgetCaps.daily}
                      onChange={(e) => handleCapChange('daily', parseInt(e.target.value))}
                      className="w-full z-10 relative cursor-pointer"
                      style={{
                        WebkitAppearance: 'none',
                        background: 'transparent'
                      }}
                    />
                    <div className="absolute top-1/2 left-0 w-full h-1 bg-[#28392e] -translate-y-1/2 rounded pointer-events-none"></div>
                    <div
                      className="absolute top-1/2 left-0 h-1 bg-[#0df259]/50 -translate-y-1/2 rounded pointer-events-none transition-all"
                      style={{ width: `${((budgetCaps.daily - 5) / 495) * 100}%` }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-[10px] text-[#5c856b]">
                    <span>$5</span>
                    <span>$500</span>
                  </div>
                </div>

                {/* Auto-Pause Toggle */}
                <div className="mt-4 pt-4 border-t border-[#28392e] flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-white font-bold text-sm">Auto-Pause Project</span>
                    <span className="text-[10px] text-[#9cbaa6] uppercase">Halt agents if cap reached</span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoPause}
                      onChange={handleAutoPauseToggle}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-[#28392e] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-500"></div>
                  </label>
                </div>

                {autoPause && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-[10px] text-red-400 font-mono mt-2">
                    WARNING: Enabling auto-pause may interrupt active inference chains.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer Stats */}
        <footer className="mt-4 border-t border-[#28392e] pt-4 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-[#5c856b]">
          <div className="flex gap-6 uppercase tracking-wider font-bold">
            <div className="flex items-center gap-2">
              <CreditCard size={14} />
              <span>
                Est. Month End: {hasData
                  ? `$${formatCurrency(budgetStats.burn_rate_daily * 30)}`
                  : 'N/A'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Database size={14} />
              <span>
                {hasData
                  ? `${budgetStats.total_records || 0} Records`
                  : 'Awaiting Data'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Zap size={14} />
              <span>
                Data: {hasData ? 'REAL' : 'NONE'}
              </span>
            </div>
          </div>
          <div className="font-mono">
            Agent Smith OS v4.0.2 &copy; {new Date().getFullYear()}
          </div>
        </footer>
      </main>

      {/* Decorative background */}
      <div
        className="fixed bottom-0 left-0 w-full h-[30vh] pointer-events-none z-0 opacity-10"
        style={{ background: 'repeating-linear-gradient(45deg, transparent, transparent 10px, #0df259 10px, #0df259 11px)' }}
      />

    </div>
  );
};

export default BudgetDashboard;
