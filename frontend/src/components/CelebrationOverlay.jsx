/**
 * Author: rahn
 * Datum: 14.02.2026
 * Version: 1.0
 * Beschreibung: Fullscreen Celebration-Overlay bei erfolgreichem Projektabschluss.
 *               Confetti-Partikel + Success-Message + Feature-Stats.
 *               Pure framer-motion Loesung ohne externe Confetti-Library.
 *               Auto-Dismiss nach 6 Sekunden oder bei Klick.
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Sparkles } from 'lucide-react';
import { COLORS } from '../constants/config';

// AENDERUNG 14.02.2026: Confetti-Farben (KEIN purple — Regel 19)
const CONFETTI_COLORS = [
  COLORS.cyan.hex,
  COLORS.green.hex,
  COLORS.yellow.hex,
  COLORS.blue.hex,
  COLORS.orange.hex,
  COLORS.pink.hex,
];

// Confetti-Formen: Rechteck, Kreis, Dreieck (via CSS)
const SHAPES = ['rounded-none', 'rounded-full', 'rounded-sm'];

// Einmalig generierte Partikel-Konfigurationen (stabil ueber Rerenders)
const generateParticles = (count = 50) =>
  Array.from({ length: count }, (_, i) => ({
    id: i,
    x: Math.random() * 100,            // Start-X in vw
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    shape: SHAPES[i % SHAPES.length],
    size: 6 + Math.random() * 8,       // 6-14px
    delay: Math.random() * 1.5,         // 0-1.5s Verzoegerung
    duration: 2.5 + Math.random() * 2,  // 2.5-4.5s Fallzeit
    rotation: Math.random() * 720 - 360,
    drift: (Math.random() - 0.5) * 80,  // Seitliche Drift in px
  }));

const CelebrationOverlay = ({ show, onDismiss, featureStats }) => {
  // Partikel nur einmal generieren (nicht bei jedem Render)
  const particles = useMemo(() => generateParticles(50), []);

  const totalFeatures = featureStats?.total || 0;
  const doneFeatures = featureStats?.done || 0;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="celebration-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          onClick={onDismiss}
          className="fixed inset-0 z-[100] flex items-center justify-center cursor-pointer"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}
        >
          {/* Confetti-Partikel */}
          {particles.map((p) => (
            <motion.div
              key={p.id}
              initial={{
                x: `${p.x}vw`,
                y: '-5vh',
                rotate: 0,
                opacity: 1,
                scale: 1,
              }}
              animate={{
                y: '110vh',
                rotate: p.rotation,
                x: `calc(${p.x}vw + ${p.drift}px)`,
                opacity: [1, 1, 0.8, 0],
                scale: [1, 1.2, 0.8, 0.5],
              }}
              transition={{
                duration: p.duration,
                delay: p.delay,
                ease: 'easeIn',
              }}
              className={`absolute ${p.shape}`}
              style={{
                width: p.size,
                height: p.size * (p.shape === 'rounded-none' ? 0.6 : 1),
                backgroundColor: p.color,
              }}
            />
          ))}

          {/* Success-Badge */}
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.3 }}
            className="relative z-10 flex flex-col items-center gap-4 p-8 rounded-2xl border border-green-500/30 bg-gray-900/90"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Glow-Ring */}
            <div className="absolute inset-0 rounded-2xl opacity-50"
              style={{ boxShadow: '0 0 60px rgba(34, 197, 94, 0.4), 0 0 120px rgba(6, 182, 212, 0.2)' }}
            />

            {/* Icon */}
            <motion.div
              initial={{ rotate: -180, scale: 0 }}
              animate={{ rotate: 0, scale: 1 }}
              transition={{ type: 'spring', stiffness: 150, delay: 0.5 }}
              className="relative"
            >
              <CheckCircle2 className="w-16 h-16 text-green-400" strokeWidth={1.5} />
              <Sparkles className="absolute -top-2 -right-2 w-6 h-6 text-yellow-400 animate-pulse" />
            </motion.div>

            {/* Titel */}
            <motion.h2
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="text-2xl font-bold text-white"
            >
              Projekt erfolgreich!
            </motion.h2>

            {/* Stats */}
            {totalFeatures > 0 && (
              <motion.div
                initial={{ y: 10, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="flex items-center gap-3 text-sm"
              >
                <span className="px-3 py-1 rounded-lg bg-green-500/20 text-green-400 font-medium">
                  {doneFeatures} / {totalFeatures} Features
                </span>
              </motion.div>
            )}

            {/* Hinweis */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.5 }}
              transition={{ delay: 1.2 }}
              className="text-xs text-gray-500 mt-2"
            >
              Klicken um zu schliessen
            </motion.p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

CelebrationOverlay.propTypes = {
  show: PropTypes.bool.isRequired,
  onDismiss: PropTypes.func.isRequired,
  featureStats: PropTypes.shape({
    total: PropTypes.number,
    done: PropTypes.number,
    percentage: PropTypes.number,
  }),
};

export default CelebrationOverlay;
