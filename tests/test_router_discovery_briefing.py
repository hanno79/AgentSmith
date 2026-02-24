# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/discovery_briefing.py.
              Testet reine Hilfs-Funktionen (load_memory_safe, find_relevant_lessons,
              sanitize_project_name, generate_briefing_markdown) sowie die
              API-Endpoints POST /discovery/save-briefing und GET /discovery/briefing.
"""
# ÄNDERUNG 22.02.2026: DUMMY-WERT-Markierung und Fehlerbehandlung in sample_briefing-Tests ergänzt.

import os
import sys
import json
import logging
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.routers.discovery_briefing import (
    router,
    load_memory_safe,
    find_relevant_lessons,
    sanitize_project_name,
    generate_briefing_markdown,
)


# =========================================================================
# Gemeinsame Test-Fixtures
# =========================================================================

@pytest.fixture
def mock_manager():
    """Erstellt einen Mock-Manager fuer Discovery-Briefing-Tests."""
    mgr = MagicMock()
    mgr.set_discovery_briefing = MagicMock()
    return mgr


@pytest.fixture
def mock_session_mgr():
    """Erstellt einen Mock-SessionManager."""
    session = MagicMock()
    session.set_discovery_briefing = MagicMock()
    session.get_discovery_briefing = MagicMock(return_value={"projectName": "TestProjekt"})
    return session


@pytest.fixture
def app(mock_manager):
    """Erstellt eine FastAPI Test-App mit gemocktem Manager."""
    test_app = FastAPI()
    test_app.include_router(router)
    with patch("backend.routers.discovery_briefing.manager", mock_manager):
        yield test_app


@pytest.fixture
def client(app, mock_manager):
    """Erstellt einen TestClient mit gemocktem Manager."""
    with patch("backend.routers.discovery_briefing.manager", mock_manager), \
         patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None):
        yield TestClient(app)


@pytest.fixture
def sample_briefing():
    """Beispiel-Briefing fuer Tests. DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!"""
    return {
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        "projectName": "MeinProjekt",
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        "date": "14.02.2026",
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        "goal": "Eine Todo-App erstellen",
        # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
        "agents": ["Coder", "Designer", "Tester"],
        "techRequirements": {
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            "language": "python",
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            "deployment": "docker"
        },
        "answers": [
            {
                "agent": "Coder",
                "questionText": "Welche Sprache?",
                "selectedValues": ["Python"],
                "customText": "",
                "skipped": False
            },
            {
                "agent": "Designer",
                "questionText": "Welcher Stil?",
                "selectedValues": [],
                "customText": "Modern und minimalistisch",
                "skipped": False
            },
            {
                "agent": "Tester",
                "questionText": "",
                "selectedValues": ["Unit Tests"],
                "customText": "",
                "skipped": False
            },
            {
                "agent": "Analyst",
                "questionText": "Uebersprungene Frage",
                "selectedValues": [],
                "customText": "",
                "skipped": True
            }
        ],
        "openPoints": ["Datenbank-Schema klären", "API-Design festlegen"]
    }


@pytest.fixture
def sample_lessons():
    """Beispiel-Lessons fuer find_relevant_lessons Tests."""
    return [
        {
            "pattern": "ModuleNotFoundError bei Flask",
            "action": "Flask korrekt installieren",
            "tags": ["flask", "python"],
            "count": 5
        },
        {
            "pattern": "React Hydration Error",
            "action": "suppressHydrationWarning verwenden",
            "tags": ["react", "nextjs"],
            "count": 3
        },
        {
            "pattern": "SQL Injection Risiko",
            "action": "Prepared Statements verwenden",
            "tags": ["security", "database"],
            "count": 8
        },
        {
            "pattern": "Timeout bei API-Aufrufen",
            "action": "Timeout konfigurierbar machen",
            "tags": ["api", "performance"],
            "count": 2
        },
        {
            "pattern": "Docker Build fehlgeschlagen",
            "action": "Multi-Stage Build verwenden",
            "tags": ["docker", "deployment"],
            "count": 4
        },
        {
            "pattern": "CSS Layout Probleme",
            "action": "Flexbox statt Float verwenden",
            "tags": ["css", "frontend"],
            "count": 1
        },
        {
            "pattern": "Flask Session Management",
            "action": "Flask-Login verwenden",
            "tags": ["flask", "auth"],
            "count": 6
        },
    ]


# =========================================================================
# TestLoadMemorySafe — Tests fuer load_memory_safe()
# =========================================================================

class TestLoadMemorySafe:
    """Tests fuer die load_memory_safe() Hilfsfunktion."""

    def test_datei_nicht_vorhanden_gibt_default(self):
        """Gibt Default-Dict zurueck wenn Memory-Datei nicht existiert."""
        with patch("backend.routers.discovery_briefing.os.path.exists", return_value=False):
            result = load_memory_safe()
            assert result == {"history": [], "lessons": []}, (
                f"Erwartet: leeres Default-Dict, Erhalten: {result}"
            )

    def test_gueltige_json_datei_wird_geladen(self, tmp_path):
        """Laedt korrekt formatierte JSON-Datei erfolgreich."""
        test_data = {"history": [{"event": "test"}], "lessons": [{"pattern": "test"}]}
        memory_file = tmp_path / "agent_memory.json"
        memory_file.write_text(json.dumps(test_data), encoding="utf-8")

        with patch("backend.routers.discovery_briefing.MEMORY_PATH", str(memory_file)):
            result = load_memory_safe()
            assert result == test_data, (
                f"Erwartet: {test_data}, Erhalten: {result}"
            )

    def test_ungueltige_json_gibt_default(self, tmp_path):
        """Gibt Default-Dict zurueck bei ungueltiger JSON-Datei."""
        memory_file = tmp_path / "broken.json"
        memory_file.write_text("{invalid json content", encoding="utf-8")

        with patch("backend.routers.discovery_briefing.MEMORY_PATH", str(memory_file)), \
             patch("backend.routers.discovery_briefing.log_event"):
            result = load_memory_safe()
            assert result == {"history": [], "lessons": []}, (
                "Erwartet: Default-Dict bei ungueltiger JSON"
            )

    def test_io_fehler_gibt_default(self):
        """Gibt Default-Dict zurueck bei IO-Fehler."""
        with patch("backend.routers.discovery_briefing.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=IOError("Lesefehler")), \
             patch("backend.routers.discovery_briefing.log_event"):
            result = load_memory_safe()
            assert result == {"history": [], "lessons": []}, (
                "Erwartet: Default-Dict bei IO-Fehler"
            )


# =========================================================================
# TestFindRelevantLessons — Tests fuer find_relevant_lessons()
# =========================================================================

class TestFindRelevantLessons:
    """Tests fuer die find_relevant_lessons() Hilfsfunktion."""

    def test_leere_lessons_gibt_leere_liste(self):
        """Leere Lessons-Liste gibt leere Ergebnis-Liste zurueck."""
        result = find_relevant_lessons([], ["python", "flask"])
        assert result == [], f"Erwartet: [], Erhalten: {result}"

    def test_leere_keywords_gibt_leere_liste(self, sample_lessons):
        """Leere Keywords-Liste gibt leere Ergebnis-Liste zurueck."""
        result = find_relevant_lessons(sample_lessons, [])
        assert result == [], f"Erwartet: [], Erhalten: {result}"

    def test_tag_matching_findet_lessons(self, sample_lessons):
        """Findet Lessons anhand uebereinstimmender Tags."""
        result = find_relevant_lessons(sample_lessons, ["flask"])
        assert len(result) == 2, f"Erwartet: 2 Flask-Lessons, Erhalten: {len(result)}"
        # Beide Flask-Lessons muessen vorhanden sein
        patterns = [r["pattern"] for r in result]
        assert "ModuleNotFoundError bei Flask" in patterns
        assert "Flask Session Management" in patterns

    def test_pattern_matching_findet_lessons(self, sample_lessons):
        """Findet Lessons anhand uebereinstimmender Pattern-Texte."""
        result = find_relevant_lessons(sample_lessons, ["hydration"])
        assert len(result) == 1, f"Erwartet: 1 Hydration-Lesson, Erhalten: {len(result)}"
        assert result[0]["pattern"] == "React Hydration Error"

    def test_action_matching_findet_lessons(self, sample_lessons):
        """Findet Lessons anhand uebereinstimmender Action-Texte."""
        result = find_relevant_lessons(sample_lessons, ["flexbox"])
        assert len(result) == 1, f"Erwartet: 1 Flexbox-Lesson, Erhalten: {len(result)}"
        assert result[0]["action"] == "Flexbox statt Float verwenden"

    def test_sortierung_nach_count_absteigend(self, sample_lessons):
        """Ergebnisse sind nach count absteigend sortiert."""
        result = find_relevant_lessons(sample_lessons, ["flask", "security"])
        # Flask Session (count=6), ModuleNotFound (count=5), SQL Injection (count=8)
        # Sortiert: SQL Injection (8), Flask Session (6), ModuleNotFound (5)
        assert len(result) == 3, f"Erwartet: 3 Ergebnisse, Erhalten: {len(result)}"
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True), (
            f"Erwartet: absteigende Sortierung nach count, Erhalten: {counts}"
        )

    def test_maximal_5_ergebnisse(self, sample_lessons):
        """Gibt maximal 5 Ergebnisse zurueck auch wenn mehr passen."""
        # Suche nach Begriffen die in vielen Lessons vorkommen
        all_keywords = ["flask", "react", "sql", "timeout", "docker", "css", "python"]
        result = find_relevant_lessons(sample_lessons, all_keywords)
        assert len(result) <= 5, (
            f"Erwartet: maximal 5, Erhalten: {len(result)}"
        )

    def test_case_insensitive_matching(self, sample_lessons):
        """Matching ist case-insensitive bei Tags und Keywords."""
        result = find_relevant_lessons(sample_lessons, ["FLASK"])
        assert len(result) == 2, (
            f"Erwartet: 2 Treffer fuer 'FLASK' (case-insensitive), Erhalten: {len(result)}"
        )

    def test_lesson_ohne_tags_wird_gefunden_via_pattern(self):
        """Lesson ohne Tags-Liste kann ueber Pattern gefunden werden."""
        lessons = [{"pattern": "docker compose fehler", "action": "restart", "count": 1}]
        result = find_relevant_lessons(lessons, ["docker"])
        assert len(result) == 1, "Erwartet: 1 Treffer via Pattern-Matching"

    def test_lesson_mit_nicht_list_tags(self):
        """Lesson mit Tags als String statt Liste wird sicher behandelt."""
        lessons = [{"pattern": "test", "action": "fix", "tags": "not-a-list", "count": 1}]
        # tags ist kein list/tuple → tags_lower wird []
        result = find_relevant_lessons(lessons, ["test"])
        # Sollte dennoch ueber Pattern gefunden werden
        assert len(result) == 1, "Erwartet: Treffer ueber Pattern trotz String-Tags"


# =========================================================================
# TestSanitizeProjectName — Tests fuer sanitize_project_name()
# =========================================================================

class TestSanitizeProjectName:
    """Tests fuer die sanitize_project_name() Hilfsfunktion."""

    def test_normaler_name_bleibt(self):
        """Normaler Projektname ohne Sonderzeichen bleibt unveraendert."""
        result = sanitize_project_name("MeinProjekt")
        assert result == "MeinProjekt", f"Erwartet: 'MeinProjekt', Erhalten: '{result}'"

    def test_none_gibt_unnamed_project(self):
        """None als Input gibt 'unnamed_project' zurueck."""
        result = sanitize_project_name(None)
        assert result == "unnamed_project", f"Erwartet: 'unnamed_project', Erhalten: '{result}'"

    def test_leerer_string_gibt_unnamed_project(self):
        """Leerer String gibt 'unnamed_project' zurueck."""
        result = sanitize_project_name("")
        assert result == "unnamed_project", f"Erwartet: 'unnamed_project', Erhalten: '{result}'"

    def test_sonderzeichen_werden_entfernt(self):
        """Sonderzeichen (ausser _ und -) werden entfernt."""
        result = sanitize_project_name("Mein Projekt! @#$%")
        assert result == "MeinProjekt", f"Erwartet: 'MeinProjekt', Erhalten: '{result}'"

    def test_pfadtrenner_werden_entfernt(self):
        """Pfadtrenner (/ und \\) werden entfernt."""
        result = sanitize_project_name("path/to\\project")
        assert "/" not in result, "Erwartet: kein / im Ergebnis"
        assert "\\" not in result, "Erwartet: kein \\\\ im Ergebnis"

    def test_fuehrende_punkte_werden_entfernt(self):
        """Fuehrende Punkte werden entfernt (verhindert versteckte Dateien)."""
        result = sanitize_project_name("..hidden_project")
        assert not result.startswith("."), "Erwartet: kein fuehrender Punkt"

    def test_doppelpunkte_werden_entfernt(self):
        """Doppelpunkte (..) werden entfernt (Path-Traversal-Schutz)."""
        result = sanitize_project_name("projekt..name")
        assert ".." not in result, "Erwartet: keine Doppelpunkte im Ergebnis"

    def test_max_length_beschraenkung(self):
        """Name wird auf max_length gekuerzt."""
        langer_name = "A" * 200
        result = sanitize_project_name(langer_name, max_length=80)
        assert len(result) <= 80, f"Erwartet: max 80 Zeichen, Erhalten: {len(result)}"

    def test_custom_max_length(self):
        """Benutzerdefinierte max_length wird beachtet."""
        result = sanitize_project_name("ABCDEFGHIJ", max_length=5)
        assert result == "ABCDE", f"Erwartet: 'ABCDE', Erhalten: '{result}'"

    def test_unterstrich_und_bindestrich_bleiben(self):
        """Unterstriche und Bindestriche werden beibehalten."""
        result = sanitize_project_name("mein_projekt-v2")
        assert result == "mein_projekt-v2", f"Erwartet: 'mein_projekt-v2', Erhalten: '{result}'"

    def test_nicht_string_input(self):
        """Nicht-String Input (z.B. int) wird zu String konvertiert."""
        result = sanitize_project_name(12345)
        assert result == "12345", f"Erwartet: '12345', Erhalten: '{result}'"

    def test_nur_sonderzeichen_gibt_unnamed_project(self):
        """Name der nur aus Sonderzeichen besteht gibt 'unnamed_project' zurueck."""
        result = sanitize_project_name("!@#$%^&*()")
        assert result == "unnamed_project", f"Erwartet: 'unnamed_project', Erhalten: '{result}'"


# =========================================================================
# TestGenerateBriefingMarkdown — Tests fuer generate_briefing_markdown()
# =========================================================================

class TestGenerateBriefingMarkdown:
    """Tests fuer die generate_briefing_markdown() Hilfsfunktion."""

    def test_markdown_enthaelt_projektname(self, sample_briefing):
        """Generiertes Markdown enthaelt den Projektnamen."""
        md = generate_briefing_markdown(sample_briefing)
        assert "MeinProjekt" in md, "Erwartet: Projektname im Markdown"

    def test_markdown_enthaelt_datum(self, sample_briefing):
        """Generiertes Markdown enthaelt das Datum."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "14.02.2026" in md, "Erwartet: Datum im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_datum: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_agenten(self, sample_briefing):
        """Generiertes Markdown enthaelt die teilnehmenden Agenten."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Coder" in md, "Erwartet: 'Coder' im Markdown"
            assert "Designer" in md, "Erwartet: 'Designer' im Markdown"
            assert "Tester" in md, "Erwartet: 'Tester' im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_agenten: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_ziel(self, sample_briefing):
        """Generiertes Markdown enthaelt das Projektziel."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Eine Todo-App erstellen" in md, "Erwartet: Projektziel im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_ziel: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_tech_anforderungen(self, sample_briefing):
        """Generiertes Markdown enthaelt technische Anforderungen."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "python" in md, "Erwartet: Sprache im Markdown"
            assert "docker" in md, "Erwartet: Deployment im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_tech_anforderungen: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_antworten(self, sample_briefing):
        """Generiertes Markdown enthaelt nicht-uebersprungene Antworten."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Welche Sprache?" in md, "Erwartet: Frage im Markdown"
            assert "Python" in md, "Erwartet: Antwort 'Python' im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_antworten: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_custom_text(self, sample_briefing):
        """Generiertes Markdown enthaelt Custom-Text wenn keine selectedValues."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Modern und minimalistisch" in md, "Erwartet: CustomText im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_custom_text: %s", e)
            pytest.fail(str(e))

    def test_uebersprungene_antworten_werden_ignoriert(self, sample_briefing):
        """Uebersprungene Antworten erscheinen nicht im Markdown."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Uebersprungene Frage" not in md, "Erwartet: Uebersprungene Frage NICHT im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_uebersprungene_antworten_werden_ignoriert: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_offene_punkte(self, sample_briefing):
        """Generiertes Markdown enthaelt offene Punkte."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Datenbank-Schema klären" in md, "Erwartet: Offener Punkt im Markdown"
            assert "API-Design festlegen" in md, "Erwartet: Zweiter offener Punkt im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_offene_punkte: %s", e)
            pytest.fail(str(e))

    def test_markdown_ohne_offene_punkte(self, sample_briefing):
        """Markdown ohne offene Punkte enthaelt keinen OFFENE PUNKTE Abschnitt."""
        try:
            sample_briefing["openPoints"] = []
            md = generate_briefing_markdown(sample_briefing)
            assert "OFFENE PUNKTE" not in md, "Erwartet: Kein OFFENE PUNKTE Abschnitt"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_ohne_offene_punkte: %s", e)
            pytest.fail(str(e))

    def test_markdown_enthaelt_footer(self, sample_briefing):
        """Generiertes Markdown enthaelt den Generator-Footer."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "AgentSmith Discovery Session" in md, "Erwartet: Footer im Markdown"
        except Exception as e:
            logging.error("Fehler beim Test test_markdown_enthaelt_footer: %s", e)
            pytest.fail(str(e))

    def test_leeres_briefing_defaults(self):
        """Leeres Briefing verwendet Default-Werte."""
        md = generate_briefing_markdown({})
        assert "Unbenannt" in md, "Erwartet: Default-Projektname 'Unbenannt'"
        assert "Unbekannt" in md, "Erwartet: Default-Datum 'Unbekannt'"
        assert "Kein Ziel definiert" in md, "Erwartet: Default-Ziel"

    def test_antwort_ohne_frage_text(self, sample_briefing):
        """Antwort ohne questionText wird als Aufzaehlungspunkt dargestellt."""
        try:
            md = generate_briefing_markdown(sample_briefing)
            assert "Unit Tests" in md, "Erwartet: Antwort ohne Frage als Listenpunkt"
        except Exception as e:
            logging.error("Fehler beim Test test_antwort_ohne_frage_text: %s", e)
            pytest.fail(str(e))


