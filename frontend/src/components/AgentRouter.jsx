/**
 * Author: rahn
 * Datum: 31.01.2026
 * Version: 1.0
 * Beschreibung: AgentRouter - Routing für Agent Offices und Spezialbereiche.
 * # ÄNDERUNG [31.01.2026]: Agent-Routing aus App.jsx ausgelagert.
 */

import React from 'react';
import axios from 'axios';
import { API_BASE } from '../constants/config';
import CoderOffice from '../CoderOffice';
import TesterOffice from '../TesterOffice';
import DesignerOffice from '../DesignerOffice';
import ReviewerOffice from '../ReviewerOffice';
import ResearcherOffice from '../ResearcherOffice';
import SecurityOffice from '../SecurityOffice';
import TechStackOffice from '../TechStackOffice';
import DBDesignerOffice from '../DBDesignerOffice';
import LibraryOffice from '../LibraryOffice';
import ExternalBureauOffice from '../ExternalBureauOffice';
import DependencyOffice from '../DependencyOffice';
import DiscoveryOffice from '../DiscoveryOffice';
import DocumentationOffice from '../DocumentationOffice';
// AENDERUNG 02.02.2026: PlannerOffice hinzugefuegt
import PlannerOffice from '../PlannerOffice';
// AENDERUNG 07.02.2026: FixOffice hinzugefuegt (Fix 14)
import FixOffice from '../FixOffice';

const ROUTES = new Set([
  'agent-coder',
  'agent-tester',
  'agent-designer',
  'agent-reviewer',
  'agent-researcher',
  'agent-security',
  'agent-techstack',
  'agent-dbdesigner',
  'agent-documentation',
  'agent-planner',  // AENDERUNG 02.02.2026: Planner Office
  'agent-fix',      // AENDERUNG 07.02.2026: Fix Office (Fix 14)
  'library',
  'external-bureau',
  'dependency',
  'discovery'
]);

export const isAgentRoute = (room) => ROUTES.has(room);

