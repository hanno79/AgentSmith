# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 22.02.2026
Version: 1.0
Beschreibung: Pydantic-Modelltests fuer backend/routers/budget.py.
"""
# ÄNDERUNG 24.02.2026: DUMMY-Konstanten + ValidationError-Assertions fuer BudgetCapsRequest ergänzt.

import os
import sys
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers.budget import BudgetCapsRequest, ProjectCreateRequest

DUMMY_MONTHLY = 50.0  # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
DUMMY_DAILY = 5.0  # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
DUMMY_SLACK_WEBHOOK = "https://hooks.slack.com/test"  # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
DUMMY_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/test"  # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!


class TestBudgetCapsRequest:
    """Tests fuer das BudgetCapsRequest Pydantic-Modell."""

    def test_gueltige_caps(self):
        caps = BudgetCapsRequest(monthly=DUMMY_MONTHLY, daily=DUMMY_DAILY)
        assert caps.monthly == DUMMY_MONTHLY
        assert caps.daily == DUMMY_DAILY

    def test_null_werte_erlaubt(self):
        caps = BudgetCapsRequest(monthly=0.0, daily=0.0)
        assert caps.monthly == 0.0
        assert caps.daily == 0.0

    def test_negative_monthly_abgelehnt(self):
        with pytest.raises(ValidationError):
            BudgetCapsRequest(monthly=-1.0, daily=DUMMY_DAILY)

    def test_negative_daily_abgelehnt(self):
        with pytest.raises(ValidationError):
            BudgetCapsRequest(monthly=DUMMY_MONTHLY, daily=-5.0)

    def test_default_auto_pause(self):
        caps = BudgetCapsRequest(monthly=DUMMY_MONTHLY, daily=DUMMY_DAILY)
        assert caps.auto_pause is True

    def test_optionale_webhooks(self):
        caps = BudgetCapsRequest(monthly=DUMMY_MONTHLY, daily=DUMMY_DAILY)
        assert caps.slack_webhook is None
        assert caps.discord_webhook is None

    def test_webhooks_gesetzt(self):
        caps = BudgetCapsRequest(
            monthly=DUMMY_MONTHLY,
            daily=DUMMY_DAILY,
            slack_webhook=DUMMY_SLACK_WEBHOOK,
            discord_webhook=DUMMY_DISCORD_WEBHOOK,
        )
        assert caps.slack_webhook == DUMMY_SLACK_WEBHOOK
        assert caps.discord_webhook == DUMMY_DISCORD_WEBHOOK


class TestProjectCreateRequest:
    """Tests fuer das ProjectCreateRequest Pydantic-Modell."""

    def test_gueltiges_projekt(self):
        req = ProjectCreateRequest(project_id="p1", name="Testprojekt", budget=500.0)
        assert req.project_id == "p1"
        assert req.name == "Testprojekt"
        assert req.budget == 500.0
