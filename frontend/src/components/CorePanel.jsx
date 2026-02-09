/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Mittleres Panel – The Core, Environment Control, SliderControls.
 *               Aus MainframeHub.jsx extrahiert (Regel 1).
 */

import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, Box } from 'lucide-react';
import SliderControls from './SliderControls';

const CorePanel = ({
  config,
  agents,
  setMode,
  effectiveModelAttempts,
  effectiveMaxRetries,
  onModelAttemptsChange,
  onMaxRetriesChange,
  // AENDERUNG 06.02.2026: Docker-Toggle
  dockerEnabled,
  onDockerToggle
}) => {
  // ÄNDERUNG 01.02.2026: justify-start für Top-Alignment statt Mitte
  return (
    <div className="xl:col-span-4 flex flex-col gap-6">
      <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden relative flex flex-col items-center shadow-[0_0_30px_rgba(13,242,89,0.05)]">
        <div className="absolute inset-0 opacity-10 pointer-events-none"
          style={{ backgroundImage: 'radial-gradient(#0df259 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 bg-primary/20 rounded-full blur-[60px] animate-pulse pointer-events-none" />

        <div className="relative z-10 w-full flex flex-col items-center p-6">
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

          <div className="mt-6 grid grid-cols-2 gap-4 w-full max-w-xs">
            <div className="bg-[#0d120f] rounded-lg p-3 border border-[#28392e]">
              <div className="text-[10px] text-[#9cbaa6] uppercase mb-1">Active Agents</div>
              <div className="text-xl font-bold text-white">{agents?.length ?? 0}</div>
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

        {/* Environment Control - 3-Tier-Selector */}
        <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-6">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest">Environment Control</h4>
            <div className="flex gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'test' ? 'bg-primary' : 'bg-primary/20'}`} />
              <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'production' ? 'bg-yellow-500' : 'bg-yellow-500/20'}`} />
              <span className={`w-1.5 h-1.5 rounded-full ${config?.mode === 'premium' ? 'bg-amber-300' : 'bg-amber-300/20'}`} />
            </div>
          </div>

          <div className="relative bg-[#1b271f] p-2 rounded-lg border border-[#28392e]">
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

          <div className="mt-3 text-center text-[10px] text-[#9cbaa6]">
            {config?.mode === 'test' && 'Kostenlose Modelle - Ideal für Tests und Entwicklung'}
            {config?.mode === 'production' && 'Preis-Leistungs-Sieger - Beste Balance für den Alltag'}
            {config?.mode === 'premium' && 'Top-Premium-Modelle - Höchste Qualität ohne Kompromisse'}
          </div>
        </div>

        {/* AENDERUNG 06.02.2026: Docker-Isolation Toggle */}
        {onDockerToggle && (
          <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-6">
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                <Box size={14} className="text-cyan-400" />
                Docker-Isolation
              </h4>
              <span className={`w-1.5 h-1.5 rounded-full ${dockerEnabled ? 'bg-cyan-400' : 'bg-cyan-400/20'}`} />
            </div>

            <div className="relative bg-[#1b271f] p-2 rounded-lg border border-[#28392e]">
              <motion.div
                className={`absolute top-2 bottom-2 rounded-md ${
                  dockerEnabled
                    ? 'bg-gradient-to-br from-cyan-600/30 to-cyan-800/30 border border-cyan-400/50'
                    : 'bg-gradient-to-br from-[#4a6b56]/50 to-[#28392e]/50 border border-[#5c856b]/50'
                }`}
                initial={false}
                animate={{
                  left: dockerEnabled ? 'calc(50% + 4px)' : '8px',
                  width: 'calc(50% - 12px)'
                }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
              <div className="relative flex">
                <button
                  onClick={() => onDockerToggle(false)}
                  className={`flex-1 py-3 px-2 text-center transition-all z-10 rounded-md ${
                    !dockerEnabled ? '' : 'hover:bg-white/5'
                  }`}
                >
                  <div className={`font-bold text-sm transition-colors ${
                    !dockerEnabled ? 'text-[#9cbaa6]' : 'text-white/60'
                  }`}>AUS</div>
                </button>
                <button
                  onClick={() => onDockerToggle(true)}
                  className={`flex-1 py-3 px-2 text-center transition-all z-10 rounded-md ${
                    dockerEnabled ? '' : 'hover:bg-white/5'
                  }`}
                >
                  <div className={`font-bold text-sm transition-colors ${
                    dockerEnabled ? 'text-cyan-400' : 'text-white/60'
                  }`}>EIN</div>
                </button>
              </div>
            </div>

            <div className="mt-3 text-center text-[10px] text-[#9cbaa6]">
              {dockerEnabled
                ? 'Tests werden in isolierten Docker-Containern ausgefuehrt'
                : 'Tests werden direkt auf dem Host-System ausgefuehrt'}
            </div>
          </div>
        )}

        <SliderControls
          effectiveModelAttempts={effectiveModelAttempts}
          effectiveMaxRetries={effectiveMaxRetries}
          onModelAttemptsChange={onModelAttemptsChange}
          onMaxRetriesChange={onMaxRetriesChange}
        />
      </div>
    </div>
  );
};

export default CorePanel;
