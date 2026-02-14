/**
 * Author: rahn
 * Datum: 14.02.2026
 * Version: 1.0
 * Beschreibung: Toast-Benachrichtigungen fuer Agent-Events.
 *               Slide-in von links, Auto-Dismiss nach 4s, max 4 gleichzeitig.
 *               Farbkodierung via AGENT_CONFIG (Single Source of Truth).
 */

import React, { useState, useCallback, useImperativeHandle, forwardRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';
import { COLORS, AGENT_CONFIG } from '../constants/config';

const MAX_TOASTS = 4;
const AUTO_DISMISS_MS = 4000;

// Icon + Farbe pro Toast-Typ
const TOAST_STYLES = {
  info:    { Icon: Info,          borderColor: 'border-cyan-500/50',   iconColor: 'text-cyan-400' },
  success: { Icon: CheckCircle2,  borderColor: 'border-green-500/50',  iconColor: 'text-green-400' },
  warning: { Icon: AlertTriangle, borderColor: 'border-yellow-500/50', iconColor: 'text-yellow-400' },
  error:   { Icon: AlertCircle,   borderColor: 'border-red-500/50',    iconColor: 'text-red-400' },
};

let toastIdCounter = 0;

const ToastContainer = forwardRef((_, ref) => {
  const [toasts, setToasts] = useState([]);

  // Entfernt einen Toast per ID
  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Fuegt neuen Toast hinzu (max MAX_TOASTS, FIFO bei Ueberlauf)
  const addToast = useCallback((agent, message, type = 'info') => {
    const id = ++toastIdCounter;
    setToasts(prev => {
      const next = [...prev, { id, agent, message, type, timestamp: Date.now() }];
      // FIFO: aelteste entfernen wenn Limit ueberschritten
      return next.length > MAX_TOASTS ? next.slice(-MAX_TOASTS) : next;
    });

    // Auto-Dismiss Timer
    setTimeout(() => removeToast(id), AUTO_DISMISS_MS);
  }, [removeToast]);

  // Exponiert addToast an Parent via ref
  useImperativeHandle(ref, () => ({ addToast }), [addToast]);

  // Agent-Farbe ermitteln (Fallback auf cyan)
  const getAgentHex = (agentName) => {
    const key = agentName?.toLowerCase().replace(/\s+/g, '');
    const colorKey = AGENT_CONFIG[key];
    return colorKey && COLORS[colorKey] ? COLORS[colorKey].hex : '#06b6d4';
  };

  return (
    <div className="fixed bottom-4 left-4 z-40 flex flex-col-reverse gap-2 max-w-sm pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map(toast => {
          const style = TOAST_STYLES[toast.type] || TOAST_STYLES.info;
          const IconComponent = style.Icon;

          return (
            <motion.div
              key={toast.id}
              layout
              initial={{ opacity: 0, x: -200, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: -200, scale: 0.9 }}
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}
              className={`pointer-events-auto flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg
                bg-gray-900/95 backdrop-blur-sm border ${style.borderColor}
                shadow-lg shadow-black/30 cursor-pointer group`}
              onClick={() => removeToast(toast.id)}
            >
              {/* Agent-Farbindikator */}
              <div
                className="w-1 self-stretch rounded-full flex-shrink-0"
                style={{ backgroundColor: getAgentHex(toast.agent) }}
              />

              {/* Icon */}
              <IconComponent className={`w-4 h-4 mt-0.5 flex-shrink-0 ${style.iconColor}`} />

              {/* Inhalt */}
              <div className="flex-1 min-w-0">
                {toast.agent && (
                  <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wider block">
                    {toast.agent}
                  </span>
                )}
                <p className="text-xs text-gray-300 leading-snug truncate">
                  {toast.message}
                </p>
              </div>

              {/* Schliessen-Button */}
              <button
                className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-500 hover:text-gray-300 flex-shrink-0"
                onClick={(e) => { e.stopPropagation(); removeToast(toast.id); }}
              >
                <X className="w-3 h-3" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
});

ToastContainer.displayName = 'ToastContainer';

export default ToastContainer;
