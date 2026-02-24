# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer backend/orchestration_readme.py - generate_simple_readme().
              Testet Template-basierte README-Generierung ohne LLM-Abhaengigkeiten.
              Prueft Projektname-Ableitung, Beschreibungs-Prioritaet (Briefing > DocService > Default),
              TechStack-Details, Installations-/Start-Kommandos und run.bat-Erkennung.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestration_readme import generate_simple_readme


# =========================================================================
# Tests fuer Grundstruktur und Projektname
# =========================================================================
class TestGenerateSimpleReadme:
    """Tests fuer die Grundstruktur der generierten README."""

    def test_rueckgabetyp_ist_string(self):
        """Rueckgabewert ist immer ein String."""
        ergebnis = generate_simple_readme("/tmp/test_projekt", {})
        assert isinstance(ergebnis, str), (
            f"Erwartet: str, Erhalten: {type(ergebnis).__name__} bei generate_simple_readme()"
        )

    def test_project_path_none_ergibt_projekt(self):
        """Bei project_path=None wird 'Projekt' als Titel verwendet."""
        ergebnis = generate_simple_readme(None, {})
        assert "# Projekt" in ergebnis, (
            "Erwartet: '# Projekt' im Titel bei project_path=None"
        )

    def test_project_path_basename_als_titel(self):
        """Der Basename des Projektpfads wird als Titel verwendet."""
        ergebnis = generate_simple_readme("/foo/bar/mein_projekt", {})
        assert "# mein_projekt" in ergebnis, (
            "Erwartet: '# mein_projekt' als Titel aus Pfad '/foo/bar/mein_projekt'"
        )

    def test_project_path_einfacher_name(self):
        """Ein einfacher Pfad ohne Unterverzeichnisse wird korrekt extrahiert."""
        ergebnis = generate_simple_readme("/demo", {})
        assert "# demo" in ergebnis, (
            "Erwartet: '# demo' als Titel aus Pfad '/demo'"
        )

    def test_enthaelt_agentsmith_signatur(self):
        """Die README enthaelt die AgentSmith-Signatur."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "AgentSmith Multi-Agent System" in ergebnis, (
            "Erwartet: 'AgentSmith Multi-Agent System' in der README"
        )

    def test_enthaelt_erstellt_am(self):
        """Die README enthaelt den 'Erstellt am'-Zeitstempel."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "Erstellt am:" in ergebnis, (
            "Erwartet: 'Erstellt am:' Zeitstempel in der README"
        )

    def test_ergebnis_enthaelt_newlines(self):
        """Das Ergebnis besteht aus mehreren Zeilen (Join mit Newlines)."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        zeilen = ergebnis.split("\n")
        assert len(zeilen) > 10, (
            f"Erwartet: mehr als 10 Zeilen, Erhalten: {len(zeilen)} Zeilen"
        )

    def test_leerer_pfad_string_ergibt_keinen_crash(self):
        """Ein leerer String als Pfad fuehrt nicht zum Absturz."""
        ergebnis = generate_simple_readme("", {})
        assert isinstance(ergebnis, str)


# =========================================================================
# Tests fuer README-Sektionen und Inhalt
# =========================================================================
class TestReadmeInhalt:
    """Tests fuer die Sektions-Ueberschriften und statischen Inhalte."""

    def test_enthaelt_beschreibung_section(self):
        """Die README enthaelt die Sektion '## Beschreibung'."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "## Beschreibung" in ergebnis, (
            "Erwartet: '## Beschreibung' Sektion in der README"
        )

    def test_enthaelt_technische_details_section(self):
        """Die README enthaelt die Sektion '## Technische Details'."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "## Technische Details" in ergebnis, (
            "Erwartet: '## Technische Details' Sektion in der README"
        )

    def test_enthaelt_lizenz_section(self):
        """Die README enthaelt die Sektion '## Lizenz'."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "## Lizenz" in ergebnis, (
            "Erwartet: '## Lizenz' Sektion in der README"
        )

    def test_enthaelt_auto_generiert_am(self):
        """Die README enthaelt den 'Auto-generiert am'-Fussnoten-Text."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "Auto-generiert am" in ergebnis, (
            "Erwartet: 'Auto-generiert am' Fusszeile in der README"
        )

    def test_enthaelt_lizenz_text(self):
        """Die README enthaelt den AgentSmith-Lizenzhinweis."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "Erstellt mit AgentSmith - Multi-Agent Development System" in ergebnis, (
            "Erwartet: Lizenztext 'Erstellt mit AgentSmith' in der README"
        )

    def test_enthaelt_trennlinie(self):
        """Die README enthaelt eine Markdown-Trennlinie (---)."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "---" in ergebnis, (
            "Erwartet: Markdown-Trennlinie '---' in der README"
        )

    def test_titel_ist_erste_zeile(self):
        """Der Titel steht in der ersten Zeile."""
        ergebnis = generate_simple_readme("/tmp/mein_app", {})
        erste_zeile = ergebnis.split("\n")[0]
        assert erste_zeile == "# mein_app", (
            f"Erwartet: '# mein_app' als erste Zeile, Erhalten: '{erste_zeile}'"
        )


# =========================================================================
# Tests fuer Beschreibungs-Prioritaet (Briefing > DocService > Default)
# =========================================================================
class TestReadmeBriefing:
    """Tests fuer die Beschreibungs-Ableitung aus Briefing, DocService und Default."""

    def test_briefing_mit_project_goal(self):
        """discovery_briefing mit projectGoal wird als Beschreibung verwendet."""
        briefing = {"projectGoal": "Eine Todo-App bauen"}
        ergebnis = generate_simple_readme("/tmp/test", {}, discovery_briefing=briefing)
        assert "Eine Todo-App bauen" in ergebnis, (
            "Erwartet: Briefing projectGoal 'Eine Todo-App bauen' in der README"
        )

    def test_doc_service_als_fallback(self):
        """doc_service.data['goal'] wird genutzt wenn kein Briefing vorhanden."""
        doc_service = MagicMock()
        doc_service.data = {"goal": "Ein Wetter-Dashboard erstellen"}
        ergebnis = generate_simple_readme("/tmp/test", {}, doc_service=doc_service)
        assert "Ein Wetter-Dashboard erstellen" in ergebnis, (
            "Erwartet: DocService goal 'Ein Wetter-Dashboard erstellen' in der README"
        )

    def test_default_beschreibung_ohne_quellen(self):
        """Ohne Briefing und DocService wird der Default-Text angezeigt."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "*Keine Beschreibung verfügbar.*" in ergebnis, (
            "Erwartet: Default-Text '*Keine Beschreibung verfügbar.*' in der README"
        )

    def test_briefing_hat_vorrang_vor_doc_service(self):
        """Briefing hat Prioritaet gegenueber doc_service."""
        briefing = {"projectGoal": "Briefing-Ziel"}
        doc_service = MagicMock()
        doc_service.data = {"goal": "DocService-Ziel"}
        ergebnis = generate_simple_readme(
            "/tmp/test", {}, discovery_briefing=briefing, doc_service=doc_service
        )
        assert "Briefing-Ziel" in ergebnis, (
            "Erwartet: Briefing-Ziel hat Vorrang vor DocService-Ziel"
        )
        assert "DocService-Ziel" not in ergebnis, (
            "Erwartet: DocService-Ziel NICHT in der README wenn Briefing vorhanden"
        )

    def test_briefing_ohne_project_goal_key(self):
        """Briefing ohne projectGoal-Key faellt auf doc_service zurueck."""
        briefing = {"otherKey": "irrelevant"}
        doc_service = MagicMock()
        doc_service.data = {"goal": "Fallback-Ziel"}
        ergebnis = generate_simple_readme(
            "/tmp/test", {}, discovery_briefing=briefing, doc_service=doc_service
        )
        assert "Fallback-Ziel" in ergebnis, (
            "Erwartet: DocService-Ziel als Fallback wenn Briefing keinen projectGoal hat"
        )

    def test_briefing_mit_leerem_project_goal(self):
        """Briefing mit leerem projectGoal-String faellt auf doc_service zurueck."""
        briefing = {"projectGoal": ""}
        doc_service = MagicMock()
        doc_service.data = {"goal": "DocService-Fallback"}
        ergebnis = generate_simple_readme(
            "/tmp/test", {}, discovery_briefing=briefing, doc_service=doc_service
        )
        # Leerer String ist falsy → Fallback auf doc_service
        assert "DocService-Fallback" in ergebnis, (
            "Erwartet: DocService-Fallback bei leerem projectGoal"
        )

    def test_doc_service_ohne_goal_key(self):
        """doc_service ohne goal-Key faellt auf Default zurueck."""
        doc_service = MagicMock()
        doc_service.data = {"anderer_key": "wert"}
        ergebnis = generate_simple_readme("/tmp/test", {}, doc_service=doc_service)
        assert "*Keine Beschreibung verfügbar.*" in ergebnis, (
            "Erwartet: Default-Text wenn doc_service keinen goal-Key hat"
        )

    def test_briefing_none_doc_service_none(self):
        """Beide None ergibt Default-Text."""
        ergebnis = generate_simple_readme(
            "/tmp/test", {}, discovery_briefing=None, doc_service=None
        )
        assert "*Keine Beschreibung verfügbar.*" in ergebnis, (
            "Erwartet: Default-Text bei briefing=None und doc_service=None"
        )

    def test_leeres_briefing_dict(self):
        """Leeres Briefing-Dict faellt auf Default zurueck (kein doc_service)."""
        ergebnis = generate_simple_readme("/tmp/test", {}, discovery_briefing={})
        assert "*Keine Beschreibung verfügbar.*" in ergebnis, (
            "Erwartet: Default-Text bei leerem Briefing-Dict ohne doc_service"
        )


