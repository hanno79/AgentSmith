# Codebasis-Dokumentation – Multi-Agenten-System

**Author:** rahn  
**Datum:** 22.02.2026  
**Version:** 1.0

---

## 1. Projektübersicht

Das Multi-Agenten-System ist eine umfassende Entwicklungsplattform, die auf dem Prinzip der verteilten künstlichen Intelligenz basiert. Das System orchestriert verschiedene spezialisierte Agenten, die zusammen verschiedene Aufgaben im Softwareentwicklungsprozess übernehmen. Von der initialen Anforderungsanalyse über die Code-Generierung bis hin zum Testen und der Qualitätssicherung wird der gesamte Entwicklungszyklus durch autonome Agenten gesteuert.

Das System zeichnet sich durch mehrere Kernmerkmale aus. Zum einen verfügt es über ein intelligentes Model-Routing, das bei Rate-Limits automatisch auf Fallback-Modelle umschaltet. Zum anderen implementiert es ein Budget-Management, das die Nutzung von kostenpflichtigen KI-Ressourcen kontrolliert und optimiert. Die Discovery-Session ermöglicht eine strukturierte Projektaufnahme, bei der die Anforderungen systematisch erfasst und dokumentiert werden.

Die Architektur folgt dem Prinzip der Modularität, wobei jeder Agent eine klar definierte Verantwortung besitzt. Die Kommunikation zwischen den Agenten erfolgt über definierte Schnittstellen, und das System nutzt sowohl synchrone als auch asynchrone Verarbeitungsmuster, um eine hohe Effizienz zu gewährleisten.

---

## 2. Verwendete Bibliotheken und Frameworks

### 2.1 KI und Machine Learning

Die Basis des Agentensystems bildet CrewAI, ein Framework zur Erstellung von Multi-Agenten-Systemen. CrewAI ermöglicht die Definition von Rollen, Zielen und Hintergründen für jeden Agenten und orchestriert deren Zusammenarbeit. Die Konfiguration erfolgt über das Model-Objekt, das verschiedene Large Language Models integrieren kann.

Für die Anbindung an verschiedene LLM-Provider wird LiteLLM verwendet. Dieses Tool abstrahiert die Unterschiede zwischen verschiedenen API-Schnittstellen und ermöglicht einen einheitlichen Zugriff auf Modelle von OpenAI, Anthropic, Meta und vielen weiteren Anbietern. Die Besonderheit liegt in der Unterstützung von über 100 verschiedenen Modellen, die über eine einheitliche API angesprochen werden können.

Das Claude Agent SDK wird als zusätzliches Backend für komplexe Denkaufgaben eingesetzt. Es bietet erweiterte Fähigkeiten für Reasoning und Tool-Use und wird besonders bei Aufgaben eingesetzt, die tiefergehende Analyse erfordern.

### 2.2 Web-Frameworks

FastAPI dient als Web-Framework für das Backend. Es bietet hohe Performance durch asynchrone Verarbeitung und eine moderne API-Entwicklung mit automatischer Dokumentation. Die Integration von Uvicorn als ASGI-Server ermöglicht skalierbare und effiziente Server-Prozesse.

Für das Frontend wird Playwright für UI-Tests eingesetzt. Dieses Tool ermöglicht die Automatisierung von Browser-Tests und unterstützt verschiedene Browser-Engines. Die Screenshot‑Funktionalität erlaubt visuelle Regressionstests, bei denen Änderungen in der Benutzeroberfläche erkannt werden können.

### 2.3 Datenbank und Speicherung

Für die lokale Datenspeicherung wird SQLite verwendet. Die Datenbanken umfassen mehrere Einsatzgebiete: Die Model-Stats-DB speichert Statistiken über die Nutzung verschiedener Modelle, während die Feature-Tracking-DB die Nachverfolgung von Feature-Entwicklungen ermöglicht. Zusätzlich existiert eine Budget-Datenbank zur Verwaltung von Ressourcenkontingenten.

Die Datenspeicherung erfolgt über SQLAlchemy als ORM-Schicht, die sowohl typsichere Abfragen als auch eine Abstraktion über verschiedene Datenbank-Backends ermöglicht.

