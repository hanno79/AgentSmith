# Plan: UTDS-Konsolidierung - TargetedFix entfernen

**Author:** rahn
**Datum:** 07.02.2026
**Version:** 1.0
**Beschreibung:** Konsolidierungsplan fuer die Zusammenlegung von TargetedFix und UTDS
                   in ein einziges Fix-System (UTDS). TargetedFix wird entfernt, da es
                   vor dem Review laeuft und daher kein Reviewer-Feedback erhaelt.

<!-- AENDERUNG 07.02.2026: Initiale Erstellung des Konsolidierungsplans -->

---

## Problem

**TargetedFix** und **UTDS** sind zwei parallele Systeme für Fehlerkorrekturen:

| System | TargetedFix | UTDS |
|--------|-------------|------|
| **Timing** | VOR Review | NACH Review |
| **review_output** | `""` (leer!) | Review verfügbar |
| **Ergebnis** | ❌ "Keine analysierbaren Fehler" | ✅ Funktioniert |

### Root Cause

In [`backend/dev_loop.py:543-548`](backend/dev_loop.py:543):
```python
fix_success, fixed_code, updated_files = self._try_targeted_fix(
    sandbox_result=sandbox_result,
    review_output="",  # ❌ LEER - Review noch nicht gelaufen!
    created_files=created_files,
    ...
)
```

TargetedFix wird **vor** dem Review aufgerufen und erhält daher kein Reviewer-Feedback.

## Lösung: TargetedFix entfernen, UTDS für alles nutzen

UTDS funktioniert bereits für:
- ✅ Security-Fixes
- ✅ Sandbox-Fixes  
- ✅ Reviewer-Fixes

### Änderungen

#### 1. `backend/dev_loop.py`
- [ ] TargetedFix-Block entfernen (Zeilen 537-568)
- [ ] Stattdessen: UTDS nach Review mit kombiniertem Feedback aufrufen
- [ ] `targeted_fix_applied` Variable entfernen

#### 2. `backend/error_analyzer.py`
- [ ] `analyze_errors()` Funktion behalten (wird von anderen Modulen genutzt)
- [ ] TargetedFix-spezifische Imports prüfen

#### 3. `backend/parallel_fixer.py`
- [ ] ParallelFixer-Klasse behalten (könnte von anderen Modulen genutzt werden)
- [ ] TargetedFix-spezifische Kommentare aktualisieren

#### 4. Imports in `backend/dev_loop.py`
- [ ] TargetedFix-Imports entfernen:
  ```python
  # ENTfernen:
  from .error_analyzer import ErrorAnalyzer, analyze_errors, get_files_to_fix, save_detected_constraints
  from .parallel_fixer import ParallelFixer, should_use_parallel_fix
  ```
- [ ] `_parallel_fixer` und `_error_analyzer` aus `__init__` entfernen

### Neuer Ablauf

```
1. Coder generiert Code
2. Sandbox Tests ausführen
3. Reviewer analysiert Code  ← Reviewer-Feedback verfügbar
4. Security scannt Code
5. UTDS (kombiniert):       ← ALLES wird hier gefixt!
   - Reviewer-Fixes
   - Security-Fixes
   - Sandbox-Fixes
```

### Vorteile

1. **Einfachheit**: Ein System statt zwei
2. **Wartbarkeit**: Weniger Code = weniger Bugs
3. **Konsistenz**: UTDS funktioniert bereits
4. **Keine Redundanz**: Reviewer-Feedback wird genutzt

### Risiken

1. UTDS muss alle TargetedFix-Fälle abdecken
2. Parallele Fixes könnten langsamer sein

### Mitigation

- UTDS unterstützt bereits parallele Task-Ausführung
- Bei Bedarf kann UTDS erweitert werden