# =========================================================================
# Tests fuer TechStack-Details
# =========================================================================
class TestReadmeTechDetails:
    """Tests fuer die Darstellung von TechStack-Details in der README."""

    def test_projekttyp_wird_angezeigt(self):
        """tech_blueprint mit project_type zeigt den Projekttyp an."""
        blueprint = {"project_type": "web_application"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "**Projekttyp:** web_application" in ergebnis, (
            "Erwartet: '**Projekttyp:** web_application' in der README"
        )

    def test_sprache_wird_angezeigt(self):
        """tech_blueprint mit language zeigt die Sprache an."""
        blueprint = {"language": "python"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "**Sprache:** python" in ergebnis, (
            "Erwartet: '**Sprache:** python' in der README"
        )

    def test_leeres_blueprint_zeigt_unbekannt(self):
        """Leeres tech_blueprint zeigt 'unbekannt' fuer Projekttyp und Sprache."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "**Projekttyp:** unbekannt" in ergebnis, (
            "Erwartet: '**Projekttyp:** unbekannt' bei leerem Blueprint"
        )
        assert "**Sprache:** unbekannt" in ergebnis, (
            "Erwartet: '**Sprache:** unbekannt' bei leerem Blueprint"
        )

    def test_datenbank_wird_angezeigt(self):
        """tech_blueprint mit database zeigt die Datenbank an."""
        blueprint = {"database": "PostgreSQL"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "**Datenbank:** PostgreSQL" in ergebnis, (
            "Erwartet: '**Datenbank:** PostgreSQL' in der README"
        )

    def test_ohne_datenbank_kein_eintrag(self):
        """Ohne database im Blueprint erscheint kein Datenbank-Eintrag."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "Datenbank" not in ergebnis, (
            "Erwartet: Kein 'Datenbank' Eintrag bei fehlendem database-Key"
        )

    def test_server_port_wird_angezeigt(self):
        """tech_blueprint mit requires_server zeigt den Server-Port an."""
        blueprint = {"requires_server": True, "server_port": 3000}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "**Server-Port:** 3000" in ergebnis, (
            "Erwartet: '**Server-Port:** 3000' in der README"
        )

    def test_server_port_default_nicht_definiert(self):
        """requires_server ohne server_port zeigt 'nicht definiert'."""
        blueprint = {"requires_server": True}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "**Server-Port:** nicht definiert" in ergebnis, (
            "Erwartet: '**Server-Port:** nicht definiert' bei fehlendem server_port"
        )

    def test_ohne_requires_server_kein_port(self):
        """Ohne requires_server erscheint kein Server-Port-Eintrag."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "Server-Port" not in ergebnis, (
            "Erwartet: Kein 'Server-Port' Eintrag bei fehlendem requires_server"
        )

    def test_install_command_erzeugt_installation_section(self):
        """tech_blueprint mit install_command erzeugt die Installations-Sektion."""
        blueprint = {"install_command": "npm install"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "## Installation" in ergebnis, (
            "Erwartet: '## Installation' Sektion in der README"
        )
        assert "npm install" in ergebnis, (
            "Erwartet: 'npm install' Kommando in der README"
        )

    def test_ohne_install_command_keine_installation_section(self):
        """Ohne install_command fehlt die Installations-Sektion."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "## Installation" not in ergebnis, (
            "Erwartet: Keine '## Installation' Sektion bei fehlendem install_command"
        )

    def test_run_command_erzeugt_starten_section(self):
        """tech_blueprint mit run_command erzeugt die Starten-Sektion."""
        blueprint = {"run_command": "npm run dev"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "## Starten" in ergebnis, (
            "Erwartet: '## Starten' Sektion in der README"
        )
        assert "npm run dev" in ergebnis, (
            "Erwartet: 'npm run dev' Kommando in der README"
        )

    def test_ohne_run_command_keine_starten_section(self):
        """Ohne run_command fehlt die Starten-Sektion."""
        ergebnis = generate_simple_readme("/tmp/test", {})
        assert "## Starten" not in ergebnis, (
            "Erwartet: Keine '## Starten' Sektion bei fehlendem run_command"
        )

    def test_install_command_in_code_block(self):
        """Das Installations-Kommando ist in einem Bash-Codeblock."""
        blueprint = {"install_command": "pip install -r requirements.txt"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "```bash" in ergebnis, (
            "Erwartet: Bash-Codeblock fuer install_command"
        )
        assert "pip install -r requirements.txt" in ergebnis

    def test_run_command_in_code_block(self):
        """Das Start-Kommando ist in einem Bash-Codeblock."""
        blueprint = {"run_command": "python app.py"}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "```bash" in ergebnis, (
            "Erwartet: Bash-Codeblock fuer run_command"
        )
        assert "python app.py" in ergebnis

    def test_run_bat_vorhanden_zeigt_windows_hinweis(self, tmp_path):
        """Wenn run.bat existiert, erscheint der Windows-Hinweis."""
        # run.bat im temporaeren Verzeichnis erstellen
        run_bat = tmp_path / "run.bat"
        run_bat.write_text("@echo off\nnpm start")

        ergebnis = generate_simple_readme(str(tmp_path), {})
        assert "Oder unter Windows:" in ergebnis, (
            "Erwartet: 'Oder unter Windows:' Hinweis wenn run.bat existiert"
        )
        assert "run.bat" in ergebnis, (
            "Erwartet: 'run.bat' im Batch-Codeblock"
        )

    def test_run_bat_nicht_vorhanden_kein_windows_hinweis(self, tmp_path):
        """Ohne run.bat erscheint kein Windows-Hinweis."""
        ergebnis = generate_simple_readme(str(tmp_path), {})
        assert "Oder unter Windows:" not in ergebnis, (
            "Erwartet: Kein 'Oder unter Windows:' ohne run.bat"
        )

    def test_run_bat_batch_codeblock(self, tmp_path):
        """Der run.bat-Abschnitt verwendet einen batch-Codeblock."""
        run_bat = tmp_path / "run.bat"
        run_bat.write_text("@echo off")

        ergebnis = generate_simple_readme(str(tmp_path), {})
        assert "```batch" in ergebnis, (
            "Erwartet: Batch-Codeblock '```batch' fuer run.bat"
        )

    def test_requires_server_false_kein_port(self):
        """requires_server=False erzeugt keinen Server-Port-Eintrag."""
        blueprint = {"requires_server": False, "server_port": 8080}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "Server-Port" not in ergebnis, (
            "Erwartet: Kein Server-Port bei requires_server=False"
        )

    def test_vollstaendiges_blueprint(self):
        """Ein vollstaendiges Blueprint erzeugt alle Sektionen."""
        blueprint = {
            "project_type": "fullstack",
            "language": "javascript",
            "database": "MongoDB",
            "requires_server": True,
            "server_port": 5000,
            "install_command": "npm ci",
            "run_command": "npm start",
        }
        ergebnis = generate_simple_readme("/tmp/test_app", blueprint)
        assert "# test_app" in ergebnis
        assert "**Projekttyp:** fullstack" in ergebnis
        assert "**Sprache:** javascript" in ergebnis
        assert "**Datenbank:** MongoDB" in ergebnis
        assert "**Server-Port:** 5000" in ergebnis
        assert "## Installation" in ergebnis
        assert "npm ci" in ergebnis
        assert "## Starten" in ergebnis
        assert "npm start" in ergebnis
        assert "## Lizenz" in ergebnis

    def test_database_leerer_string_kein_eintrag(self):
        """database als leerer String erzeugt keinen Datenbank-Eintrag."""
        blueprint = {"database": ""}
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        assert "Datenbank" not in ergebnis, (
            "Erwartet: Kein Datenbank-Eintrag bei leerem database-String"
        )

    def test_project_path_none_kein_run_bat_check(self):
        """Bei project_path=None wird kein run.bat-Check durchgefuehrt."""
        # Sollte keinen Fehler werfen (os.path.join mit None wuerde crashen)
        ergebnis = generate_simple_readme(None, {})
        assert "Oder unter Windows:" not in ergebnis, (
            "Erwartet: Kein Windows-Hinweis bei project_path=None"
        )

    def test_reihenfolge_sektionen(self):
        """Die Sektionen erscheinen in der korrekten Reihenfolge."""
        blueprint = {
            "install_command": "npm install",
            "run_command": "npm start",
        }
        ergebnis = generate_simple_readme("/tmp/test", blueprint)
        pos_beschreibung = ergebnis.index("## Beschreibung")
        pos_tech = ergebnis.index("## Technische Details")
        pos_install = ergebnis.index("## Installation")
        pos_start = ergebnis.index("## Starten")
        pos_lizenz = ergebnis.index("## Lizenz")

        assert pos_beschreibung < pos_tech < pos_install < pos_start < pos_lizenz, (
            "Erwartet: Sektionen in Reihenfolge Beschreibung < Tech < Installation < Starten < Lizenz"
        )
