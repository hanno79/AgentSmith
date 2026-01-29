/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.2
 * Beschreibung: Hook für Fragen-Logik, Antworten und Agentensteuerung.
 */
// ÄNDERUNG 29.01.2026: Fragen- und Antwort-Logik ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: restoreSession Funktion für vollständigen Session-Restore
// ÄNDERUNG 29.01.2026 v1.2: Feedback-Schleifen nach Agent-Runden

import { useState, useCallback } from 'react';
import { PHASES } from '../constants/discoveryConstants';

export const useQuestions = ({
  vision,
  apiBase,
  defaultQuestions,
  setPhase,
  setIsLoading,
  setLoadingMessage
}) => {
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [agentQuestions, setAgentQuestions] = useState({});
  const [dynamicQuestions, setDynamicQuestions] = useState([]);
  const [currentDynamicIndex, setCurrentDynamicIndex] = useState(0);
  const [currentAgent, setCurrentAgent] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [openPoints, setOpenPoints] = useState([]);
  // ÄNDERUNG 29.01.2026 v1.2: Feedback-Schleifen State
  const [completedAgent, setCompletedAgent] = useState(null);
  const [pendingNextAgent, setPendingNextAgent] = useState(null);

  const handleVisionSubmit = useCallback(() => {
    if (!vision.trim()) return;

    setIsLoading(true);

    setTimeout(() => {
      const agents = ['Analyst', 'Coder', 'Tester', 'Planner'];

      if (vision.toLowerCase().includes('ui') || vision.toLowerCase().includes('web')) {
        agents.splice(2, 0, 'Designer');
      }
      if (vision.toLowerCase().includes('daten') || vision.toLowerCase().includes('data')) {
        agents.splice(1, 0, 'Data Researcher');
      }

      setSelectedAgents(agents);
      setAgentQuestions(defaultQuestions);
      setPhase(PHASES.TEAM_SETUP);
      setIsLoading(false);
    }, 1000);
  }, [vision, defaultQuestions, setPhase, setIsLoading]);

  const handleTeamConfirm = useCallback(async () => {
    if (selectedAgents.length === 0) return;

    setIsLoading(true);
    setLoadingMessage('Agenten analysieren dein Projekt...');

    try {
      const response = await fetch(`${apiBase}/discovery/generate-questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vision, agents: selectedAgents })
      });

      if (response.ok) {
        const data = await response.json();

        if (data.questions && data.questions.length > 0) {
          setDynamicQuestions(data.questions);
          setCurrentDynamicIndex(0);
          setPhase(PHASES.DYNAMIC_QUESTIONS);
        } else {
          setCurrentAgent(selectedAgents[0]);
          setCurrentQuestionIndex(0);
          setPhase(PHASES.GUIDED_QA);
        }
      } else {
        console.warn('Dynamische Fragen konnten nicht geladen werden, verwende statische Fragen');
        setCurrentAgent(selectedAgents[0]);
        setCurrentQuestionIndex(0);
        setPhase(PHASES.GUIDED_QA);
      }
    } catch (error) {
      console.error('Fehler beim Laden der dynamischen Fragen:', error);
      setCurrentAgent(selectedAgents[0]);
      setCurrentQuestionIndex(0);
      setPhase(PHASES.GUIDED_QA);
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  }, [apiBase, selectedAgents, vision, setPhase, setIsLoading, setLoadingMessage]);

  const handleDynamicAnswer = useCallback((answer) => {
    if (!answer.skipped) {
      setAnswers(prev => [...prev, {
        ...answer,
        questionId: answer.questionId,
        agents: answer.agents || [answer.agent || 'Unknown'],
        agent: (answer.agents && answer.agents[0]) || answer.agent || 'Unknown',
        selectedValues: answer.selectedValues || [],
        customText: answer.customText || '',
        timestamp: new Date().toISOString(),
        isDynamic: true
      }]);
    } else {
      const agentNames = (answer.agents || [answer.agent]).join(', ');
      setOpenPoints(prev => [...prev, `${agentNames}: ${answer.question || 'Frage übersprungen'}`]);
    }

    if (currentDynamicIndex < dynamicQuestions.length - 1) {
      setCurrentDynamicIndex(prev => prev + 1);
    } else {
      // ÄNDERUNG 29.01.2026 v1.2: Feedback nach dynamischen Fragen
      setCompletedAgent('Dynamische Fragen');
      setPendingNextAgent(selectedAgents[0]);
      setPhase(PHASES.AGENT_FEEDBACK);
    }
  }, [currentDynamicIndex, dynamicQuestions.length, selectedAgents, setPhase]);

  const handleAnswer = useCallback((questionId, selectedValues, customText = null, skipped = false) => {
    const currentQ = agentQuestions[currentAgent]?.[currentQuestionIndex];
    const answer = {
      questionId,
      questionText: currentQ?.question || '',
      agent: currentAgent,
      selectedValues: Array.isArray(selectedValues) ? selectedValues : [selectedValues],
      customText,
      skipped,
      timestamp: new Date().toISOString()
    };

    setAnswers(prev => [...prev, answer]);

    if (skipped) {
      setOpenPoints(prev => [...prev, `${currentAgent}: ${currentQ?.question}`]);
    }

    const questions = agentQuestions[currentAgent] || [];
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else {
      // ÄNDERUNG 29.01.2026 v1.2: Feedback nach jeder Agent-Runde
      const agentIndex = selectedAgents.indexOf(currentAgent);
      if (agentIndex < selectedAgents.length - 1) {
        setCompletedAgent(currentAgent);
        setPendingNextAgent(selectedAgents[agentIndex + 1]);
        setPhase(PHASES.AGENT_FEEDBACK);
      } else {
        // Letzter Agent - direkt zur Summary
        setCompletedAgent(currentAgent);
        setPendingNextAgent(null);
        setPhase(PHASES.AGENT_FEEDBACK);
      }
    }
  }, [agentQuestions, currentAgent, currentQuestionIndex, selectedAgents, setPhase]);

  // ÄNDERUNG 29.01.2026 v1.1: Vollständiger Session-Restore
  const restoreSession = useCallback((savedSession) => {
    if (!savedSession) return false;

    try {
      if (savedSession.selectedAgents) setSelectedAgents(savedSession.selectedAgents);
      if (savedSession.dynamicQuestions) setDynamicQuestions(savedSession.dynamicQuestions);
      if (typeof savedSession.currentDynamicIndex === 'number') setCurrentDynamicIndex(savedSession.currentDynamicIndex);
      if (savedSession.currentAgent) setCurrentAgent(savedSession.currentAgent);
      if (typeof savedSession.currentQuestionIndex === 'number') setCurrentQuestionIndex(savedSession.currentQuestionIndex);
      if (savedSession.answers) setAnswers(savedSession.answers);
      if (savedSession.openPoints) setOpenPoints(savedSession.openPoints);
      // agentQuestions werden aus defaultQuestions geladen
      setAgentQuestions(defaultQuestions);
      return true;
    } catch (e) {
      console.error('Fehler beim Wiederherstellen der Session:', e);
      return false;
    }
  }, [defaultQuestions]);

  // ÄNDERUNG 29.01.2026 v1.2: Feedback-Schleifen Handler
  const handleFeedbackContinue = useCallback(() => {
    if (pendingNextAgent) {
      setCurrentAgent(pendingNextAgent);
      setCurrentQuestionIndex(0);
      setPhase(PHASES.GUIDED_QA);
    } else {
      // Kein weiterer Agent - zur Summary
      setPhase(PHASES.SUMMARY);
    }
    setCompletedAgent(null);
    setPendingNextAgent(null);
  }, [pendingNextAgent, setPhase]);

  // Antworten des aktuellen Agents aus answers filtern
  const getAgentAnswers = useCallback((agentName) => {
    if (agentName === 'Dynamische Fragen') {
      return answers.filter(a => a.isDynamic);
    }
    return answers.filter(a => a.agent === agentName);
  }, [answers]);

  return {
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
    // ÄNDERUNG 29.01.2026 v1.1: Session-Restore
    restoreSession,
    // ÄNDERUNG 29.01.2026 v1.2: Feedback-Schleifen
    completedAgent,
    pendingNextAgent,
    handleFeedbackContinue,
    getAgentAnswers
  };
};
