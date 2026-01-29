/**
 * Author: rahn / Claude
 * Datum: 29.01.2026
 * Version: 1.5
 * Beschreibung: Discovery Office - Strukturierte Projektaufnahme mit Guided Choice System.
 *               Implementiert interaktive Fragen mit vorgeschlagenen Antwortoptionen.
 *
 * ÄNDERUNG 29.01.2026 v1.1: Fehlende Agenten-Fragen für Data Researcher, Designer und Security hinzugefügt.
 * ÄNDERUNG 29.01.2026 v1.2: Dynamische LLM-generierte Fragen pro Agent (projektspezifisch).
 * ÄNDERUNG 29.01.2026 v1.3: Multi-Agent Support nach Backend-Deduplizierung.
 *                           Fragen mit agents: [] Array statt verschachtelter Struktur.
 * ÄNDERUNG 29.01.2026 v1.4: Session-Persistenz für Pausieren/Fortsetzen.
 * ÄNDERUNG 29.01.2026 v1.5: LLM-basierte Agenten-Auswahl mit Begründungen.
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import DynamicQuestionCard from './components/DynamicQuestionCard';
import QuestionCard from './components/QuestionCard';
import ProgressBar from './components/ProgressBar';
import { useDiscoveryPhase } from './hooks/useDiscoveryPhase';
import { useQuestions } from './hooks/useQuestions';
import { useBriefing } from './hooks/useBriefing';
import { useSessionStorage } from './hooks/useSessionStorage';
import defaultDiscoveryQuestions from './constants/defaultDiscoveryQuestions';
import { PHASES, AGENT_COLOR_CLASSES, ALL_AGENTS } from './constants/discoveryConstants';
import { Lightbulb } from 'lucide-react';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Users,
  FileText,
  Download,
  RefreshCw,
  PlayCircle,
  Pause,
  Plus,
  X
} from 'lucide-react';

// API Base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DiscoveryOffice = ({
  onBack,
  onComplete
}) => {
  // Session State
  const [vision, setVision] = useState('');
  const [briefing, setBriefing] = useState(null);
  // ÄNDERUNG 29.01.2026: Session-Persistenz Dialog
  const [showResumeDialog, setShowResumeDialog] = useState(false);

  const {
    phase,
    setPhase,
    isLoading,
    setIsLoading,
    loadingMessage,
    setLoadingMessage
  } = useDiscoveryPhase();

  // ÄNDERUNG 29.01.2026: Session-Persistenz Hook
  const { hasSavedSession, saveSession, loadSession, clearSession } = useSessionStorage();

  const {
    selectedAgents,
    agentQuestions,
    dynamicQuestions,
    currentDynamicIndex,
    currentAgent,
    currentQuestionIndex,
    answers,
    openPoints,
    setSelectedAgents,
    handleVisionSubmit,
    handleTeamConfirm,
    handleDynamicAnswer,
    handleAnswer,
    restoreSession,
    // ÄNDERUNG 29.01.2026: Feedback-Schleifen
    completedAgent,
    pendingNextAgent,
    handleFeedbackContinue,
    getAgentAnswers,
    // ÄNDERUNG 29.01.2026 v1.3: LLM-basierte Agenten-Auswahl
    agentReasons,
    notNeededAgents
  } = useQuestions({
    vision,
    apiBase: API_BASE,
    defaultQuestions: defaultDiscoveryQuestions,
    setPhase,
    setIsLoading,
    setLoadingMessage
  });

  const {
    buildBriefing,
    generateBriefingMarkdown,
    exportBriefing
  } = useBriefing();

  // ÄNDERUNG 29.01.2026: Prüfe beim Start ob Session fortgesetzt werden kann
  useEffect(() => {
    if (hasSavedSession && phase === PHASES.VISION) {
      setShowResumeDialog(true);
    }
  }, [hasSavedSession, phase]);

  // ÄNDERUNG 29.01.2026: Session automatisch speichern bei relevanten Änderungen
  useEffect(() => {
    // Nur speichern wenn wir über die Vision-Phase hinaus sind
    if (phase !== PHASES.VISION && phase !== PHASES.BRIEFING && vision) {
      saveSession({
        vision,
        phase,
        selectedAgents,
        dynamicQuestions,
        currentDynamicIndex,
        currentAgent,
        currentQuestionIndex,
        answers,
        openPoints
      });
    }
  }, [phase, vision, selectedAgents, dynamicQuestions, currentDynamicIndex,
      currentAgent, currentQuestionIndex, answers, openPoints, saveSession]);

  // ÄNDERUNG 29.01.2026: Session fortsetzen (vollständig)
  const handleResumeSession = () => {
    try {
      const saved = loadSession();
      const isValidPhase = saved && Object.values(PHASES).includes(saved.phase);
      const hasRequiredKeys = saved && typeof saved === 'object' && saved.vision !== undefined && isValidPhase;
      if (hasRequiredKeys) {
        setVision(saved.vision || '');
        // ÄNDERUNG 29.01.2026 v1.1: Vollständiger Session-Restore
        restoreSession(saved);
        setPhase(saved.phase || PHASES.VISION);
      } else {
        console.warn('Ungültige Session-Daten gefunden. Session wird verworfen.');
        clearSession();
      }
    } catch (err) {
      console.error('Fehler beim Fortsetzen der Session:', err);
      clearSession();
    } finally {
      // ÄNDERUNG 29.01.2026: UI-Zustand immer schließen
      setShowResumeDialog(false);
    }
  };

  // ÄNDERUNG 29.01.2026: Neue Session starten
  const handleNewSession = () => {
    clearSession();
    setShowResumeDialog(false);
  };

  // Phase 4: Briefing generieren
  const handleGenerateBriefing = () => {
    setIsLoading(true);

    // Generiere Briefing aus Antworten
    setTimeout(() => {
      const generatedBriefing = buildBriefing(vision, selectedAgents, answers, openPoints);

      setBriefing(generatedBriefing);
      setPhase(PHASES.BRIEFING);
      setIsLoading(false);
      // ÄNDERUNG 29.01.2026: Session löschen nach erfolgreichem Briefing
      clearSession();
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={20} />
          Zurück
        </button>
        <h1 className="text-2xl font-bold text-white">Discovery Session</h1>
        <div className="w-20" /> {/* Spacer */}
      </div>

      {/* ÄNDERUNG 29.01.2026: Resume Dialog */}
      {showResumeDialog && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-8 border border-slate-600 max-w-md mx-4">
            <div className="text-center mb-6">
              <Pause size={48} className="text-cyan-400 mx-auto mb-4" />
              <h2 className="text-xl font-bold text-white mb-2">Session fortsetzen?</h2>
              <p className="text-slate-400 text-sm">
                Es wurde eine unterbrochene Discovery Session gefunden.
                Möchtest du diese fortsetzen oder neu beginnen?
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleResumeSession}
                className="flex-1 py-3 rounded-lg font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center gap-2"
              >
                <PlayCircle size={18} />
                Fortsetzen
              </button>
              <button
                onClick={handleNewSession}
                className="flex-1 py-3 rounded-lg font-semibold bg-slate-700 hover:bg-slate-600 text-white"
              >
                Neu starten
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      <ProgressBar phase={phase} />

      {/* Content */}
      <div className="max-w-3xl mx-auto">
        <AnimatePresence mode="wait">
          {/* Phase 1: Vision */}
          {phase === PHASES.VISION && (
            <motion.div
              key="vision"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-slate-800 rounded-xl p-8 border border-slate-700"
            >
              <div className="text-center mb-8">
                <Lightbulb size={48} className="text-yellow-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-white mb-2">Phase 1: Vision & Ziel</h2>
                <p className="text-slate-400">
                  Beschreibe dein Projekt frei und unstrukturiert.
                  Was möchtest du entwickeln? Welches Problem soll gelöst werden?
                </p>
              </div>

              <textarea
                value={vision}
                onChange={(e) => setVision(e.target.value)}
                placeholder="z.B. Ich möchte eine Web-App entwickeln, die Nutzer bei der Projektverwaltung unterstützt..."
                className="w-full h-40 bg-slate-900 border border-slate-600 rounded-lg p-4 text-white focus:border-cyan-500 focus:outline-none resize-none"
              />

              <button
                onClick={handleVisionSubmit}
                disabled={!vision.trim() || isLoading}
                className={`w-full mt-6 py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all ${
                  vision.trim() && !isLoading
                    ? 'bg-cyan-600 hover:bg-cyan-500 text-white'
                    : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                }`}
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Analysiere...
                  </>
                ) : (
                  <>
                    Weiter
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </motion.div>
          )}

          {/* Phase 2: Team - ÄNDERUNG 29.01.2026 v1.4: Manuelle Team-Bearbeitung */}
          {phase === PHASES.TEAM_SETUP && (
            <motion.div
              key="team"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-slate-800 rounded-xl p-8 border border-slate-700"
            >
              <div className="text-center mb-8">
                <Users size={48} className="text-green-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-white mb-2">Phase 2: Team-Zusammenstellung</h2>
                <p className="text-slate-400">
                  Basierend auf deiner Vision wurden folgende Experten ausgewählt.
                  Du kannst das Team anpassen:
                </p>
              </div>

              {/* Ausgewählte Agenten - ÄNDERUNG 29.01.2026 v1.5: LLM-Begründungen anzeigen */}
              <div className="mb-6">
                <h3 className="text-sm text-slate-400 uppercase tracking-wider mb-3">
                  Empfohlenes Team ({selectedAgents.length})
                </h3>
                <div className="space-y-2">
                  {selectedAgents.map((agent) => {
                    const agentInfo = ALL_AGENTS.find(a => a.id === agent);
                    const llmReason = agentReasons[agent];
                    return (
                      <div
                        key={agent}
                        className="p-3 rounded-lg bg-slate-700/50 border border-slate-600 flex items-center gap-3"
                      >
                        <div className={`w-3 h-3 rounded-full ${AGENT_COLOR_CLASSES[agent] || 'bg-gray-400'}`} />
                        <div className="flex-1">
                          <span className="text-white font-medium">{agent}</span>
                          {/* LLM-Begründung hat Priorität über statische Beschreibung */}
                          {llmReason ? (
                            <p className="text-cyan-400 text-xs">
                              <span className="text-slate-500">Empfohlen:</span> {llmReason}
                            </p>
                          ) : agentInfo ? (
                            <p className="text-slate-400 text-xs">{agentInfo.description}</p>
                          ) : null}
                        </div>
                        <button
                          onClick={() => setSelectedAgents(prev => prev.filter(a => a !== agent))}
                          className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors"
                          title="Entfernen"
                        >
                          <X size={16} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Verfügbare Agenten zum Hinzufügen - ÄNDERUNG 29.01.2026 v1.5: Nicht-benötigt Begründungen */}
              {ALL_AGENTS.filter(a => !selectedAgents.includes(a.id)).length > 0 && (
                <div className="mb-8">
                  <h3 className="text-sm text-slate-400 uppercase tracking-wider mb-3">
                    Nicht empfohlen für dieses Projekt
                  </h3>
                  <div className="space-y-2">
                    {ALL_AGENTS.filter(a => !selectedAgents.includes(a.id)).map((agent) => {
                      const notNeededReason = notNeededAgents[agent.id] || notNeededAgents[agent.name];
                      return (
                        <div
                          key={agent.id}
                          className="p-3 rounded-lg bg-slate-900/50 border border-slate-700 flex items-center gap-3"
                        >
                          <div className={`${AGENT_COLOR_CLASSES[agent.id] || 'bg-gray-400'} w-3 h-3 rounded-full opacity-50`} />
                          <div className="flex-1">
                            <span className="text-slate-300 font-medium">{agent.name}</span>
                            {/* LLM-Begründung warum nicht benötigt */}
                            {notNeededReason ? (
                              <p className="text-amber-500/70 text-xs">
                                <span className="text-slate-500">Nicht nötig:</span> {notNeededReason}
                              </p>
                            ) : (
                              <p className="text-slate-500 text-xs">{agent.description}</p>
                            )}
                          </div>
                          <button
                            onClick={() => setSelectedAgents(prev => [...prev, agent.id])}
                            className="p-1 rounded hover:bg-green-500/20 text-slate-400 hover:text-green-400 transition-colors"
                            title="Trotzdem hinzufügen"
                          >
                            <Plus size={16} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <button
                onClick={handleTeamConfirm}
                disabled={isLoading || selectedAgents.length === 0}
                className={`w-full py-3 rounded-lg font-semibold flex items-center justify-center gap-2 ${
                  isLoading || selectedAgents.length === 0
                    ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-500 text-white'
                }`}
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    {loadingMessage || 'Lade Fragen...'}
                  </>
                ) : (
                  <>
                    Mit diesem Team starten
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </motion.div>
          )}

          {/* Phase 2.5: Dynamische LLM-Fragen */}
          {/* ÄNDERUNG 29.01.2026 v1.3: Flache Fragen-Struktur nach Deduplizierung */}
          {phase === PHASES.DYNAMIC_QUESTIONS && dynamicQuestions.length > 0 && (
            <motion.div
              key={`dynamic-${currentDynamicIndex}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <DynamicQuestionCard
                question={dynamicQuestions[currentDynamicIndex]}
                currentIndex={currentDynamicIndex}
                totalQuestions={dynamicQuestions.length}
                onAnswer={handleDynamicAnswer}
              />
            </motion.div>
          )}

          {/* ÄNDERUNG 29.01.2026 v1.2: Feedback-Schleife nach Agent-Runde */}
          {phase === PHASES.AGENT_FEEDBACK && completedAgent && (
            <motion.div
              key="agent-feedback"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-slate-800 rounded-xl p-8 border border-slate-700"
            >
              <div className="text-center mb-6">
                <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
                <h2 className="text-xl font-bold text-white mb-2">
                  {completedAgent} abgeschlossen
                </h2>
                <p className="text-slate-400">
                  Hier sind die gesammelten Antworten. Alles korrekt?
                </p>
              </div>

              {/* Antworten-Übersicht */}
              <div className="bg-slate-900 rounded-lg p-4 mb-6 max-h-64 overflow-y-auto">
                {getAgentAnswers(completedAgent).length > 0 ? (
                  <div className="space-y-3">
                    {getAgentAnswers(completedAgent).map((a, idx) => (
                      <div key={idx} className="border-b border-slate-700 pb-2 last:border-0">
                        <p className="text-slate-400 text-sm">{a.questionText || a.question || 'Frage'}</p>
                        <p className="text-white">
                          {a.selectedValues?.join(', ') || a.customText || '-'}
                          {a.autoFallback && <span className="text-cyan-400 text-xs ml-2">(Auto)</span>}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 text-center">Keine Antworten erfasst</p>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleFeedbackContinue}
                  className="flex-1 py-3 rounded-lg font-semibold bg-green-600 hover:bg-green-500 text-white flex items-center justify-center gap-2"
                >
                  <CheckCircle size={18} />
                  {pendingNextAgent ? `Weiter zu ${pendingNextAgent}` : 'Zur Zusammenfassung'}
                </button>
              </div>
            </motion.div>
          )}

          {/* Phase 3: Guided Questions (statisch) */}
          {phase === PHASES.GUIDED_QA && currentAgent && (
            <motion.div
              key={`qa-${currentAgent}-${currentQuestionIndex}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {/* Progress innerhalb der Phase */}
              <div className="mb-6 flex items-center justify-between text-sm text-slate-400">
                <span>Agent: {currentAgent}</span>
                <span>
                  Frage {currentQuestionIndex + 1} von {agentQuestions[currentAgent]?.length || 0}
                </span>
              </div>

              {agentQuestions[currentAgent]?.[currentQuestionIndex] && (
                <QuestionCard
                  question={agentQuestions[currentAgent][currentQuestionIndex]}
                  currentAgent={currentAgent}
                  onAnswer={handleAnswer}
                />
              )}
            </motion.div>
          )}

          {/* Phase 4: Summary */}
          {phase === PHASES.SUMMARY && (
            <motion.div
              key="summary"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-slate-800 rounded-xl p-8 border border-slate-700"
            >
              <div className="text-center mb-8">
                <CheckCircle size={48} className="text-green-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-white mb-2">Zusammenfassung</h2>
                <p className="text-slate-400">
                  Alle Fragen wurden beantwortet. Hier ist eine Übersicht:
                </p>
              </div>

              <div className="space-y-4 mb-8">
                <div className="p-4 bg-slate-900 rounded-lg">
                  <h3 className="text-white font-semibold mb-2">Projektziel</h3>
                  <p className="text-slate-300">{vision}</p>
                </div>

                <div className="p-4 bg-slate-900 rounded-lg">
                  <h3 className="text-white font-semibold mb-2">Antworten: {answers.length}</h3>
                  <p className="text-slate-400 text-sm">
                    {answers.filter(a => !a.skipped).length} beantwortet,
                    {' '}{openPoints.length} offene Punkte
                  </p>
                </div>

                {openPoints.length > 0 && (
                  <div className="p-4 bg-yellow-900/20 border border-yellow-700 rounded-lg">
                    <h3 className="text-yellow-400 font-semibold mb-2">Offene Punkte</h3>
                    <ul className="text-slate-300 text-sm space-y-1">
                      {openPoints.map((point, idx) => (
                        <li key={idx}>• {point}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <button
                onClick={handleGenerateBriefing}
                disabled={isLoading}
                className="w-full py-3 rounded-lg font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Generiere Briefing...
                  </>
                ) : (
                  <>
                    <FileText size={18} />
                    Briefing generieren
                  </>
                )}
              </button>
            </motion.div>
          )}

          {/* Phase 5: Briefing */}
          {phase === PHASES.BRIEFING && briefing && (
            <motion.div
              key="briefing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-slate-800 rounded-xl p-8 border border-slate-700"
            >
              <div className="text-center mb-8">
                <FileText size={48} className="text-cyan-400 mx-auto mb-4" />
                <h2 className="text-2xl font-bold text-white mb-2">Projektbriefing</h2>
                <p className="text-slate-400">
                  Das Briefing wurde erfolgreich erstellt.
                </p>
              </div>

              <div className="bg-slate-900 rounded-lg p-6 mb-6 font-mono text-sm">
                <pre className="text-slate-300 whitespace-pre-wrap">
                  {generateBriefingMarkdown(briefing)}
                </pre>
              </div>

              <div className="flex gap-4">
                <button
                  onClick={() => exportBriefing(briefing)}
                  className="flex-1 py-3 rounded-lg font-semibold bg-green-600 hover:bg-green-500 text-white flex items-center justify-center gap-2"
                >
                  <Download size={18} />
                  Als Markdown exportieren
                </button>
                <button
                  onClick={() => onComplete?.(briefing)}
                  className="flex-1 py-3 rounded-lg font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center gap-2"
                >
                  <ArrowRight size={18} />
                  Zur Entwicklung
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default DiscoveryOffice;