# =========================================================================
# TestSaveBriefingEndpoint — Tests fuer POST /discovery/save-briefing
# =========================================================================

class TestSaveBriefingEndpoint:
    """Tests fuer den POST /discovery/save-briefing Endpoint."""

    def test_save_briefing_erfolgreich(self, app, mock_manager, sample_briefing):
        """POST /discovery/save-briefing gibt status ok zurueck."""
        try:
            with patch("backend.routers.discovery_briefing.manager", mock_manager), \
                 patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None), \
                 patch("backend.routers.discovery_briefing.os.makedirs"), \
                 patch("builtins.open", mock_open()):
                client = TestClient(app)
                response = client.post("/discovery/save-briefing", json=sample_briefing)
                assert response.status_code == 200, (
                    f"Erwartet: 200, Erhalten: {response.status_code}"
                )
                data = response.json()
                assert data["status"] == "ok", f"Erwartet: 'ok', Erhalten: {data['status']}"
                assert data["project_name"] == "MeinProjekt", (
                    f"Erwartet: 'MeinProjekt', Erhalten: {data['project_name']}"
                )
        except Exception as e:
            logging.error("Fehler beim Test test_save_briefing_erfolgreich: %s", e)
            pytest.fail(str(e))

    def test_save_briefing_ruft_manager_auf(self, app, mock_manager, sample_briefing):
        """POST /discovery/save-briefing ruft manager.set_discovery_briefing auf."""
        try:
            with patch("backend.routers.discovery_briefing.manager", mock_manager), \
                 patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None), \
                 patch("backend.routers.discovery_briefing.os.makedirs"), \
                 patch("builtins.open", mock_open()):
                client = TestClient(app)
                client.post("/discovery/save-briefing", json=sample_briefing)
                mock_manager.set_discovery_briefing.assert_called_once_with(sample_briefing)
        except Exception as e:
            logging.error("Fehler beim Test test_save_briefing_ruft_manager_auf: %s", e)
            pytest.fail(str(e))

    def test_save_briefing_mit_session_manager(self, app, mock_manager, mock_session_mgr, sample_briefing):
        """POST /discovery/save-briefing nutzt SessionManager wenn verfuegbar."""
        try:
            with patch("backend.routers.discovery_briefing.manager", mock_manager), \
                 patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=mock_session_mgr), \
                 patch("backend.routers.discovery_briefing.os.makedirs"), \
                 patch("builtins.open", mock_open()):
                client = TestClient(app)
                client.post("/discovery/save-briefing", json=sample_briefing)
                mock_session_mgr.set_discovery_briefing.assert_called_once_with(sample_briefing)
        except Exception as e:
            logging.error("Fehler beim Test test_save_briefing_mit_session_manager: %s", e)
            pytest.fail(str(e))

    def test_save_briefing_bei_dateifehler(self, app, mock_manager, sample_briefing):
        """POST /discovery/save-briefing gibt trotzdem ok zurueck bei Dateifehler."""
        try:
            with patch("backend.routers.discovery_briefing.manager", mock_manager), \
                 patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None), \
                 patch("backend.routers.discovery_briefing.os.makedirs", side_effect=OSError("Verzeichnis-Fehler")):
                client = TestClient(app)
                response = client.post("/discovery/save-briefing", json=sample_briefing)
                assert response.status_code == 200, "Erwartet: 200 trotz Dateifehler"
                assert response.json()["status"] == "ok"
        except Exception as e:
            logging.error("Fehler beim Test test_save_briefing_bei_dateifehler: %s", e)
            pytest.fail(str(e))

    def test_save_briefing_sanitiziert_projectname(self, app, mock_manager):
        """POST /discovery/save-briefing sanitiziert den Projektnamen."""
        briefing = {"projectName": "../../evil_path"}
        with patch("backend.routers.discovery_briefing.manager", mock_manager), \
             patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None), \
             patch("backend.routers.discovery_briefing.os.makedirs"), \
             patch("builtins.open", mock_open()):
            client = TestClient(app)
            response = client.post("/discovery/save-briefing", json=briefing)
            data = response.json()
            # Path-Traversal-Zeichen muessen entfernt worden sein
            assert ".." not in data["project_name"], "Erwartet: keine Path-Traversal-Zeichen"
            assert "/" not in data["project_name"], "Erwartet: kein Slash im Namen"


