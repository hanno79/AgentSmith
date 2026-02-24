# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/library.py.
              Testet die Library- und Archiv-Endpoints sowie die
              sanitize_search_query() Hilfsfunktion.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.library import router, sanitize_search_query

# Test-App mit eingebundenem Router erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# =========================================================================
# TestSanitizeSearchQuery — Tests fuer die Pure Funktion
# =========================================================================

class TestSanitizeSearchQuery:
    """Tests fuer die sanitize_search_query() Hilfsfunktion."""

    def test_normaler_text_unveraendert(self):
        """Normaler Suchtext bleibt unveraendert."""
        ergebnis = sanitize_search_query("Hallo Welt")
        assert ergebnis == "Hallo Welt", (
            f"Erwartet: 'Hallo Welt', Erhalten: '{ergebnis}'"
        )

    def test_leerer_string_gibt_leer_zurueck(self):
        """Leerer String gibt leeren String zurueck."""
        ergebnis = sanitize_search_query("")
        assert ergebnis == "", (
            f"Erwartet: '', Erhalten: '{ergebnis}'"
        )

    def test_none_gibt_leer_zurueck(self):
        """None-Wert gibt leeren String zurueck (falsy)."""
        ergebnis = sanitize_search_query(None)
        assert ergebnis == "", (
            f"Erwartet: '', Erhalten: '{ergebnis}'"
        )

    def test_max_length_kuerzt_korrekt(self):
        """Query wird auf max_length gekuerzt."""
        langer_text = "a" * 300
        ergebnis = sanitize_search_query(langer_text, max_length=200)
        assert len(ergebnis) == 200, (
            f"Erwartet: 200 Zeichen, Erhalten: {len(ergebnis)}"
        )

    def test_custom_max_length(self):
        """Benutzerdefinierte max_length wird respektiert."""
        langer_text = "abcdefghij"
        ergebnis = sanitize_search_query(langer_text, max_length=5)
        assert ergebnis == "abcde", (
            f"Erwartet: 'abcde', Erhalten: '{ergebnis}'"
        )

    def test_sonderzeichen_entfernt(self):
        """Sonderzeichen wie <, >, ;, ' werden entfernt."""
        ergebnis = sanitize_search_query("Test<script>alert('xss')</script>")
        # Nach Regex: Nur Wortzeichen, Leerzeichen, -, _, ., komma, !, ? bleiben
        assert "<" not in ergebnis, "< sollte entfernt werden"
        assert ">" not in ergebnis, "> sollte entfernt werden"
        assert "'" not in ergebnis, "' sollte entfernt werden"
        assert "(" not in ergebnis, "( sollte entfernt werden"

    def test_erlaubte_zeichen_bleiben(self):
        """Bindestrich, Unterstrich, Punkt, Komma, !, ? bleiben erhalten."""
        ergebnis = sanitize_search_query("test-wort_hier.,!?")
        assert ergebnis == "test-wort_hier.,!?", (
            f"Erwartet: 'test-wort_hier.,!?', Erhalten: '{ergebnis}'"
        )

    def test_whitespace_wird_gestrippt(self):
        """Fuehrende und nachfolgende Leerzeichen werden entfernt."""
        ergebnis = sanitize_search_query("  hallo welt  ")
        assert ergebnis == "hallo welt", (
            f"Erwartet: 'hallo welt', Erhalten: '{ergebnis}'"
        )

    def test_umlaute_erhalten(self):
        """Deutsche Umlaute als Wortzeichen bleiben erhalten."""
        ergebnis = sanitize_search_query("Ueberprüfung Ärger Öffnung")
        assert "ü" in ergebnis, "ue sollte erhalten bleiben"
        assert "Ä" in ergebnis, "Ae sollte erhalten bleiben"
        assert "Ö" in ergebnis, "Oe sollte erhalten bleiben"


# =========================================================================
# TestGetCurrentProject — GET /library/current
# =========================================================================

class TestGetCurrentProject:
    """Tests fuer den GET /library/current Endpoint."""

    @patch("backend.routers.library.get_library_manager")
    def test_projekt_vorhanden(self, mock_get_lib):
        """Gibt status='ok' und Projektdaten zurueck wenn Projekt existiert."""
        mock_lib = MagicMock()
        mock_lib.get_current_project.return_value = {"id": "proj-1", "name": "Testprojekt"}
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/current")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok", (
            f"Erwartet: status='ok', Erhalten: '{daten['status']}'"
        )
        assert daten["project"]["id"] == "proj-1"

    @patch("backend.routers.library.get_library_manager")
    def test_kein_projekt(self, mock_get_lib):
        """Gibt status='no_project' zurueck wenn kein Projekt aktiv."""
        mock_lib = MagicMock()
        mock_lib.get_current_project.return_value = None
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/current")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "no_project", (
            f"Erwartet: status='no_project', Erhalten: '{daten['status']}'"
        )
        assert daten["project"] is None


# =========================================================================
# TestGetEntries — GET /library/entries
# =========================================================================

