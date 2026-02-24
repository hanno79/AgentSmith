# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/routers/external_bureau.py.
              Testet _safe_serialize(), get_external_bureau_manager(),
              alle REST-Endpunkte (status, specialists, activate, deactivate,
              findings, search, review) sowie Fehlerbehandlung bei
              nicht verfuegbarem External Bureau Manager.
"""

import os
import sys
import dataclasses
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pydantic import BaseModel

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.external_bureau import router, _safe_serialize
import backend.routers.external_bureau as bureau_module

# FastAPI-App mit Router fuer TestClient erstellen
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# =========================================================================
# Hilfs-Datenstrukturen fuer Tests
# =========================================================================

@dataclasses.dataclass
class DummyDataclass:
    """Dataclass fuer Serialisierungstests."""
    name: str
    wert: int


class DummyPydanticModel(BaseModel):
    """Pydantic-Model fuer Serialisierungstests."""
    titel: str
    aktiv: bool = True


class DummyObjektMitDict:
    """Objekt mit __dict__ fuer Serialisierungstests."""
    def __init__(self, x, y):
        self.x = x
        self.y = y


class NichtSerialisierbaresObjekt:
    """Objekt das sich nicht normal serialisieren laesst."""
    def __init__(self):
        self._intern = object()

    @property
    def __dict__(self):
        raise TypeError("Nicht serialisierbar")


class DummyFinding:
    """Simples Finding-Objekt fuer Tests."""
    def __init__(self, severity, message):
        self.severity = severity
        self.message = message


class DummySearchResult:
    """Simuliertes Search-Ergebnis."""
    def __init__(self, success=True, findings=None, summary="", duration_ms=100, error=None):
        self.success = success
        self.findings = findings or []
        self.summary = summary
        self.duration_ms = duration_ms
        self.error = error


class DummyReviewResult:
    """Simuliertes Review-Ergebnis."""
    def __init__(self, success=True, findings=None, summary="", duration_ms=200, error=None):
        self.success = success
        self.findings = findings or []
        self.summary = summary
        self.duration_ms = duration_ms
        self.error = error


# =========================================================================
# Fixture: External Bureau Manager global zuruecksetzen
# =========================================================================

@pytest.fixture(autouse=True)
def reset_bureau_manager():
    """Setzt den globalen _external_bureau_manager vor und nach jedem Test zurueck."""
    bureau_module._external_bureau_manager = None
    yield
    bureau_module._external_bureau_manager = None


# =========================================================================
# TestSafeSerialize - Tests fuer _safe_serialize()
# =========================================================================

class TestSafeSerialize:
    """Tests fuer die Hilfsfunktion _safe_serialize."""

    def test_dataclass_wird_zu_dict(self):
        """Dataclass-Objekte werden korrekt zu dict serialisiert."""
        obj = DummyDataclass(name="test", wert=42)
        ergebnis = _safe_serialize(obj)
        assert ergebnis == {"name": "test", "wert": 42}, (
            f"Erwartet: dict mit name/wert, Erhalten: {ergebnis}"
        )

    def test_pydantic_model_wird_serialisiert(self):
        """Pydantic-Models werden ueber .dict() serialisiert."""
        obj = DummyPydanticModel(titel="Analyse", aktiv=False)
        ergebnis = _safe_serialize(obj)
        assert ergebnis["titel"] == "Analyse", (
            f"Erwartet: 'Analyse', Erhalten: {ergebnis.get('titel')}"
        )
        assert ergebnis["aktiv"] is False, (
            f"Erwartet: False, Erhalten: {ergebnis.get('aktiv')}"
        )

    def test_dict_wird_rekursiv_serialisiert(self):
        """Verschachtelte dicts werden rekursiv serialisiert."""
        obj = {"a": {"b": 1}, "c": [2, 3]}
        ergebnis = _safe_serialize(obj)
        assert ergebnis == {"a": {"b": 1}, "c": [2, 3]}, (
            f"Erwartet: verschachteltes dict, Erhalten: {ergebnis}"
        )

    def test_liste_wird_elementweise_serialisiert(self):
        """Listen und Tupel werden elementweise serialisiert."""
        obj = [DummyDataclass(name="eins", wert=1), DummyDataclass(name="zwei", wert=2)]
        ergebnis = _safe_serialize(obj)
        assert len(ergebnis) == 2, (
            f"Erwartet: 2 Elemente, Erhalten: {len(ergebnis)}"
        )
        assert ergebnis[0] == {"name": "eins", "wert": 1}
        assert ergebnis[1] == {"name": "zwei", "wert": 2}

    def test_tuple_wird_zu_liste(self):
        """Tupel werden als Liste serialisiert."""
        ergebnis = _safe_serialize((1, "zwei", 3.0))
        assert ergebnis == [1, "zwei", 3.0], (
            f"Erwartet: [1, 'zwei', 3.0], Erhalten: {ergebnis}"
        )

    def test_primitive_typen_unveraendert(self):
        """Primitive Typen (str, int, float, bool, None) werden unveraendert zurueckgegeben."""
        assert _safe_serialize("hallo") == "hallo"
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14
        assert _safe_serialize(True) is True
        assert _safe_serialize(None) is None

    def test_objekt_mit_dict_attribut(self):
        """Objekte mit __dict__ werden ueber vars() serialisiert."""
        obj = DummyObjektMitDict(x=10, y="abc")
        ergebnis = _safe_serialize(obj)
        assert ergebnis == {"x": 10, "y": "abc"}, (
            f"Erwartet: dict mit x/y, Erhalten: {ergebnis}"
        )

    def test_nicht_serialisierbares_objekt_gibt_fallback(self):
        """Nicht serialisierbare Objekte ergeben ein Fallback-dict mit _unserializable."""
        obj = NichtSerialisierbaresObjekt()
        ergebnis = _safe_serialize(obj)
        assert ergebnis.get("_unserializable") is True, (
            f"Erwartet: _unserializable=True, Erhalten: {ergebnis}"
        )
        assert "repr" in ergebnis, (
            f"Erwartet: 'repr' Schluessel vorhanden, Erhalten: {ergebnis}"
        )


# =========================================================================
# TestGetExternalBureauManager - Tests fuer get_external_bureau_manager()
# =========================================================================

class TestGetExternalBureauManager:
    """Tests fuer die Lazy-Load Funktion get_external_bureau_manager."""

    def test_import_fehler_gibt_none(self):
        """Bei Import-Fehler wird None zurueckgegeben."""
        # Patch auf Modul-Ebene: Import soll fehlschlagen
        with patch.dict("sys.modules", {"agents.external_bureau_manager": None}):
            bureau_module._external_bureau_manager = None
            from backend.routers.external_bureau import get_external_bureau_manager
            ergebnis = get_external_bureau_manager()
            assert ergebnis is None, (
                f"Erwartet: None bei Import-Fehler, Erhalten: {ergebnis}"
            )

    def test_cached_manager_wird_wiederverwendet(self):
        """Ein bereits geladener Manager wird beim naechsten Aufruf wiederverwendet."""
        mock_bureau = MagicMock()
        bureau_module._external_bureau_manager = mock_bureau
        from backend.routers.external_bureau import get_external_bureau_manager
        ergebnis = get_external_bureau_manager()
        assert ergebnis is mock_bureau, (
            "Erwartet: Gecachter Manager wird zurueckgegeben"
        )


# =========================================================================
# TestStatusEndpoint - Tests fuer GET /external-bureau/status
# =========================================================================

class TestStatusEndpoint:
    """Tests fuer den Status-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_status_ohne_bureau_gibt_disabled(self, mock_get_bureau):
        """Wenn Bureau nicht verfuegbar, wird enabled=False zurueckgegeben."""
        mock_get_bureau.return_value = None
        response = client.get("/external-bureau/status")
        assert response.status_code == 200, (
            f"Erwartet: Status 200, Erhalten: {response.status_code}"
        )
        daten = response.json()
        assert daten["enabled"] is False, (
            f"Erwartet: enabled=False, Erhalten: {daten.get('enabled')}"
        )
        assert "specialists" in daten
        assert daten["specialists"] == []

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_status_mit_bureau_gibt_bureau_status(self, mock_get_bureau):
        """Bei verfuegbarem Bureau wird dessen Status zurueckgegeben."""
        mock_bureau = MagicMock()
        mock_bureau.get_status.return_value = {
            "enabled": True,
            "specialists": ["CodeRabbit", "Semgrep"]
        }
        mock_get_bureau.return_value = mock_bureau
        response = client.get("/external-bureau/status")
        assert response.status_code == 200
        daten = response.json()
        assert daten["enabled"] is True
        assert len(daten["specialists"]) == 2


