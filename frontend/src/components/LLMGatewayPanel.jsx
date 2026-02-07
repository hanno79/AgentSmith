/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: Linkes Panel – LLM Gateway [Agents] mit Agent-Liste und Rate-Limits.
 *               Aus MainframeHub.jsx extrahiert (Regel 1).
 * # ÄNDERUNG [01.02.2026]: max-h für begrenzte Höhe mit Scroll – Begrenzung der Panel-Höhe und Overflow-Scrolling
 */

import React from 'react';
import { motion } from 'framer-motion';
import { Server, Clock } from 'lucide-react';

const noop = () => {};
const LLMGatewayPanel = ({
  agents = [],
  routerStatus = { rate_limited_models: {} },
  onAgentClick = noop,
  getModelDisplayName = (m) => m || '',
  isModelRateLimited = () => false,
  onClearRateLimits = noop
}) => {
  const safeRateLimited = routerStatus?.rate_limited_models ?? {};
  const handleAgentClick = (agent) => {
    try {
      onAgentClick(agent);
    } catch (e) {
      const ts = new Date().toISOString();
      console.error(`[${ts}] [ERROR] [LLMGatewayPanel] - onAgentClick Fehler: ${e?.message ?? e}`);
    }
  };
  return (
    <div className="xl:col-span-4 flex flex-col gap-4 max-h-[calc(100vh-160px)]">
      <div className="bg-[#111813] rounded-xl border border-[#28392e] overflow-hidden flex flex-col shadow-2xl h-full">
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
          <div className="grid grid-cols-12 gap-2 text-[10px] text-[#9cbaa6] font-mono uppercase px-3 mb-1">
            <div className="col-span-5">Agent</div>
            <div className="col-span-4">Model</div>
            <div className="col-span-3 text-right">Status</div>
          </div>

          {/* Performance: map über agents – bei großer Liste ggf. Memoization/Virtualisierung */}
          {(agents || []).map((agent) => (
            <motion.div
              key={agent.role}
              whileHover={{ scale: 1.01 }}
              onClick={() => handleAgentClick(agent)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleAgentClick(agent);
                }
              }}
              role="button"
              tabIndex={0}
              aria-label={`${agent.name ?? ''} - ${agent.role ?? ''} - ${isModelRateLimited(agent?.model) ? 'Rate Limited' : 'Ready'}`}
              className={`group relative bg-[#1b271f] hover:bg-[#233328] border border-[#28392e] hover:border-primary/50 rounded-lg p-3 transition-all cursor-pointer ${
                isModelRateLimited(agent?.model) ? 'opacity-60' : ''
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
              <div className={`absolute right-0 top-0 bottom-0 w-1 rounded-r-lg ${
                isModelRateLimited(agent?.model) ? 'bg-red-500/50' : 'bg-primary shadow-[0_0_10px_rgba(13,242,89,0.5)]'
              }`} />
            </motion.div>
          ))}
        </div>

        {Object.keys(routerStatus.rate_limited_models || {}).length > 0 && (
          <div className="p-4 border-t border-[#28392e] bg-[#0d120f]">
            <div className="flex justify-between items-center mb-2">
              <span className="text-[10px] text-red-400 uppercase tracking-wider font-bold">Rate Limited Models</span>
              <button
                onClick={onClearRateLimits}
                className="text-[10px] text-primary hover:underline"
              >
                Clear All
              </button>
            </div>
            {Object.entries(safeRateLimited).map(([model, info]) => (
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
  );
};

export default LLMGatewayPanel;
