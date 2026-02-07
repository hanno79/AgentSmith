# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Umfassende Tests fuer budget_reporting.py.
              Prueft alle 6 Funktionen fuer Budget-Statistiken und Reporting.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from budget_reporting import (
    get_today_totals,
    get_stats,
    get_costs_by_agent,
    get_hourly_heatmap,
    get_historical_data,
    fetch_openrouter_usage,
)
from budget_config import UsageRecord, BudgetConfig


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _make_record(
    days_ago: int = 0,
    hours_ago: int = 0,
    cost: float = 1.0,
    agent: str = "coder",
    tokens: int = 100,
) -> UsageRecord:
    """Erzeugt einen UsageRecord mit konfigurierbarem Zeitstempel."""
    ts = (datetime.now() - timedelta(days=days_ago, hours=hours_ago)).isoformat()
    return UsageRecord(
        timestamp=ts,
        agent=agent,
        model="test-model",
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        total_tokens=tokens,
        cost_usd=cost,
    )


# ===========================================================================
# Tests fuer get_today_totals
# ===========================================================================

class TestGetTodayTotals:
    """Tests fuer die Tages-Gesamtberechnung."""

    def test_eintraege_heute(self):
        """Zwei Eintraege von heute muessen korrekt summiert werden."""
        records = [
            _make_record(days_ago=0, cost=2.5, tokens=200),
            _make_record(days_ago=0, cost=1.5, tokens=300),
        ]
        result = get_today_totals(records)

        assert result["total_tokens"] == 500, (
            f"Erwartet: 500, Erhalten: {result['total_tokens']} bei total_tokens"
        )
        assert result["total_cost"] == 4.0, (
            f"Erwartet: 4.0, Erhalten: {result['total_cost']} bei total_cost"
        )
        assert result["records_count"] == 2, (
            f"Erwartet: 2, Erhalten: {result['records_count']} bei records_count"
        )

    def test_keine_heute(self):
        """Nur gestrige Eintraege ergeben Nullwerte fuer heute."""
        records = [
            _make_record(days_ago=1, cost=5.0, tokens=500),
            _make_record(days_ago=2, cost=3.0, tokens=300),
        ]
        result = get_today_totals(records)

        assert result["total_tokens"] == 0, (
            f"Erwartet: 0, Erhalten: {result['total_tokens']} - gestrige Eintraege zaehlen nicht"
        )
        assert result["total_cost"] == 0, (
            f"Erwartet: 0, Erhalten: {result['total_cost']} - gestrige Kosten zaehlen nicht"
        )
        assert result["records_count"] == 0

    def test_leere_history(self):
        """Leere Historie ergibt Nullwerte."""
        result = get_today_totals([])

        assert result["total_tokens"] == 0
        assert result["total_cost"] == 0
        assert result["records_count"] == 0


# ===========================================================================
# Tests fuer get_stats
# ===========================================================================

class TestGetStats:
    """Tests fuer die vollstaendige Statistik-Berechnung."""

    @patch("budget_reporting.fetch_openrouter_usage", return_value=None)
    def test_volle_statistik(self, mock_fetch):
        """Statistiken mit Eintraegen ueber 30 Tage berechnen."""
        config = BudgetConfig(global_monthly_cap=1000.0)
        records = [
            _make_record(days_ago=0, cost=10.0, tokens=1000),
            _make_record(days_ago=5, cost=20.0, tokens=2000),
            _make_record(days_ago=15, cost=30.0, tokens=3000),
        ]

        result = get_stats(records, config, openrouter_api_key=None, period_days=30)

        assert result["total_budget"] == 1000.0, (
            f"Erwartet: 1000.0, Erhalten: {result['total_budget']}"
        )
        assert result["spent_this_period"] == 60.0, (
            f"Erwartet: 60.0, Erhalten: {result['spent_this_period']}"
        )
        assert result["remaining"] == 940.0, (
            f"Erwartet: 940.0, Erhalten: {result['remaining']}"
        )
        assert result["spent_today"] == 10.0, (
            f"Erwartet: 10.0, Erhalten: {result['spent_today']}"
        )
        assert result["total_records"] == 3
        assert result["period_days"] == 30
        assert result["data_source"] == "real"
        assert result["openrouter_data"] is None
        # Burn Rate muss positiv sein (es gibt Ausgaben)
        assert result["burn_rate_daily"] > 0
        # days_remaining muss berechnet sein
        assert result["days_remaining"] > 0

    @patch("budget_reporting.fetch_openrouter_usage", return_value=None)
    def test_leere_history(self, mock_fetch):
        """Leere Historie ergibt Nullwerte und data_source 'no_data'."""
        config = BudgetConfig(global_monthly_cap=500.0)

        result = get_stats([], config, openrouter_api_key=None)

        assert result["spent_this_period"] == 0.0
        assert result["spent_today"] == 0.0
        assert result["burn_rate_daily"] == 0.0
        assert result["data_source"] == "no_data"
        assert result["remaining"] == 500.0
        assert result["total_records"] == 0
        assert result["days_remaining"] == 999
        assert result["projected_runout"] == "N/A"

    @patch("budget_reporting.fetch_openrouter_usage", return_value=None)
    def test_burn_rate_aenderung(self, mock_fetch):
        """Unterschiedliche Wochen ergeben eine prozentuale Burn-Rate-Aenderung."""
        config = BudgetConfig(global_monthly_cap=10000.0)
        # Letzte Woche: 100 USD, vorherige Woche: 50 USD -> +100% Aenderung
        records = [
            _make_record(days_ago=3, cost=100.0, tokens=5000),   # letzte Woche
            _make_record(days_ago=10, cost=50.0, tokens=2500),   # vorherige Woche
        ]

        result = get_stats(records, config, openrouter_api_key=None, period_days=30)

        assert result["burn_rate_change"] == 100.0, (
            f"Erwartet: 100.0% Aenderung, Erhalten: {result['burn_rate_change']}"
        )