# =========================================================================
# TestGetBriefingEndpoint — Tests fuer GET /discovery/briefing
# =========================================================================

class TestGetBriefingEndpoint:
    """Tests fuer den GET /discovery/briefing Endpoint."""

    def test_get_briefing_mit_session_manager(self, app, mock_manager, mock_session_mgr):
        """GET /discovery/briefing gibt Briefing aus SessionManager zurueck."""
        with patch("backend.routers.discovery_briefing.manager", mock_manager), \
             patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=mock_session_mgr):
            client = TestClient(app)
            response = client.get("/discovery/briefing")
            assert response.status_code == 200
            data = response.json()
            assert data["briefing"] == {"projectName": "TestProjekt"}, (
                f"Erwartet: Briefing aus SessionManager, Erhalten: {data['briefing']}"
            )

    def test_get_briefing_ohne_session_manager(self, app, mock_manager):
        """GET /discovery/briefing gibt None zurueck wenn kein SessionManager."""
        with patch("backend.routers.discovery_briefing.manager", mock_manager), \
             patch("backend.routers.discovery_briefing.get_session_manager_instance", return_value=None):
            client = TestClient(app)
            response = client.get("/discovery/briefing")
            assert response.status_code == 200
            data = response.json()
            assert data["briefing"] is None, (
                f"Erwartet: None (kein SessionManager), Erhalten: {data['briefing']}"
            )