### 2.4 Testing und Qualitätssicherung

Pytest bildet die Grundlage für alle Unit- und Integrationstests. Die Erweiterung pytest-asyncio ermöglicht das Testen von asynchronem Code, während pytest-qt spezifische Tests für PyQt- und PySide-Anwendungen bereitstellt. Diese Kombination erlaubt umfassende Testabdeckung für verschiedene Anwendungstypen.

### 2.5 Sicherheit und Validierung

Pydantic wird für die Datenvalidierung und Schema-Definition eingesetzt. Es ermöglicht die automatische Validierung von Eingabedaten und bietet eine typsichere Alternative zu klassischen Validierungsansätzen. Die cryptography-Bibliothek kommt für die Verschlüsselung von sensiblen Daten zum Einsatz, insbesondere bei der Speicherung von Memory-Daten.

SlowAPI implementiert Rate-Limiting für die API-Endpunkte und schützt das System vor übermäßiger Nutzung. Dies ist besonders wichtig, da das System auf externen KI-Diensten basiert, die selbst Rate-Limits unterliegen.

### 2.6 Hilfsbibliotheken

PyYAML und ruamel.yaml dienen dem Parsen und Bearbeiten von YAML-Konfigurationsdateien. Letztere erhält beim Schreiben die ursprünglichen Kommentare, was die Konfigurationspflege erleichtert. Rich ermöglicht die formatierte Ausgabe in der Konsole mit Panels, Farben und Fortschrittsanzeigen, was die Benutzerführung verbessert.

---

## 3. Architektur und Design Patterns

### 3.1 Gesamtarchitektur

Die Architektur des Systems folgt einem Schichtenmodell, das sich in drei Hauptbereiche gliedert. Die oberste Schicht bilden die Agenten, die als spezialisierte KI-Entitäten verschiedene Aufgaben wahrnehmen. Die mittlere Schicht enthält das Orchestrierungssystem, das die Zusammenarbeit der Agenten koordiniert. Die unterste Schicht umfasst die Infrastruktur-Dienste wie Datenbanken, API-Server und externen Dienste.

Die Kommunikation zwischen den Schichten erfolgt über definierte Schnittstellen. Die Agenten erhalten ihre Aufgaben durch das Orchestration-Manager-Modul und berichten Ergebnisse zurück. Das Model-Routing entscheidet dynamisch, welches KI-Modell für welche Aufgabe eingesetzt wird, basierend auf Verfügbarkeit und Performance-Kennzahlen.

### 3.2 Agent-Architektur

Jeder Agent ist als spezialisierte Einheit konzipiert, die eine klar definierte Funktion erfüllt. Die Agenten werden durch die Agent-Factory erzeugt, die Konfiguration und Routing-Informationen bereitstellt. Die Grundstruktur umfasst Role, Goal und Backstory, die das Verhalten des Agenten definieren.

Die wichtigsten Agenten sind der Coder, der Code generiert, der Reviewer, der die Codequalität prüft, und der Tester, der die Funktionalität verifiziert. Ergänzend gibt es spezialisierte Agenten für Sicherheitsprüfungen, Recherche, Datenbank-Design und technische Planung.

### 3.3 Orchestrierungsmuster

Das Orchestrierungssystem implementiert mehrere Koordinationsmuster. Der Development-Loop bildet die zentrale Schleife, in der Code generiert, getestet und überarbeitet wird, bis die gewünschte Qualität erreicht ist. Dieser Loop kann maximal 50 Iterationen durchlaufen, wobei jede Iteration den aktuellen Zustand evaluiert und Verbesserungen vorschlägt.

Das Universal Task Derivation System ermöglicht die Zerlegung komplexer Aufgaben in einzelne Tasks, die parallel ausgeführt werden können. Der Task-Dispatcher verwaltet diese Parallelisierung und beachtet Abhängigkeiten zwischen Tasks, sodass voneinander abhängige Tasks in der korrekten Reihenfolge verarbeitet werden.

### 3.4 Fallback-Strategien

