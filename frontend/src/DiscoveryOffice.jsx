/**
 * Author: rahn / Claude
 * Datum: 29.01.2026
 * Version: 1.3
 * Beschreibung: Discovery Office - Strukturierte Projektaufnahme mit Guided Choice System.
 *               Implementiert interaktive Fragen mit vorgeschlagenen Antwortoptionen.
 *
 * ÄNDERUNG 29.01.2026 v1.1: Fehlende Agenten-Fragen für Data Researcher, Designer und Security hinzugefügt.
 * ÄNDERUNG 29.01.2026 v1.2: Dynamische LLM-generierte Fragen pro Agent (projektspezifisch).
 * ÄNDERUNG 29.01.2026 v1.3: Multi-Agent Support nach Backend-Deduplizierung.
 *                           Fragen mit agents: [] Array statt verschachtelter Struktur.
 */

import React, { useState, useEffect } from 'react';
import { useOfficeCommon } from './hooks/useOfficeCommon';
import { motion, AnimatePresence } from 'framer-motion';
import DynamicQuestionCard from './components/DynamicQuestionCard';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Circle,
  MessageSquare,
  Users,
  FileText,
  Lightbulb,
  Star,
  SkipForward,
  Edit3,
  Save,
  Download,
  RefreshCw
} from 'lucide-react';

// Phasen der Discovery Session
// ÄNDERUNG 29.01.2026: Neue Phase DYNAMIC_QUESTIONS für LLM-generierte Fragen
const PHASES = {
  VISION: 'vision',
  TEAM_SETUP: 'team_setup',
  DYNAMIC_QUESTIONS: 'dynamic_questions',
  GUIDED_QA: 'guided_qa',
  SUMMARY: 'summary',
  BRIEFING: 'briefing'
};

// API Base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Agenten-Farben
const AGENT_COLORS = {
  'Analyst': 'blue',
  'Data Researcher': 'green',
  'Coder': 'yellow',
  'Tester': 'purple',
  'Designer': 'cyan',
  'Planner': 'red',
  'Security': 'orange'
};

