# MULTI-AGENTEN-WORKFLOW

**Author:** rahn
**Datum:** 02.02.2026
**Version:** 1.0

---

## ÜBERSICHT

Dieser Workflow definiert den obligatorischen Ablauf für alle Entwicklungsaufgaben.
Ziel: Maximale Parallelisierung durch mehrere Agenten bei gleichzeitiger Qualitätssicherung.

---

## PHASE 1: PLANUNG

**Agenten:** Mindestens 2 Planungsagenten parallel

**Aufgaben:**
- Aufgabe in kleine, testbare Tasks aufteilen
- Jeder Task muss ein eindeutiges, testbares Ziel haben
- Tasks nach Möglichkeit parallel erstellbar

**Output:** Liste von Tasks mit klaren Zielen

---

## PHASE 2: VALIDIERUNG

**Agenten:** 1 Validierungsagent

**Aufgaben:**
- Prüfung aller Tasks auf:
  - Eindeutigkeit
  - Widerspruchsfreiheit
  - Testbarkeit
- Bei Unklarheiten: AskUserQuestion nutzen

**Kriterium:** Ein Task ist eindeutig wenn:
- Er ein klares, messbares Ziel hat
- Er testbar ist (Erfolgskriterium definiert)
- Keine Widersprüche zu anderen Tasks bestehen

---

## PHASE 3: ORCHESTRIERUNG

**Agenten:** 1 Orchestrator-Agent

**Aufgaben:**
- Abhängigkeiten zwischen Tasks identifizieren
- Tasks gruppieren in:
  - Unabhängige Tasks (parallel ausführbar)
  - Abhängige Tasks (sequenzielle Reihenfolge)
- Ausführungsreihenfolge festlegen

**Output:** Sortierte Task-Liste mit Abhängigkeitsgraph

---

## PHASE 4: IMPLEMENTIERUNG

**Agenten:** Mehrere Coder-Agenten parallel

**Aufgaben:**
- Unabhängige Tasks parallel bearbeiten
- Abhängige Tasks in korrekter Reihenfolge
- CLAUDE.md Projektregeln beachten

**Wichtig:**
- Nur klar abgegrenzte Tasks parallel
- Bei Überschneidungen: sequenziell arbeiten

---

## PHASE 5: REVIEW

**Agenten:** Mindestens 2 Reviewer parallel

**Prüfbereiche:**
- Funktionale Fehler und Bugs
- Security Issues (OWASP Top 10)
- Code-Qualität (CLAUDE.md Regel 13)
- Performance (CLAUDE.md Regel 16)
- Einhaltung aller Projektregeln

**Output:** Liste gefundener Issues

---

## PHASE 6: ITERATION

**Ablauf:**
1. Bei gefundenen Fehlern → zurück zu Coder-Agenten
2. Nach Fixes → zurück zu Reviewern
3. Wiederholen bis keine Fehler mehr

**Abschlusskriterium:**
- Alle Reviewer melden: Keine Fehler gefunden
- Alle Tasks als erledigt markiert

---

## VISUALISIERUNG

```
[Aufgabe]
    ↓
[PHASE 1: Planung] ← Mehrere Agenten parallel
    ↓
[PHASE 2: Validierung] ← Prüfagent + AskUserQuestion
    ↓
[PHASE 3: Orchestrierung] ← Abhängigkeitsanalyse
    ↓
[PHASE 4: Implementierung] ← Mehrere Coder parallel
    ↓
[PHASE 5: Review] ← Mehrere Reviewer parallel
    ↓
[Fehler?] → JA → zurück zu Phase 4
    ↓ NEIN
[ABGESCHLOSSEN]
```

---

## COMPLIANCE

Dieser Workflow ist VERBINDLICH für alle Entwicklungsaufgaben.
Er ergänzt die Regeln in CLAUDE.md und muss zusammen mit diesen beachtet werden.