Ein zentrales Element der Architektur ist das intelligente Fallback-System. Wenn ein KI-Modell nicht verfügbar ist oder Rate-Limits erreicht, schaltet das System automatisch auf alternative Modelle um. Diese Fallback-Kette kann mehrere Stufen umfassen: Primary-Modell, reguläre Fallbacks, erweiterte Fallbacks und schließlich dynamische Fallbacks, die aus der OpenRouter-API abgerufen werden.

Das Budget-Management überwacht die Nutzung und verhindert unbeabsichtigte Kosten. Im Test-Modus werden ausschließlich kostenlose Modelle verwendet, während im Produktionsmodus auch kostenpflichtige Modelle mit höherer Qualität eingesetzt werden können.

### 3.5 Qualitätssicherung

Die Quality-Gate-Komponente implementiert verschiedene Prüfmechanismen. Jeder durchlaufene Qualitäts-Check muss bestanden werden, bevor der Entwicklungsprozess fortgesetzt wird. Die Prüfungen umfassen Code-Qualität, Sicherheitsaspekte, Testabdeckung und Einhaltung von Coding-Standards.

---

## 4. Agenten-Dokumentation

### 4.1 Meta-Orchestrator

Der Meta-Orchestrator analysiert die Benutzeranforderungen und bestimmt, welche Agenten für die Umsetzung benötigt werden. Er identifiziert Projekttypen und Anforderungen automatisch und erstellt einen Ausführungsplan. Die verfügbaren Agenten umfassen Coder, Reviewer, Designer, Tester, Researcher, Database-Designer, TechStack-Architect und Memory-Agent.

### 4.2 Coder-Agent

Der Coder-Agent generiert produktionsreifen Code basierend auf den Projektanforderungen. Er unterstützt sowohl Multi-File- als auch Single-File-Modi. Der Single-File-Modus wurde eingeführt, um Truncation-Probleme bei kostenlosen Modellen zu vermeiden, indem jede Datei einzeln generiert wird.

Der Agent befolgt strikte Anti-Pattern-Regeln, die häufige Fehler vermeiden helfen. Dazu gehören die Vermeidung zirkulärer Imports, korrekte Import-Reihenfolgen und die Vollständigkeit des generierten Codes. Besondere Aufmerksamkeit gilt der korrekten Behandlung von Abhängigkeiten in requirements.txt.

### 4.3 Reviewer-Agent

Der Reviewer-Agent prüft generierten Code auf Qualität, Funktionalität und Regelkonformität. Er führt verschärfte Vollständigkeitsprüfungen durch und akzeptiert nur Code, der tatsächlich ausführbar ist. Die Feedback-Formulierung erfolgt im Root-Cause-Format, das die Ursache von Fehlern analysiert und konkrete Lösungsvorschläge enthält.

### 4.4 Tester-Agent

Der Tester-Agent orchestriert verschiedene Teststrategien basierend auf dem Projekttyp. Für Web-Anwendungen kommt Playwright zum Einsatz, für PyQt- und PySide-Anwendungen pytest-qt, für Tkinter-Anwendungen PyAutoGUI und für CLI-Anwendungen spezielle CLI-Tests. Die Teststrategie wird automatisch basierend auf erkannten Frameworks gewählt.

### 4.5 Fix-Agent

Der Fix-Agent ist spezialisiert auf gezielte Code-Korrekturen. Er erhält spezifische Fehlerinformationen und korrigiert nur die betroffenen Dateien, ohne funktionierenden Code zu verändern. Der Agent unterstützt verschiedene Fehlertypen wie Syntaxfehler, Import-Probleme, Runtime-Fehler und Truncation-Probleme.

### 4.6 Planner-Agent

Der Planner-Agent zerlegt Projekte in einzelne Datei-Tasks. Er erstellt einen strukturierten Implementierungsplan, wobei jede Datei maximal 200 Zeilen umfassen sollte. Der Plan definiert Abhängigkeiten zwischen Dateien und bestimmt die optimale Erstellungsreihenfolge.

### 4.7 Dependency-Agent

