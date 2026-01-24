# PROJEKTREGELN - AgentSmith Multi-Agent POC

**Author:** rahn
**Datum:** 24.01.2026
**Version:** 1.4

---

## ÜBERSICHT

Diese Regeln definieren die Standards für die Entwicklung und Wartung der Codebasis.
Alle Teammitglieder und KI-Assistenten müssen sich strikt an diese Regeln halten.

---

## REGEL 0: BEGRIFFE/WORTWAHL

Vermeide martialische und kriegstreiberische Worte wie "Kill the process" oder "töte den Prozess".
Nutze etwas neutrales wie "stop the process".

---

## REGEL 1: DATEI-GRÖSSENBESCHRÄNKUNG

**Skriptdateien dürfen MAXIMAL 500 Zeilen Code enthalten.**

**Vorgehen:**
- Vor jeder neuen Funktionalität prüfen: Bleibt die Datei unter 500 Zeilen?
- Bei Überschreitung: Sofortiges Refactoring erforderlich
- Code in logische Module/Dateien aufteilen
- Gemeinsame Funktionen in separate Utility-Dateien auslagern
- Vor der Umsetzung selbst darauf achten ob ein Refactoring notwendig ist

**Zweck:** Wartbarkeit und Lesbarkeit des Codes sicherstellen

---

## REGEL 2: KEINE DUPLIKATDATEIEN BEI FIXES

Bei Fehlerbehebungen NIEMALS neue Dateien mit Prefix oder Suffix erstellen wie:
- `*_fixed`, `fixed_*`
- `*_korrigiert`, `korrigiert_*`
- `*_new`, `new_*`
- `*_updated`, `updated_*`

**Vorgehen:**
- Defekte Dateien direkt editieren
- Bestehende Datei überschreiben
- Änderungen mit Kommentaren dokumentieren
- Zu einem Thema nur jeweils eine konkrete Datei erstellen

**Zweck:** Vermeidung einer unübersichtlichen Codebasis

---

## REGEL 3: VERSIONIERUNG NACH BEDARF

Neue Versionen NUR erstellen wenn:
- Eine funktionierende Version als Backup benötigt wird
- Grundlegende Architekturänderungen anstehen
- Experimentelle Features entwickelt werden
- Tatsächlich eine neue Datei erstellt werden muss

**Namenskonvention:**
- Ausschließlich Versionsnummern verwenden: `*_v1`, `*_v2`, `*_v3`
- VERBOTEN: `*_final`, `*_korrigiert`, `*_latest`, `*_backup`

**Vorgehen:**
- Sparsam verwenden - nur bei echter Notwendigkeit
- Bei Minor-Fixes: Direkte Bearbeitung ohne neue Version
- Bei Korrekturen direkt die entsprechende Datei korrigieren ohne neue zu erstellen

---

## REGEL 4: KOMMUNIKATIONSSPRACHE

**Standardsprache: DEUTSCH**

Ausnahmen nur bei expliziter anderslautender Anweisung.
Code-Kommentare, Dokumentation und Kommunikation auf Deutsch.

---

## REGEL 5: CHAT-ZUSAMMENFASSUNGEN

Bei Anfrage nach Zusammenfassung:

**Anforderungen:**
- Ausführlich und vollständig
- Chronologisch strukturiert
- Alle wichtigen Entscheidungen dokumentieren
- Aktuelle Problemstellungen erwähnen
- Nächste Schritte definieren
- Sorgfältig und konzentriert arbeiten

**Speicherort:** `documentation/chat_summary_[DATUM].txt`

**Zweck:** Nahtlose Fortsetzung in neuen Chat-Sessions

---

## REGEL 6: DATEI-ORGANISATION

**Ordnerstruktur beachten:**

```
/frontend/          → Frontend-Code, UI-Komponenten
/backend/           → Backend-Code, API-Tests
/documentation/     → Dokumentation, Zusammenfassungen, Regeln
/to_delete/         → Veraltete/obsolete Dateien
/tests/             → Test-Dateien für alle Module
/agents/            → KI-Agenten Module
/config/            → Konfigurationsdateien
```

