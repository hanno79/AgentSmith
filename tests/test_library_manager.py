# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer das Library-Manager-Modul (backend/library_manager.py).
              Prueft Projektlebenszyklus, Log-Eintraege, Serialisierung,
              Archivierung, Suche und Singleton-Pattern.
"""

import json
import os
import sys

import pytest
from unittest.mock import patch, MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.library_manager import LibraryManager, get_library_manager


# =============================================================================
# Fixture: LibraryManager mit temporaerem Verzeichnis
# =============================================================================

@pytest.fixture
def lib_mgr(tmp_path):
    """LibraryManager mit temporaerem Verzeichnis."""
    return LibraryManager(base_dir=str(tmp_path))


# =============================================================================
# TestInit - Initialisierung und Verzeichnisstruktur
# =============================================================================

class TestInit:
    """Tests fuer __init__() - Verzeichniserstellung und Laden."""

    def test_verzeichnisse_werden_erstellt(self, tmp_path):
        """Library- und Archiv-Verzeichnisse werden bei Initialisierung erstellt."""
        mgr = LibraryManager(base_dir=str(tmp_path))
        assert os.path.isdir(mgr.library_dir), "library/ Verzeichnis fehlt"
        assert os.path.isdir(mgr.archive_dir), "library/archive/ Verzeichnis fehlt"

    def test_current_project_ist_initial_none(self, lib_mgr):
        """Ohne vorhandene Projektdatei ist current_project None."""
        assert lib_mgr.current_project is None

    def test_laedt_vorhandenes_projekt_bei_init(self, tmp_path):
        """Wenn current_project.json existiert, wird es beim Init geladen."""
        library_dir = os.path.join(str(tmp_path), "library")
        os.makedirs(library_dir, exist_ok=True)
        projekt_daten = {
            "project_id": "proj_test_123",
            "name": "Testprojekt",
            "entries": []
        }
        with open(os.path.join(library_dir, "current_project.json"), "w", encoding="utf-8") as f:
            json.dump(projekt_daten, f)

        mgr = LibraryManager(base_dir=str(tmp_path))
        assert mgr.current_project is not None
        assert mgr.current_project["project_id"] == "proj_test_123"

    def test_korrupte_json_ergibt_none(self, tmp_path):
        """Bei korrupter JSON-Datei bleibt current_project None."""
        library_dir = os.path.join(str(tmp_path), "library")
        os.makedirs(library_dir, exist_ok=True)
        with open(os.path.join(library_dir, "current_project.json"), "w") as f:
            f.write("{korrupt json!!!")

        mgr = LibraryManager(base_dir=str(tmp_path))
        assert mgr.current_project is None

    def test_pfade_korrekt_gesetzt(self, tmp_path):
        """Alle Pfad-Attribute werden korrekt basierend auf base_dir gesetzt."""
        mgr = LibraryManager(base_dir=str(tmp_path))
        assert mgr.base_dir == str(tmp_path)
        assert mgr.library_dir == os.path.join(str(tmp_path), "library")
        assert mgr.archive_dir == os.path.join(str(tmp_path), "library", "archive")


# =============================================================================
# TestProjectLifecycle - Projekt starten, Dateien hinzufuegen, abschliessen
# =============================================================================

class TestProjectLifecycle:
    """Tests fuer start_project(), add_created_file(), get_current_project()."""

    def test_start_project_erstellt_projekt(self, lib_mgr):
        """start_project() erstellt ein Projekt mit korrekten Feldern."""
        projekt_id = lib_mgr.start_project("Mein Projekt", "Ein Testziel")

        assert projekt_id.startswith("proj_")
        assert lib_mgr.current_project is not None
        assert lib_mgr.current_project["name"] == "Mein Projekt"
        assert lib_mgr.current_project["goal"] == "Ein Testziel"
        assert lib_mgr.current_project["status"] == "running"
        assert lib_mgr.current_project["iterations"] == 0
        assert lib_mgr.current_project["entries"] == []
        assert lib_mgr.current_project["files_created"] == []

    def test_start_project_mit_briefing(self, lib_mgr):
        """start_project() speichert Discovery-Briefing korrekt."""
        briefing = {"tech": "Next.js", "db": "sqlite"}
        lib_mgr.start_project("Briefing-Projekt", "Ziel", briefing=briefing)

        assert lib_mgr.current_project["briefing"] == briefing
        assert isinstance(lib_mgr.current_project["briefing_preview"], str)
        assert len(lib_mgr.current_project["briefing_preview"]) <= 200

    def test_start_project_speichert_datei(self, lib_mgr):
        """start_project() schreibt current_project.json auf Disk."""
        lib_mgr.start_project("Disk-Test", "Ziel")
        assert os.path.exists(lib_mgr.current_project_file)

    def test_add_created_file(self, lib_mgr):
        """add_created_file() fuegt Dateinamen zur files_created Liste hinzu."""
        lib_mgr.start_project("Dateien-Test", "Ziel")
        lib_mgr.add_created_file("app/page.js")
        lib_mgr.add_created_file("lib/db.js")

        assert "app/page.js" in lib_mgr.current_project["files_created"]
        assert "lib/db.js" in lib_mgr.current_project["files_created"]

    def test_add_created_file_keine_duplikate(self, lib_mgr):
        """add_created_file() ignoriert bereits vorhandene Dateinamen."""
        lib_mgr.start_project("Duplikat-Test", "Ziel")
        lib_mgr.add_created_file("app/page.js")
        lib_mgr.add_created_file("app/page.js")

        assert lib_mgr.current_project["files_created"].count("app/page.js") == 1

    def test_add_created_file_ohne_projekt(self, lib_mgr):
        """add_created_file() ohne laufendes Projekt wirft keinen Fehler."""
        # Kein Projekt gestartet — soll still ignoriert werden
        lib_mgr.add_created_file("test.js")
        assert lib_mgr.current_project is None

    def test_get_current_project(self, lib_mgr):
        """get_current_project() gibt das aktuelle Projekt oder None zurueck."""
        assert lib_mgr.get_current_project() is None

        lib_mgr.start_project("Test", "Ziel")
        projekt = lib_mgr.get_current_project()
        assert projekt is not None
        assert projekt["name"] == "Test"


# =============================================================================
# TestLogEntry - Eintraege loggen und filtern
# =============================================================================

class TestLogEntry:
    """Tests fuer log_entry() und get_entries()."""

    def test_log_entry_ohne_projekt_gibt_leer_zurueck(self, lib_mgr):
        """log_entry() ohne Projekt gibt leeren String zurueck."""
        ergebnis = lib_mgr.log_entry("Coder", "Reviewer", "code", "Inhalt")
        assert ergebnis == ""

    def test_log_entry_erstellt_eintrag(self, lib_mgr):
        """log_entry() fuegt einen Eintrag mit korrekten Feldern hinzu."""
        lib_mgr.start_project("Log-Test", "Ziel")
        entry_id = lib_mgr.log_entry(
            from_agent="Coder",
            to_agent="Reviewer",
            entry_type="code_submission",
            content="def hello(): pass",
            iteration=1,
            metadata={"model": "test-model", "tokens": 100, "cost": 0.01}
        )

        assert entry_id == "entry_0001"
        eintraege = lib_mgr.current_project["entries"]
        assert len(eintraege) == 1
        assert eintraege[0]["from_agent"] == "Coder"
        assert eintraege[0]["to_agent"] == "Reviewer"
        assert eintraege[0]["type"] == "code_submission"

    def test_log_entry_aktualisiert_agenten_liste(self, lib_mgr):
        """log_entry() fuegt neue Agenten zur agents_involved Liste hinzu."""
        lib_mgr.start_project("Agent-Test", "Ziel")
        lib_mgr.log_entry("Coder", "System", "code", "Inhalt")
        lib_mgr.log_entry("Reviewer", "System", "feedback", "Feedback")
        lib_mgr.log_entry("Coder", "System", "code", "Mehr Code")

        agenten = lib_mgr.current_project["agents_involved"]
        assert "Coder" in agenten
        assert "Reviewer" in agenten
        # Coder soll nicht doppelt vorkommen
        assert agenten.count("Coder") == 1

    def test_log_entry_aktualisiert_iteration(self, lib_mgr):
        """log_entry() aktualisiert den hoechsten Iterationszaehler."""
        lib_mgr.start_project("Iteration-Test", "Ziel")
        lib_mgr.log_entry("Coder", "System", "code", "V1", iteration=1)
        lib_mgr.log_entry("Coder", "System", "code", "V3", iteration=3)
        lib_mgr.log_entry("Coder", "System", "code", "V2", iteration=2)

        # Hoechste Iteration bleibt 3 (wird nie dekrementiert)
        assert lib_mgr.current_project["iterations"] == 3

    def test_log_entry_token_tracking(self, lib_mgr):
        """log_entry() summiert Tokens und Kosten aus Metadata."""
        lib_mgr.start_project("Token-Test", "Ziel")
        lib_mgr.log_entry("Coder", "System", "code", "V1",
                          metadata={"tokens": 100, "cost": 0.01})
        lib_mgr.log_entry("Reviewer", "System", "review", "OK",
                          metadata={"tokens": 50, "cost": 0.005})

        assert lib_mgr.current_project["total_tokens"] == 150
        assert abs(lib_mgr.current_project["total_cost"] - 0.015) < 1e-9

    def test_get_entries_ohne_projekt(self, lib_mgr):
        """get_entries() ohne Projekt gibt leere Liste zurueck."""
        assert lib_mgr.get_entries() == []

    def test_get_entries_mit_agent_filter(self, lib_mgr):
        """get_entries() filtert nach Agent-Name."""
        lib_mgr.start_project("Filter-Test", "Ziel")
        lib_mgr.log_entry("Coder", "System", "code", "Code-Inhalt")
        lib_mgr.log_entry("Reviewer", "System", "review", "Feedback")
        lib_mgr.log_entry("Coder", "System", "code", "Mehr Code")

        nur_coder = lib_mgr.get_entries(agent_filter="Coder")
        assert len(nur_coder) == 2
        assert all(e["from_agent"] == "Coder" for e in nur_coder)

    def test_get_entries_mit_limit(self, lib_mgr):
        """get_entries() begrenzt die Anzahl der zurueckgegebenen Eintraege."""
        lib_mgr.start_project("Limit-Test", "Ziel")
        for i in range(10):
            lib_mgr.log_entry("Coder", "System", "code", f"Eintrag {i}")

        begrenzt = lib_mgr.get_entries(limit=3)
        assert len(begrenzt) == 3
        # Die letzten 3 Eintraege werden zurueckgegeben
        assert begrenzt[0]["content"] == "Eintrag 7"


# =============================================================================
# TestSerialization - Content-Serialisierung und Truncation
# =============================================================================

class TestSerialization:
    """Tests fuer _serialize_content() - Truncation und Typ-Behandlung."""

    def test_kurzer_string_bleibt_unveraendert(self, lib_mgr):
        """Strings unter 50000 Zeichen werden unveraendert zurueckgegeben."""
        ergebnis = lib_mgr._serialize_content("Kurzer Text")
        assert ergebnis == "Kurzer Text"

    def test_langer_string_wird_truncated(self, lib_mgr):
        """Strings ueber 50000 Zeichen werden mit Truncation-Metadaten versehen."""
        langer_text = "A" * 60000
        ergebnis = lib_mgr._serialize_content(langer_text)

        assert isinstance(ergebnis, dict)
        assert ergebnis["type"] == "truncated"
        assert len(ergebnis["preview"]) == 10000
        assert ergebnis["full_length"] == 60000

    def test_dict_wird_durchgereicht(self, lib_mgr):
        """Dicts werden unveraendert zurueckgegeben."""
        daten = {"key": "value", "nested": {"a": 1}}
        ergebnis = lib_mgr._serialize_content(daten)
        assert ergebnis == daten

    def test_list_wird_durchgereicht(self, lib_mgr):
        """Listen werden unveraendert zurueckgegeben."""
        liste = [1, 2, 3, "test"]
        ergebnis = lib_mgr._serialize_content(liste)
        assert ergebnis == liste

    def test_anderer_typ_wird_zu_string(self, lib_mgr):
        """Andere Typen (int, float, etc.) werden mit str() konvertiert."""
        assert lib_mgr._serialize_content(42) == "42"
        assert lib_mgr._serialize_content(3.14) == "3.14"
        assert lib_mgr._serialize_content(None) == "None"

    def test_truncation_grenzwert_exakt_50000(self, lib_mgr):
        """Exakt 50000 Zeichen wird NICHT truncated (nur > 50000)."""
        text_exakt = "B" * 50000
        ergebnis = lib_mgr._serialize_content(text_exakt)
        assert isinstance(ergebnis, str)
        assert ergebnis == text_exakt


# =============================================================================
# TestNormalizeBriefingPreview - Briefing-Normalisierung
# =============================================================================

class TestNormalizeBriefingPreview:
    """Tests fuer _normalize_briefing_preview() - Dict/None/String Normalisierung."""

    def test_none_gibt_leeren_string(self, lib_mgr):
        """None wird zu leerem String normalisiert."""
        assert lib_mgr._normalize_briefing_preview(None) == ""

    def test_dict_wird_zu_json_string(self, lib_mgr):
        """Dicts werden als kompakter JSON-String zurueckgegeben."""
        briefing = {"tech": "React", "db": "sqlite"}
        ergebnis = lib_mgr._normalize_briefing_preview(briefing)
        assert isinstance(ergebnis, str)
        # Kompaktes JSON ohne Leerzeichen
        assert '"tech":"React"' in ergebnis

    def test_string_wird_durchgereicht(self, lib_mgr):
        """Strings werden unveraendert zurueckgegeben."""
        ergebnis = lib_mgr._normalize_briefing_preview("Einfaches Briefing")
        assert ergebnis == "Einfaches Briefing"

    def test_anderer_typ_wird_zu_string(self, lib_mgr):
        """Andere Typen werden mit str() konvertiert."""
        assert lib_mgr._normalize_briefing_preview(123) == "123"


# =============================================================================
# TestArchive - Archivierung und Projekt-Abschluss
# =============================================================================

class TestArchive:
    """Tests fuer complete_project(), get_archived_projects(), get_archived_project()."""

    @patch("backend.library_manager.prepare_archive_payload")
    def test_complete_project_success_archiviert(self, mock_sanitize, lib_mgr):
        """complete_project(status='success') archiviert und ruft _try_learn_from_project auf."""
        lib_mgr.start_project("Archiv-Test", "Ziel")
        projekt_id = lib_mgr.current_project["project_id"]

        # Mock: prepare_archive_payload gibt die Daten unveraendert zurueck
        mock_sanitize.side_effect = lambda p: p

        with patch.object(lib_mgr, "_try_learn_from_project") as mock_learn:
            lib_mgr.complete_project(status="success")
            mock_learn.assert_called_once()

        # Projekt ist archiviert
        archiv_datei = os.path.join(lib_mgr.archive_dir, f"{projekt_id}.json")
        assert os.path.exists(archiv_datei), "Archiv-Datei wurde nicht erstellt"

        # current_project ist zurueckgesetzt
        assert lib_mgr.current_project is None

        # current_project.json wurde entfernt
        assert not os.path.exists(lib_mgr.current_project_file)

    def test_complete_project_error_nicht_archivieren(self, lib_mgr):
        """complete_project(status='error', allow_error_archives=False) archiviert NICHT."""
        lib_mgr.start_project("Error-Test", "Ziel")
        projekt_id = lib_mgr.current_project["project_id"]

        lib_mgr.complete_project(status="error", allow_error_archives=False)

        # Keine Archiv-Datei erstellt
        archiv_datei = os.path.join(lib_mgr.archive_dir, f"{projekt_id}.json")
        assert not os.path.exists(archiv_datei), "Fehlerhafte Projekte sollen nicht archiviert werden"

        # current_project ist zurueckgesetzt
        assert lib_mgr.current_project is None

    @patch("backend.library_manager.prepare_archive_payload")
    def test_complete_project_error_mit_allow(self, mock_sanitize, lib_mgr):
        """complete_project(status='error', allow_error_archives=True) archiviert trotzdem."""
        lib_mgr.start_project("Error-Erlaubt-Test", "Ziel")
        projekt_id = lib_mgr.current_project["project_id"]

        mock_sanitize.side_effect = lambda p: p

        with patch.object(lib_mgr, "_try_learn_from_project"):
            lib_mgr.complete_project(status="error", allow_error_archives=True)

        archiv_datei = os.path.join(lib_mgr.archive_dir, f"{projekt_id}.json")
        assert os.path.exists(archiv_datei), "Bei allow_error_archives=True soll archiviert werden"

    def test_complete_project_ohne_projekt(self, lib_mgr):
        """complete_project() ohne laufendes Projekt macht nichts."""
        # Soll keinen Fehler werfen
        lib_mgr.complete_project(status="success")
        assert lib_mgr.current_project is None

    @patch("backend.library_manager.prepare_archive_payload")
    def test_complete_project_success_kein_learn_bei_nicht_success(self, mock_sanitize, lib_mgr):
        """_try_learn_from_project wird NUR bei status='success' aufgerufen."""
        lib_mgr.start_project("Kein-Learn-Test", "Ziel")
        mock_sanitize.side_effect = lambda p: p

        with patch.object(lib_mgr, "_try_learn_from_project") as mock_learn:
            lib_mgr.complete_project(status="cancelled")
            mock_learn.assert_not_called()

    @patch("backend.library_manager.prepare_archive_payload")
    def test_get_archived_projects_liste(self, mock_sanitize, lib_mgr):
        """get_archived_projects() gibt Metadaten aller archivierten Projekte zurueck."""
        mock_sanitize.side_effect = lambda p: p

        # Zwei Projekte erstellen und archivieren
        with patch.object(lib_mgr, "_try_learn_from_project"):
            lib_mgr.start_project("Projekt A", "Ziel A")
            lib_mgr.log_entry("Coder", "System", "code", "Code A")
            lib_mgr.complete_project(status="success")

            lib_mgr.start_project("Projekt B", "Ziel B")
            lib_mgr.complete_project(status="success")

        projekte = lib_mgr.get_archived_projects()
        assert len(projekte) == 2

        # Metadaten-Felder pruefen (kein vollstaendiger entries-Inhalt)
        for p in projekte:
            assert "project_id" in p
            assert "name" in p
            assert "entry_count" in p

    @patch("backend.library_manager.prepare_archive_payload")
    def test_get_archived_project_einzeln(self, mock_sanitize, lib_mgr):
        """get_archived_project() laedt ein einzelnes Archiv vollstaendig."""
        mock_sanitize.side_effect = lambda p: p

        with patch.object(lib_mgr, "_try_learn_from_project"):
            lib_mgr.start_project("Einzeln-Test", "Ziel")
            projekt_id = lib_mgr.current_project["project_id"]
            lib_mgr.complete_project(status="success")

        archiv = lib_mgr.get_archived_project(projekt_id)
        assert archiv is not None
        assert archiv["project_id"] == projekt_id

    def test_get_archived_project_nicht_gefunden(self, lib_mgr):
        """get_archived_project() gibt None zurueck bei unbekannter ID."""
        assert lib_mgr.get_archived_project("proj_nicht_vorhanden") is None


# =============================================================================
# TestSearch - Archiv-Suche
# =============================================================================

class TestSearch:
    """Tests fuer search_archives() - Suche in Archiven."""

    def _archiviere_testprojekt(self, lib_mgr, name, goal, entries=None):
        """Hilfsmethode: Erstellt ein archiviertes Testprojekt direkt als JSON-Datei."""
        projekt_id = f"proj_test_{name.replace(' ', '_').lower()}"
        projekt = {
            "project_id": projekt_id,
            "name": name,
            "goal": goal,
            "entries": entries or [],
            "status": "success",
            "started_at": "2026-02-14T10:00:00",
            "completed_at": "2026-02-14T11:00:00"
        }
        archiv_datei = os.path.join(lib_mgr.archive_dir, f"{projekt_id}.json")
        with open(archiv_datei, "w", encoding="utf-8") as f:
            json.dump(projekt, f, ensure_ascii=False)
        return projekt_id

    def test_suche_in_name(self, lib_mgr):
        """search_archives() findet Projekte anhand des Namens."""
        self._archiviere_testprojekt(lib_mgr, "Bugtracker App", "Eine App")
        self._archiviere_testprojekt(lib_mgr, "Wetter Dashboard", "Wetter anzeigen")

        treffer = lib_mgr.search_archives("Bugtracker")
        assert len(treffer) == 1
        assert treffer[0]["match_type"] == "name"
        assert "Bugtracker" in treffer[0]["match_text"]

    def test_suche_in_goal(self, lib_mgr):
        """search_archives() findet Projekte anhand des Ziels."""
        self._archiviere_testprojekt(lib_mgr, "Mein Projekt", "React Dashboard mit SQLite")

        treffer = lib_mgr.search_archives("SQLite")
        assert len(treffer) == 1
        assert treffer[0]["match_type"] == "goal"

    def test_suche_in_entries(self, lib_mgr):
        """search_archives() findet Projekte anhand von Entry-Inhalten."""
        eintraege = [
            {"id": "entry_0001", "content": "ModuleNotFoundError: flask"}
        ]
        self._archiviere_testprojekt(lib_mgr, "Server App", "REST API", entries=eintraege)

        treffer = lib_mgr.search_archives("flask")
        assert len(treffer) == 1
        assert treffer[0]["match_type"] == "entry"

    def test_suche_case_insensitive(self, lib_mgr):
        """search_archives() ignoriert Gross-/Kleinschreibung."""
        self._archiviere_testprojekt(lib_mgr, "GROSSER Name", "Ziel")

        treffer = lib_mgr.search_archives("grosser")
        assert len(treffer) == 1

    def test_suche_mit_limit(self, lib_mgr):
        """search_archives() begrenzt die Anzahl der Ergebnisse."""
        for i in range(5):
            self._archiviere_testprojekt(lib_mgr, f"Testprojekt {i}", f"Ziel {i}")

        treffer = lib_mgr.search_archives("Testprojekt", limit=2)
        assert len(treffer) <= 2

    def test_suche_keine_treffer(self, lib_mgr):
        """search_archives() gibt leere Liste bei keinem Treffer zurueck."""
        self._archiviere_testprojekt(lib_mgr, "Projekt X", "Ziel X")

        treffer = lib_mgr.search_archives("nichtvorhanden")
        assert treffer == []

    def test_suche_korrupte_dateien_werden_uebersprungen(self, lib_mgr):
        """search_archives() ueberspringt korrupte JSON-Dateien."""
        # Korrupte Datei erstellen
        korrupte_datei = os.path.join(lib_mgr.archive_dir, "proj_korrupt.json")
        with open(korrupte_datei, "w") as f:
            f.write("{korrupt!!!")

        # Valides Projekt erstellen
        self._archiviere_testprojekt(lib_mgr, "Valides Projekt", "Ziel")

        # Soll nicht abstuerzen
        treffer = lib_mgr.search_archives("Valides")
        assert len(treffer) == 1


# =============================================================================
# TestSaveLoadPersistence - Speichern und Laden
# =============================================================================

class TestSaveLoadPersistence:
    """Tests fuer _save_current_project() und _load_current_project() Persistenz."""

    def test_save_und_reload_konsistent(self, tmp_path):
        """Gespeicherte Projekte werden bei neuem Manager korrekt geladen."""
        mgr1 = LibraryManager(base_dir=str(tmp_path))
        mgr1.start_project("Persistenz-Test", "Ziel")
        mgr1.log_entry("Coder", "System", "code", "Test-Code")
        mgr1.add_created_file("test.js")

        # Neuer Manager am selben Pfad laedt das Projekt
        mgr2 = LibraryManager(base_dir=str(tmp_path))
        assert mgr2.current_project is not None
        assert mgr2.current_project["name"] == "Persistenz-Test"
        assert len(mgr2.current_project["entries"]) == 1
        assert "test.js" in mgr2.current_project["files_created"]

    def test_save_error_setzt_error_felder(self, lib_mgr):
        """Bei Speicherfehler werden save_error Felder gesetzt und Fehler weitergereicht."""
        lib_mgr.start_project("Error-Save-Test", "Ziel")

        # Datei read-only machen, um Schreibfehler auszuloesen
        with patch("builtins.open", side_effect=PermissionError("Kein Schreibzugriff")):
            with pytest.raises(PermissionError):
                lib_mgr._save_current_project()

        assert lib_mgr.current_project["save_error"] is not None
        assert "Kein Schreibzugriff" in lib_mgr.current_project["save_error"]

    def test_save_loescht_vorherige_error_felder(self, lib_mgr):
        """Erfolgreicher Save loescht vorherige save_error Felder."""
        lib_mgr.start_project("Error-Reset-Test", "Ziel")
        lib_mgr.current_project["save_error"] = "alter Fehler"
        lib_mgr.current_project["save_error_timestamp"] = "2026-01-01T00:00:00"

        lib_mgr._save_current_project()

        assert lib_mgr.current_project["save_error"] is None
        assert lib_mgr.current_project["save_error_timestamp"] is None


# =============================================================================
# TestSingleton - get_library_manager() Singleton
# =============================================================================

class TestSingleton:
    """Tests fuer get_library_manager() - Singleton-Pattern."""

    def test_singleton_gibt_instanz_zurueck(self):
        """get_library_manager() gibt eine LibraryManager-Instanz zurueck."""
        # Singleton zuruecksetzen fuer Test-Isolation
        import backend.library_manager as lm_module
        original = lm_module._library_manager
        try:
            lm_module._library_manager = None
            instanz = get_library_manager()
            assert isinstance(instanz, LibraryManager)
        finally:
            # Zuruecksetzen auf Originalzustand
            lm_module._library_manager = original

    def test_singleton_identische_instanz(self):
        """get_library_manager() gibt immer dieselbe Instanz zurueck."""
        import backend.library_manager as lm_module
        original = lm_module._library_manager
        try:
            lm_module._library_manager = None
            instanz1 = get_library_manager()
            instanz2 = get_library_manager()
            assert instanz1 is instanz2
        finally:
            lm_module._library_manager = original
