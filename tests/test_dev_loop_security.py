# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Tests fuer run_security_rescan aus backend/dev_loop_security.py.
              Alle externen Abhaengigkeiten (CrewAI, agent_factory, orchestration_helpers,
              heartbeat_utils) werden vollstaendig gemockt.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call


@pytest.fixture
def mock_manager():
    """Erstellt einen Mock-Manager mit allen benoetigten Attributen."""
    m = MagicMock()
    m.config = {
        "agent_timeouts": {"security": 300}
    }
    m.agent_security = True
    m.model_router = MagicMock()
    m.model_router.get_model.return_value = "test-model"
    m.project_path = None
    m.security_vulnerabilities = []
    m.tech_blueprint = {"framework": "nextjs"}
    return m


@pytest.fixture
def sample_project_rules():
    """Beispielhafte Projektregeln fuer Tests."""
    return {"name": "Test-Projekt", "rules": ["Regel 1"]}


@pytest.fixture
def sample_current_code():
    """Beispielhafter generierter Code fuer Security-Scans."""
    return "const app = express();\napp.listen(3000);"


# Basis-Patch-Pfade fuer alle externen Abhaengigkeiten
PATCH_INIT_AGENTS = "backend.dev_loop_security.init_agents"
PATCH_TASK = "backend.dev_loop_security.Task"
PATCH_RUN_WITH_HEARTBEAT = "backend.dev_loop_security.run_with_heartbeat"
PATCH_EXTRACT_VULNS = "backend.dev_loop_security.extract_vulnerabilities"
PATCH_IS_RATE_LIMIT = "backend.dev_loop_security.is_rate_limit_error"
PATCH_IS_MODEL_UNAVAIL = "backend.dev_loop_security.is_model_unavailable_error"
PATCH_IS_EMPTY_RESPONSE = "backend.dev_loop_security.is_empty_response_error"


