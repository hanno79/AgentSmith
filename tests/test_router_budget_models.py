# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 22.02.2026
Version: 1.0
Beschreibung: Pydantic-Modelltests fuer backend/routers/budget.py.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers.budget import BudgetCapsRequest, ProjectCreateRequest


class TestBudgetCapsRequest:
    """Tests fuer das BudgetCapsRequest Pydantic-Modell."""

    def test_gueltige_caps(self):
        caps = BudgetCapsRequest(monthly=100.0, daily=10.0)
        assert caps.monthly == 100.0
        assert caps.daily == 10.0

    def test_null_werte_erlaubt(self):
        caps = BudgetCapsRequest(monthly=0.0, daily=0.0)
        assert caps.monthly == 0.0
        assert caps.daily == 0.0

    def test_negative_monthly_abgelehnt(self):
        with pytest.raises(Exception):
            BudgetCapsRequest(monthly=-1.0, daily=10.0)

    def test_negative_daily_abgelehnt(self):
        with pytest.raises(Exception):
            BudgetCapsRequest(monthly=10.0, daily=-5.0)

    def test_default_auto_pause(self):
        caps = BudgetCapsRequest(monthly=50.0, daily=5.0)
        assert caps.auto_pause is True

    def test_optionale_webhooks(self):
        caps = BudgetCapsRequest(monthly=50.0, daily=5.0)
        assert caps.slack_webhook is None
        assert caps.discord_webhook is None

    def test_webhooks_gesetzt(self):
        caps = BudgetCapsRequest(
            monthly=50.0,
            daily=5.0,
            slack_webhook="https://hooks.slack.com/test",
            discord_webhook="https://discord.com/api/webhooks/test",
        )
        assert caps.slack_webhook == "https://hooks.slack.com/test"
        assert caps.discord_webhook == "https://discord.com/api/webhooks/test"


class TestProjectCreateRequest:
    """Tests fuer das ProjectCreateRequest Pydantic-Modell."""

    def test_gueltiges_projekt(self):
        req = ProjectCreateRequest(project_id="p1", name="Testprojekt", budget=500.0)
        assert req.project_id == "p1"
        assert req.name == "Testprojekt"
        assert req.budget == 500.0
