/**
 * Author: rahn
 * Datum: 29.01.2026
 * Version: 1.2
 * Beschreibung: Hook für Briefing-Erstellung und Export.
 */
// ÄNDERUNG 29.01.2026: Briefing-Logik ausgelagert
// ÄNDERUNG 29.01.2026 v1.1: SCOPE und ERFOLGSKRITERIEN Sektionen hinzugefügt
// ÄNDERUNG 29.01.2026 v1.2: DATENGRUNDLAGE und TIMELINE Sektionen hinzugefügt

import { useCallback } from 'react';

export const useBriefing = () => {
  const extractTechRequirements = useCallback((answers) => {
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
  }, []);

  // ÄNDERUNG 29.01.2026: SCOPE Extraktion
  const extractScope = useCallback((answers) => {
    const scope = { inScope: [], outScope: [] };
    answers.forEach(a => {
      if (a.questionId === 'analyst_scope_in' && a.selectedValues.length > 0) {
        scope.inScope = a.selectedValues;
        if (a.customText) scope.inScope.push(a.customText);
      }
      if (a.questionId === 'analyst_scope_out' && a.selectedValues.length > 0) {
        scope.outScope = a.selectedValues;
        if (a.customText) scope.outScope.push(a.customText);
      }
    });
    return scope;
  }, []);

  // ÄNDERUNG 29.01.2026: ERFOLGSKRITERIEN Extraktion
  const extractSuccessCriteria = useCallback((answers) => {
    const criteria = [];
    answers.forEach(a => {
      if (a.questionId === 'analyst_success_criteria' && a.selectedValues.length > 0) {
        criteria.push(...a.selectedValues);
        if (a.customText) criteria.push(a.customText);
      }
    });
    return criteria;
  }, []);

  // ÄNDERUNG 29.01.2026 v1.2: DATENGRUNDLAGE Extraktion
  const extractDataFoundation = useCallback((answers) => {
    const data = { sources: [], availability: '', quality: '' };
    answers.forEach(a => {
      if (a.questionId === 'researcher_sources' && a.selectedValues.length > 0) {
        data.sources = a.selectedValues;
        if (a.customText) data.sources.push(a.customText);
      }
      if (a.questionId === 'researcher_data_availability' && a.selectedValues.length > 0) {
        data.availability = a.selectedValues[0];
      }
      if (a.questionId === 'researcher_data_quality' && a.selectedValues.length > 0) {
        data.quality = a.selectedValues[0];
      }
    });
    return data;
  }, []);

  // ÄNDERUNG 29.01.2026 v1.2: TIMELINE Extraktion
  const extractTimeline = useCallback((answers) => {
    const timeline = { timeframe: '', milestones: [], deadline: '' };
    answers.forEach(a => {
      if (a.questionId === 'planner_timeline' && a.selectedValues.length > 0) {
        timeline.timeframe = a.selectedValues[0];
      }
      if (a.questionId === 'planner_milestones' && a.selectedValues.length > 0) {
        timeline.milestones = a.selectedValues;
        if (a.customText) timeline.milestones.push(a.customText);
      }
      if (a.questionId === 'planner_deadline' && a.selectedValues.length > 0) {
        timeline.deadline = a.selectedValues[0];
        if (a.customText) timeline.deadline += ` (${a.customText})`;
      }
    });
    return timeline;
  }, []);

  const buildBriefing = useCallback((vision, selectedAgents, answers, openPoints) => {
    return {
      projectName: vision.split(' ').slice(0, 3).join('_').toLowerCase(),
      date: new Date().toLocaleDateString('de-DE'),
      agents: selectedAgents,
      goal: vision,
      answers,
      openPoints,
      techRequirements: extractTechRequirements(answers),
      // ÄNDERUNG 29.01.2026: Neue Sektionen
      scope: extractScope(answers),
      successCriteria: extractSuccessCriteria(answers),
      // ÄNDERUNG 29.01.2026 v1.2: Weitere Sektionen
      dataFoundation: extractDataFoundation(answers),
      timeline: extractTimeline(answers)
    };
  }, [extractTechRequirements, extractScope, extractSuccessCriteria, extractDataFoundation, extractTimeline]);

  const generateBriefingMarkdown = useCallback((b) => {
    return `# PROJEKTBRIEFING

**Projekt:** ${b.projectName}
**Datum:** ${b.date}
**Teilnehmende Agenten:** ${b.agents.join(', ')}

---

## PROJEKTZIEL

${b.goal}

---

## SCOPE

### In-Scope (enthalten)
${b.scope?.inScope?.length > 0 ? b.scope.inScope.map(s => `- ${s}`).join('\n') : '- Noch nicht definiert'}

### Out-of-Scope (ausgeschlossen)
${b.scope?.outScope?.length > 0 ? b.scope.outScope.map(s => `- ${s}`).join('\n') : '- Noch nicht definiert'}

---

## ERFOLGSKRITERIEN

${b.successCriteria?.length > 0 ? b.successCriteria.map(c => `- ${c}`).join('\n') : '- Noch nicht definiert'}

---

## DATENGRUNDLAGE

- **Quellen:** ${b.dataFoundation?.sources?.length > 0 ? b.dataFoundation.sources.join(', ') : 'Noch nicht definiert'}
- **Verfügbarkeit:** ${b.dataFoundation?.availability || 'Noch nicht definiert'}
- **Qualität:** ${b.dataFoundation?.quality || 'Noch nicht definiert'}

---

## TIMELINE

- **Zeitrahmen:** ${b.timeline?.timeframe || 'Noch nicht definiert'}
- **Meilensteine:** ${b.timeline?.milestones?.length > 0 ? b.timeline.milestones.join(', ') : 'Noch nicht definiert'}
- **Deadline:** ${b.timeline?.deadline || 'Noch nicht definiert'}

---

## TECHNISCHE ANFORDERUNGEN

- **Sprache:** ${b.techRequirements.language || 'auto'}
- **Deployment:** ${b.techRequirements.deployment || 'local'}

---

## ENTSCHEIDUNGEN AUS DISCOVERY

${b.answers && b.answers.length > 0
  ? b.answers
      .filter(a => !a.skipped)
      .map(a => {
        const question = a.questionText || a.question || '';
        const values = a.selectedValues?.join(', ') || a.customText || '';
        const agent = a.agent || (a.agents?.join(', ')) || 'Allgemein';
        // ÄNDERUNG 29.01.2026: Auto-Fallback Kennzeichnung
        const autoTag = a.autoFallback ? ' *(Auto-Empfehlung)*' : '';
        return question
          ? `### ${agent}\n**Frage:** ${question}\n**Antwort:** ${values}${autoTag}\n`
          : `- **${agent}:** ${values}${autoTag}`;
      })
      .join('\n')
  : '- Keine spezifischen Entscheidungen'}

---

## OFFENE PUNKTE

${b.openPoints.length > 0 ? b.openPoints.map(p => `- ${p}`).join('\n') : '- Keine offenen Punkte'}

---

*Generiert von AgentSmith Discovery Session*
`;
  }, []);

  const exportBriefing = useCallback((briefing) => {
    if (!briefing) return;
    const markdown = generateBriefingMarkdown(briefing);
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `briefing_${briefing.projectName}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [generateBriefingMarkdown]);

  return {
    buildBriefing,
    generateBriefingMarkdown,
    exportBriefing
  };
};