**Vorgehen:**
- Vor Dateierstellung: Verzeichnisstruktur prüfen
- Logische Zuordnung zu entsprechendem Ordner
- Bei Unsicherheit: Dokumentation in `/documentation/`
- Immer darauf achten, Dateien am richtigen Ort zu speichern

---

## REGEL 7: CODEBASIS-BEREINIGUNG

Bei expliziter Bereinigungsanfrage:

**Vorgehen:**
1. Gesamte Codebasis analysieren
2. Veraltete/überflüssige Dateien identifizieren
3. Obsolete Versionen finden
4. Dateien nach `/to_delete/` verschieben (NICHT löschen)

**Kriterien für Verschiebung:**
- Ältere Versionen bei funktionierender neuer Version
- Test-Dateien ohne aktuellen Bezug
- Backup-Dateien älter als 30 Tage
- Dateien mit veralteten Endungen (`*_old`, `*_backup`, etc.)

---

## REGEL 8: AUTOR-KENNZEICHNUNG

**In JEDER Skriptdatei mandatory:**

**Python-Format:**
```python
"""
Author: rahn
Datum: [TT.MM.YYYY]
Version: [X.X]
Beschreibung: [Kurze Funktionsbeschreibung]
"""
```

**JavaScript/JSX-Format:**
```javascript
/**
 * Author: rahn
 * Datum: [TT.MM.YYYY]
 * Version: [X.X]
 * Beschreibung: [Kurze Funktionsbeschreibung]
 */
```

**Zweck:** Nachvollziehbarkeit und Verantwortlichkeit

---

## REGEL 9: ÄNDERUNGSDOKUMENTATION

**JEDE Änderung dokumentieren mit:**

**Format:**
```
# ÄNDERUNG [TT.MM.YYYY]: [Begründung]
# [Beschreibung der Änderung]
```

**Beispiel:**
```python
# ÄNDERUNG 11.06.2025: Bugfix für Login-Timeout
# Timeout von 5s auf 10s erhöht wegen langsamer Serverantwort
```

**Speicherort:**
- Im Code als Kommentar
- Bei größeren Änderungen zusätzlich in `CHANGELOG.txt`

---

## REGEL 10: KEINE DUMMY- UND FALLBACK-WERTE

**STRIKT VERBOTEN:**
- Hardcodierte Dummy-Werte ohne Kennzeichnung
- Versteckte Fallback-Werte bei Fehlern
- Ausgedachte Testwerte die echte Daten vortäuschen
- "Irgendein Wert" bei Problemen oder Fehlern

**Falls absolut notwendig:**

Dummy-Werte: Eindeutig kennzeichnen mit Kommentaren
```python
# DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
test_user = "DUMMY_USER_FOR_TESTING_ONLY"
```

Fallback-Werte: Explizit ausweisen und loggen
```python
# FALLBACK: Verwendet wenn API nicht erreichbar
fallback_value = "FALLBACK_API_UNAVAILABLE"
print("WARNUNG: Fallback-Wert verwendet - API Problem!")
```

**Kennzeichnung:**
- Frontend: Deutlich sichtbare Markierung in UI
- Backend: Logging mit WARNUNG/ERROR Level
- Beide: Kommentare im Code mit "DUMMY" oder "FALLBACK"

**Vermeidung:**
- Proper Error Handling statt Fallbacks
- Validierung statt Dummy-Werte
- Explizite Fehlermeldungen statt versteckte Ersatzwerte
- Fail-Fast Prinzip: Bei Problemen sofort stoppen

**Zweck:** Transparenz und Nachvollziehbarkeit aller Datenwerte

---

## REGEL 11: MCP SERVER NUTZUNG

Model Context Protocol (MCP) Server sollen aktiv genutzt werden:

**Vorgehen:**
- Bei Fragen oder Aufgaben: Verfügbare MCP Server prüfen
- Eigenständige Entscheidung welcher Server sinnvoll hilft
- MCP Tools bevorzugt nutzen wenn verfügbar und passend
- Effizienz durch spezialisierte Tools steigern

**MCP Server:**
- SEMGREP
- REF
- PLAYWRIGHT
- FILE SYSTEM
- GITHUB
- TASKMASTER
- PIECES
- EXA SEARCH