Der Dependency-Agent verwaltet Software-Abhängigkeiten des Systems. Er führt ein Inventar der installierten Pakete, prüft deren Verfügbarkeit und kann fehlende Pakete automatisch installieren. Ein Vulnerability-Check identifiziert bekannte Sicherheitslücken in verwendeten Bibliotheken.

### 4.8 Memory-Agent

Der Memory-Agent speichert Erkenntnisse aus früheren Entwicklungszyklen. Er lernt aus Fehlern und vermeidet deren Wiederholung in späteren Projekten. Die Memory-Funktionalität umfasst auch Data-Sources und Domain-Vocabulary für domänenspezifisches Wissen.

---

## 5. Backend-Module

### 5.1 Orchestration-Manager

Der Orchestration-Manager bildet das Herzstück der Backend-Logik. Er koordiniert alle Phasen des Entwicklungsprozesses von der initialen Anforderungsaufnahme bis zur finalen Dokumentationserstellung. Die Hauptaufgaben umfassen die Initialisierung von Agenten, die Verwaltung des Entwicklungsloops und die Integration aller Subsysteme.

Der Manager implementiert Callbacks für verschiedene Ereignisse wie Worker-Status-Änderungen und Fallback-Wechsel. Er verwaltet auch das Budget-Tracking und die Model-Stats-Datenbank.

### 5.2 Development-Loop

Der Development-Loop ist für die iterative Code-Entwicklung verantwortlich. In jeder Iteration wird Code generiert, in einer Sandbox ausgeführt, von Reviewern geprüft und bei Bedarf überarbeitet. Der Loop implementiert verschiedene Optimierungen wie Parallel-Patching, bei dem mehrere Dateien gleichzeitig korrigiert werden können.

### 5.3 Task-Dispatcher

Der Task-Dispatcher implementiert das Universal Task Derivation System. Er zerlegt komplexe Aufgaben in einzelne Tasks, erstellt Batches für parallele Verarbeitung und führt die Tasks aus. Der Dispatcher beachtet Abhängigkeiten zwischen Tasks und kann bei Fehlern automatische Retry-Logik anwenden.

### 5.4 Model-Router

Der Model-Router verwaltet die Auswahl von KI-Modellen. Er implementiert Fallback-Strategien bei Rate-Limits, führt Health-Checks durch und verfolgt die Nutzungsstatistiken. Der Router unterstützt sowohl synchrone als auch asynchrone Operationen und kann dynamisch Modelle von OpenRouter abrufen, wenn alle konfigurierten Modelle nicht verfügbar sind.

### 5.5 Discovery-Session

Die Discovery-Session ermöglicht eine strukturierte Projektaufnahme. Sie führt den Benutzer durch eine Reihe von Fragen zu Projektzielen, Zielgruppe, Funktionen und technischen Anforderungen. Die gesammelten Informationen werden als Briefing zusammengefasst und an alle nachfolgenden Agenten weitergegeben.

### 5.6 Qualitäts-Gate

Das Qualitäts-Gate implementiert verschiedene Prüfmechanismen während des Entwicklungsprozesses. Es prüft Code-Qualität, Sicherheitsaspekte und Testabdeckung. Die Ergebnisse werden dokumentiert und fließen in die Entscheidung ein, ob der Entwicklungsprozess fortgesetzt oder eine Überarbeitung erforderlich ist.

---

## 6. API-Endpunkte

### 6.1 Core-API

Die Core-API stellt grundlegende Endpunkte für die Systemverwaltung bereit. Sie umfasst Health-Checks, Status-Abfragen und Konfigurationsoptionen.

### 6.2 Budget-API

Die Budget-API verwaltet Ressourcenkontingente. Sie ermöglicht das Setzen von Limits für verschiedene Agenten und Projekttypen und liefert Statistiken über die aktuelle Nutzung.

### 6.3 Session-API

Die Session-API verwaltet Entwicklungs-Sessions. Sie ermöglicht das Erstellen, Fortsetzen und Beenden von Sessions und speichert den Verlauf aller Aktionen.

### 6.4 Discovery-API

Die Discovery-API bietet Endpunkte für die strukturierte Projektaufnahme. Sie unterstützt das Laden und Speichern von Discovery-Briefings und ermöglicht die Abfrage von Projektinformationen.