const DiscoveryOffice = ({
  onBack,
  onComplete,
  wsConnection,
  logs = []
}) => {
  const { logRef, getStatusBadge, formatTime } = useOfficeCommon(logs);

  // Session State
  const [phase, setPhase] = useState(PHASES.VISION);
  const [vision, setVision] = useState('');
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [currentAgent, setCurrentAgent] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [openPoints, setOpenPoints] = useState([]);
  const [briefing, setBriefing] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');

  // Fragen pro Agent (vereinfachte Version für Frontend)
  const [agentQuestions, setAgentQuestions] = useState({});

  // ÄNDERUNG 29.01.2026 v1.3: State für dynamische LLM-Fragen (flache Struktur nach Deduplizierung)
  // Backend liefert jetzt: [{id, question, agents: [...], options, ...}, ...]
  const [dynamicQuestions, setDynamicQuestions] = useState([]);
  const [currentDynamicIndex, setCurrentDynamicIndex] = useState(0);

  // Vordefinierte Fragen (wird später vom Backend geladen)
  const defaultQuestions = {
    'Analyst': [
      {
        id: 'analyst_purpose',
        question: 'Was ist der primäre Geschäftszweck dieses Projekts?',
        options: [
          { text: 'Interne Prozessoptimierung', value: 'internal', recommended: false },
          { text: 'Kundenprodukt / Externe Nutzung', value: 'customer', recommended: true, reason: 'Höhere Qualitätsanforderungen' },
          { text: 'Forschung / Prototyp', value: 'research', recommended: false },
          { text: 'Datenanalyse / Reporting', value: 'analytics', recommended: false }
        ],
        allowCustom: true,
        allowSkip: true
      },
      {
        id: 'analyst_users',
        question: 'Wer sind die Hauptnutzer des Systems?',
        options: [
          { text: 'Technische Mitarbeiter', value: 'technical', recommended: false },
          { text: 'Nicht-technische Endnutzer', value: 'non_technical', recommended: true, reason: 'Erfordert bessere UX' },
          { text: 'Administratoren', value: 'admins', recommended: false },
          { text: 'Externe Kunden', value: 'external', recommended: false }
        ],
        multiple: true,
        allowCustom: true
      }
    ],
    'Coder': [
      {
        id: 'coder_language',
        question: 'Gibt es Vorgaben für die Programmiersprache?',
        options: [
          { text: 'Python', value: 'python', recommended: true, reason: 'Flexibel, große Community' },
          { text: 'JavaScript / TypeScript', value: 'javascript', recommended: false },
          { text: 'Java', value: 'java', recommended: false },
          { text: 'Keine Vorgabe - beste Wahl treffen', value: 'auto', recommended: false }
        ],
        allowCustom: true
      },
      {
        id: 'coder_deployment',
        question: 'Welche Deployment-Umgebung ist geplant?',
        options: [
          { text: 'Lokale Ausführung', value: 'local', recommended: true, reason: 'Einfachster Start' },
          { text: 'Cloud (AWS, Azure, GCP)', value: 'cloud', recommended: false },
          { text: 'Docker Container', value: 'docker', recommended: false },
          { text: 'Noch unklar', value: 'unknown', recommended: false }
        ]
      }
    ],
    'Tester': [
      {
        id: 'tester_coverage',
        question: 'Welche Test-Abdeckung wird erwartet?',
        options: [
          { text: 'Minimal (nur kritische Pfade)', value: 'minimal', recommended: false },
          { text: 'Standard (Unit + Integration)', value: 'standard', recommended: true },
          { text: 'Umfassend (inkl. E2E)', value: 'comprehensive', recommended: false },
          { text: 'Keine automatisierten Tests', value: 'none', recommended: false }
        ]
      }
    ],
    'Planner': [
      {
        id: 'planner_timeline',
        question: 'Wie ist der gewünschte Zeitrahmen?',
        options: [
          { text: 'So schnell wie möglich', value: 'asap', recommended: false },
          { text: '1-2 Wochen', value: 'short', recommended: true },
          { text: '1 Monat', value: 'medium', recommended: false },
          { text: 'Kein fester Termin', value: 'flexible', recommended: false }
        ]
      }
    ],
    // ÄNDERUNG 29.01.2026: Fehlende Agenten-Fragen hinzugefügt
    'Data Researcher': [
      {
        id: 'researcher_sources',
        question: 'Welche Datenquellen sollen verwendet werden?',
        options: [
          { text: 'Interne Datenbanken', value: 'internal_db', recommended: true, reason: 'Direkter Zugriff' },
          { text: 'Externe APIs', value: 'external_api', recommended: false },
          { text: 'Dateien (CSV, Excel, JSON)', value: 'files', recommended: false },
          { text: 'Web Scraping', value: 'scraping', recommended: false }
        ],
        multiple: true,
        allowCustom: true
      },
      {
        id: 'researcher_volume',
        question: 'Welches Datenvolumen wird erwartet?',
        options: [
          { text: 'Klein (< 10.000 Datensätze)', value: 'small', recommended: true },
          { text: 'Mittel (10.000 - 1 Million)', value: 'medium', recommended: false },
          { text: 'Groß (> 1 Million)', value: 'large', recommended: false },
          { text: 'Noch unklar', value: 'unknown', recommended: false }
        ]
      }
    ],
    'Designer': [
      {
        id: 'designer_style',
        question: 'Welchen Designstil bevorzugst du?',
        options: [
          { text: 'Modern / Minimalistisch', value: 'modern', recommended: true, reason: 'Zeitgemäß und übersichtlich' },
          { text: 'Klassisch / Business', value: 'business', recommended: false },
          { text: 'Verspielt / Kreativ', value: 'creative', recommended: false },
          { text: 'Kein spezieller Stil', value: 'auto', recommended: false }
        ]
      },
      {
        id: 'designer_responsive',
        question: 'Welche Geräte sollen unterstützt werden?',
        options: [
          { text: 'Nur Desktop', value: 'desktop', recommended: false },
          { text: 'Desktop + Tablet', value: 'desktop_tablet', recommended: false },
          { text: 'Alle Geräte (Responsive)', value: 'responsive', recommended: true, reason: 'Maximale Reichweite' },
          { text: 'Mobile First', value: 'mobile_first', recommended: false }
        ]
      }
    ],
    'Security': [
      {
        id: 'security_auth',
        question: 'Welche Authentifizierung wird benötigt?',
        options: [
          { text: 'Keine (öffentliche Anwendung)', value: 'none', recommended: false },
          { text: 'Einfache Anmeldung (Benutzername/Passwort)', value: 'basic', recommended: true },
          { text: 'OAuth / Social Login', value: 'oauth', recommended: false },
          { text: 'Enterprise SSO', value: 'sso', recommended: false }
        ]
      },
      {
        id: 'security_data',
        question: 'Welche Daten-Sensitivität liegt vor?',
        options: [
          { text: 'Öffentliche Daten', value: 'public', recommended: false },
          { text: 'Interne Daten', value: 'internal', recommended: true },
          { text: 'Personenbezogene Daten (DSGVO)', value: 'personal', recommended: false },
          { text: 'Hochsensible Daten', value: 'sensitive', recommended: false }
        ]
      }
    ]
  };

  // Phase 1: Vision eingeben
  const handleVisionSubmit = () => {
    if (!vision.trim()) return;

    setIsLoading(true);

    // Simuliere Team-Zusammenstellung (später: API-Call)
    setTimeout(() => {
      const agents = ['Analyst', 'Coder', 'Tester', 'Planner'];

      // Bedingte Agenten basierend auf Vision
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
  };

  // Phase 2: Team bestätigen und dynamische Fragen laden
  // ÄNDERUNG 29.01.2026: API-Call für LLM-generierte Fragen
  const handleTeamConfirm = async () => {
    if (selectedAgents.length === 0) return;

    setIsLoading(true);
    setLoadingMessage('Agenten analysieren dein Projekt...');

    try {
      // Dynamische Fragen vom Backend holen
      const response = await fetch(`${API_BASE}/discovery/generate-questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vision, agents: selectedAgents })
      });

      if (response.ok) {
        const data = await response.json();

        if (data.questions && data.questions.length > 0) {
          // ÄNDERUNG 29.01.2026 v1.3: Dynamische Fragen sind jetzt flach (dedupliziert)
          // Format: [{id, question, agents: [...], options, ...}, ...]
          setDynamicQuestions(data.questions);
          setCurrentDynamicIndex(0);
          setPhase(PHASES.DYNAMIC_QUESTIONS);
        } else {
          // Keine dynamischen Fragen -> direkt zu statischen Fragen
          setCurrentAgent(selectedAgents[0]);
          setCurrentQuestionIndex(0);
          setPhase(PHASES.GUIDED_QA);
        }
      } else {
        // API-Fehler -> Fallback zu statischen Fragen
        console.warn('Dynamische Fragen konnten nicht geladen werden, verwende statische Fragen');
        setCurrentAgent(selectedAgents[0]);
        setCurrentQuestionIndex(0);
        setPhase(PHASES.GUIDED_QA);
      }
    } catch (error) {
      console.error('Fehler beim Laden der dynamischen Fragen:', error);
      // Fallback zu statischen Fragen
      setCurrentAgent(selectedAgents[0]);
      setCurrentQuestionIndex(0);
      setPhase(PHASES.GUIDED_QA);
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  };

  // Dynamische Frage beantworten
  // ÄNDERUNG 29.01.2026 v1.3: Vereinfachte Logik für flache Fragen-Struktur
  const handleDynamicAnswer = (answer) => {
    // Antwort speichern (mit agents Array für Multi-Agent Support)
    if (!answer.skipped) {
      setAnswers(prev => [...prev, {
        ...answer,
        questionId: answer.questionId,
        // ÄNDERUNG 29.01.2026 v1.3: agents Array statt einzelnem agent
        agents: answer.agents || [answer.agent || 'Unknown'],
        // Für Abwärtskompatibilität: Erster Agent als Fallback
        agent: (answer.agents && answer.agents[0]) || answer.agent || 'Unknown',
        selectedValues: answer.selectedValues || [],
        customText: answer.customText || '',
        timestamp: new Date().toISOString(),
        isDynamic: true
      }]);
    } else {
      // Übersprungene Frage als offener Punkt
      const agentNames = (answer.agents || [answer.agent]).join(', ');
      setOpenPoints(prev => [...prev, `${agentNames}: ${answer.question || 'Frage übersprungen'}`]);
    }

    // ÄNDERUNG 29.01.2026 v1.3: Einfache Index-Navigation durch flaches Array
    if (currentDynamicIndex < dynamicQuestions.length - 1) {
      // Nächste Frage
      setCurrentDynamicIndex(prev => prev + 1);
    } else {
      // Alle dynamischen Fragen beantwortet -> zu statischen Fragen
      setCurrentAgent(selectedAgents[0]);
      setCurrentQuestionIndex(0);
      setPhase(PHASES.GUIDED_QA);
    }
  };

  // Phase 3: Antwort speichern
  const handleAnswer = (questionId, selectedValues, customText = null, skipped = false) => {
    const answer = {
      questionId,
      agent: currentAgent,
      selectedValues: Array.isArray(selectedValues) ? selectedValues : [selectedValues],
      customText,
      skipped,
      timestamp: new Date().toISOString()
    };

    setAnswers(prev => [...prev, answer]);

    if (skipped) {
      const currentQ = agentQuestions[currentAgent]?.[currentQuestionIndex];
      setOpenPoints(prev => [...prev, `${currentAgent}: ${currentQ?.question}`]);
    }

    // Nächste Frage oder nächster Agent
    const questions = agentQuestions[currentAgent] || [];
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
    } else {
      // Nächster Agent
      const agentIndex = selectedAgents.indexOf(currentAgent);
      if (agentIndex < selectedAgents.length - 1) {
        setCurrentAgent(selectedAgents[agentIndex + 1]);
        setCurrentQuestionIndex(0);
      } else {
        // Alle Fragen beantwortet -> Zusammenfassung
        setPhase(PHASES.SUMMARY);
      }
    }
  };

  // Phase 4: Briefing generieren
  const handleGenerateBriefing = () => {
    setIsLoading(true);

    // Generiere Briefing aus Antworten
    setTimeout(() => {
      const generatedBriefing = {
        projectName: vision.split(' ').slice(0, 3).join('_').toLowerCase(),
        date: new Date().toLocaleDateString('de-DE'),
        agents: selectedAgents,
        goal: vision,
        answers: answers,
        openPoints: openPoints,
        techRequirements: extractTechRequirements(answers)
      };

      setBriefing(generatedBriefing);
      setPhase(PHASES.BRIEFING);
      setIsLoading(false);
    }, 1500);
  };

  // Helfer: Tech-Anforderungen extrahieren
  const extractTechRequirements = (answers) => {
    const tech = {};
    answers.forEach(a => {
      if (a.questionId === 'coder_language' && a.selectedValues.length > 0) {
        tech.language = a.selectedValues[0];
      }
      if (a.questionId === 'coder_deployment' && a.selectedValues.length > 0) {
        tech.deployment = a.selectedValues[0];
      }
    });
    return tech;
  };

  // Export Briefing
  const handleExportBriefing = () => {
    if (!briefing) return;

    const markdown = generateBriefingMarkdown(briefing);
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `briefing_${briefing.projectName}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Markdown-Generator
  const generateBriefingMarkdown = (b) => {
    return `# PROJEKTBRIEFING

**Projekt:** ${b.projectName}
**Datum:** ${b.date}
**Teilnehmende Agenten:** ${b.agents.join(', ')}

---

## PROJEKTZIEL

${b.goal}

---

## TECHNISCHE ANFORDERUNGEN

- **Sprache:** ${b.techRequirements.language || 'auto'}
- **Deployment:** ${b.techRequirements.deployment || 'local'}

---

## OFFENE PUNKTE

${b.openPoints.length > 0 ? b.openPoints.map(p => `- ${p}`).join('\n') : '- Keine offenen Punkte'}

---

*Generiert von AgentSmith Discovery Session*
`;
  };

  // Render: Question Card
  const QuestionCard = ({ question, onAnswer }) => {
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

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-slate-800 rounded-xl p-6 border border-slate-700"
      >
        {/* Agent Header */}
        <div className={`flex items-center gap-2 mb-4 text-${color}-400`}>
          <MessageSquare size={20} />
          <span className="font-semibold">{currentAgent} fragt:</span>
        </div>

        {/* Frage */}
        <h3 className="text-xl font-bold text-white mb-6">{question.question}</h3>

        {/* Optionen */}
        <div className="space-y-3 mb-6">
          {question.options.map((opt, idx) => (
            <button
              key={idx}
              onClick={() => handleSelect(opt.value)}
              className={`w-full p-4 rounded-lg border-2 transition-all text-left flex items-start gap-3 ${
                (question.multiple ? selected.includes(opt.value) : selected === opt.value)
                  ? `border-${color}-500 bg-${color}-900/30`
                  : 'border-slate-600 hover:border-slate-500 bg-slate-700/50'
              }`}
            >
              <div className="mt-0.5">
                {(question.multiple ? selected.includes(opt.value) : selected === opt.value) ? (
                  <CheckCircle size={20} className={`text-${color}-400`} />
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
          ))}

          {/* Eigene Eingabe */}
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

        {/* Actions */}
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
            disabled={!showCustom && selected === null}
            className={`flex items-center gap-2 px-6 py-2 rounded-lg font-semibold transition-all ${
              (showCustom && customInput.trim()) || selected !== null
                ? `bg-${color}-600 hover:bg-${color}-500 text-white`
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

  // Progress Bar
  // ÄNDERUNG 29.01.2026: DYNAMIC_QUESTIONS Phase hinzugefügt
  const ProgressBar = () => {
    const phases = [
      { key: PHASES.VISION, label: 'Vision', icon: Lightbulb },
      { key: PHASES.TEAM_SETUP, label: 'Team', icon: Users },
      { key: PHASES.DYNAMIC_QUESTIONS, label: 'Projekt-Fragen', icon: MessageSquare },
      { key: PHASES.GUIDED_QA, label: 'Tech-Fragen', icon: MessageSquare },
      { key: PHASES.SUMMARY, label: 'Zusammenfassung', icon: CheckCircle },
      { key: PHASES.BRIEFING, label: 'Briefing', icon: FileText }
    ];

    const currentIndex = phases.findIndex(p => p.key === phase);

    return (
      <div className="flex items-center justify-between mb-8 px-4">
        {phases.map((p, idx) => {
          const Icon = p.icon;
          const isActive = idx === currentIndex;
          const isComplete = idx < currentIndex;

          return (
            <React.Fragment key={p.key}>
              <div className={`flex flex-col items-center ${
                isActive ? 'text-cyan-400' : isComplete ? 'text-green-400' : 'text-slate-500'
              }`}>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  isActive ? 'bg-cyan-900/50 ring-2 ring-cyan-400' :
                  isComplete ? 'bg-green-900/50' : 'bg-slate-800'
                }`}>
                  <Icon size={20} />
                </div>
                <span className="text-xs mt-2">{p.label}</span>
              </div>
              {idx < phases.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${
                  idx < currentIndex ? 'bg-green-400' : 'bg-slate-700'
                }`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
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

      {/* Progress */}
      <ProgressBar />

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

          {/* Phase 2: Team */}
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
                  Basierend auf deiner Vision wurden folgende Experten ausgewählt:
                </p>
              </div>

              <div className="space-y-3 mb-8">
                {selectedAgents.map((agent, idx) => (
                  <div
                    key={agent}
                    className={`p-4 rounded-lg bg-slate-700/50 border border-slate-600 flex items-center gap-3`}
                  >
                    <div className={`w-3 h-3 rounded-full bg-${AGENT_COLORS[agent] || 'gray'}-400`} />
                    <span className="text-white font-medium">{agent}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={handleTeamConfirm}
                disabled={isLoading}
                className={`w-full py-3 rounded-lg font-semibold flex items-center justify-center gap-2 ${
                  isLoading
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
                  onClick={handleExportBriefing}
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
