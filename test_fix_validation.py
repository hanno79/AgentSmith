#!/usr/bin/env python3
"""Test-Script zur Validierung des _is_targeted_fix_context Fixes"""

def _is_targeted_fix_context(feedback: str) -> bool:
    """Kopie der Funktion zum Testen"""
    if not feedback:
        return False
    
    fix_indicators = [
        # Englische Error-Typen
        "TypeError:", "NameError:", "SyntaxError:", "ImportError:",
        "AttributeError:", "KeyError:", "ValueError:", "ModuleNotFoundError:",
        "expected", "got", "argument", "parameter", "takes",
        "missing", "undefined", "not defined", "cannot import",
        # Deutsche Fehlerbegriffe
        "Syntaxfehler", "Fehler:", "ungültig", "fehlgeschlagen",
        "nicht gefunden", "nicht definiert", "fehlerhaft", "Formatierung",
        # FIX 05.02.2026: Additive Änderungen (Unit-Tests, Dokumentation, etc.)
        "unit-test", "unittest", "test", "erstelle", "hinzufügen", "add",
        "create", "implement", "dokumentation", "docstring", "kommentar"
    ]
    
    feedback_lower = feedback.lower()
    return any(ind.lower() in feedback_lower for ind in fix_indicators)


# Test-Cases
test_cases = [
    {
        "name": "Unit-Tests fehlen (Deutsch)",
        "feedback": """🧪 UNIT-TESTS FEHLEN:
Es wurden keine Unit-Tests gefunden (tests/ Verzeichnis oder *_test.py Dateien).
PFLICHT: Erstelle Unit-Tests für alle Funktionen:
- Datei: tests/test_calculator.py (für pytest)""",
        "expected": True
    },
    {
        "name": "TypeError",
        "feedback": "TypeError: 'str' object has no attribute 'keys'",
        "expected": True
    },
    {
        "name": "Allgemeines Feedback ohne Indikatoren",
        "feedback": "Der Code sieht gut aus, aber könnte besser strukturiert sein.",
        "expected": False
    },
    {
        "name": "Dokumentation hinzufügen",
        "feedback": "Bitte füge Dokumentation für die Funktion calculate() hinzu.",
        "expected": True
    }
]

print("=" * 60)
print("TEST: _is_targeted_fix_context Fix-Validierung")
print("=" * 60)

passed = 0
failed = 0

for test in test_cases:
    result = _is_targeted_fix_context(test["feedback"])
    status = "✅ PASS" if result == test["expected"] else "❌ FAIL"
    
    if result == test["expected"]:
        passed += 1
    else:
        failed += 1
    
    print(f"\n{status} - {test['name']}")
    print(f"  Expected: {test['expected']}, Got: {result}")
    if result != test["expected"]:
        print(f"  Feedback: {test['feedback'][:100]}...")

print("\n" + "=" * 60)
print(f"ERGEBNIS: {passed} passed, {failed} failed")
print("=" * 60)