### 6.5 Features-API

Die Features-API dient der Nachverfolgung von Feature-Entwicklungen. Sie implementiert ein Kanban-Board-ähnliches System mit Tasks, die verschiedenen Phasen zugeordnet werden können.

### 6.6 Model-Stats-API

Die Model-Stats-API liefert Statistiken über die Nutzung verschiedener KI-Modelle. Sie ermöglicht die Analyse von Performance, Kosten und Verfügbarkeit.

---

## 7. Datenbanken

### 7.1 Model-Stats-DB

Die Model-Stats-DB speichert Informationen über jeden Lauf des Systems. Sie erfasst genutzte Modelle, Iterationszahlen, Erfolgs-Status und Metriken. Diese Daten ermöglichen die Optimierung der Model-Auswahl und die Identifikation von Problemen.

### 7.2 Feature-Tracking-DB

Die Feature-Tracking-DB implementiert ein System zur Nachverfolgung von Feature-Entwicklungen. Sie speichert Tasks, Features und Anforderungen sowie deren Status und Zuordnung zu Dateien.

### 7.3 Budget-DB

Die Budget-DB verwaltet Ressourcenkontingente für verschiedene Agenten und Projekttypen. Sie ermöglicht das Setzen von Limits und das Tracking der aktuellen Nutzung.

---

## 8. Konfigurationssystem

### 8.1 Hauptkonfiguration

Die Hauptkonfiguration erfolgt über die Datei config.yaml. Sie definiert verschiedene Modi wie test, production und premium, wobei jeder Modus unterschiedliche Model-Konfigurationen und Ressourcen-Limits besitzt.

Die Model-Konfiguration für jeden Agenten umfasst Primary-Modell, Fallback-Modelle und erweiterte Fallbacks. Zusätzlich können Token-Limits und Timeouts pro Agent konfiguriert werden.

### 8.2 Umgebungsvariablen

Umgebungsvariablen werden über die .env-Datei verwaltet. Die wichtigsten Variablen umfassen API-Keys für OpenRouter und andere Dienste sowie Konfigurationsoptionen für das Verhalten des Systems.

### 8.3 Vorlagen

Das Template-System enthält vordefinierte Projektkonfigurationen für verschiedene Typen wie CLI, Webapp und ML. Jede Vorlage enthält globale Regeln und rollenspezifische Anweisungen für die Agenten.

---

## 9. Fehler und Bugs

### 9.1 Bekannte Probleme

Das System hat im Laufe der Entwicklung verschiedene Fehlerkategorien erfahren. Die häufigsten Probleme waren Truncation, bei denen kostenlose Modelle ihre Antworten abschneiden, zirkuläre Imports in generiertem Python-Code und Phantom-Dateien, bei denen neue Dateien statt existierende Dateien erstellt wurden.

Weitere Probleme umfassten fehlende Abhängigkeiten in requirements.txt, Template-Config-Dateien, die versehentlich überschrieben wurden, und Security‑Issues in generiertem Code.

### 9.2 Lösungsansätze

Für Truncation-Probleme wurde der Single-File-Modus eingeführt, bei dem jede Datei einzeln generiert wird. Für zirkuläre Imports wurden Anti-Pattern-Regeln in den Coder-Agent implementiert. Phantom-Dateien werden durch Ähnlichkeitsprüfungen erkannt und auf existierende Dateien umgeleitet.

Das Dependency-Merging verhindert das Überschreiben von Template-Konfigurationen, indem bestehende Abhängigkeiten mit neuen zusammengeführt werden. Der Security-Scan nach erfolgreicher Code-Generierung identifiziert und dokumentiert potenzielle Sicherheitslücken.

### 9.3 Fix-System

Das Fix-System ermöglicht gezielte Korrekturen durch spezialisierte Fix-Agents. Jeder Fix wird im Root-Cause-Format dokumentiert, das die Ursache des Problems und die Lösung beschreibt. Die Dokumentation erfolgt direkt im Code mit speziellen Kommentar-Markierungen.

---

## 10. Verbesserungspotenzial

### 10.1 Architektur