# =========================================================================
# TestSpecialistsEndpoint - Tests fuer GET /external-bureau/specialists
# =========================================================================

class TestSpecialistsEndpoint:
    """Tests fuer den Specialists-Listen-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_specialists_ohne_bureau(self, mock_get_bureau):
        """Ohne Bureau wird leere Liste mit Fehlermeldung zurueckgegeben."""
        mock_get_bureau.return_value = None
        response = client.get("/external-bureau/specialists")
        assert response.status_code == 200
        daten = response.json()
        assert daten["specialists"] == []
        assert "error" in daten

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_specialists_alle_ohne_filter(self, mock_get_bureau):
        """Ohne category-Filter werden alle Specialists zurueckgegeben."""
        mock_bureau = MagicMock()
        mock_bureau.get_all_specialists.return_value = ["CodeRabbit", "Semgrep", "Context7"]
        mock_get_bureau.return_value = mock_bureau
        response = client.get("/external-bureau/specialists")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 3
        mock_bureau.get_all_specialists.assert_called_once()

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_specialists_mit_category_filter(self, mock_get_bureau):
        """Mit category-Filter wird get_specialists_by_category aufgerufen."""
        mock_bureau = MagicMock()
        mock_bureau.get_specialists_by_category.return_value = ["Semgrep"]
        mock_get_bureau.return_value = mock_bureau
        response = client.get("/external-bureau/specialists?category=combat")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 1
        mock_bureau.get_specialists_by_category.assert_called_once_with("combat")


# =========================================================================
# TestActivateEndpoint - Tests fuer POST .../activate
# =========================================================================

class TestActivateEndpoint:
    """Tests fuer den Specialist-Aktivieren-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_activate_ohne_bureau_gibt_503(self, mock_get_bureau):
        """Ohne Bureau wird HTTPException 503 geworfen."""
        mock_get_bureau.return_value = None
        response = client.post("/external-bureau/specialists/coderabbit/activate")
        assert response.status_code == 503, (
            f"Erwartet: 503, Erhalten: {response.status_code}"
        )

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_activate_erfolgreich(self, mock_get_bureau):
        """Erfolgreiche Aktivierung gibt das Ergebnis zurueck."""
        mock_bureau = MagicMock()
        mock_bureau.activate_specialist.return_value = {"success": True, "message": "Aktiviert"}
        mock_get_bureau.return_value = mock_bureau
        response = client.post("/external-bureau/specialists/semgrep/activate")
        assert response.status_code == 200
        daten = response.json()
        assert daten["success"] is True

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_activate_fehlschlag_gibt_400(self, mock_get_bureau):
        """Fehlgeschlagene Aktivierung gibt HTTPException 400 zurueck."""
        mock_bureau = MagicMock()
        mock_bureau.activate_specialist.return_value = {
            "success": False,
            "message": "Specialist nicht gefunden"
        }
        mock_get_bureau.return_value = mock_bureau
        response = client.post("/external-bureau/specialists/unbekannt/activate")
        assert response.status_code == 400, (
            f"Erwartet: 400, Erhalten: {response.status_code}"
        )
        assert "Specialist nicht gefunden" in response.json()["detail"]


