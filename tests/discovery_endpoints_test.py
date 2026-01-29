# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 29.01.2026
Version: 1.0
Beschreibung: Tests fuer Discovery-Endpunkte und Dedup-Logik.
"""
# ÄNDERUNG 29.01.2026: Tests für Discovery-Endpoints und LLM-Mocking ergänzt

import os
import sys
import json
import asyncio
from unittest.mock import MagicMock, mock_open

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers import discovery as discovery_router


class DummySessionManager:
    """Einfacher Session-Manager Dummy für Tests."""

    def __init__(self):
        self.briefing = None

    def set_discovery_briefing(self, briefing: dict) -> None:
        self.briefing = briefing

    def get_discovery_briefing(self):
        return self.briefing


class DummyManager:
    """Dummy-Manager mit minimaler Config."""

    def __init__(self):
        self.briefing = None
        self.config = {
            "mode": "test",
            "models": {
                "test": {
                    "orchestrator": "openrouter/test-model"
                }
            }
        }

    def set_discovery_briefing(self, briefing: dict) -> None:
        self.briefing = briefing


def _build_client():
    app = FastAPI()
    app.include_router(discovery_router.router)
    return TestClient(app)


class TestDiscoveryBriefingEndpoint:
    """Tests für save_discovery_briefing."""

    def test_save_discovery_briefing_updates_session_and_path(self, monkeypatch, tmp_path):
        """Briefing wird gespeichert und Session aktualisiert."""
        session_mgr = DummySessionManager()
        manager = DummyManager()

        monkeypatch.setattr(discovery_router, "get_session_manager_instance", lambda: session_mgr)
        monkeypatch.setattr(discovery_router, "manager", manager)

        fake_dir = tmp_path / "backend" / "routers"
        fake_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(discovery_router.os.path, "dirname", lambda _: str(fake_dir))

        open_mock = mock_open()
        monkeypatch.setattr(discovery_router, "open", open_mock)
        monkeypatch.setattr(discovery_router.os, "makedirs", MagicMock())

        client = _build_client()
        briefing = {
            "projectName": "MyProject",
            "date": "29.01.2026",
            "goal": "Testziel",
            "agents": ["Coder", "Designer"]
        }

        response = client.post("/discovery/save-briefing", json=briefing)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project_name"] == "MyProject"
        assert data["path"] is not None
        assert data["path"].endswith("MyProject_briefing.md")
        assert session_mgr.briefing == briefing
        assert manager.briefing == briefing
        open_mock.assert_called_once()


class TestDiscoveryQuestionsRequest:
    """Tests für DiscoveryQuestionsRequest."""

    def test_request_model_accepts_fields(self):
        """DiscoveryQuestionsRequest akzeptiert vision und agents."""
        request = discovery_router.DiscoveryQuestionsRequest(
            vision="Projektbeschreibung",
            agents=["Coder", "Designer"]
        )
        assert request.vision == "Projektbeschreibung"
        assert request.agents == ["Coder", "Designer"]


class TestGenerateAgentQuestions:
    """Tests für _generate_agent_questions."""

    def test_generate_agent_questions_parses_json(self, monkeypatch):
        """LLM-Antwort wird korrekt geparst."""
        manager = DummyManager()
        monkeypatch.setattr(discovery_router, "manager", manager)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "agent": "Coder",
                            "questions": [
                                {
                                    "id": "q1",
                                    "question": "Soll die App offline funktionieren?",
                                    "example": "Offline-Nutzung im Flugzeug",
                                    "options": [{"text": "Ja", "value": "yes"}],
                                    "allowCustom": True
                                }
                            ]
                        })
                    }
                }
            ]
        }

        response_mock = MagicMock()
        response_mock.raise_for_status.return_value = None
        response_mock.json.return_value = payload
        monkeypatch.setattr(discovery_router.requests, "post", MagicMock(return_value=response_mock))

        result = asyncio.run(discovery_router._generate_agent_questions("Coder", "Vision"))

        assert result["agent"] == "Coder"
        assert len(result["questions"]) == 1
        assert result["questions"][0]["id"] == "q1"

    def test_generate_agent_questions_dedup_merge(self, monkeypatch):
        """Dedup-Zusammenführung liefert agents-Array."""
        manager = DummyManager()
        monkeypatch.setattr(discovery_router, "manager", manager)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        response_payloads = [
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "agent": "Coder",
                                "questions": [
                                    {
                                        "id": "q1",
                                        "question": "Soll die App offline funktionieren?",
                                        "example": "Offline-Nutzung",
                                        "options": [{"text": "Ja", "value": "yes"}],
                                        "allowCustom": True
                                    }
                                ]
                            })
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "agent": "Designer",
                                "questions": [
                                    {
                                        "id": "q2",
                                        "question": "Soll die App offline funktionieren?",
                                        "example": "Offline-Modus",
                                        "options": [{"text": "Nein", "value": "no"}],
                                        "allowCustom": True
                                    }
                                ]
                            })
                        }
                    }
                ]
            }
        ]

        response_mocks = []
        for payload in response_payloads:
            response_mock = MagicMock()
            response_mock.raise_for_status.return_value = None
            response_mock.json.return_value = payload
            response_mocks.append(response_mock)

        post_mock = MagicMock(side_effect=response_mocks)
        monkeypatch.setattr(discovery_router.requests, "post", post_mock)

        coder_questions = asyncio.run(discovery_router._generate_agent_questions("Coder", "Vision"))
        designer_questions = asyncio.run(discovery_router._generate_agent_questions("Designer", "Vision"))

        merged = discovery_router._deduplicate_questions([coder_questions, designer_questions])

        assert len(merged) == 1
        assert "agents" in merged[0]
        assert set(merged[0]["agents"]) == {"Coder", "Designer"}
        assert len(merged[0]["options"]) == 2


class TestGenerateDiscoveryQuestionsEndpoint:
    """Tests für generate_discovery_questions."""

    def test_generate_questions_endpoint_deduplicates(self, monkeypatch):
        """Endpoint dedupliziert ähnliche Fragen."""
        async def fake_generate(agent: str, vision: str) -> dict:
            return {
                "agent": agent,
                "questions": [
                    {
                        "id": f"{agent}_q1",
                        "question": "Soll die App offline funktionieren?",
                        "example": "Offline-Nutzung",
                        "options": [{"text": "Ja", "value": "yes"}],
                        "allowCustom": True
                    }
                ]
            }

        monkeypatch.setattr(discovery_router, "_generate_agent_questions", fake_generate)

        client = _build_client()
        payload = {
            "vision": "Neue App mit Offline-Funktion",
            "agents": ["Coder", "Designer"]
        }

        response = client.post("/discovery/generate-questions", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["questions"], list)
        assert data["agents_processed"] == 2
        assert data["questions_original"] == 2
        assert data["questions_deduplicated"] == 1
        assert data["questions_merged"] == 1
        assert "agents" in data["questions"][0]
        assert set(data["questions"][0]["agents"]) == {"Coder", "Designer"}
