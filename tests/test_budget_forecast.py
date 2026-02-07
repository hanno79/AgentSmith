# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Unit Tests fuer budget_forecast.py - Kostenprognose und Trend-Analyse.

              Tests validieren:
              - Lineare Regression bei Kostenprognose (predict_costs)
              - Trend-Berechnung (_calculate_trend)
              - Burn-Rate-Berechnung (calculate_burn_rate)
"""

import pytest
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budget_forecast import predict_costs, _calculate_trend, calculate_burn_rate
from budget_config import UsageRecord


# =========================================================================
# Hilfsfunktionen
# =========================================================================

def _make_record(days_ago, cost, agent="test_agent"):
    """Erstellt einen UsageRecord mit dem angegebenen Alter in Tagen und Kosten."""
    ts = (datetime.now() - timedelta(days=days_ago)).isoformat()
    return UsageRecord(
        timestamp=ts,
        agent=agent,
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=cost
    )


def _make_records_over_days(num_days, cost_func=None):
    """
    Erstellt UsageRecords ueber mehrere Tage verteilt.

    Args:
        num_days: Anzahl der Tage (ein Record pro Tag)
        cost_func: Funktion die Tag-Index auf Kosten abbildet.
                   Standard: konstant 1.0
    """
    if cost_func is None:
        cost_func = lambda i: 1.0
    records = []
    for i in range(num_days):
        days_ago = num_days - 1 - i  # aeltester zuerst
        records.append(_make_record(days_ago, cost_func(i)))
    return records


# =========================================================================
# Tests fuer predict_costs
# =========================================================================

class TestPredictCosts:
    """Tests fuer die Kostenprognose-Funktion."""

    def test_zu_wenig_daten(self):
        """Weniger als 7 Records muessen prediction_available=False liefern."""
        records = [_make_record(i, 1.0) for i in range(6)]
        ergebnis = predict_costs(records)

        assert ergebnis["prediction_available"] is False, (
            f"Erwartet: prediction_available=False, Erhalten: {ergebnis['prediction_available']} "
            f"bei {len(records)} Records"
        )
        assert "reason" in ergebnis, "Erwartet: 'reason' Feld in der Antwort"

    def test_zu_wenig_tage(self):
        """7 Records am gleichen Tag muessen prediction_available=False liefern."""
        # Alle Records am gleichen Tag (0 Tage zurueck)
        records = [_make_record(0, 1.0 + i * 0.1) for i in range(7)]
        ergebnis = predict_costs(records)

        assert ergebnis["prediction_available"] is False, (
            "Erwartet: prediction_available=False bei 7 Records am selben Tag"
        )
        assert "reason" in ergebnis, "Erwartet: 'reason' Feld in der Antwort"

    def test_lineare_prognose_steigende_kosten(self):
        """10 Tage mit steigenden Kosten muessen eine verfuegbare Prognose mit positivem Slope liefern."""
        # Kosten steigen linear: 1.0, 2.0, 3.0, ..., 10.0
        records = _make_records_over_days(10, cost_func=lambda i: float(i + 1))
        ergebnis = predict_costs(records)

        assert ergebnis["prediction_available"] is True, (
            "Erwartet: prediction_available=True bei 10 Tagen Daten"
        )
        assert ergebnis["slope_per_day"] > 0, (
            f"Erwartet: positiver Slope bei steigenden Kosten, Erhalten: {ergebnis['slope_per_day']}"
        )
        assert "predictions" in ergebnis, "Erwartet: 'predictions' Feld in der Antwort"
        assert len(ergebnis["predictions"]) == 30, (
            f"Erwartet: 30 Tage Prognose, Erhalten: {len(ergebnis['predictions'])}"
        )
        assert ergebnis["total_predicted_30d"] > 0, (
            "Erwartet: positive Gesamtprognose bei steigenden Kosten"
        )

    def test_fallende_kosten(self):
        """Fallende Kosten muessen einen negativen Slope ergeben."""
        # Kosten fallen linear: 10.0, 9.0, 8.0, ..., 1.0
        records = _make_records_over_days(10, cost_func=lambda i: float(10 - i))
        ergebnis = predict_costs(records)

        assert ergebnis["prediction_available"] is True, (
            "Erwartet: prediction_available=True bei 10 Tagen Daten"
        )
        assert ergebnis["slope_per_day"] < 0, (
            f"Erwartet: negativer Slope bei fallenden Kosten, Erhalten: {ergebnis['slope_per_day']}"
        )

    def test_confidence_low(self):
        """Weniger als 14 Tage muessen Confidence 'low' ergeben."""
        records = _make_records_over_days(10, cost_func=lambda i: float(i + 1))
        ergebnis = predict_costs(records)

        assert ergebnis["confidence"] == "low", (
            f"Erwartet: confidence='low' bei 10 Tagen, Erhalten: {ergebnis['confidence']}"
        )

    def test_confidence_medium(self):
        """14 bis 29 Tage muessen Confidence 'medium' ergeben."""
        records = _make_records_over_days(20, cost_func=lambda i: float(i + 1))
        ergebnis = predict_costs(records)

        assert ergebnis["confidence"] == "medium", (
            f"Erwartet: confidence='medium' bei 20 Tagen, Erhalten: {ergebnis['confidence']}"
        )

    def test_confidence_high(self):
        """30 oder mehr Tage muessen Confidence 'high' ergeben."""
        records = _make_records_over_days(35, cost_func=lambda i: float(i + 1))
        ergebnis = predict_costs(records)

        assert ergebnis["confidence"] == "high", (
            f"Erwartet: confidence='high' bei 35 Tagen, Erhalten: {ergebnis['confidence']}"
        )

    def test_prognose_keine_negativen_kosten(self):
        """Prognostizierte Kosten duerfen nie negativ sein (max(0, ...) Logik)."""
        # Stark fallende Kosten die in Zukunft negativ werden wuerden
        records = _make_records_over_days(10, cost_func=lambda i: max(0.01, 10.0 - i * 2.0))
        ergebnis = predict_costs(records)

        assert ergebnis["prediction_available"] is True
        for prediction in ergebnis["predictions"]:
            assert prediction["predicted_cost"] >= 0, (
                f"Erwartet: keine negativen Kosten, Erhalten: {prediction['predicted_cost']} "
                f"am {prediction['date']}"
            )

    def test_days_ahead_parameter(self):
        """Der days_ahead-Parameter muss die Anzahl der Prognosen steuern."""
        records = _make_records_over_days(10, cost_func=lambda i: float(i + 1))
        ergebnis = predict_costs(records, days_ahead=15)

        assert len(ergebnis["predictions"]) == 15, (
            f"Erwartet: 15 Prognose-Tage, Erhalten: {len(ergebnis['predictions'])}"
        )


# =========================================================================
# Tests fuer _calculate_trend
# =========================================================================

class TestCalculateTrend:
    """Tests fuer die Trend-Berechnungsfunktion."""

    def test_zu_wenig_daten(self):
        """Weniger als 2 Kostenwerte muessen 'unknown' liefern."""
        assert _calculate_trend([]) == "unknown", (
            "Erwartet: 'unknown' bei leerer Liste"
        )
        assert _calculate_trend([5.0]) == "unknown", (
            "Erwartet: 'unknown' bei nur einem Wert"
        )

    def test_steigend(self):
        """Deutlich hoehere aktuelle Kosten muessen 'rising' ergeben."""
        # 10 alte Werte niedrig, 7 aktuelle Werte hoch (> 10% mehr)
        costs = [1.0] * 10 + [5.0] * 7
        ergebnis = _calculate_trend(costs)

        assert ergebnis == "rising", (
            f"Erwartet: 'rising' bei deutlich steigenden Kosten, Erhalten: '{ergebnis}'"
        )

    def test_fallend(self):
        """Deutlich niedrigere aktuelle Kosten muessen 'falling' ergeben."""
        # 10 alte Werte hoch, 7 aktuelle Werte niedrig (< 90% vom Alten)
        costs = [10.0] * 10 + [1.0] * 7
        ergebnis = _calculate_trend(costs)

        assert ergebnis == "falling", (
            f"Erwartet: 'falling' bei deutlich fallenden Kosten, Erhalten: '{ergebnis}'"
        )

    def test_stabil(self):
        """Aehnliche Durchschnitte muessen 'stable' ergeben."""
        # Alle Werte sehr aehnlich (innerhalb 10% Schwankung)
        costs = [5.0] * 10 + [5.2] * 7
        ergebnis = _calculate_trend(costs)

        assert ergebnis == "stable", (
            f"Erwartet: 'stable' bei stabilen Kosten, Erhalten: '{ergebnis}'"
        )

    def test_grenzwert_knapp_ueber_110_prozent(self):
        """Werte knapp ueber der 110%-Schwelle muessen 'rising' ergeben."""
        # older_avg = 10.0, recent_avg muss > 11.0 sein
        costs = [10.0] * 10 + [11.5] * 7
        ergebnis = _calculate_trend(costs)

        assert ergebnis == "rising", (
            f"Erwartet: 'rising' bei recent_avg > older_avg * 1.1, Erhalten: '{ergebnis}'"
        )

    def test_grenzwert_genau_110_prozent(self):
        """Werte genau bei 110% muessen 'stable' ergeben (nicht > sondern ==)."""
        # older_avg = 10.0, recent_avg = 11.0 (genau 1.1 * 10)
        costs = [10.0] * 10 + [11.0] * 7
        ergebnis = _calculate_trend(costs)

        assert ergebnis == "stable", (
            f"Erwartet: 'stable' bei recent_avg == older_avg * 1.1, Erhalten: '{ergebnis}'"
        )


# =========================================================================
# Tests fuer calculate_burn_rate
# =========================================================================

class TestCalculateBurnRate:
    """Tests fuer die Burn-Rate-Berechnung."""

    def test_berechnung_korrekt(self):
        """Aktuelle Records muessen korrekte Raten ergeben."""
        # 3 Records innerhalb der letzten 7 Tage, je 2.0 USD
        records = [
            _make_record(1, 2.0),
            _make_record(3, 2.0),
            _make_record(5, 2.0),
        ]
        ergebnis = calculate_burn_rate(records, days=7)

        assert ergebnis["period_days"] == 7, (
            f"Erwartet: period_days=7, Erhalten: {ergebnis['period_days']}"
        )
        assert ergebnis["total_cost"] == 6.0, (
            f"Erwartet: total_cost=6.0, Erhalten: {ergebnis['total_cost']}"
        )
        # Die Funktion berechnet: daily_rate = total_cost / days (ungerundet intern)
        # weekly_rate und monthly_rate werden aus dem ungerundeten daily_rate berechnet
        # und erst dann gerundet
        raw_daily = 6.0 / 7
        expected_daily = round(raw_daily, 2)
        expected_weekly = round(raw_daily * 7, 2)
        expected_monthly = round(raw_daily * 30, 2)

        assert ergebnis["daily_rate"] == expected_daily, (
            f"Erwartet: daily_rate={expected_daily}, Erhalten: {ergebnis['daily_rate']}"
        )
        assert ergebnis["weekly_rate"] == expected_weekly, (
            f"Erwartet: weekly_rate={expected_weekly}, Erhalten: {ergebnis['weekly_rate']}"
        )
        assert ergebnis["monthly_rate"] == expected_monthly, (
            f"Erwartet: monthly_rate={expected_monthly}, Erhalten: {ergebnis['monthly_rate']}"
        )

    def test_leere_history(self):
        """Leere History muss Null-Raten liefern."""
        ergebnis = calculate_burn_rate([], days=7)

        assert ergebnis["total_cost"] == 0.0, (
            f"Erwartet: total_cost=0.0, Erhalten: {ergebnis['total_cost']}"
        )
        assert ergebnis["daily_rate"] == 0.0, (
            f"Erwartet: daily_rate=0.0, Erhalten: {ergebnis['daily_rate']}"
        )
        assert ergebnis["weekly_rate"] == 0.0, (
            f"Erwartet: weekly_rate=0.0, Erhalten: {ergebnis['weekly_rate']}"
        )
        assert ergebnis["monthly_rate"] == 0.0, (
            f"Erwartet: monthly_rate=0.0, Erhalten: {ergebnis['monthly_rate']}"
        )

    def test_alte_records_werden_ignoriert(self):
        """Records ausserhalb des Zeitfensters duerfen nicht gezaehlt werden."""
        records = [
            _make_record(1, 3.0),    # innerhalb von 7 Tagen
            _make_record(10, 100.0), # ausserhalb von 7 Tagen
            _make_record(20, 200.0), # ausserhalb von 7 Tagen
        ]
        ergebnis = calculate_burn_rate(records, days=7)

        assert ergebnis["total_cost"] == 3.0, (
            f"Erwartet: total_cost=3.0 (nur aktuelle Records), Erhalten: {ergebnis['total_cost']}"
        )

    def test_ungueltiger_timestamp(self):
        """Records mit ungueltigem Timestamp duerfen keinen Fehler werfen."""
        records = [
            _make_record(1, 5.0),
            UsageRecord(
                timestamp="kein-gueltiger-timestamp",
                agent="test",
                model="test",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=99.0
            ),
        ]
        ergebnis = calculate_burn_rate(records, days=7)

        # Nur der gueltige Record soll gezaehlt werden
        assert ergebnis["total_cost"] == 5.0, (
            f"Erwartet: total_cost=5.0 (ungueltiger Record ignoriert), Erhalten: {ergebnis['total_cost']}"
        )

    def test_custom_days_parameter(self):
        """Der days-Parameter muss das Zeitfenster korrekt steuern."""
        records = [
            _make_record(2, 5.0),   # innerhalb von 3 Tagen
            _make_record(5, 10.0),  # ausserhalb von 3 Tagen
        ]
        ergebnis = calculate_burn_rate(records, days=3)

        assert ergebnis["period_days"] == 3, (
            f"Erwartet: period_days=3, Erhalten: {ergebnis['period_days']}"
        )
        assert ergebnis["total_cost"] == 5.0, (
            f"Erwartet: total_cost=5.0, Erhalten: {ergebnis['total_cost']}"
        )