const AgentRouter = ({
  currentRoom,
  setCurrentRoom,
  logs = [],
  activeAgents = {},
  agentData = {},
  setDiscoveryBriefing,
  setGoal
}) => {
  const onBackToMission = () => setCurrentRoom('mission-control');

  if (currentRoom === 'agent-coder') {
    return (
      <CoderOffice
        agentName="Coder"
        status={activeAgents?.coder?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Coder')}
        onBack={onBackToMission}
        color="blue"
        code={agentData?.coder?.code}
        files={agentData?.coder?.files}
        iteration={agentData?.coder?.iteration}
        maxIterations={agentData?.coder?.maxIterations}
        model={agentData?.coder?.model}
        tasks={agentData?.coder?.tasks}
        taskCount={agentData?.coder?.taskCount}
        modelsUsed={agentData?.coder?.modelsUsed}
        currentModel={agentData?.coder?.currentModel}
        previousModel={agentData?.coder?.previousModel}
        failedAttempts={agentData?.coder?.failedAttempts}
        totalTokens={agentData?.coder?.totalTokens || 0}
        totalCost={agentData?.coder?.totalCost || 0}
        workers={agentData?.coder?.workers || []}
      />
    );
  }
  if (currentRoom === 'agent-tester') {
    return (
      <TesterOffice
        agentName="Tester"
        status={activeAgents?.tester?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Tester')}
        onBack={onBackToMission}
        color="orange"
        defects={agentData?.tester?.defects}
        coverage={agentData?.tester?.coverage}
        stability={agentData?.tester?.stability}
        risk={agentData?.tester?.risk}
        screenshot={agentData?.tester?.screenshot}
        model={agentData?.tester?.model}
        workers={agentData?.tester?.workers || []}
      />
    );
  }
  if (currentRoom === 'agent-designer') {
    return (
      <DesignerOffice
        agentName="Designer"
        status={activeAgents?.designer?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Designer')}
        onBack={onBackToMission}
        color="pink"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        colorPalette={agentData?.designer?.colorPalette}
        typography={agentData?.designer?.typography}
        atomicAssets={agentData?.designer?.atomicAssets}
        qualityScore={agentData?.designer?.qualityScore}
        iterationInfo={agentData?.designer?.iterationInfo}
        viewport={agentData?.designer?.viewport}
        previewUrl={agentData?.designer?.previewUrl}
        concept={agentData?.designer?.concept}
        model={agentData?.designer?.model}
      />
    );
  }
  if (currentRoom === 'agent-reviewer') {
    return (
      <ReviewerOffice
        agentName="Reviewer"
        status={activeAgents?.reviewer?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Reviewer')}
        onBack={onBackToMission}
        color="yellow"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend (erweitert mit humanSummary)
        verdict={agentData?.reviewer?.verdict}
        isApproved={agentData?.reviewer?.isApproved}
        humanSummary={agentData?.reviewer?.humanSummary}
        feedback={agentData?.reviewer?.feedback}
        model={agentData?.reviewer?.model}
        iteration={agentData?.reviewer?.iteration}
        maxIterations={agentData?.reviewer?.maxIterations}
        sandboxStatus={agentData?.reviewer?.sandboxStatus}
        sandboxResult={agentData?.reviewer?.sandboxResult}
        testSummary={agentData?.reviewer?.testSummary}
      />
    );
  }
  if (currentRoom === 'agent-researcher') {
    return (
      <ResearcherOffice
        agentName="Researcher"
        status={activeAgents?.researcher?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Researcher')}
        onBack={onBackToMission}
        color="cyan"
        query={agentData?.researcher?.query}
        result={agentData?.researcher?.result}
        researchStatus={agentData?.researcher?.status}
        model={agentData?.researcher?.model}
        error={agentData?.researcher?.error}
        // ÄNDERUNG 08.02.2026: researchTimeoutMinutes entfernt - pro Agent im ModelModal
      />
    );
  }
  if (currentRoom === 'agent-security') {
    return (
      <SecurityOffice
        agentName="Security"
        status={activeAgents?.security?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'Security')}
        onBack={onBackToMission}
        color="red"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        vulnerabilities={agentData?.security?.vulnerabilities}
        overallStatus={agentData?.security?.overallStatus}
        scanResult={agentData?.security?.scanResult}
        model={agentData?.security?.model}
        scannedFiles={agentData?.security?.scannedFiles}
        // ÄNDERUNG 24.01.2026: Neue Props für Code-Scan
        scanType={agentData?.security?.scanType}
        iteration={agentData?.security?.iteration}
        blocking={agentData?.security?.blocking}
      />
    );
  }
  if (currentRoom === 'agent-techstack') {
    return (
      <TechStackOffice
        agentName="Tech-Stack"
        status={activeAgents?.techarchitect?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'TechArchitect')}
        onBack={onBackToMission}
        color="purple"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        blueprint={agentData?.techstack?.blueprint}
        model={agentData?.techstack?.model}
        decisions={agentData?.techstack?.decisions}
        dependencies={agentData?.techstack?.dependencies}
        reasoning={agentData?.techstack?.reasoning}
      />
    );
  }
  if (currentRoom === 'agent-dbdesigner') {
    return (
      <DBDesignerOffice
        agentName="Database Designer"
        status={activeAgents?.dbdesigner?.status || 'Idle'}
        logs={logs.filter(l => l.agent === 'DBDesigner')}
        onBack={onBackToMission}
        color="green"
        // ÄNDERUNG 24.01.2026: Echte Daten vom Backend
        schema={agentData?.dbdesigner?.schema}
        model={agentData?.dbdesigner?.model}
        tables={agentData?.dbdesigner?.tables}
        dbStatus={agentData?.dbdesigner?.status}
      />
    );
  }

  if (currentRoom === 'library') {
    return (
      <LibraryOffice
        onBack={onBackToMission}
        logs={logs}
      />
    );
  }

  if (currentRoom === 'external-bureau') {
    return (
      <ExternalBureauOffice
        onBack={onBackToMission}
      />
    );
  }

  if (currentRoom === 'dependency') {
    return (
      <DependencyOffice
        onBack={onBackToMission}
      />
    );
  }

  if (currentRoom === 'discovery') {
    return (
      <DiscoveryOffice
        onBack={onBackToMission}
        onComplete={async (briefing) => {
          // ÄNDERUNG 29.01.2026: Briefing speichern und an Backend senden
          if (typeof setDiscoveryBriefing === 'function') {
            setDiscoveryBriefing(briefing);
          }
          if (typeof setGoal === 'function') {
            setGoal(briefing.goal || '');
          }

          // An Backend senden für Agent-Kontext
          try {
            await axios.post(`${API_BASE}/discovery/save-briefing`, briefing);
            console.log('Discovery Briefing gespeichert:', briefing.projectName);
          } catch (e) {
            console.error('Briefing speichern fehlgeschlagen:', e);
          }

          onBackToMission();
        }}
        logs={logs}
      />
    );
  }

  if (currentRoom === 'agent-documentation') {
    return (
      <DocumentationOffice
        logs={logs.filter(l =>
          l.agent === 'DocumentationManager' ||
          l.agent === 'QualityGate'
        )}
        workerData={agentData?.documentationmanager || {}}
        status={activeAgents?.documentationmanager?.status || 'Idle'}
        onBack={onBackToMission}
      />
    );
  }

  // AENDERUNG 02.02.2026: Planner Office
  if (currentRoom === 'agent-planner') {
    return (
      <PlannerOffice
        logs={logs.filter(l => l.agent === 'Planner')}
        status={activeAgents?.planner?.status || 'Idle'}
        planData={agentData?.planner || {}}
        onBack={onBackToMission}
      />
    );
  }

  // AENDERUNG 07.02.2026: Fix Office (Fix 14)
  if (currentRoom === 'agent-fix') {
    return (
      <FixOffice
        logs={logs.filter(l => l.agent === 'Fix')}
        status={activeAgents?.fix?.status || 'Idle'}
        fixData={agentData?.fix || {}}
        onBack={onBackToMission}
      />
    );
  }

  return null;
};

export default AgentRouter;