Die Architektur könnte von einer stärkeren Modularisierung profitieren. Einige Module wie der Orchestration-Manager haben über 900 Zeilen Code und sollten nach dem Prinzip des Single‑Responsibility‑Prinzips in kleinere Einheiten aufgeteilt werden. Die Regel 1 in CLAUDE.md fordert bereits maximal 500 Zeilen pro Datei, wobei einige Dateien diese Grenze überschreiten.

Die Trennung zwischen Agenten und Backend-Logik könnte verbessert werden. Derzeit gibt es Überschneidungen in der Verantwortlichkeit, die zu Komplexität führen.

### 10.2 Testing

Die Testabdeckung könnte erweitert werden. Während Unit-Tests für einzelne Funktionen existieren, fehlen Integrationstests für komplexere Workflows. Besonders die Interaktion zwischen Agenten und die Fallback-Logik sollten systematisch getestet werden.

### 10.3 Dokumentation

Die Dokumentation ist teilweise veraltet oder unvollständig. Einige Agenten und Module haben keine aktuelle Dokumentation ihrer Schnittstellen. Die Einführung einer automatischen API-Dokumentation könnte hier Abhilfe schaffen.

### 10.4 Performance

Die asynchrone Verarbeitung könnte weiter optimiert werden. Einige Bereiche verwenden noch synchrone Aufrufe, die bei I/O-Operationen zu Blockierungen führen können. Die konsequente Nutzung von asyncio könnte die Gesamtperformance verbessern.

### 10.5 Monitoring

Das System könnte von einem umfassenderen Monitoring profitieren. Metriken über Agenten-Performance, Fehlerraten und Ressourcennutzung würden eine proaktive Fehlererkennung und Optimierung ermöglichen. Die Integration mit externen Monitoring-Tools wie Prometheus oder Grafana wäre wünschenswert.

---

## 11. Sicherheitsaspekte

### 11.1 Input-Validierung

Das System implementiert verschiedene Validierungsschichten. Die Eingaben werden durch Pydantic-Modelle validiert, und kritische Operationen wie Dateizugriffe durch Security-Checks abgesichert. Path-Traversal-Angriffe werden durch sichere Pfadverifikation verhindert.

### 11.2 API-Sicherheit

Die API verwendet Rate-Limiting, um Missbrauch zu verhindern. CORS-Middleware erlaubt die Konfiguration erlaubter Ursprünge, und Security-Headers werden automatisch hinzugefügt.

### 11.3 Secrets-Management

API-Keys und andere Secrets werden über Umgebungsvariablen verwaltet und niemals im Code gespeichert. Die .env-Datei ist in .gitignore enthalten, um versehentliche Commits zu verhindern.

---

## 12. Betrieb

### 12.1 Server-Start

Der Server kann über verschiedene Methoden gestartet werden. Die einfachste Methode ist der Aufruf von main.py, der alle notwendigen Initialisierungen durchführt. Alternativ kann der FastAPI-Server direkt über Uvicorn gestartet werden.

### 12.2 Entwicklung

Für die Entwicklung stehen verschiedene Hilfsskripte zur Verfügung. Das Script run_office.bat startet das Multi-Agenten-System, während stop_office.bat den Server beendet. Die Batch-Dateien sind für Windows optimiert.

### 12.3 Docker

Das System kann in Docker-Containern betrieben werden. Die docker-compose.yml definiert die erforderlichen Services, und spezielle Container für Projekte ermöglichen isolierte Entwicklungsumgebungen.

---

## 13. Glossar

| Begriff | Beschreibung |
|---------|--------------|
| Agent | Spezialisierte KI-Einheit für bestimmte Aufgaben |
| CrewAI | Framework für Multi-Agenten-Systeme |
| LiteLLM | Abstraktionsschicht für verschiedene LLM-Provider |
| Fallback | Automatische Umschaltung auf alternatives Modell |
| Truncation | Abschneiden von Antworten bei Token-Limits |
| Discovery | Strukturierte Projektaufnahme |
| Quality-Gate | Prüfmechanismus für Codequalität |
| Task-Dispatcher | System zur parallelen Task-Ausführung |

---

**Ende der Dokumentation**