class TestRunSecurityRescan:
    """Tests fuer run_security_rescan - vollstaendig gemockte Abhaengigkeiten."""

    # --- Skip-Faelle: Kein Scan noetig ---

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_kein_agent_security_gibt_skip_zurueck(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules
    ):
        """Wenn agent_security None/False ist, wird der Scan uebersprungen."""
        from backend.dev_loop_security import run_security_rescan

        mock_manager.agent_security = None
        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, "some code", iteration=0
        )

        assert passed is True, \
            "Erwartet: True, Erhalten: False - ohne agent_security soll skip (True, []) zurueckgegeben werden"
        assert vulns == [], \
            "Erwartet: leere Liste, Erhalten: nicht-leere Liste - ohne agent_security keine Vulnerabilities"
        # init_agents darf NICHT aufgerufen worden sein
        mock_init.assert_not_called()

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_leerer_current_code_gibt_skip_zurueck(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules
    ):
        """Wenn current_code leer ist, wird der Scan uebersprungen."""
        from backend.dev_loop_security import run_security_rescan

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, "", iteration=0
        )

        assert passed is True, \
            "Erwartet: True - leerer Code soll skip zurueckgeben"
        assert vulns == [], \
            "Erwartet: leere Liste - leerer Code ergibt keine Vulnerabilities"
        mock_init.assert_not_called()

    # --- Erfolgreiche Scans ---

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_erfolg_secure_keine_vulns(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """SECURE-Ergebnis: Keine Vulnerabilities gefunden → passed=True."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - SECURE Ergebnis soll passed=True ergeben"
        assert vulns == [], \
            "Erwartet: leere Liste - SECURE ergibt keine Vulnerabilities"

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="VULNERABILITY: ...")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_erfolg_mit_low_severity_vulns(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Alle Vulnerabilities mit severity=low → passed=True (nicht blockierend)."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        low_vulns = [
            {"severity": "low", "description": "Kleines Problem 1"},
            {"severity": "low", "description": "Kleines Problem 2"},
        ]
        mock_extract.return_value = low_vulns

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - nur LOW-Severity soll als passed gelten"
        assert vulns == low_vulns, \
            "Erwartet: Low-Vulns zurueckgegeben, Erhalten: andere Liste"

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="VULNERABILITY: ...")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_fehler_mit_high_severity_vulns(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """HIGH-Severity-Vulnerabilities → passed=False (blockierend)."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        high_vulns = [
            {"severity": "high", "description": "XSS in UserForm"},
            {"severity": "low", "description": "Kleines Problem"},
        ]
        mock_extract.return_value = high_vulns

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is False, \
            "Erwartet: False - HIGH-Severity soll als nicht-bestanden gelten"
        assert vulns == high_vulns, \
            "Erwartet: High-Vulns zurueckgegeben"

    # --- Retry-Logik ---

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=False)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=False)
    @patch(PATCH_IS_RATE_LIMIT, return_value=True)
    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_rate_limit_retry_dann_erfolg(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Rate-Limit beim ersten Versuch → Retry → zweiter Versuch gelingt."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        # Erster Aufruf wirft Exception, zweiter liefert Ergebnis
        mock_heartbeat.side_effect = [
            Exception("Rate limit exceeded"),
            "SECURE"
        ]
        # is_rate_limit_error nur beim ersten Aufruf True, danach irrelevant
        mock_is_rate.side_effect = [True, True]

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - nach Retry sollte SECURE zurueckgegeben werden"
        assert mock_heartbeat.call_count == 2, \
            "Erwartet: 2 Aufrufe (1 Fehler + 1 Erfolg)"
        # mark_rate_limited_sync muss beim Fehler aufgerufen werden
        mock_manager.model_router.mark_rate_limited_sync.assert_called_once_with("test-model")

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=False)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=False)
    @patch(PATCH_IS_RATE_LIMIT, return_value=True)
    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, side_effect=Exception("Rate limit"))
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_alle_retries_fehlgeschlagen(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Alle 3 Retry-Versuche fehlgeschlagen → passed=False, leere Liste."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is False, \
            "Erwartet: False - alle Retries fehlgeschlagen, Fail-Closed"
        assert vulns == [], \
            "Erwartet: leere Liste - kein Scan erfolgreich"
        assert mock_heartbeat.call_count == 3, \
            "Erwartet: 3 Versuche (MAX_SECURITY_RETRIES)"

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=False)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=True)
    @patch(PATCH_IS_RATE_LIMIT, return_value=False)
    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_model_unavailable_retry(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Model-Unavailable (404) beim ersten Versuch → Retry mit Fallback-Modell."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_heartbeat.side_effect = [
            Exception("Model not found"),
            "SECURE"
        ]

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - nach Retry mit Fallback-Modell sollte SECURE zurueckgegeben werden"
        assert mock_heartbeat.call_count == 2, \
            "Erwartet: 2 Aufrufe (1 Fehler + 1 Erfolg)"

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=True)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=False)
    @patch(PATCH_IS_RATE_LIMIT, return_value=False)
    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_empty_response_retry(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Leere Antwort vom Modell → Retry."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_heartbeat.side_effect = [
            Exception("Empty response"),
            "SECURE"
        ]

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - nach Retry bei leerer Antwort sollte SECURE zurueckgegeben werden"
        assert mock_heartbeat.call_count == 2, \
            "Erwartet: 2 Aufrufe (1 Fehler + 1 Erfolg)"

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=False)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=False)
    @patch(PATCH_IS_RATE_LIMIT, return_value=False)
    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, side_effect=Exception("Unbekannter Fehler"))
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_nicht_retriable_exception_sofort_abbruch(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Exception die NICHT rate_limit/unavailable/empty ist → sofortiger Abbruch (kein Retry)."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is False, \
            "Erwartet: False - nicht-retriable Exception fuehrt zu Fail-Closed"
        assert mock_heartbeat.call_count == 1, \
            "Erwartet: 1 Aufruf - bei nicht-retriable Exception kein Retry"

    # --- Timeout-Konfiguration ---

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_timeout_aus_config(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Timeout-Wert aus config.agent_timeouts.security wird an run_with_heartbeat uebergeben."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_manager.config = {"agent_timeouts": {"security": 500}}

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        # Pruefe dass timeout_seconds=500 uebergeben wurde
        heartbeat_kwargs = mock_heartbeat.call_args
        assert heartbeat_kwargs[1]["timeout_seconds"] == 500, \
            "Erwartet: timeout_seconds=500 aus Config, Erhalten: anderer Wert"

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_default_timeout_ohne_config(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Ohne agent_timeouts in config → Default-Timeout 300 Sekunden."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_manager.config = {}  # Kein agent_timeouts key

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        heartbeat_kwargs = mock_heartbeat.call_args
        assert heartbeat_kwargs[1]["timeout_seconds"] == 300, \
            "Erwartet: timeout_seconds=300 (Default), Erhalten: anderer Wert"

    # --- Manager-Zustand nach Scan ---

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="VULNERABILITY: ...")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_security_vulnerabilities_auf_manager_gesetzt(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Nach erfolgreichem Scan wird manager.security_vulnerabilities aktualisiert."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        found_vulns = [
            {"severity": "high", "description": "SQL Injection"},
            {"severity": "low", "description": "Info Disclosure"},
        ]
        mock_extract.return_value = found_vulns

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert mock_manager.security_vulnerabilities == found_vulns, \
            "Erwartet: manager.security_vulnerabilities soll auf gefundene Vulns gesetzt werden"

    # --- UI-Logging ---

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_ui_log_rescan_start_wird_aufgerufen(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """_ui_log wird mit 'RescanStart' aufgerufen bei Scanbeginn."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=2
        )

        # Pruefe dass RescanStart mit korrekter Iteration geloggt wird
        ui_log_calls = mock_manager._ui_log.call_args_list
        rescan_start_calls = [
            c for c in ui_log_calls
            if c[0][0] == "Security" and c[0][1] == "RescanStart"
        ]
        assert len(rescan_start_calls) >= 1, \
            "Erwartet: mindestens ein _ui_log('Security', 'RescanStart', ...) Aufruf"
        # Iteration+1 = 3 muss im Log-Text erscheinen
        assert "3" in rescan_start_calls[0][0][2], \
            "Erwartet: Iteration 3 (iteration+1) im RescanStart-Text"

    # --- init_agents Parameter ---

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_init_agents_mit_korrekten_parametern(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """init_agents wird mit include=['security'] und tech_blueprint aufgerufen."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        mock_init.assert_called_once_with(
            mock_manager.config,
            sample_project_rules,
            router=mock_manager.model_router,
            include=["security"],
            tech_blueprint=mock_manager.tech_blueprint
        )

    # --- Zusaetzliche Edge Cases ---

    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="VULNERABILITY: ...")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_gemischte_severity_mit_critical(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """CRITICAL-Severity zwischen LOW-Vulns → passed=False."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mixed_vulns = [
            {"severity": "low", "description": "Info Leak"},
            {"severity": "critical", "description": "SQL Injection"},
            {"severity": "low", "description": "Veraltete Header"},
        ]
        mock_extract.return_value = mixed_vulns

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is False, \
            "Erwartet: False - CRITICAL zwischen LOW macht den Scan nicht-bestanden"
        assert len(vulns) == 3, \
            "Erwartet: alle 3 Vulns zurueckgegeben"

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_update_worker_status_aufgerufen(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """_update_worker_status wird mit 'working' und 'idle' aufgerufen."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        # Pruefe dass working-Status mit Modell gesetzt wird
        worker_calls = mock_manager._update_worker_status.call_args_list
        working_calls = [c for c in worker_calls if c[0][1] == "working"]
        idle_calls = [c for c in worker_calls if c[0][1] == "idle"]

        assert len(working_calls) >= 1, \
            "Erwartet: mindestens ein _update_worker_status('security', 'working', ...) Aufruf"
        assert len(idle_calls) >= 1, \
            "Erwartet: mindestens ein _update_worker_status('security', 'idle') Aufruf"
        # Working-Aufruf muss Modellname als 4. Argument haben
        assert working_calls[0][0][3] == "test-model", \
            "Erwartet: Modellname 'test-model' im worker_status, Erhalten: anderer Wert"

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_model_router_none_fallback(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Wenn model_router None ist, wird 'unknown' als Modellname verwendet."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_manager.model_router = None

        passed, vulns = run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        assert passed is True, \
            "Erwartet: True - Scan soll auch ohne model_router funktionieren"

    @patch(PATCH_IS_EMPTY_RESPONSE, return_value=False)
    @patch(PATCH_IS_MODEL_UNAVAIL, return_value=False)
    @patch(PATCH_IS_RATE_LIMIT, return_value=True)
    @patch(PATCH_EXTRACT_VULNS)
    @patch(PATCH_RUN_WITH_HEARTBEAT)
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_fallback_info_log_bei_retry(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_is_rate, mock_is_unavail, mock_is_empty,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """Bei Retry nach Rate-Limit wird 'Wechsle zu Fallback-Modell...' geloggt."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}
        mock_heartbeat.side_effect = [
            Exception("Rate limit"),
            "SECURE"
        ]
        mock_extract.return_value = []

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=0
        )

        # Pruefe dass Info-Log fuer Fallback-Wechsel vorhanden ist
        ui_log_calls = mock_manager._ui_log.call_args_list
        fallback_calls = [
            c for c in ui_log_calls
            if len(c[0]) >= 3 and "Fallback" in str(c[0][2])
        ]
        assert len(fallback_calls) >= 1, \
            "Erwartet: mindestens ein Log-Eintrag mit 'Fallback-Modell'"

    @patch(PATCH_EXTRACT_VULNS, return_value=[])
    @patch(PATCH_RUN_WITH_HEARTBEAT, return_value="SECURE")
    @patch(PATCH_TASK)
    @patch(PATCH_INIT_AGENTS)
    def test_security_rescan_output_json_log(
        self, mock_init, mock_task, mock_heartbeat, mock_extract,
        mock_manager, sample_project_rules, sample_current_code
    ):
        """SecurityRescanOutput wird als gueltige JSON-Struktur geloggt."""
        from backend.dev_loop_security import run_security_rescan

        mock_init.return_value = {"security": MagicMock()}

        run_security_rescan(
            mock_manager, sample_project_rules, sample_current_code, iteration=1
        )

        # Finde den SecurityRescanOutput-Aufruf
        ui_log_calls = mock_manager._ui_log.call_args_list
        output_calls = [
            c for c in ui_log_calls
            if c[0][1] == "SecurityRescanOutput"
        ]
        assert len(output_calls) == 1, \
            "Erwartet: genau ein SecurityRescanOutput-Log"

        # JSON muss parsebar sein
        json_str = output_calls[0][0][2]
        parsed = json.loads(json_str)
        assert parsed["overall_status"] == "SECURE", \
            "Erwartet: overall_status=SECURE"
        assert parsed["iteration"] == 2, \
            "Erwartet: iteration=2 (iteration+1)"
        assert parsed["model"] == "test-model", \
            "Erwartet: model=test-model"
        assert "timestamp" in parsed, \
            "Erwartet: timestamp-Feld im JSON"
