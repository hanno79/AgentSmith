/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.2
 * Beschreibung: Slider-Bereiche für Coder-Konfiguration, Research Timeout, Agent Timeout.
 *               Aus MainframeHub.jsx extrahiert (Regel 1).
 *
 * ÄNDERUNG 03.02.2026: Feature 10a - Token-Limit Slider hinzugefügt
 * ÄNDERUNG 07.02.2026: Token-Limit-Slider entfernt - jetzt pro Agent im ModelModal
 */

import React from 'react';
import { RefreshCw, Clock } from 'lucide-react';

const SliderControls = ({
  effectiveModelAttempts,
  effectiveMaxRetries,
  effectiveResearchTimeout,
  agentTimeout,
  onModelAttemptsChange,
  onMaxRetriesChange,
  onResearchTimeoutChange,
  onAgentTimeoutChange
}) => {
  const effectiveModelAttemptsSafe = Number.isFinite(Number(effectiveModelAttempts)) ? Number(effectiveModelAttempts) : 0;
  const effectiveMaxRetriesSafe = Number.isFinite(Number(effectiveMaxRetries)) ? Number(effectiveMaxRetries) : 1;
  const upperBound = effectiveMaxRetriesSafe - 1;
  const safeModelAttempts = effectiveModelAttemptsSafe < 1 ? 0 : effectiveModelAttemptsSafe;
  const safeUpperBound = Math.max(1, upperBound);
  const leftPercent = upperBound < 1 ? 0 : ((safeModelAttempts - 1) / safeUpperBound) * 100;
  const sliderMax = Math.max(1, upperBound);
  const sliderValue = effectiveModelAttemptsSafe < 1 ? 1 : Math.max(1, Math.min(effectiveModelAttemptsSafe, sliderMax));
  const isModelSliderDisabled = upperBound < 1;

  return (
    <>
      {/* Coder Konfiguration - Dual-Slider */}
      <div className="w-full bg-[#0d120f] border-t border-[#28392e] p-4">
        <div className="flex justify-between items-center mb-3">
          <h4 className="text-[#9cbaa6] text-xs font-bold uppercase tracking-widest flex items-center gap-2">
            <RefreshCw size={14} className="text-primary" />
            Coder Konfiguration
          </h4>
        </div>

        <div className="flex justify-between mb-3">
          <div className="text-center">
            <span className="text-amber-400 font-mono font-bold text-xl">{effectiveModelAttemptsSafe}</span>
            <p className="text-[9px] text-amber-400/70 uppercase">Modellwechsel</p>
          </div>
          <div className="text-center">
            <span className="text-primary font-mono font-bold text-xl">{effectiveMaxRetriesSafe}</span>
            <p className="text-[9px] text-primary/70 uppercase">Iterationen</p>
          </div>
        </div>

        <div className="bg-[#1b271f] p-3 rounded-lg border border-[#28392e]">
          <div className="relative h-10 flex items-center px-2">
            <div className="absolute left-2 right-2 h-2 bg-[#28392e] rounded-full" />
            <div
              className="absolute h-2 bg-gradient-to-r from-amber-500/60 to-primary/60 rounded-full"
              style={{
                left: `calc(${leftPercent}% + 8px)`,
                right: `calc(${(100 - leftPercent)}% + 8px)`
              }}
            />
            <input
              type="range"
              min="1"
              max={sliderMax}
              value={sliderValue}
              disabled={isModelSliderDisabled}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                onModelAttemptsChange(Math.min(val, upperBound));
              }}
              className="absolute inset-x-2 w-[calc(100%-16px)] dual-slider-left"
              style={{ zIndex: effectiveModelAttemptsSafe > effectiveMaxRetriesSafe - 10 ? 3 : 1, opacity: isModelSliderDisabled ? 0.5 : 1 }}
            />
            <input
              type="range"
              min="2"
              max="100"
              value={effectiveMaxRetriesSafe}
              onChange={(e) => {
                const newVal = Math.max(2, parseInt(e.target.value, 10));
                onMaxRetriesChange(newVal);
                const newUpperBound = newVal - 1;
                if (effectiveModelAttemptsSafe > 0 && effectiveModelAttemptsSafe >= newVal) {
                  onModelAttemptsChange(newUpperBound < 1 ? 0 : newUpperBound);
                } else if (effectiveModelAttemptsSafe === 0 && newUpperBound >= 1) {
                  onModelAttemptsChange(1);
                }
              }}
              className="absolute inset-x-2 w-[calc(100%-16px)] dual-slider-right"
              style={{ zIndex: effectiveModelAttemptsSafe > effectiveMaxRetriesSafe - 10 ? 1 : 3 }}
            />
          </div>

          <div className="flex justify-between mt-1 px-2">
            <span className="text-[10px] text-[#9cbaa6] font-mono">1</span>
            <span className="text-[10px] text-[#9cbaa6] font-mono">100</span>
          </div>

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

      {/* Research Timeout */}
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
              onChange={(e) => onResearchTimeoutChange(parseInt(e.target.value))}
              className="flex-1 mainframe-slider"
            />
            <span className="text-[10px] text-[#9cbaa6] font-mono w-8">60</span>
          </div>
          <p className="text-[10px] text-[#5c856b] mt-2 text-center">
            Maximale Zeit für Web-Recherche (in Minuten)
          </p>
        </div>
      </div>

      {/* Agent Timeout */}
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
              max="1800"
              step="30"
              value={agentTimeout}
              onChange={(e) => onAgentTimeoutChange(parseInt(e.target.value))}
              className="flex-1 mainframe-slider"
            />
            {/* ÄNDERUNG 02.02.2026: max von 600 (10 min) auf 1800 (30 min) erhöht für langsame Free-Modelle */}
            <span className="text-[10px] text-[#9cbaa6] font-mono w-8">30</span>
          </div>
          <p className="text-[10px] text-[#5c856b] mt-2 text-center">
            Maximale Zeit pro Agent-Operation (in Minuten)
          </p>
        </div>
      </div>

      {/* ÄNDERUNG 07.02.2026: Token-Limit-Slider entfernt - jetzt pro Agent im ModelModal */}
    </>
  );
};

export default SliderControls;