# =========================================================================
# TestDeactivateEndpoint - Tests fuer POST .../deactivate
# =========================================================================

class TestDeactivateEndpoint:
    """Tests fuer den Specialist-Deaktivieren-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_deactivate_ohne_bureau_gibt_503(self, mock_get_bureau):
        """Ohne Bureau wird HTTPException 503 geworfen."""
        mock_get_bureau.return_value = None
        response = client.post("/external-bureau/specialists/coderabbit/deactivate")
        assert response.status_code == 503

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_deactivate_erfolgreich(self, mock_get_bureau):
        """Erfolgreiche Deaktivierung gibt das Ergebnis zurueck."""
        mock_bureau = MagicMock()
        mock_bureau.deactivate_specialist.return_value = {"success": True, "message": "Deaktiviert"}
        mock_get_bureau.return_value = mock_bureau
        response = client.post("/external-bureau/specialists/semgrep/deactivate")
        assert response.status_code == 200
        daten = response.json()
        assert daten["success"] is True

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_deactivate_fehlschlag_gibt_400(self, mock_get_bureau):
        """Fehlgeschlagene Deaktivierung gibt HTTPException 400 zurueck."""
        mock_bureau = MagicMock()
        mock_bureau.deactivate_specialist.return_value = {
            "success": False,
            "message": "Bereits deaktiviert"
        }
        mock_get_bureau.return_value = mock_bureau
        response = client.post("/external-bureau/specialists/semgrep/deactivate")
        assert response.status_code == 400
        assert "Bereits deaktiviert" in response.json()["detail"]


# =========================================================================
# TestFindingsEndpoint - Tests fuer GET /external-bureau/findings
# =========================================================================

class TestFindingsEndpoint:
    """Tests fuer den Findings-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_findings_ohne_bureau(self, mock_get_bureau):
        """Ohne Bureau wird leere Findings-Liste zurueckgegeben."""
        mock_get_bureau.return_value = None
        response = client.get("/external-bureau/findings")
        assert response.status_code == 200
        daten = response.json()
        assert daten["findings"] == []
        assert "error" in daten

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_findings_mit_ergebnissen(self, mock_get_bureau):
        """Vorhandene Findings werden mit count zurueckgegeben."""
        mock_bureau = MagicMock()
        mock_bureau.get_combined_findings.return_value = [
            {"severity": "HIGH", "message": "SQL Injection"},
            {"severity": "LOW", "message": "Unused import"}
        ]
        mock_get_bureau.return_value = mock_bureau
        response = client.get("/external-bureau/findings")
        assert response.status_code == 200
        daten = response.json()
        assert daten["count"] == 2
        assert len(daten["findings"]) == 2