class TestGetEntries:
    """Tests fuer den GET /library/entries Endpoint."""

    @patch("backend.routers.library.get_library_manager")
    def test_eintraege_ohne_filter(self, mock_get_lib):
        """Gibt alle Eintraege ohne Agent-Filter zurueck."""
        mock_lib = MagicMock()
        eintraege = [{"id": 1, "text": "Eintrag 1"}, {"id": 2, "text": "Eintrag 2"}]
        mock_lib.get_entries.return_value = eintraege
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/entries")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["count"] == 2, (
            f"Erwartet: count=2, Erhalten: {daten['count']}"
        )
        assert len(daten["entries"]) == 2
        mock_lib.get_entries.assert_called_once_with(agent_filter=None, limit=100)

    @patch("backend.routers.library.get_library_manager")
    def test_eintraege_mit_agent_filter(self, mock_get_lib):
        """Gibt gefilterte Eintraege nach Agent zurueck."""
        mock_lib = MagicMock()
        mock_lib.get_entries.return_value = [{"agent": "coder", "text": "Code"}]
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/entries?agent=coder&limit=50")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 1
        mock_lib.get_entries.assert_called_once_with(agent_filter="coder", limit=50)

    @patch("backend.routers.library.get_library_manager")
    def test_leere_eintraege(self, mock_get_lib):
        """Gibt leere Liste zurueck wenn keine Eintraege vorhanden."""
        mock_lib = MagicMock()
        mock_lib.get_entries.return_value = []
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/entries")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 0
        assert daten["entries"] == []


# =========================================================================
# TestGetArchivedProjects — GET /library/archive
# =========================================================================

class TestGetArchivedProjects:
    """Tests fuer den GET /library/archive Endpoint."""

    @patch("backend.routers.library.get_library_manager")
    def test_archivierte_projekte_vorhanden(self, mock_get_lib):
        """Gibt alle archivierten Projekte zurueck."""
        mock_lib = MagicMock()
        projekte = [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]
        mock_lib.get_archived_projects.return_value = projekte
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/archive")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["count"] == 3, (
            f"Erwartet: count=3, Erhalten: {daten['count']}"
        )

    @patch("backend.routers.library.get_library_manager")
    def test_archiv_leer(self, mock_get_lib):
        """Gibt leere Liste zurueck wenn kein Archiv vorhanden."""
        mock_lib = MagicMock()
        mock_lib.get_archived_projects.return_value = []
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/archive")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 0
        assert daten["projects"] == []


# =========================================================================
# TestGetArchivedProject — GET /library/archive/{project_id}
# =========================================================================

class TestGetArchivedProject:
    """Tests fuer den GET /library/archive/{project_id} Endpoint."""

    @patch("backend.routers.library.get_library_manager")
    def test_projekt_gefunden(self, mock_get_lib):
        """Gibt archiviertes Projekt zurueck wenn vorhanden."""
        mock_lib = MagicMock()
        mock_lib.get_archived_project.return_value = {"id": "proj-42", "name": "Archiviert"}
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/archive/proj-42")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["project"]["id"] == "proj-42"

    @patch("backend.routers.library.get_library_manager")
    def test_projekt_nicht_gefunden_404(self, mock_get_lib):
        """Gibt 404 zurueck wenn Projekt nicht im Archiv."""
        mock_lib = MagicMock()
        mock_lib.get_archived_project.return_value = None
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/archive/nicht-vorhanden")
        assert response.status_code == 404, (
            f"Erwartet: 404, Erhalten: {response.status_code}"
        )


# =========================================================================
# TestSearchArchives — GET /library/search
# =========================================================================

class TestSearchArchives:
    """Tests fuer den GET /library/search Endpoint."""

    @patch("backend.routers.library.get_library_manager")
    def test_suche_mit_ergebnissen(self, mock_get_lib):
        """Gibt Suchergebnisse zurueck bei gueltigem Query."""
        mock_lib = MagicMock()
        mock_lib.search_archives.return_value = [{"id": "r1", "title": "Treffer"}]
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/search?q=Treffer")
        assert response.status_code == 200
        daten = response.json()
        assert daten["status"] == "ok"
        assert daten["count"] == 1

    @patch("backend.routers.library.get_library_manager")
    def test_suche_leer_bei_leerem_query(self, mock_get_lib):
        """Gibt leere Ergebnisse bei leerem Suchbegriff zurueck."""
        mock_lib = MagicMock()
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/search?q=")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 0
        assert daten["results"] == []
        # search_archives sollte NICHT aufgerufen werden bei leerem Query
        mock_lib.search_archives.assert_not_called()

    @patch("backend.routers.library.get_library_manager")
    def test_suche_mit_limit(self, mock_get_lib):
        """Limit-Parameter wird an search_archives weitergereicht."""
        mock_lib = MagicMock()
        mock_lib.search_archives.return_value = []
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/search?q=test&limit=5")
        assert response.status_code == 200
        # Pruefe dass sanitized Query und Limit korrekt weitergegeben wurden
        mock_lib.search_archives.assert_called_once_with("test", limit=5)

    @patch("backend.routers.library.get_library_manager")
    def test_suche_sanitized_query(self, mock_get_lib):
        """Sonderzeichen werden vor der Suche entfernt."""
        mock_lib = MagicMock()
        mock_lib.search_archives.return_value = []
        mock_get_lib.return_value = mock_lib

        response = client.get("/library/search?q=test<script>")
        assert response.status_code == 200
        # Der Query sollte sanitized sein (keine <, > etc.)
        aufgerufener_query = mock_lib.search_archives.call_args[0][0]
        assert "<" not in aufgerufener_query, "Sonderzeichen sollten entfernt sein"
        assert ">" not in aufgerufener_query, "Sonderzeichen sollten entfernt sein"

    @patch("backend.routers.library.get_library_manager")
    def test_suche_nur_sonderzeichen_leer(self, mock_get_lib):
        """Query mit nur Sonderzeichen ergibt leere Ergebnisse."""
        mock_lib = MagicMock()
        mock_get_lib.return_value = mock_lib

        # Nur Sonderzeichen die vom Regex entfernt werden
        response = client.get("/library/search?q=%3C%3E%3B%27%22")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 0
        # search_archives sollte NICHT aufgerufen werden da sanitized Query leer
        mock_lib.search_archives.assert_not_called()
