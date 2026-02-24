# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 14.02.2026
Version: 1.0
Beschreibung: Unit-Tests fuer backend/session_manager.py.
              Testet den SessionManager-Singleton mit allen Methoden:
              Session-Lifecycle, Agent-Blocking (HELP_NEEDED), Logging,
              Discovery-Briefing, State-Recovery und Thread-Safety.
"""
# ÄNDERUNG 22.02.2026: DUMMY-WERT-Markierung und Fehlerbehandlung für Start-Session-Tests ergänzt.
# Ziel: Testfehler schneller diagnostizierbar machen.

import os
import sys
import json
import threading
import logging
import pytest

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.session_manager import SessionManager, get_session_manager


# =========================================================================
# Singleton-Reset Fixture
# =========================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """Setzt den SessionManager-Singleton vor jedem Test zurueck."""
    SessionManager._instance = None
    yield
    SessionManager._instance = None


# =========================================================================
# TestSingleton - Singleton-Verhalten
# =========================================================================

class TestSingleton:
    """Tests fuer das Singleton-Pattern des SessionManagers."""

    def test_singleton_liefert_gleiche_instanz(self):
        """Zwei Aufrufe von SessionManager() liefern dieselbe Instanz."""
        sm1 = SessionManager()
        sm2 = SessionManager()
        assert sm1 is sm2, (
            f"Erwartet identische Instanz, erhalten: {id(sm1)} vs {id(sm2)}"
        )

    def test_get_session_manager_liefert_singleton(self):
        """get_session_manager() gibt die Singleton-Instanz zurueck."""
        sm1 = get_session_manager()
        sm2 = get_session_manager()
        assert sm1 is sm2, (
            "Erwartet identische Instanz via get_session_manager()"
        )

    def test_singleton_reset_erzeugt_neue_instanz(self):
        """Nach _instance=None wird eine neue Instanz erzeugt."""
        sm1 = SessionManager()
        alte_id = id(sm1)
        SessionManager._instance = None
        sm2 = SessionManager()
        assert id(sm2) != alte_id, (
            "Erwartet neue Instanz nach Singleton-Reset"
        )

    def test_init_wird_nur_einmal_ausgefuehrt(self):
        """__init__ laeuft nur einmal dank _initialized Flag."""
        sm = SessionManager()
        sm.current_session["goal"] = "Mein Ziel"
        sm2 = SessionManager()
        assert sm2.current_session["goal"] == "Mein Ziel", (
            "Erwartet dass __init__ den State nicht zuruecksetzt"
        )


# =========================================================================
# TestSessionLifecycle - Session starten, beenden, Status
# =========================================================================

class TestSessionLifecycle:
    """Tests fuer Session-Start, -Ende und Status-Updates."""
    # Hinweis: Fehlerpfade fuer start_session/add_log werden in separaten Lifecycle/Thread-Safety-Tests abgedeckt.

    def test_start_session_setzt_working_status(self):
        """start_session() setzt Status auf 'Working'."""
        try:
            sm = SessionManager()
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            result = sm.start_session("Testprojekt bauen")
            assert result["status"] == "Working", (
                f"Erwartet Status 'Working', erhalten: {result['status']}"
            )
        except Exception as e:
            logging.error("Fehler in test_start_session_setzt_working_status: %s", e)
            raise

    def test_start_session_mit_project_id(self):
        """start_session() uebernimmt gegebene project_id."""
        try:
            sm = SessionManager()
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            result = sm.start_session("Ziel", project_id="mein_projekt_42")
            assert result["project_id"] == "mein_projekt_42", (
                f"Erwartet 'mein_projekt_42', erhalten: {result['project_id']}"
            )
        except Exception as e:
            logging.error("Fehler in test_start_session_mit_project_id: %s", e)
            raise

    def test_start_session_auto_project_id(self):
        """start_session() generiert project_id wenn keine gegeben."""
        try:
            sm = SessionManager()
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            result = sm.start_session("Ziel")
            assert result["project_id"].startswith("proj_"), (
                f"Erwartet 'proj_'-Prefix, erhalten: {result['project_id']}"
            )
        except Exception as e:
            logging.error("Fehler in test_start_session_auto_project_id: %s", e)
            raise

    def test_start_session_leert_logs(self):
        """start_session() leert vorherige Logs und erstellt SessionStart-Log."""
        try:
            sm = SessionManager()
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            sm.add_log("test", "event", "alter Log")
            # DUMMY-WERT: Nur für Tests - NICHT produktiv verwenden!
            sm.start_session("Neues Ziel")
            logs, total = sm.get_logs()
            assert total == 1, (
                f"Erwartet 1 Log (SessionStart), erhalten: {total}"
            )
            assert logs[0]["event"] == "SessionStart", (
                f"Erwartet 'SessionStart', erhalten: {logs[0]['event']}"
            )
        except Exception as e:
            logging.error("Fehler in test_start_session_leert_logs: %s", e)
            raise

    def test_start_session_setzt_agent_snapshots_zurueck(self):
        """start_session() leert alle Agent-Snapshots."""
        sm = SessionManager()
        sm.agent_snapshots["coder"] = {"status": "aktiv"}
        sm.start_session("Reset-Test")
        assert sm.agent_snapshots["coder"] == {}, (
            "Erwartet leeren Coder-Snapshot nach start_session()"
        )

    def test_end_session_setzt_status(self):
        """end_session() setzt den gewuenschten Endstatus."""
        sm = SessionManager()
        sm.start_session("Test")
        result = sm.end_session("Error")
        assert result["status"] == "Error", (
            f"Erwartet 'Error', erhalten: {result['status']}"
        )

    def test_end_session_setzt_ended_at(self):
        """end_session() fuegt ended_at Zeitstempel hinzu."""
        sm = SessionManager()
        sm.start_session("Test")
        result = sm.end_session("Success")
        assert "ended_at" in result, (
            "Erwartet 'ended_at' Feld nach end_session()"
        )

    def test_end_session_default_success(self):
        """end_session() verwendet 'Success' als Default-Status."""
        sm = SessionManager()
        sm.start_session("Test")
        result = sm.end_session()
        assert result["status"] == "Success", (
            f"Erwartet 'Success' als Default, erhalten: {result['status']}"
        )

    def test_update_status(self):
        """update_status() aendert den Session-Status."""
        sm = SessionManager()
        sm.update_status("Error")
        assert sm.current_session["status"] == "Error", (
            f"Erwartet 'Error', erhalten: {sm.current_session['status']}"
        )

    def test_update_iteration(self):
        """update_iteration() aendert die aktuelle Iteration."""
        sm = SessionManager()
        sm.update_iteration(5)
        assert sm.current_session["iteration"] == 5, (
            f"Erwartet Iteration 5, erhalten: {sm.current_session['iteration']}"
        )

    def test_is_active_bei_working(self):
        """is_active() gibt True zurueck wenn Status 'Working'."""
        sm = SessionManager()
        sm.start_session("Test")
        assert sm.is_active() is True, (
            "Erwartet is_active()=True bei Status 'Working'"
        )

    def test_is_active_bei_idle(self):
        """is_active() gibt False zurueck bei Status 'Idle'."""
        sm = SessionManager()
        assert sm.is_active() is False, (
            "Erwartet is_active()=False bei Status 'Idle'"
        )

    def test_set_agent_active(self):
        """set_agent_active() setzt Agent aktiv/inaktiv."""
        sm = SessionManager()
        sm.set_agent_active("coder", True)
        assert sm.current_session["active_agents"]["coder"] is True, (
            "Erwartet coder als aktiv"
        )
        sm.set_agent_active("coder", False)
        assert sm.current_session["active_agents"]["coder"] is False, (
            "Erwartet coder als inaktiv"
        )

    def test_reset_setzt_alles_zurueck(self):
        """reset() stellt den Ausgangszustand wieder her."""
        sm = SessionManager()
        sm.start_session("Test")
        sm.set_discovery_briefing({"goal": "Test"})
        sm.add_log("coder", "event", "nachricht")
        sm.reset()
        assert sm.current_session["status"] == "Idle", (
            "Erwartet Status 'Idle' nach reset()"
        )
        assert sm.current_session["project_id"] is None, (
            "Erwartet project_id=None nach reset()"
        )
        assert sm.discovery_briefing is None, (
            "Erwartet discovery_briefing=None nach reset()"
        )
        _, total = sm.get_logs()
        assert total == 0, (
            f"Erwartet 0 Logs nach reset(), erhalten: {total}"
        )


# =========================================================================
# TestAgentBlocking - HELP_NEEDED / Blockierung
# =========================================================================

class TestAgentBlocking:
    """Tests fuer Agent-Blockade (HELP_NEEDED) Funktionalitaet."""

    def test_set_agent_blocked(self):
        """set_agent_blocked() markiert Agent als blockiert."""
        sm = SessionManager()
        reason = json.dumps({"action_required": "Hilfe bei DB"})
        sm.set_agent_blocked("security", True, reason)
        snapshot = sm.agent_snapshots["security"]
        assert snapshot["blocked"] is True, (
            "Erwartet blocked=True fuer security Agent"
        )
        assert snapshot["blocked_reason"] == reason, (
            "Erwartet gespeicherten Reason-String"
        )
        assert snapshot["blocked_at"] is not None, (
            "Erwartet blocked_at Zeitstempel"
        )

    def test_set_agent_blocked_false_leert_reason(self):
        """set_agent_blocked(is_blocked=False) leert den Grund."""
        sm = SessionManager()
        sm.set_agent_blocked("coder", True, "Problem")
        sm.set_agent_blocked("coder", False)
        snapshot = sm.agent_snapshots["coder"]
        assert snapshot["blocked"] is False, (
            "Erwartet blocked=False nach Aufhebung"
        )
        assert snapshot["blocked_reason"] == "", (
            "Erwartet leeren Grund nach Aufhebung"
        )
        assert snapshot["blocked_at"] is None, (
            "Erwartet blocked_at=None nach Aufhebung"
        )

    def test_set_agent_blocked_unbekannter_agent(self):
        """set_agent_blocked() initialisiert unbekannte Agents automatisch."""
        sm = SessionManager()
        sm.set_agent_blocked("neuer_agent", True, "Blockiert")
        assert "neuer_agent" in sm.agent_snapshots, (
            "Erwartet neuer_agent in agent_snapshots"
        )
        assert sm.agent_snapshots["neuer_agent"]["blocked"] is True, (
            "Erwartet blocked=True fuer neuen Agent"
        )

    def test_set_agent_blocked_erzeugt_help_needed_log(self):
        """set_agent_blocked(True) erzeugt einen HELP_NEEDED Log."""
        sm = SessionManager()
        sm.set_agent_blocked("reviewer", True, "Brauche Hilfe")
        logs, _ = sm.get_logs()
        help_logs = [l for l in logs if l["event"] == "HELP_NEEDED"]
        assert len(help_logs) == 1, (
            f"Erwartet 1 HELP_NEEDED Log, erhalten: {len(help_logs)}"
        )

    def test_get_blocked_agents_leer(self):
        """get_blocked_agents() gibt leeres Dict wenn nichts blockiert."""
        sm = SessionManager()
        blocked = sm.get_blocked_agents()
        assert blocked == {}, (
            f"Erwartet leeres Dict, erhalten: {blocked}"
        )

    def test_get_blocked_agents_mit_blockierten(self):
        """get_blocked_agents() gibt nur blockierte Agents zurueck."""
        sm = SessionManager()
        sm.set_agent_blocked("security", True, '{"priority": "high"}')
        sm.set_agent_blocked("coder", False)
        blocked = sm.get_blocked_agents()
        assert "security" in blocked, (
            "Erwartet 'security' in blockierten Agents"
        )
        assert "coder" not in blocked, (
            "Erwartet 'coder' NICHT in blockierten Agents"
        )

    def test_clear_agent_blocked(self):
        """clear_agent_blocked() hebt Blockade auf."""
        sm = SessionManager()
        sm.set_agent_blocked("tester", True, "Blockiert")
        sm.clear_agent_blocked("tester")
        snapshot = sm.agent_snapshots["tester"]
        assert snapshot["blocked"] is False, (
            "Erwartet blocked=False nach clear"
        )

    def test_clear_agent_blocked_erzeugt_help_resolved_log(self):
        """clear_agent_blocked() erzeugt HELP_RESOLVED Log."""
        sm = SessionManager()
        sm.set_agent_blocked("tester", True, "Problem")
        sm.clear_agent_blocked("tester")
        logs, _ = sm.get_logs()
        resolved_logs = [l for l in logs if l["event"] == "HELP_RESOLVED"]
        assert len(resolved_logs) == 1, (
            f"Erwartet 1 HELP_RESOLVED Log, erhalten: {len(resolved_logs)}"
        )

    def test_clear_agent_blocked_unbekannter_agent(self):
        """clear_agent_blocked() bei unbekanntem Agent wirft keinen Fehler."""
        sm = SessionManager()
        # Sollte keinen Fehler werfen
        sm.clear_agent_blocked("unbekannt")


# =========================================================================
# TestExtractPriority - Priority-Extraktion aus JSON
# =========================================================================

class TestExtractPriority:
    """Tests fuer _extract_priority() mit verschiedenen Eingaben."""

    def test_priority_aus_gueltigem_json(self):
        """_extract_priority() liest 'priority' direkt aus JSON."""
        sm = SessionManager()
        reason = json.dumps({"priority": "critical"})
        assert sm._extract_priority(reason) == "critical", (
            "Erwartet 'critical' aus JSON-Feld"
        )

    def test_priority_ableitung_aus_action_security(self):
        """_extract_priority() leitet 'high' ab bei security in action_required."""
        sm = SessionManager()
        reason = json.dumps({"action_required": "Security-Check noetig"})
        assert sm._extract_priority(reason) == "high", (
            "Erwartet 'high' bei security in action_required"
        )

    def test_priority_ableitung_aus_action_critical(self):
        """_extract_priority() leitet 'high' ab bei critical in action_required."""
        sm = SessionManager()
        reason = json.dumps({"action_required": "Critical Bug gefunden"})
        assert sm._extract_priority(reason) == "high", (
            "Erwartet 'high' bei critical in action_required"
        )

    def test_priority_default_normal(self):
        """_extract_priority() gibt 'normal' als Default zurueck."""
        sm = SessionManager()
        reason = json.dumps({"action_required": "Code ueberarbeiten"})
        assert sm._extract_priority(reason) == "normal", (
            "Erwartet 'normal' als Default-Priority"
        )

    def test_priority_bei_ungueltigem_json(self):
        """_extract_priority() gibt 'normal' bei ungueltigem JSON zurueck."""
        sm = SessionManager()
        assert sm._extract_priority("kein json {{{") == "normal", (
            "Erwartet 'normal' bei ungueltigem JSON"
        )

    def test_priority_bei_none(self):
        """_extract_priority() gibt 'normal' bei None zurueck."""
        sm = SessionManager()
        assert sm._extract_priority(None) == "normal", (
            "Erwartet 'normal' bei None-Eingabe"
        )

    def test_priority_bei_leerem_string(self):
        """_extract_priority() gibt 'normal' bei leerem String zurueck."""
        sm = SessionManager()
        assert sm._extract_priority("") == "normal", (
            "Erwartet 'normal' bei leerem String"
        )


# =========================================================================
# TestLogging - Log-Eintraege und Abruf
# =========================================================================

class TestLogging:
    """Tests fuer add_log() und get_logs()."""

    def test_add_log_erzeugt_eintrag(self):
        """add_log() erstellt Log-Eintrag mit korrekten Feldern."""
        sm = SessionManager()
        eintrag = sm.add_log("coder", "CodeGenerated", "3 Dateien generiert")
        assert eintrag["agent"] == "coder", (
            f"Erwartet agent='coder', erhalten: {eintrag['agent']}"
        )
        assert eintrag["event"] == "CodeGenerated", (
            f"Erwartet event='CodeGenerated', erhalten: {eintrag['event']}"
        )
        assert eintrag["message"] == "3 Dateien generiert", (
            f"Erwartet korrekte Nachricht, erhalten: {eintrag['message']}"
        )
        assert "timestamp" in eintrag, (
            "Erwartet 'timestamp' im Log-Eintrag"
        )

    def test_get_logs_limit(self):
        """get_logs(limit=N) begrenzt die Anzahl zurueckgegebener Logs."""
        sm = SessionManager()
        for i in range(10):
            sm.add_log("test", "event", f"Log {i}")
        logs, total = sm.get_logs(limit=3)
        assert len(logs) == 3, (
            f"Erwartet 3 Logs, erhalten: {len(logs)}"
        )
        assert total == 10, (
            f"Erwartet total=10, erhalten: {total}"
        )

    def test_get_logs_offset(self):
        """get_logs(offset=N) ueberspringt die letzten N Logs."""
        sm = SessionManager()
        for i in range(10):
            sm.add_log("test", "event", f"Log {i}")
        logs, total = sm.get_logs(limit=3, offset=2)
        assert len(logs) == 3, (
            f"Erwartet 3 Logs, erhalten: {len(logs)}"
        )
        # Bei offset=2 werden die letzten 2 uebersprungen
        # Also Logs 5,6,7 (Index-basiert aus den 10 Logs: 0-9)
        assert logs[-1]["message"] == "Log 7", (
            f"Erwartet letztes Log 'Log 7', erhalten: {logs[-1]['message']}"
        )

    def test_get_logs_offset_null(self):
        """get_logs(offset=0) gibt die neuesten Logs zurueck."""
        sm = SessionManager()
        for i in range(5):
            sm.add_log("test", "event", f"Log {i}")
        logs, total = sm.get_logs(limit=2, offset=0)
        assert logs[-1]["message"] == "Log 4", (
            f"Erwartet letztes Log 'Log 4', erhalten: {logs[-1]['message']}"
        )

    def test_get_logs_leere_logs(self):
        """get_logs() bei leeren Logs gibt leere Liste zurueck."""
        sm = SessionManager()
        logs, total = sm.get_logs()
        assert logs == [], (
            f"Erwartet leere Liste, erhalten: {logs}"
        )
        assert total == 0, (
            f"Erwartet total=0, erhalten: {total}"
        )

    def test_log_ringbuffer_begrenzt(self):
        """Log-Buffer ist auf _max_logs Eintraege begrenzt (Ring-Buffer)."""
        sm = SessionManager()
        for i in range(600):
            sm.add_log("test", "event", f"Log {i}")
        _, total = sm.get_logs(limit=600)
        assert total == sm._max_logs, (
            f"Erwartet max {sm._max_logs} Logs, erhalten: {total}"
        )


# =========================================================================
# TestAgentSnapshot - Snapshot und Status-Updates
# =========================================================================

class TestAgentSnapshot:
    """Tests fuer update_agent_snapshot() und update_agent_status()."""

    def test_update_agent_snapshot_bekannter_agent(self):
        """update_agent_snapshot() aktualisiert bekannten Agent."""
        sm = SessionManager()
        sm.update_agent_snapshot("coder", {"status": "running", "file": "app.py"})
        assert sm.agent_snapshots["coder"]["status"] == "running", (
            "Erwartet status='running' im Coder-Snapshot"
        )
        assert sm.agent_snapshots["coder"]["file"] == "app.py", (
            "Erwartet file='app.py' im Coder-Snapshot"
        )
        assert "last_update" in sm.agent_snapshots["coder"], (
            "Erwartet 'last_update' im Snapshot"
        )

    def test_update_agent_snapshot_unbekannter_agent(self):
        """update_agent_snapshot() ignoriert unbekannte Agents."""
        sm = SessionManager()
        sm.update_agent_snapshot("unbekannt", {"status": "test"})
        assert "unbekannt" not in sm.agent_snapshots, (
            "Erwartet keinen Snapshot fuer unbekannten Agent"
        )

    def test_update_agent_status_running(self):
        """update_agent_status() setzt Agent auf aktiv bei 'running'."""
        sm = SessionManager()
        sm.update_agent_status("parallel_fixer", {
            "status": "running",
            "message": "Bearbeite Dateien"
        })
        assert sm.current_session["active_agents"]["parallel_fixer"] is True, (
            "Erwartet parallel_fixer als aktiv bei 'running'"
        )

    def test_update_agent_status_completed(self):
        """update_agent_status() setzt Agent auf inaktiv bei 'completed'."""
        sm = SessionManager()
        sm.update_agent_status("fix", {
            "status": "completed",
            "message": "Fertig"
        })
        assert sm.current_session["active_agents"]["fix"] is False, (
            "Erwartet fix als inaktiv bei 'completed'"
        )

    def test_update_agent_status_erzeugt_log(self):
        """update_agent_status() erzeugt Log bei running/completed/error."""
        sm = SessionManager()
        sm.update_agent_status("fix", {"status": "error", "message": "Fehler"})
        logs, _ = sm.get_logs()
        status_logs = [l for l in logs if l["event"] == "Status_error"]
        assert len(status_logs) == 1, (
            f"Erwartet 1 Status_error Log, erhalten: {len(status_logs)}"
        )

    def test_update_agent_status_unbekannter_agent(self):
        """update_agent_status() initialisiert unbekannte Agents."""
        sm = SessionManager()
        sm.update_agent_status("neuer_agent", {"status": "running", "message": "Start"})
        assert "neuer_agent" in sm.agent_snapshots, (
            "Erwartet neuen Agent in Snapshots"
        )


# =========================================================================
# TestGetCurrentState - Kompletter State-Abruf
# =========================================================================

class TestGetCurrentState:
    """Tests fuer get_current_state()."""

    def test_state_enthaelt_alle_felder(self):
        """get_current_state() liefert session, agent_data, recent_logs, is_active."""
        sm = SessionManager()
        state = sm.get_current_state()
        assert "session" in state, "Erwartet 'session' im State"
        assert "agent_data" in state, "Erwartet 'agent_data' im State"
        assert "recent_logs" in state, "Erwartet 'recent_logs' im State"
        assert "is_active" in state, "Erwartet 'is_active' im State"

    def test_state_is_active_bei_working(self):
        """get_current_state() zeigt is_active=True bei Working-Status."""
        sm = SessionManager()
        sm.start_session("Test")
        state = sm.get_current_state()
        assert state["is_active"] is True, (
            "Erwartet is_active=True bei Working"
        )

    def test_state_recent_logs_max_100(self):
        """get_current_state() liefert maximal 100 Logs."""
        sm = SessionManager()
        for i in range(200):
            sm.add_log("test", "event", f"Log {i}")
        state = sm.get_current_state()
        assert len(state["recent_logs"]) == 100, (
            f"Erwartet max 100 Logs, erhalten: {len(state['recent_logs'])}"
        )


# =========================================================================
# TestDiscoveryBriefing - Briefing setzen und abrufen
# =========================================================================

class TestDiscoveryBriefing:
    """Tests fuer Discovery-Briefing Funktionalitaet."""

    def test_set_und_get_briefing(self):
        """set_discovery_briefing() speichert, get_discovery_briefing() liest."""
        sm = SessionManager()
        briefing = {"projectName": "TestApp", "goal": "App bauen"}
        sm.set_discovery_briefing(briefing)
        result = sm.get_discovery_briefing()
        assert result == briefing, (
            f"Erwartet gespeichertes Briefing, erhalten: {result}"
        )

    def test_get_briefing_none_ohne_setzen(self):
        """get_discovery_briefing() gibt None zurueck ohne vorheriges Setzen."""
        sm = SessionManager()
        assert sm.get_discovery_briefing() is None, (
            "Erwartet None ohne gesetztes Briefing"
        )

    def test_get_briefing_liefert_deepcopy(self):
        """get_discovery_briefing() liefert eine tiefe Kopie (nicht Referenz)."""
        sm = SessionManager()
        briefing = {"projectName": "Test", "nested": {"key": "value"}}
        sm.set_discovery_briefing(briefing)
        kopie = sm.get_discovery_briefing()
        # Aenderung an der Kopie darf Original nicht beeinflussen
        kopie["projectName"] = "Geaendert"
        kopie["nested"]["key"] = "geaendert"
        original = sm.get_discovery_briefing()
        assert original["projectName"] == "Test", (
            "Erwartet unveraendertes Original nach Kopie-Aenderung"
        )
        assert original["nested"]["key"] == "value", (
            "Erwartet unveraendertes verschachteltes Original"
        )

    def test_set_briefing_erzeugt_log(self):
        """set_discovery_briefing() erzeugt einen DiscoveryBriefing-Log."""
        sm = SessionManager()
        sm.set_discovery_briefing({"projectName": "MeinProjekt"})
        logs, _ = sm.get_logs()
        briefing_logs = [l for l in logs if l["event"] == "DiscoveryBriefing"]
        assert len(briefing_logs) == 1, (
            f"Erwartet 1 DiscoveryBriefing Log, erhalten: {len(briefing_logs)}"
        )

    def test_get_briefing_context_leer_ohne_briefing(self):
        """get_briefing_context_for_agent() gibt leeren String ohne Briefing."""
        sm = SessionManager()
        assert sm.get_briefing_context_for_agent() == "", (
            "Erwartet leeren String ohne Briefing"
        )

    def test_get_briefing_context_enthaelt_ziel(self):
        """get_briefing_context_for_agent() enthaelt das Projektziel."""
        sm = SessionManager()
        sm.set_discovery_briefing({
            "goal": "Todo-App bauen",
            "techRequirements": {"language": "python", "deployment": "docker"},
            "agents": ["coder", "reviewer"],
            "answers": []
        })
        context = sm.get_briefing_context_for_agent()
        assert "Todo-App bauen" in context, (
            "Erwartet Projektziel im Kontext-String"
        )
        assert "python" in context, (
            "Erwartet Sprache im Kontext-String"
        )
        assert "coder, reviewer" in context, (
            "Erwartet Agenten-Liste im Kontext-String"
        )

    def test_get_briefing_context_mit_answers(self):
        """get_briefing_context_for_agent() enthaelt nicht-uebersprungene Antworten."""
        sm = SessionManager()
        sm.set_discovery_briefing({
            "goal": "Test",
            "techRequirements": {},
            "agents": [],
            "answers": [
                {"agent": "Designer", "selectedValues": ["Modern", "Dark"], "skipped": False},
                {"agent": "Skipped", "selectedValues": ["X"], "skipped": True},
                {"agent": "Custom", "customText": "Spezielles Layout", "skipped": False}
            ]
        })
        context = sm.get_briefing_context_for_agent()
        assert "Designer" in context, "Erwartet Designer-Antwort im Kontext"
        assert "Modern, Dark" in context, "Erwartet ausgewaehlte Werte im Kontext"
        assert "Skipped" not in context, "Erwartet KEINE uebersprungene Antwort"
        assert "Spezielles Layout" in context, "Erwartet Custom-Text im Kontext"

    def test_get_briefing_context_mit_open_points(self):
        """get_briefing_context_for_agent() enthaelt offene Punkte."""
        sm = SessionManager()
        sm.set_discovery_briefing({
            "goal": "Test",
            "techRequirements": {},
            "agents": [],
            "answers": [],
            "openPoints": ["Datenbank klären", "API-Design festlegen"]
        })
        context = sm.get_briefing_context_for_agent()
        assert "Offene Punkte" in context, "Erwartet 'Offene Punkte' Abschnitt"
        assert "Datenbank klären" in context, "Erwartet offenen Punkt im Kontext"


# =========================================================================
# TestRestoreFromLibrary - Session-Wiederherstellung
# =========================================================================

class TestRestoreFromLibrary:
    """Tests fuer restore_from_library()."""

    def test_restore_setzt_project_id(self):
        """restore_from_library() uebernimmt project_id."""
        sm = SessionManager()
        result = sm.restore_from_library({
            "project_id": "altes_projekt",
            "goal": "Altes Ziel",
            "started_at": "2026-01-01T00:00:00"
        })
        assert result["project_id"] == "altes_projekt", (
            "Erwartet wiederhergestellte project_id"
        )
        assert result["status"] == "Restored", (
            "Erwartet Status 'Restored'"
        )

    def test_restore_laedt_logs(self):
        """restore_from_library() laedt vorhandene Logs."""
        sm = SessionManager()
        alte_logs = [
            {"timestamp": "2026-01-01", "agent": "coder", "event": "e", "message": "m"}
        ]
        sm.restore_from_library({
            "project_id": "p1",
            "logs": alte_logs
        })
        _, total = sm.get_logs()
        # alte_logs + SessionRestore Log
        assert total == 2, (
            f"Erwartet 2 Logs (1 alter + 1 Restore), erhalten: {total}"
        )

    def test_restore_ohne_logs(self):
        """restore_from_library() ohne logs-Feld bricht nicht ab."""
        sm = SessionManager()
        result = sm.restore_from_library({"project_id": "p2"})
        assert result["project_id"] == "p2", (
            "Erwartet project_id auch ohne Logs"
        )

    def test_restore_setzt_restored_from(self):
        """restore_from_library() setzt 'restored_from' Feld."""
        sm = SessionManager()
        result = sm.restore_from_library({"project_id": "quelle"})
        assert result.get("restored_from") == "quelle", (
            "Erwartet 'restored_from' mit Quell-ID"
        )


# =========================================================================
# TestThreadSafety - Parallele Zugriffe
# =========================================================================

class TestThreadSafety:
    """Tests fuer Thread-Safety des SessionManagers."""

    def test_parallele_log_eintraege(self):
        """Parallele add_log() Aufrufe verlieren keine Eintraege."""
        sm = SessionManager()
        anzahl_threads = 10
        logs_pro_thread = 20
        fehler = []

        def log_schreiber(thread_id):
            try:
                for i in range(logs_pro_thread):
                    sm.add_log(f"thread_{thread_id}", "event", f"Log {i}")
            except Exception as e:
                fehler.append(str(e))

        threads = [
            threading.Thread(target=log_schreiber, args=(t,))
            for t in range(anzahl_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(fehler) == 0, (
            f"Erwartet keine Fehler, erhalten: {fehler}"
        )
        _, total = sm.get_logs()
        erwartet = anzahl_threads * logs_pro_thread
        assert total == erwartet, (
            f"Erwartet {erwartet} Logs, erhalten: {total}"
        )

    def test_paralleler_singleton_zugriff(self):
        """Parallele SessionManager()-Aufrufe liefern dieselbe Instanz."""
        instanzen = []

        def hole_instanz():
            instanzen.append(SessionManager())

        threads = [
            threading.Thread(target=hole_instanz)
            for _ in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Alle Instanzen muessen identisch sein
        erste = instanzen[0]
        for idx, inst in enumerate(instanzen[1:], 1):
            assert inst is erste, (
                f"Erwartet identische Instanz bei Thread {idx}"
            )
