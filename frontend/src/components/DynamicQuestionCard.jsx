/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.1
 * Beschreibung: DynamicQuestionCard - Zeigt LLM-generierte, projektspezifische Fragen
 *               in der Discovery Session an. Kundenfreundlich mit Beispielen.
 *               ÄNDERUNG 29.01.2026: Multi-Agent Support nach Fragen-Deduplizierung.
 *               Fragen können jetzt mehreren Agenten zugeordnet sein.
 */

import React, { useState } from 'react';
import {
  ChevronRight,
  CheckCircle,
  Lightbulb,
  User,
  Code,
  Database,
  Palette,
  Search,
  Settings,
  Users
} from 'lucide-react';

// Agent-Icons Mapping
const AGENT_ICONS = {
  'Coder': Code,
  'DB-Designer': Database,
  'Designer': Palette,
  'Researcher': Search,
  'TechStack': Settings,
  'Analyst': Users
};

// Farbpalette passend zum Discovery Office
const COLORS = {
  primary: '#ec9c13',
  woodDark: '#2c241b',
  glass: 'rgba(44, 36, 27, 0.7)',
  glassBorder: 'rgba(236, 156, 19, 0.2)',
  selected: 'rgba(236, 156, 19, 0.3)'
};

/**
 * DynamicQuestionCard - Zeigt eine einzelne LLM-generierte Frage an
 * ÄNDERUNG 29.01.2026: Unterstützt jetzt deduplizierte Fragen mit agents Array
 *
 * @param {Object} question - Fragen-Objekt {id, question, agents: [...], options, ...}
 * @param {number} currentIndex - Index der aktuellen Frage
 * @param {number} totalQuestions - Gesamtzahl der Fragen
 * @param {Function} onAnswer - Callback wenn Frage beantwortet wird
 */
