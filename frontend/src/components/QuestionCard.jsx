/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.0
 * Beschreibung: UI-Komponente für eine Guided-Question.
 */
// ÄNDERUNG 29.01.2026: QuestionCard aus DiscoveryOffice ausgelagert

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  CheckCircle,
  Circle,
  MessageSquare,
  SkipForward,
  Edit3,
  Star
} from 'lucide-react';
import { AGENT_COLORS } from '../constants/discoveryConstants';

// ÄNDERUNG 29.01.2026: Statische Tailwind-Klassen je Farbe
const COLOR_CLASSES = {
  blue: {
    text: 'text-blue-400',
    border: 'border-blue-500',
    bg: 'bg-blue-900/30',
    button: 'bg-blue-600 hover:bg-blue-500 text-white',
    check: 'text-blue-400'
  },
  green: {
    text: 'text-green-400',
    border: 'border-green-500',
    bg: 'bg-green-900/30',
    button: 'bg-green-600 hover:bg-green-500 text-white',
    check: 'text-green-400'
  },
  yellow: {
    text: 'text-yellow-400',
    border: 'border-yellow-500',
    bg: 'bg-yellow-900/30',
    button: 'bg-yellow-600 hover:bg-yellow-500 text-white',
    check: 'text-yellow-400'
  },
  purple: {
    text: 'text-purple-400',
    border: 'border-purple-500',
    bg: 'bg-purple-900/30',
    button: 'bg-purple-600 hover:bg-purple-500 text-white',
    check: 'text-purple-400'
  },
  cyan: {
    text: 'text-cyan-400',
    border: 'border-cyan-500',
    bg: 'bg-cyan-900/30',
    button: 'bg-cyan-600 hover:bg-cyan-500 text-white',
    check: 'text-cyan-400'
  },
  red: {
    text: 'text-red-400',
    border: 'border-red-500',
    bg: 'bg-red-900/30',
    button: 'bg-red-600 hover:bg-red-500 text-white',
    check: 'text-red-400'
  },
  orange: {
    text: 'text-orange-400',
    border: 'border-orange-500',
    bg: 'bg-orange-900/30',
    button: 'bg-orange-600 hover:bg-orange-500 text-white',
    check: 'text-orange-400'
  },
  gray: {
    text: 'text-slate-400',
    border: 'border-slate-600',
    bg: 'bg-slate-900/30',
    button: 'bg-slate-700 text-slate-500 cursor-not-allowed',
    check: 'text-slate-400'
  },
  // ÄNDERUNG 29.01.2026: Fehlende Farben für DB-Designer und TechStack hinzugefügt
  indigo: {
    text: 'text-indigo-400',
    border: 'border-indigo-500',
    bg: 'bg-indigo-900/30',
    button: 'bg-indigo-600 hover:bg-indigo-500 text-white',
    check: 'text-indigo-400'
  },
  teal: {
    text: 'text-teal-400',
    border: 'border-teal-500',
    bg: 'bg-teal-900/30',
    button: 'bg-teal-600 hover:bg-teal-500 text-white',
    check: 'text-teal-400'
  }
};

const getColorClasses = (color) => COLOR_CLASSES[color] || COLOR_CLASSES.gray;

const QuestionCard = ({ question, currentAgent, onAnswer }) => {
  const [selected, setSelected] = useState(question.multiple ? [] : null);
  const [customInput, setCustomInput] = useState('');
  const [showCustom, setShowCustom] = useState(false);

  const handleSelect = (value) => {
    if (question.multiple) {
      setSelected(prev =>
        prev.includes(value)
          ? prev.filter(v => v !== value)
          : [...prev, value]
      );
    } else {
      setSelected(value);
    }
  };

  const handleSubmit = () => {
    if (showCustom && customInput.trim()) {
      onAnswer(question.id, [], customInput);
    } else if (selected !== null && (Array.isArray(selected) ? selected.length > 0 : true)) {
      onAnswer(question.id, selected);
    }
  };

  const color = AGENT_COLORS[currentAgent] || 'gray';
  const colorClasses = getColorClasses(color);
  const isSelected = selected !== null && !(Array.isArray(selected) && selected.length === 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-slate-800 rounded-xl p-6 border border-slate-700"
    >
      <div className={`flex items-center gap-2 mb-4 ${colorClasses.text}`}>
        <MessageSquare size={20} />
        <span className="font-semibold">{currentAgent} fragt:</span>
      </div>

      <h3 className="text-xl font-bold text-white mb-6">{question.question}</h3>

      <div className="space-y-3 mb-6">
        {question.options.map((opt, idx) => {
          const optionSelected = question.multiple ? selected.includes(opt.value) : selected === opt.value;
          return (
            <button
              key={idx}
              onClick={() => handleSelect(opt.value)}
              className={`w-full p-4 rounded-lg border-2 transition-all text-left flex items-start gap-3 ${
                optionSelected
                  ? `${colorClasses.border} ${colorClasses.bg}`
                  : 'border-slate-600 hover:border-slate-500 bg-slate-700/50'
              }`}
            >
              <div className="mt-0.5">
                {optionSelected ? (
                  <CheckCircle size={20} className={colorClasses.check} />
                ) : (
                  <Circle size={20} className="text-slate-500" />
                )}
              </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-white font-medium">{opt.text}</span>
                {opt.recommended && (
                  <span className="flex items-center gap-1 text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded-full">
                    <Star size={12} />
                    EMPFOHLEN
                  </span>
                )}
              </div>
              {opt.reason && (
                <p className="text-sm text-slate-400 mt-1">{opt.reason}</p>
              )}
            </div>
          </button>
        );
        })}

        {question.allowCustom && (
          <button
            onClick={() => setShowCustom(!showCustom)}
            className={`w-full p-4 rounded-lg border-2 transition-all text-left flex items-center gap-3 ${
              showCustom
                ? 'border-yellow-500 bg-yellow-900/30'
                : 'border-slate-600 hover:border-slate-500 bg-slate-700/50'
            }`}
          >
            <Edit3 size={20} className={showCustom ? 'text-yellow-400' : 'text-slate-500'} />
            <span className="text-white">Eigene Angabe eingeben</span>
          </button>
        )}

        {showCustom && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="pl-10"
          >
            <textarea
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              placeholder="Deine eigene Angabe..."
              className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 text-white focus:border-yellow-500 focus:outline-none"
              rows={3}
            />
          </motion.div>
        )}
      </div>

      <div className="flex justify-between items-center">
        {question.allowSkip && (
          <button
            onClick={() => onAnswer(question.id, [], null, true)}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
          >
            <SkipForward size={18} />
            Überspringen
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={!showCustom && !isSelected}
          className={`flex items-center gap-2 px-6 py-2 rounded-lg font-semibold transition-all ${
            (showCustom && customInput.trim()) || isSelected
              ? colorClasses.button
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          }`}
        >
          Weiter
          <ArrowRight size={18} />
        </button>
      </div>
    </motion.div>
  );
};

export default QuestionCard;
