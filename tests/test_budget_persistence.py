# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer budget_persistence.py - Laden und Speichern von Budget-Daten.
              Testet alle 6 File-I/O-Funktionen mit pytest tmp_path Fixture.
"""

import json
from pathlib import Path

import pytest

from budget_persistence import (
    load_usage_history,
    save_usage_history,
    load_config,
    save_config,
    load_projects,
    save_projects,
)
from budget_config import UsageRecord, BudgetConfig, ProjectBudget


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Testdaten
# ---------------------------------------------------------------------------

def _erstelle_usage_records() -> list:
    """Erstellt Beispiel-UsageRecords fuer Tests."""
    return [
        UsageRecord(
            timestamp="2026-02-06T10:00:00",
            agent="coder",
            model="anthropic/claude-sonnet-4",
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.045,
            project_id="proj_001",
            task_description="Datei erstellen",
        ),
        UsageRecord(
            timestamp="2026-02-06T11:00:00",
            agent="reviewer",
            model="openai/gpt-4o",
            prompt_tokens=1000,
            completion_tokens=400,
            total_tokens=1400,
            cost_usd=0.029,
        ),
    ]


def _erstelle_custom_config() -> BudgetConfig:
    """Erstellt eine BudgetConfig mit nicht-Standard-Werten."""
    return BudgetConfig(
        global_monthly_cap=5000.0,
        global_daily_cap=250.0,
        auto_pause=False,
        alert_thresholds=[25, 50, 80],
    )


def _erstelle_projekte() -> dict:
    """Erstellt ein Beispiel-Projekte-Dictionary."""
    return {
        "proj_001": ProjectBudget(
            project_id="proj_001",
            name="Testprojekt Alpha",
            total_budget=1000.0,
            spent=150.0,
            created_at="2026-01-15T09:00:00",
            alerts_sent=["50"],
        ),
        "proj_002": ProjectBudget(
            project_id="proj_002",
            name="Testprojekt Beta",
            total_budget=2000.0,
            spent=0.0,
            created_at="2026-02-01T09:00:00",
            alerts_sent=[],
        ),
    }


# ===========================================================================
# Tests: UsageHistory
# ===========================================================================


class TestUsageHistory:
    """Tests fuer load_usage_history und save_usage_history."""

    def test_save_und_load(self, tmp_path: Path):
        """Speichern und Laden liefert identische UsageRecords zurueck."""
        datei = tmp_path / "usage.json"
        records = _erstelle_usage_records()

        ergebnis_save = save_usage_history(records, datei)
        assert ergebnis_save is True, "Speichern sollte True zurueckgeben"

        geladene = load_usage_history(datei)
        assert len(geladene) == len(records), (
            f"Erwartet: {len(records)} Records, Erhalten: {len(geladene)}"
        )

        for original, geladen in zip(records, geladene):
            assert original.timestamp == geladen.timestamp
            assert original.agent == geladen.agent
            assert original.model == geladen.model
            assert original.prompt_tokens == geladen.prompt_tokens
            assert original.completion_tokens == geladen.completion_tokens
            assert original.total_tokens == geladen.total_tokens
            assert original.cost_usd == pytest.approx(geladen.cost_usd)
            assert original.project_id == geladen.project_id
            assert original.task_description == geladen.task_description

    def test_load_fehlende_datei(self, tmp_path: Path):
        """Laden einer nicht-existierenden Datei liefert leere Liste."""
        datei = tmp_path / "nicht_vorhanden.json"
        ergebnis = load_usage_history(datei)

        assert ergebnis == [], (
            f"Erwartet: leere Liste, Erhalten: {ergebnis}"
        )

    def test_load_korruptes_json(self, tmp_path: Path):
        """Laden einer korrupten JSON-Datei liefert leere Liste ohne Absturz."""
        datei = tmp_path / "korrupt.json"
        datei.write_text("{das ist kein gueltiges json!!!", encoding="utf-8")

        ergebnis = load_usage_history(datei)
        assert ergebnis == [], (
            "Korrupte Datei sollte leere Liste zurueckgeben, kein Absturz"
        )

    def test_save_fehler(self, tmp_path: Path):
        """Speichern an unmoeglichem Pfad liefert False."""
        # Pfad auf ein nicht existierendes Unterverzeichnis zeigen
        unmoeglich = tmp_path / "nicht_existiert" / "sub" / "usage.json"
        records = _erstelle_usage_records()

        ergebnis = save_usage_history(records, unmoeglich)
        assert ergebnis is False, (
            "Speichern an unmoeglichem Pfad sollte False zurueckgeben"
        )


# ===========================================================================
# Tests: Config
# ===========================================================================


class TestConfig:
    """Tests fuer load_config und save_config."""

    def test_save_und_load(self, tmp_path: Path):
        """Speichern und Laden liefert identische BudgetConfig zurueck."""
        datei = tmp_path / "config.json"
        config = BudgetConfig()

        ergebnis_save = save_config(config, datei)
        assert ergebnis_save is True, "Speichern sollte True zurueckgeben"

        geladene = load_config(datei)
        assert geladene.global_monthly_cap == config.global_monthly_cap
        assert geladene.global_daily_cap == config.global_daily_cap
        assert geladene.auto_pause == config.auto_pause
        assert geladene.alert_thresholds == config.alert_thresholds

    def test_load_fehlende_datei(self, tmp_path: Path):
        """Laden einer fehlenden Datei liefert Standard-BudgetConfig."""
        datei = tmp_path / "nicht_vorhanden.json"
        ergebnis = load_config(datei)

        standard = BudgetConfig()
        assert ergebnis.global_monthly_cap == standard.global_monthly_cap, (
            f"Erwartet: {standard.global_monthly_cap}, "
            f"Erhalten: {ergebnis.global_monthly_cap}"
        )
        assert ergebnis.global_daily_cap == standard.global_daily_cap
        assert ergebnis.auto_pause == standard.auto_pause
        assert ergebnis.alert_thresholds == standard.alert_thresholds

    def test_load_korruptes_json(self, tmp_path: Path):
        """Laden einer korrupten JSON-Datei liefert Standard-BudgetConfig."""
        datei = tmp_path / "korrupt.json"
        datei.write_text("<<<KEINE GUELTIGE JSON>>>", encoding="utf-8")

        ergebnis = load_config(datei)
        standard = BudgetConfig()

        assert ergebnis.global_monthly_cap == standard.global_monthly_cap, (
            "Korrupte Config-Datei sollte Standard-Werte liefern"
        )
        assert ergebnis.auto_pause == standard.auto_pause

    def test_custom_config_roundtrip(self, tmp_path: Path):
        """Nicht-Standard-Konfigurationswerte ueberleben Save/Load Zyklus."""
        datei = tmp_path / "custom_config.json"
        config = _erstelle_custom_config()

        save_config(config, datei)
        geladene = load_config(datei)

        assert geladene.global_monthly_cap == 5000.0, (
            f"Erwartet: 5000.0, Erhalten: {geladene.global_monthly_cap}"
        )
        assert geladene.global_daily_cap == 250.0, (
            f"Erwartet: 250.0, Erhalten: {geladene.global_daily_cap}"
        )
        assert geladene.auto_pause is False, (
            "auto_pause sollte False sein nach Roundtrip"
        )
        assert geladene.alert_thresholds == [25, 50, 80], (
            f"Erwartet: [25, 50, 80], Erhalten: {geladene.alert_thresholds}"
        )


# ===========================================================================
# Tests: Projects
# ===========================================================================


class TestProjects:
    """Tests fuer load_projects und save_projects."""

    def test_save_und_load(self, tmp_path: Path):
        """Speichern und Laden liefert identische Projekte zurueck."""
        datei = tmp_path / "projects.json"
        projekte = _erstelle_projekte()

        ergebnis_save = save_projects(projekte, datei)
        assert ergebnis_save is True, "Speichern sollte True zurueckgeben"

        geladene = load_projects(datei)
        assert set(geladene.keys()) == set(projekte.keys()), (
            f"Erwartet Schluessel: {set(projekte.keys())}, "
            f"Erhalten: {set(geladene.keys())}"
        )

        for key in projekte:
            original = projekte[key]
            geladen = geladene[key]
            assert original.project_id == geladen.project_id
            assert original.name == geladen.name
            assert original.total_budget == pytest.approx(geladen.total_budget)
            assert original.spent == pytest.approx(geladen.spent)
            assert original.created_at == geladen.created_at
            assert original.alerts_sent == geladen.alerts_sent

    def test_load_fehlende_datei(self, tmp_path: Path):
        """Laden einer fehlenden Datei liefert leeres Dictionary."""
        datei = tmp_path / "nicht_vorhanden.json"
        ergebnis = load_projects(datei)

        assert ergebnis == {}, (
            f"Erwartet: leeres Dict, Erhalten: {ergebnis}"
        )

    def test_load_korruptes_json(self, tmp_path: Path):
        """Laden einer korrupten JSON-Datei liefert leeres Dictionary."""
        datei = tmp_path / "korrupt.json"
        datei.write_text("}{nicht--json}{", encoding="utf-8")

        ergebnis = load_projects(datei)
        assert ergebnis == {}, (
            "Korrupte Projekte-Datei sollte leeres Dict zurueckgeben"
        )

    def test_leere_projekte(self, tmp_path: Path):
        """Speichern und Laden eines leeren Dictionarys funktioniert korrekt."""
        datei = tmp_path / "leer.json"

        ergebnis_save = save_projects({}, datei)
        assert ergebnis_save is True, "Speichern leerer Projekte sollte True sein"

        geladene = load_projects(datei)
        assert geladene == {}, (
            f"Erwartet: leeres Dict, Erhalten: {geladene}"
        )
