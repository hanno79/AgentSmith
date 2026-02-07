/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Rechtes Panel – Model Registry mit Filter und Modell-Listen.
 *               Aus MainframeHub.jsx extrahiert (Regel 1).
 */

import React from 'react';
import { Database, Zap, DollarSign } from 'lucide-react';
import { PROVIDER_OPTIONS } from '../hooks/useModelFilter';

const ModelListPanel = ({
  modelFilter,
  onModelFilterChange,
  providerFilter,
  onProviderFilterChange,
  filteredFreeModels,
  filteredPaidModels,
  availableModels,
  providerOptions = PROVIDER_OPTIONS
}) => {
  const totalFiltered = (filteredFreeModels?.length ?? 0) + (filteredPaidModels?.length ?? 0);
  const totalAvailable = (availableModels?.free_models?.length ?? 0) + (availableModels?.paid_models?.length ?? 0);

  /* # ÄNDERUNG [01.02.2026]: Feste max-h für scrollbare Liste */
  return (
    <div className="xl:col-span-4 flex flex-col gap-4 max-h-[calc(100vh-160px)]">
      <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex flex-col shadow-2xl h-full">
        <div className="px-5 py-4 border-b border-[#28392e] bg-[#16211a] flex justify-between items-center">
          <h3 className="text-white font-bold tracking-wider uppercase flex items-center gap-2">
            <Database size={16} className="text-primary" />
            Model Registry
          </h3>
          <div className="px-2 py-0.5 bg-primary/20 text-primary text-[10px] font-mono rounded border border-primary/30">
            {totalFiltered} / {totalAvailable}
          </div>
        </div>

        <div className="p-3 border-b border-[#28392e] space-y-2 bg-[#0d120f]">
          <input
            type="text"
            placeholder="Search models..."
            value={modelFilter}
            onChange={(e) => onModelFilterChange(e.target.value)}
            className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white placeholder-[#6b8f71] focus:outline-none focus:border-primary"
          />
          <select
            value={providerFilter}
            onChange={(e) => onProviderFilterChange(e.target.value)}
            className="w-full bg-[#1b271f] border border-[#28392e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary"
          >
            {providerOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* ÄNDERUNG 01.02.2026: Inline-Style entfernt, flex-1 für responsive Höhe */}
        <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
          <div className="mb-4">
            <div className="text-[10px] text-primary uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
              <Zap size={12} />
              Free Tier
            </div>
            <div className="space-y-2">
              {filteredFreeModels.slice(0, 50).map((model) => (
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

          <div>
            <div className="text-[10px] text-yellow-400 uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
              <DollarSign size={12} />
              Premium Tier
            </div>
            <div className="space-y-2">
              {filteredPaidModels.slice(0, 50).map((model) => (
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

        <div className="border-t border-[#28392e] bg-[#0d120f] p-3 flex justify-end items-center text-[10px] font-mono text-[#5c856b]">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <span>LIVE_SYNC</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModelListPanel;