**Einsatzbereiche:**
- File-Management und Code-Organisation
- Dokumentation und Analyse
- Spezifische Entwicklungsaufgaben
- Automatisierung von Routineaufgaben

**Zweck:** Maximale Effizienz durch spezialisierte Tools

---

## REGEL 12: GITHUB VERSIONIERUNG

**Projektstart:**
- Bei jedem neuen Projekt: GitHub Repository anlegen
- Saubere Grundstruktur etablieren
- Ordnerstruktur entsprechend Regel 6 einrichten

**Branch-Management:**
- Neue Funktionen/Änderungen: Neuen Branch erstellen
- Branch-Naming: `v0.1`, `v0.2`, `v0.3`, etc. (fortlaufend)
- Master/Main Branch: Nur stabile, getestete Versionen

**Commit-Regeln:**
- NUR bei funktionierenden Änderungen committen
- NUR auf explizite Anweisung hin committen
- NIEMALS automatisch committen
- Vor Commit immer nachfragen: "Soll ich die aktuelle Version auf GitHub committen?"

**Commit-Nachrichten:**
- Deutsch verfasst
- Beschreibend und konkret
- Format: `[Version] - [Kurze Beschreibung der Änderung]`

**Zweck:** Professionelle Versionskontrolle und Nachvollziehbarkeit

---

## REGEL 13: CODE-QUALITÄTSSTANDARDS

**Naming Conventions:**
- Variablen: aussagekräftige Namen (`userLoginData`, `testErgebnis`)
- Funktionen: Verben verwenden (`pruefeLogin`, `sendeFormular`)
- Konstanten: GROSSBUCHSTABEN (`MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`)
- Dateien: lowercase mit underscores (`login_test.py`, `user_utils.js`)

**Error Handling:**
- Jede Funktion mit try-catch/try-except ausstatten
- Aussagekräftige Fehlermeldungen auf Deutsch
- Logging bei kritischen Fehlern mandatory
- Graceful Degradation bei nicht-kritischen Fehlern

**Code-Kommentare:**
- Komplexe Logik immer kommentieren
- Deutsch verfasste Kommentare
- Zweck der Funktion am Anfang erklären
- TODO-Kommentare mit Datum versehen

**Single Source of Truth:**
- Single Source of Truth Ansatz verwenden
- Wiederkehrende gleiche Codestrukturen vermeiden
- Keine Code-Duplikationen
- Code wenn möglich durch Nutzen von Widgets und Code Snippets wiederverwenden
- Wiederverwendbare Funktionen statt Code-Duplikate

**Zweck:** Einheitliche und wartbare Codequalität

---

## REGEL 14: TESTING-STANDARDS

**Test-Struktur:**
- Für jede Hauptfunktion: Mindestens einen Test
- Test-Dateien: `*_test.py` / `*_test.js`
- Test-Ordner: `/tests/` unterhalb der jeweiligen Module
- Test-Coverage: Mindestens 70% anstreben
- Immer Backend, Frontend und API testen
- Mit Hilfe vom Playwright MCP Server alle Funktionalitäten direkt in der Browser-Oberfläche prüfen und testen
- Nicht nur Funktionalität sondern auch Plausibilität der Werte prüfen

**Assert-Nachrichten:**
- Immer deutsche Fehlermeldungen bei fehlgeschlagenen Tests
- Format: "Erwartet: X, Erhalten: Y bei Funktion Z"
- Aussagekräftige Test-Namen auf Deutsch

**Test-Kategorien:**
- Unit Tests: Einzelne Funktionen
- Integration Tests: Zusammenspiel von Komponenten
- End-to-End Tests: Komplette User-Journeys

**Zweck:** Zuverlässige und getestete Software

---

## REGEL 15: KONFIGURATION & UMGEBUNG

**Config-Management:**
- Alle Umgebungsvariablen in `.env` Dateien
- Niemals Passwörter oder API-Keys im Code
- `config.py`/`config.js` für zentrale Konfiguration
- Separate Config-Dateien für verschiedene Umgebungen

**Umgebungen:**
- Separate Configs für dev/test/prod
- Environment-spezifische Branches wenn nötig
- Klare Trennung zwischen lokaler und produktiver Konfiguration

**Sicherheit:**
- `.env` Dateien immer in `.gitignore`
- API-Keys über Umgebungsvariablen
- Sensible Daten niemals committen

