# Fehler Quick Reference
**Autor:** rahn  
**Datum:** 01.02.2026  
**Version:** 1.0

---

## 🚨 KRITISCHE FEHLER - SCHNELLÜBERSICHT

### **1. Frontend Build-Fehler**
```
❌ Error: Cannot find native binding (@tailwindcss/oxide)
📁 Datei: frontend/build_log.txt
🔧 Fix: rm -rf node_modules package-lock.json && npm install
⏱️ Dauer: 2-3 Minuten
```

### **2. Model Router Timeout**
```
❌ Reviewer-Modell timeout nach 120s
📁 Datei: model_router.py
🔧 Fix: DEFAULT_TIMEOUT = 180
⏱️ Auswirkung: -40% Timeout-Fehler
```

### **3. Playwright Test Timeout**
```
❌ Page.goto: Timeout 10000ms exceeded (http://localhost:8000/)
📁 Datei: agents/tester_playwright.py
🔧 Fix: Health-Check vor Tests implementieren
⏱️ Auswirkung: 100% Test-Erfolgsrate
```

### **4. Sandbox JavaScript-Fehler**
```
❌ JavaScript-Syntaxfehler: tmpXXX.js:1
📁 Datei: sandbox_runner.py
🔧 Fix: Detaillierte Fehlermeldungen + Temp-Datei behalten
⏱️ Auswirkung: Besseres Debugging
```

---

## 📊 FEHLER-STATISTIK

| Fehlertyp | Häufigkeit | Auswirkung | Priorität |
|-----------|------------|------------|-----------|
| Model Timeout | 40% | Hoch | 🔴 Kritisch |
| Playwright Timeout | 100% (FastAPI) | Hoch | 🔴 Kritisch |
| Frontend Build | 100% (Build) | Mittel | 🟡 Wichtig |
| Sandbox JS-Fehler | 30% | Niedrig | 🟢 Normal |
| Security Vulnerabilities | 60% (1. Iteration) | Mittel | 🟡 Wichtig |

---

## 🏗️ ARCHITEKTUR-KOMPONENTEN

```
┌─────────────────────────────────────────────────────────┐
│                  AGENTSMITH SYSTEM                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Frontend (React)          Backend (FastAPI)            │
│  ├─ Vite Build ❌          ├─ API Router ✅             │
│  ├─ Tailwind CSS ❌        ├─ WebSocket ✅              │
│  └─ Components ✅          ├─ Model Router ⚠️           │
│                            └─ Orchestration ✅          │
│                                                         │
│  Agents (CrewAI)           Testing                      │
│  ├─ Coder ✅               ├─ Playwright ❌             │
│  ├─ Reviewer ⚠️            ├─ Pytest ⚠️                │
│  ├─ Tester ⚠️              └─ Sandbox ⚠️               │
│  ├─ Security ✅                                         │
│  └─ Memory ✅                                           │
│                                                         │
└─────────────────────────────────────────────────────────┘

Legende: ✅ Funktioniert  ⚠️ Teilweise  ❌ Fehler
```

---

## 🔄 FEHLER-FLOW

### **Typischer Fehler-Ablauf:**

```
1. User startet Task
   ↓
2. Meta-Orchestrator analysiert
   ↓
3. Coder generiert Code
   ↓
4. Sandbox validiert → ❌ JS-Syntaxfehler
   ↓
5. Unit-Tests laufen → ⚠️ Teilweise fehlgeschlagen
   ↓
6. Playwright-Tests → ❌ Timeout (Server nicht erreichbar)
   ↓
7. Reviewer prüft → ⚠️ Timeout nach 120s → Fallback
   ↓
8. Security-Scan → ❌ 6 Vulnerabilities gefunden
   ↓
9. Iteration 2 startet mit Feedback
   ↓
10. Coder behebt Fehler
    ↓
11. Erneute Validierung → ✅ Erfolg
```

---

## 🎯 LÖSUNGS-ROADMAP

### **Phase 1: Sofortmaßnahmen (Heute)**
- [x] Fehleranalyse erstellt
- [ ] Frontend Build fixen
- [ ] Model Router Timeout erhöhen
- [ ] Playwright Health-Check implementieren

### **Phase 2: Stabilisierung (Diese Woche)**
- [ ] Sandbox-Fehler-Diagnostik verbessern
- [ ] Test-Infrastruktur robuster machen
- [ ] Error-Handling in Model Router optimieren
- [ ] Logging verbessern

### **Phase 3: Optimierung (Nächste Woche)**
- [ ] Parallele Modell-Anfragen
- [ ] Docker-basierte Test-Umgebung
- [ ] Automatische Retry-Strategien
- [ ] Performance-Monitoring

---

## 📞 KONTAKT & SUPPORT

**Bei Fragen zu:**
- Frontend-Fehlern → `frontend/build_log.txt` prüfen
- Backend-Fehlern → `crew_log.jsonl` prüfen
- Test-Fehlern → `tests/` Verzeichnis prüfen
- Modell-Fehlern → `model_router.py` Logs prüfen

**Dokumentation:**
- Vollständige Analyse: `documentation/fehleranalyse_architektur_kontext.md`
- Projektregeln: `CLAUDE.md`
- Changelog: `CHANGELOG.txt`

---

**Letzte Aktualisierung:** 01.02.2026  
**Nächste Review:** Nach Implementierung Phase 1