# ===========================================================================
# Tests fuer get_costs_by_agent
# ===========================================================================

class TestGetCostsByAgent:
    """Tests fuer die Kosten-Aufschluesselung nach Agent."""

    def test_mehrere_agenten(self):
        """Drei Agenten werden korrekt aggregiert und nach Kosten sortiert."""
        records = [
            _make_record(days_ago=0, cost=50.0, agent="planner", tokens=5000),
            _make_record(days_ago=0, cost=30.0, agent="coder", tokens=3000),
            _make_record(days_ago=0, cost=20.0, agent="reviewer", tokens=2000),
        ]

        result = get_costs_by_agent(records, period_days=7)

        assert len(result) == 3, (
            f"Erwartet: 3 Agenten, Erhalten: {len(result)}"
        )
        # Sortierung: teuerster zuerst
        assert result[0]["name"] == "planner"
        assert result[1]["name"] == "coder"
        assert result[2]["name"] == "reviewer"
        # Kosten pruefen
        assert result[0]["cost"] == 50.0
        assert result[1]["cost"] == 30.0
        assert result[2]["cost"] == 20.0
        # Teuerster Agent hat 100%
        assert result[0]["percentage"] == 100.0

    def test_ein_agent(self):
        """Einzelner Agent erhaelt 100% Anteil."""
        records = [
            _make_record(days_ago=0, cost=10.0, agent="coder", tokens=1000),
            _make_record(days_ago=0, cost=5.0, agent="coder", tokens=500),
        ]

        result = get_costs_by_agent(records, period_days=7)

        assert len(result) == 1
        assert result[0]["name"] == "coder"
        assert result[0]["cost"] == 15.0
        assert result[0]["tokens"] == 1500
        assert result[0]["calls"] == 2
        assert result[0]["percentage"] == 100.0

    def test_leere_history(self):
        """Leere Historie ergibt leere Liste."""
        result = get_costs_by_agent([], period_days=7)

        assert result == [], (
            f"Erwartet: leere Liste, Erhalten: {result}"
        )


# ===========================================================================
# Tests fuer get_hourly_heatmap
# ===========================================================================

class TestGetHourlyHeatmap:
    """Tests fuer die stuendliche Heatmap-Erzeugung."""

    def test_normalisierung(self):
        """Heatmap-Werte muessen auf 0-1 normalisiert sein."""
        now = datetime.now()
        # Erzeuge Eintraege mit bekannten Stunden
        records = [
            UsageRecord(
                timestamp=now.replace(hour=10, minute=0, second=0).isoformat(),
                agent="coder",
                model="test",
                prompt_tokens=500,
                completion_tokens=500,
                total_tokens=1000,
                cost_usd=5.0,
            ),
            UsageRecord(
                timestamp=now.replace(hour=14, minute=0, second=0).isoformat(),
                agent="coder",
                model="test",
                prompt_tokens=250,
                completion_tokens=250,
                total_tokens=500,
                cost_usd=2.5,
            ),
        ]

        result = get_hourly_heatmap(records, period_days=1)

        assert "agents" in result
        assert "hours" in result
        assert "data" in result
        assert result["hours"] == list(range(24))
        assert len(result["agents"]) == 1
        assert result["agents"][0] == "coder"
        # Normalisierung: 1000 Tokens ist Maximum -> 1.0, 500 Tokens -> 0.5
        heatmap_row = result["data"][0]
        assert heatmap_row[10] == 1.0, (
            f"Erwartet: 1.0 bei Stunde 10 (Maximum), Erhalten: {heatmap_row[10]}"
        )
        assert heatmap_row[14] == 0.5, (
            f"Erwartet: 0.5 bei Stunde 14, Erhalten: {heatmap_row[14]}"
        )
        # Alle anderen Stunden muessen 0 sein
        for h in range(24):
            if h not in (10, 14):
                assert heatmap_row[h] == 0, (
                    f"Erwartet: 0 bei Stunde {h}, Erhalten: {heatmap_row[h]}"
                )

    def test_leere_daten(self):
        """Keine Eintraege ergeben leere Agenten und Daten."""
        result = get_hourly_heatmap([], period_days=1)

        assert result["agents"] == []
        assert result["hours"] == list(range(24))
        assert result["data"] == []