**Zweck:** Sichere und flexible Konfigurationsverwaltung

---

## REGEL 16: PERFORMANCE & MONITORING

**Performance:**
- Funktionen über 5 Sekunden Laufzeit dokumentieren
- Bei Schleifen: Performance-Comments hinzufügen
- Speicher-intensive Operationen kennzeichnen
- Timeouts für alle externen Aufrufe definieren

**Logging:**
- Log-Level: INFO für wichtige Aktionen, DEBUG für Details
- Log-Format: `[TIMESTAMP] [LEVEL] [FUNKTION] - Nachricht`
- Log-Rotation bei größeren Anwendungen
- Deutschsprachige Log-Nachrichten

**Monitoring:**
- Kritische Funktionen mit Monitoring ausstatten
- Metriken für wichtige Business-Prozesse
- Alerting bei Fehlern oder Performance-Problemen

**Zweck:** Performante und überwachbare Anwendungen

---

## REGEL 17: DEPENDENCY MANAGEMENT

**Bibliotheken:**
- `requirements.txt` / `package.json` aktuell halten
- Nur notwendige Dependencies installieren
- Versionsnummern fixieren für Stabilität
- Regelmäßige Security-Updates prüfen

**Lizenz-Compliance:**
- Lizenz aller verwendeten Bibliotheken prüfen
- Kompatibilität mit Projektlizenz sicherstellen
- Dokumentation der verwendeten Third-Party-Komponenten

**Update-Strategie:**
- Monatliche Überprüfung auf Updates
- Testlauf vor Update in Produktionsumgebung
- Breaking Changes dokumentieren

**Zweck:** Stabile und rechtskonforme Dependency-Verwaltung

---

## REGEL 18: STANDARD-WORKFLOW

**Obligatorischer Arbeitsablauf:**

1. **PROBLEMANALYSE:**
   - Problem durchdenken
   - Relevante Dateien im Code suchen
   - MCP Server auf Nützlichkeit prüfen
   - Plan in `projectplan.md` schreiben

2. **AUFGABENPLANUNG:**
   - Liste mit konkreten Aufgaben erstellen
   - Aufgaben nach Erledigung abhakbar machen
   - Plan vor Arbeitsbeginn zur Überprüfung melden

3. **UMSETZUNG:**
   - Aufgaben nacheinander bearbeiten
   - Jede Aufgabe nach Erledigung als erledigt markieren
   - Bei jedem Schritt detailliert erläutern welche Änderungen vorgenommen wurden

4. **EINFACHHEITSPRINZIP:**
   - Alle Aufgaben und Codeänderungen so einfach wie möglich gestalten
   - Massive oder komplexe Änderungen vermeiden
   - Jede Änderung soll minimale Auswirkungen auf den Code haben
   - **EINFACHHEIT IST ALLES**

5. **ABSCHLUSS:**
   - Überprüfungsbereich in `projectplan.md` einfügen
   - Zusammenfassung der vorgenommenen Änderungen
   - Alle relevanten Informationen dokumentieren
   - Bei funktionierenden Änderungen: GitHub Commit anbieten

**Zweck:** Strukturierte und nachvollziehbare Projektarbeit

---

## REGEL 19: LAYOUT UND STYLING

- Nutze immer modernes und sauberes Design
- **KEINE blue-purple gradients benutzen**
- Verwendung von kleinen Icons im Design auf ein Minimum beschränken
- Moderne Schriftart nutzen die nicht Standard in jeder KI App ist (z.B. Times New Roman)
- Design muss zum Thema passen

**Zweck:** Design und Layout soll sich abheben von all den vielen weiteren KI Designs. Es soll besonders sein und besser aussehen.

---

## COMPLIANCE-HINWEIS

Diese Regeln sind **VERBINDLICH** für alle Projektbeteiligten.
Bei Regelverstößen ist sofortige Korrektur erforderlich.

**Anwendungsbereich:**
- Claude AI-Assistant Projekte
- Andere Programmierumgebungen
- Allgemeine Softwareentwicklungsprojekte

**Letzte Aktualisierung:** 24.01.2026
**Nächste Review:** Nach Projektabschluss Phase 1