const DynamicQuestionCard = ({
  question,
  currentIndex = 0,
  totalQuestions = 1,
  onAnswer
}) => {
  const [selectedOptions, setSelectedOptions] = useState([]);
  const [customText, setCustomText] = useState('');

  if (!question) {
    return null;
  }

  // ÄNDERUNG 29.01.2026: Unterstütze sowohl agents Array als auch einzelnen agent
  const agents = question.agents || [question.agent || 'Unknown'];
  const isMultiAgent = agents.length > 1;

  const toggleOption = (value) => {
    setSelectedOptions(prev => {
      if (prev.includes(value)) {
        return prev.filter(v => v !== value);
      }
      return [...prev, value];
    });
  };

  const handleSubmit = () => {
    const answer = {
      // ÄNDERUNG 29.01.2026: agents Array statt einzelnem agent
      agents: agents,
      questionId: question.id,
      question: question.question,
      selectedOptions,
      selectedValues: (question.options || [])
        .filter(opt => selectedOptions.includes(opt.value))
        .map(opt => opt.text),
      customText: customText.trim()
    };

    // Reset für nächste Frage
    setSelectedOptions([]);
    setCustomText('');

    onAnswer(answer);
  };

  const canSubmit = selectedOptions.length > 0 || customText.trim().length > 0;

  return (
    <div
      className="rounded-lg p-6 max-w-2xl mx-auto"
      style={{
        backgroundColor: COLORS.glass,
        border: `1px solid ${COLORS.glassBorder}`
      }}
    >
      {/* Progress Header */}
      <div className="flex items-center justify-between mb-4 text-xs text-amber-200/50">
        <span>Frage {currentIndex + 1} von {totalQuestions}</span>
        {isMultiAgent && (
          <span className="px-2 py-0.5 rounded bg-amber-900/30 text-amber-400">
            {agents.length} Agenten interessiert
          </span>
        )}
      </div>

      {/* Agent Header - ÄNDERUNG 29.01.2026: Multi-Agent Support */}
      {isMultiAgent ? (
        // Multi-Agent Anzeige
        <div className="flex items-center gap-3 mb-4">
          <div className="flex -space-x-2">
            {agents.slice(0, 4).map((agent, i) => {
              const Icon = AGENT_ICONS[agent] || User;
              return (
                <div
                  key={agent}
                  className="w-9 h-9 rounded-full flex items-center justify-center border-2"
                  style={{
                    backgroundColor: COLORS.woodDark,
                    borderColor: COLORS.glass,
                    zIndex: agents.length - i
                  }}
                  title={agent}
                >
                  <Icon size={16} style={{ color: COLORS.primary }} />
                </div>
              );
            })}
            {agents.length > 4 && (
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center border-2 text-xs font-bold"
                style={{
                  backgroundColor: COLORS.woodDark,
                  borderColor: COLORS.glass,
                  color: COLORS.primary
                }}
              >
                +{agents.length - 4}
              </div>
            )}
          </div>
          <div>
            <span className="text-amber-400 text-sm font-medium">
              {agents.join(', ')}
            </span>
            <span className="text-amber-200/50 text-sm ml-2">fragen:</span>
          </div>
        </div>
      ) : (
        // Single Agent Anzeige
        <div className="flex items-center gap-3 mb-4">
          {(() => {
            const Icon = AGENT_ICONS[agents[0]] || User;
            return (
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center"
                style={{ backgroundColor: COLORS.woodDark }}
              >
                <Icon size={20} style={{ color: COLORS.primary }} />
              </div>
            );
          })()}
          <div>
            <span className="text-amber-400 text-sm font-medium">{agents[0]}</span>
            <span className="text-amber-200/50 text-sm ml-2">fragt:</span>
          </div>
        </div>
      )}

      {/* Frage */}
      <h3 className="text-xl text-amber-100 mb-3 leading-relaxed">
        {question.question}
      </h3>

      {/* Beispiel */}
      {question.example && (
        <div
          className="flex items-start gap-2 mb-5 p-3 rounded"
          style={{ backgroundColor: 'rgba(236, 156, 19, 0.1)' }}
        >
          <Lightbulb size={16} className="text-amber-400 mt-0.5 shrink-0" />
          <p className="text-amber-200/70 text-sm italic">
            {question.example}
          </p>
        </div>
      )}

      {/* Optionen */}
      <div className="space-y-2 mb-5">
        {(question.options || []).map((opt, i) => {
          const isSelected = selectedOptions.includes(opt.value);
          return (
            <button
              key={opt.value || i}
              onClick={() => toggleOption(opt.value)}
              className="w-full text-left p-4 rounded transition-all flex items-center gap-3"
              style={{
                backgroundColor: isSelected ? COLORS.selected : COLORS.woodDark,
                border: `1px solid ${isSelected ? COLORS.primary : COLORS.glassBorder}`,
                color: isSelected ? '#fef3c7' : '#fde68a'
              }}
            >
              <div
                className="w-5 h-5 rounded border-2 flex items-center justify-center shrink-0"
                style={{
                  borderColor: isSelected ? COLORS.primary : 'rgba(236, 156, 19, 0.4)',
                  backgroundColor: isSelected ? COLORS.primary : 'transparent'
                }}
              >
                {isSelected && <CheckCircle size={14} className="text-amber-900" />}
              </div>
              <span className="flex-1">{opt.text}</span>
            </button>
          );
        })}
      </div>

      {/* Freitext */}
      {question.allowCustom !== false && (
        <div className="mb-5">
          <label className="text-amber-200/50 text-xs uppercase tracking-wider mb-2 block">
            Oder eigene Antwort:
          </label>
          <input
            type="text"
            placeholder="Eigene Antwort eingeben..."
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            className="w-full p-3 rounded text-amber-100 placeholder-amber-200/30 focus:outline-none focus:ring-2"
            style={{
              backgroundColor: COLORS.woodDark,
              border: `1px solid ${COLORS.glassBorder}`,
              '--tw-ring-color': COLORS.primary
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && canSubmit) {
                handleSubmit();
              }
            }}
          />
        </div>
      )}

      {/* Weiter-Button */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="w-full py-3 rounded font-medium transition-all flex items-center justify-center gap-2"
        style={{
          backgroundColor: canSubmit ? COLORS.primary : 'rgba(236, 156, 19, 0.2)',
          color: canSubmit ? COLORS.woodDark : 'rgba(254, 243, 199, 0.3)',
          cursor: canSubmit ? 'pointer' : 'not-allowed'
        }}
      >
        <span>Weiter</span>
        <ChevronRight size={18} />
      </button>

      {/* Skip Option */}
      <button
        onClick={() => onAnswer({ agents, questionId: question.id, question: question.question, skipped: true })}
        className="w-full mt-2 py-2 text-amber-200/40 text-sm hover:text-amber-200/60 transition-colors"
      >
        Frage überspringen
      </button>
    </div>
  );
};

export default DynamicQuestionCard;