# ===========================================================================
# Tests fuer get_historical_data
# ===========================================================================

class TestGetHistoricalData:
    """Tests fuer die historische Tagesaggregation."""

    def test_tages_aggregation(self):
        """Eintraege an 3 Tagen muessen zu 3 Tageseintraegen aggregiert werden."""
        records = [
            _make_record(days_ago=1, cost=10.0, agent="coder", tokens=1000),
            _make_record(days_ago=1, cost=5.0, agent="planner", tokens=500),
            _make_record(days_ago=2, cost=20.0, agent="coder", tokens=2000),
            _make_record(days_ago=3, cost=15.0, agent="reviewer", tokens=1500),
        ]

        result = get_historical_data(records, period_days=30)

        assert len(result) == 3, (
            f"Erwartet: 3 Tageseintraege, Erhalten: {len(result)}"
        )
        # Ergebnis ist nach Datum aufsteigend sortiert
        # Aeltester Tag zuerst (3 Tage zurueck)
        assert result[0]["cost"] == 15.0
        assert result[0]["tokens"] == 1500
        assert result[0]["calls"] == 1
        assert result[0]["active_agents"] == 1

        # Tag 2: ein Eintrag
        assert result[1]["cost"] == 20.0
        assert result[1]["calls"] == 1

        # Tag 1 (gestern): 2 Eintraege, 2 Agenten
        assert result[2]["cost"] == 15.0  # 10 + 5
        assert result[2]["tokens"] == 1500  # 1000 + 500
        assert result[2]["calls"] == 2
        assert result[2]["active_agents"] == 2

    def test_leere_history(self):
        """Leere Historie ergibt leere Liste."""
        result = get_historical_data([], period_days=30)

        assert result == [], (
            f"Erwartet: leere Liste, Erhalten: {result}"
        )


# ===========================================================================
# Tests fuer fetch_openrouter_usage
# ===========================================================================

class TestFetchOpenrouterUsage:
    """Tests fuer den OpenRouter API-Abruf."""

    def test_kein_api_key(self):
        """Ohne API-Key wird None zurueckgegeben."""
        result = fetch_openrouter_usage(None)

        assert result is None, (
            "Erwartet: None bei fehlendem API-Key"
        )

    def test_leerer_api_key(self):
        """Leerer String als API-Key wird wie kein Key behandelt."""
        result = fetch_openrouter_usage("")

        assert result is None, (
            "Erwartet: None bei leerem API-Key"
        )

    @patch("budget_reporting.requests.get")
    def test_erfolgreicher_abruf(self, mock_get):
        """Erfolgreicher API-Abruf liefert die JSON-Antwort zurueck."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"usage": 42.0, "limit": 100.0}
        }
        mock_get.return_value = mock_response

        result = fetch_openrouter_usage("test-api-key-123")

        assert result is not None, "Erwartet: Daten bei erfolgreichem Abruf"
        assert result["data"]["usage"] == 42.0
        mock_get.assert_called_once_with(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": "Bearer test-api-key-123"},
            timeout=10,
        )

    @patch("budget_reporting.requests.get")
    def test_fehler_bei_abruf(self, mock_get):
        """Bei einer Exception wird None zurueckgegeben."""
        mock_get.side_effect = Exception("Netzwerkfehler")

        result = fetch_openrouter_usage("test-api-key-123")

        assert result is None, (
            "Erwartet: None bei Netzwerkfehler"
        )

    @patch("budget_reporting.requests.get")
    def test_http_fehlercode(self, mock_get):
        """Bei HTTP-Fehlercode (nicht 200) wird None zurueckgegeben."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = fetch_openrouter_usage("ungueltig-key")

        assert result is None, (
            "Erwartet: None bei HTTP 401"
        )