# =========================================================================
# TestSearchEndpoint - Tests fuer POST /external-bureau/search
# =========================================================================

class TestSearchEndpoint:
    """Tests fuer den EXA-Search-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_search_ohne_bureau_gibt_503(self, mock_get_bureau):
        """Ohne Bureau wird HTTPException 503 geworfen."""
        mock_get_bureau.return_value = None
        response = client.post(
            "/external-bureau/search",
            json={"query": "FastAPI best practices", "num_results": 5}
        )
        assert response.status_code == 503

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_search_erfolgreich(self, mock_get_bureau):
        """Erfolgreiche Suche gibt serialisierte Ergebnisse zurueck."""
        mock_bureau = MagicMock()
        such_ergebnis = DummySearchResult(
            success=True,
            findings=[{"titel": "Treffer 1"}],
            summary="1 Ergebnis gefunden",
            duration_ms=150,
            error=None
        )
        # run_search ist async, daher AsyncMock verwenden
        mock_bureau.run_search = AsyncMock(return_value=such_ergebnis)
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/search",
            json={"query": "React hooks", "num_results": 3}
        )
        assert response.status_code == 200
        daten = response.json()
        assert daten["success"] is True
        assert daten["summary"] == "1 Ergebnis gefunden"
        assert daten["duration_ms"] == 150

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_search_nicht_verfuegbar_gibt_400(self, mock_get_bureau):
        """Wenn run_search None zurueckgibt, wird 400 geworfen."""
        mock_bureau = MagicMock()
        mock_bureau.run_search = AsyncMock(return_value=None)
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/search",
            json={"query": "test", "num_results": 1}
        )
        assert response.status_code == 400
        assert "nicht verfuegbar" in response.json()["detail"]

    def test_search_ohne_query_gibt_422(self):
        """Fehlende query im Request-Body ergibt Validierungsfehler 422."""
        response = client.post(
            "/external-bureau/search",
            json={"num_results": 5}
        )
        assert response.status_code == 422, (
            f"Erwartet: 422 (Validierungsfehler), Erhalten: {response.status_code}"
        )

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_search_mit_findings_serialisiert(self, mock_get_bureau):
        """Findings in Search-Ergebnis werden ueber _safe_serialize verarbeitet."""
        mock_bureau = MagicMock()
        finding_obj = DummyFinding(severity="MEDIUM", message="Auffaelligkeit")
        such_ergebnis = DummySearchResult(
            success=True,
            findings=[finding_obj],
            summary="Ergebnis",
            duration_ms=80,
            error=None
        )
        mock_bureau.run_search = AsyncMock(return_value=such_ergebnis)
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/search",
            json={"query": "Sicherheit", "num_results": 1}
        )
        assert response.status_code == 200
        daten = response.json()
        # _safe_serialize wandelt DummyFinding ueber __dict__/vars() um
        assert len(daten["findings"]) == 1
        assert daten["findings"][0]["severity"] == "MEDIUM"


# =========================================================================
# TestReviewEndpoint - Tests fuer POST /external-bureau/review
# =========================================================================

class TestReviewEndpoint:
    """Tests fuer den Review-Endpunkt."""

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_ohne_bureau_gibt_503(self, mock_get_bureau):
        """Ohne Bureau wird HTTPException 503 geworfen."""
        mock_get_bureau.return_value = None
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "/tmp/test"}
        )
        assert response.status_code == 503

    @patch("backend.routers.external_bureau.os.path.isdir", return_value=True)
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_erfolgreich(self, mock_get_bureau, mock_isdir):
        """Erfolgreicher Review gibt Ergebnis-Liste zurueck."""
        mock_bureau = MagicMock()
        review_result = DummyReviewResult(
            success=True,
            findings=[{"type": "bug"}],
            summary="1 Problem gefunden",
            duration_ms=500,
            error=None
        )
        mock_bureau.run_review_specialists = AsyncMock(return_value=[review_result])
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "/tmp/test_projekt", "files": ["main.py"]}
        )
        assert response.status_code == 200
        daten = response.json()
        assert daten["total_findings"] == 1
        assert len(daten["results"]) == 1
        assert daten["results"][0]["success"] is True

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_mit_punkt_pfad_gibt_400(self, mock_get_bureau):
        """project_path='.' wird abgelehnt mit 400."""
        mock_bureau = MagicMock()
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "."}
        )
        assert response.status_code == 400
        assert "project_path" in response.json()["detail"]

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_mit_punkt_slash_pfad_gibt_400(self, mock_get_bureau):
        """project_path='./' wird ebenfalls abgelehnt mit 400."""
        mock_bureau = MagicMock()
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "./"}
        )
        assert response.status_code == 400

    @patch("backend.routers.external_bureau.manager")
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_ohne_project_path_nutzt_fallback(self, mock_get_bureau, mock_manager):
        """Ohne project_path wird manager.project_path als Fallback genutzt."""
        mock_manager.project_path = None
        mock_bureau = MagicMock()
        mock_get_bureau.return_value = mock_bureau
        # Kein project_path und kein Fallback → Fehler
        response = client.post(
            "/external-bureau/review",
            json={}
        )
        assert response.status_code == 400
        assert "project_path" in response.json()["detail"]

    @patch("backend.routers.external_bureau.os.path.isdir", return_value=False)
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_nicht_existierendes_verzeichnis_gibt_400(self, mock_get_bureau, mock_isdir):
        """Nicht existierendes Verzeichnis als project_path gibt 400."""
        mock_bureau = MagicMock()
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "/nicht/existierend/pfad"}
        )
        assert response.status_code == 400
        assert "existiert nicht" in response.json()["detail"]

    @patch("backend.routers.external_bureau.os.path.isdir", return_value=True)
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_mehrere_results(self, mock_get_bureau, mock_isdir):
        """Mehrere Review-Ergebnisse werden korrekt aggregiert."""
        mock_bureau = MagicMock()
        result_1 = DummyReviewResult(
            success=True,
            findings=[{"type": "bug"}, {"type": "smell"}],
            summary="CodeRabbit",
            duration_ms=300,
            error=None
        )
        result_2 = DummyReviewResult(
            success=True,
            findings=[{"type": "vuln"}],
            summary="Semgrep",
            duration_ms=200,
            error=None
        )
        mock_bureau.run_review_specialists = AsyncMock(return_value=[result_1, result_2])
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "/tmp/projekt", "files": ["app.py"]}
        )
        assert response.status_code == 200
        daten = response.json()
        assert daten["total_findings"] == 3, (
            f"Erwartet: 3 Gesamt-Findings (2+1), Erhalten: {daten['total_findings']}"
        )
        assert len(daten["results"]) == 2

    @patch("backend.routers.external_bureau.os.path.isdir", return_value=True)
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_ohne_files_nutzt_leere_liste(self, mock_get_bureau, mock_isdir):
        """Wenn files nicht angegeben, wird leere Liste verwendet."""
        mock_bureau = MagicMock()
        mock_bureau.run_review_specialists = AsyncMock(return_value=[])
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": "/tmp/test"}
        )
        assert response.status_code == 200
        # Pruefen dass run_review_specialists mit leerer files-Liste aufgerufen wurde
        aufruf_args = mock_bureau.run_review_specialists.call_args
        context = aufruf_args[0][0]
        assert context["files"] == [], (
            f"Erwartet: leere files-Liste, Erhalten: {context['files']}"
        )

    @patch("backend.routers.external_bureau.manager")
    @patch("backend.routers.external_bureau.os.path.isdir", return_value=True)
    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_fallback_auf_manager_project_path(self, mock_get_bureau, mock_isdir, mock_manager):
        """Wenn request.project_path leer, wird manager.project_path genutzt."""
        mock_manager.project_path = "/fallback/pfad"
        mock_bureau = MagicMock()
        mock_bureau.run_review_specialists = AsyncMock(return_value=[])
        mock_get_bureau.return_value = mock_bureau
        response = client.post(
            "/external-bureau/review",
            json={"project_path": None}
        )
        assert response.status_code == 200
        aufruf_args = mock_bureau.run_review_specialists.call_args
        context = aufruf_args[0][0]
        assert context["project_path"] == "/fallback/pfad", (
            f"Erwartet: /fallback/pfad als Fallback, Erhalten: {context['project_path']}"
        )

    @patch("backend.routers.external_bureau.get_external_bureau_manager")
    def test_review_leerer_string_als_pfad_gibt_400(self, mock_get_bureau):
        """Leerer String als project_path wird abgelehnt."""
        mock_bureau = MagicMock()
        mock_get_bureau.return_value = mock_bureau
        # Patch manager.project_path auf None damit kein Fallback greift
        with patch("backend.routers.external_bureau.manager") as mock_manager:
            mock_manager.project_path = ""
            response = client.post(
                "/external-bureau/review",
                json={"project_path": "   "}
            )
        assert response.status_code == 400
