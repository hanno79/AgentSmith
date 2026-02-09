"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Umfassende Unit-Tests fuer backend/orchestration_helpers.py.
              Testet alle oeffentlichen Hilfsfunktionen fuer Parsing, Formatting und Fehler-Checks.
"""

from unittest.mock import MagicMock, patch

from backend.orchestration_helpers import (
    create_human_readable_verdict,
    extract_tables_from_schema,
    is_server_error,
    is_litellm_internal_error,
    is_model_unavailable_error,
    is_permanently_unavailable_error,
    handle_model_error,
    is_empty_response_error,
    is_rate_limit_error,
    is_openrouter_error,
    is_empty_or_invalid_response,
    extract_vulnerabilities,
    extract_design_data,
    format_test_feedback,
    sanitize_unicode_hyphens,
    truncate_review_output,
)


# -- Hilfsklasse: Mock-Exception mit optionalem response/status_code Attribut --
class MockError(Exception):
    """Fehler-Klasse mit konfigurierbarem status_code fuer Tests."""
    pass


def _error_mit_response_status(status_code: int, nachricht: str = "Testfehler") -> MockError:
    """Erstellt eine MockError-Exception mit response.status_code."""
    err = MockError(nachricht)
    err.response = MagicMock(status_code=status_code)
    return err


def _error_mit_status_code(status_code: int, nachricht: str = "Testfehler") -> MockError:
    """Erstellt eine MockError-Exception mit direktem status_code Attribut."""
    err = MockError(nachricht)
    err.status_code = status_code
    return err


# -- TestCreateHumanReadableVerdict --
class TestCreateHumanReadableVerdict:
    """Tests fuer create_human_readable_verdict."""

    def test_ok_ohne_sandbox_fehler(self):
        """Verdict OK und kein Sandbox-Fehler ergibt 'REVIEW BESTANDEN'."""
        ergebnis = create_human_readable_verdict("OK", False, "")
        assert "REVIEW BESTANDEN" in ergebnis
        assert "Code erfüllt alle Anforderungen" in ergebnis

    def test_sandbox_fehlgeschlagen(self):
        """Sandbox-Fehler erzeugt 'REVIEW FEHLGESCHLAGEN' unabhaengig vom Verdict."""
        ergebnis = create_human_readable_verdict("OK", True, "Alles gut")
        assert "REVIEW FEHLGESCHLAGEN" in ergebnis
        assert "Sandbox/Test hat Fehler gemeldet" in ergebnis

    def test_feedback_mit_review_output(self):
        """Bei vorhandenem Review-Output wird der erste Satz extrahiert."""
        review = "Die Variable ist falsch benannt. Bitte korrigieren."
        ergebnis = create_human_readable_verdict("FEEDBACK", False, review)
        assert "ÄNDERUNGEN NÖTIG" in ergebnis
        assert "Die Variable ist falsch benannt" in ergebnis

    def test_fallback_ohne_review_output(self):
        """Ohne Review-Output erscheint die Fallback-Meldung."""
        ergebnis = create_human_readable_verdict("FEEDBACK", False, "")
        assert "ÄNDERUNGEN NÖTIG" in ergebnis
        assert "Bitte Feedback beachten" in ergebnis


# -- TestExtractTablesFromSchema --
class TestExtractTablesFromSchema:
    """Tests fuer extract_tables_from_schema."""

    def test_leeres_schema_ergibt_leere_liste(self):
        """Leerer oder None-Input liefert leere Liste."""
        assert extract_tables_from_schema("") == []
        assert extract_tables_from_schema(None) == []

    def test_einzelne_tabelle(self):
        """Eine einfache CREATE TABLE Anweisung wird korrekt geparst."""
        schema = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email VARCHAR
        );
        """
        tabellen = extract_tables_from_schema(schema)
        assert len(tabellen) == 1
        assert tabellen[0]["name"] == "users"
        assert tabellen[0]["type"] == "table"
        # id hat PRIMARY KEY im Spaltentext
        id_spalte = next(s for s in tabellen[0]["columns"] if s["name"] == "id")
        assert id_spalte["isPrimary"] is True

    def test_mehrere_tabellen(self):
        """Mehrere CREATE TABLE Anweisungen werden alle extrahiert."""
        schema = """
        CREATE TABLE users (
            id INTEGER,
            name TEXT
        );
        CREATE TABLE orders (
            id INTEGER,
            user_id INTEGER REFERENCES users(id),
            amount REAL
        );
        """
        tabellen = extract_tables_from_schema(schema)
        assert len(tabellen) == 2
        namen = [t["name"] for t in tabellen]
        assert "users" in namen
        assert "orders" in namen
        # user_id sollte als Foreign Key erkannt werden
        orders_tabelle = next(t for t in tabellen if t["name"] == "orders")
        fk_spalte = next(s for s in orders_tabelle["columns"] if s["name"] == "user_id")
        assert fk_spalte["isForeign"] is True

    def test_constraints_werden_uebersprungen(self):
        """Zeilen mit PRIMARY, FOREIGN, UNIQUE, CHECK, etc. werden uebersprungen."""
        schema = """
        CREATE TABLE produkte (
            id INTEGER,
            name TEXT,
            preis REAL,
            PRIMARY KEY (id),
            UNIQUE (name),
            CHECK (preis > 0),
            CONSTRAINT fk_cat FOREIGN KEY (cat_id) REFERENCES categories(id)
        );
        """
        tabellen = extract_tables_from_schema(schema)
        assert len(tabellen) == 1
        spalten_namen = [s["name"] for s in tabellen[0]["columns"]]
        assert "id" in spalten_namen
        assert "name" in spalten_namen
        assert "preis" in spalten_namen
        # Constraint-Zeilen duerfen nicht als Spalten auftauchen
        assert len(tabellen[0]["columns"]) == 3


# -- TestIsServerError --
class TestIsServerError:
    """Tests fuer is_server_error."""

    def test_status_code_500_via_response(self):
        """Status-Code 500 ueber response.status_code wird als Server-Fehler erkannt."""
        err = _error_mit_response_status(500, "Server Error")
        assert is_server_error(err) is True

    def test_string_pattern_bad_gateway(self):
        """String-Muster 'bad gateway' wird als Server-Fehler erkannt."""
        err = Exception("Connection failed: bad gateway")
        assert is_server_error(err) is True

    def test_kein_server_fehler(self):
        """Ein normaler Fehler ohne Server-Muster wird nicht als Server-Fehler erkannt."""
        err = Exception("Ungueltige Eingabe vom Benutzer")
        assert is_server_error(err) is False


# -- TestIsLitellmInternalError --
class TestIsLitellmInternalError:
    """Tests fuer is_litellm_internal_error."""

    def test_erkennung_request_attribut_fehler(self):
        """Fehlermuster 'has no attribute request' wird erkannt."""
        err = Exception("NoneType has no attribute 'request'")
        assert is_litellm_internal_error(err) is True

    def test_normaler_fehler_wird_nicht_erkannt(self):
        """Ein normaler Fehler ohne LiteLLM-Muster wird nicht erkannt."""
        err = Exception("Allgemeiner Verbindungsfehler")
        assert is_litellm_internal_error(err) is False


# -- TestIsModelUnavailableError --
class TestIsModelUnavailableError:
    """Tests fuer is_model_unavailable_error."""

    def test_status_code_404(self):
        """Status-Code 404 ueber response.status_code wird als 'nicht verfuegbar' erkannt."""
        err = _error_mit_response_status(404, "Modell nicht gefunden")
        assert is_model_unavailable_error(err) is True

    def test_string_pattern_not_found(self):
        """String-Muster 'not found' wird als 'nicht verfuegbar' erkannt."""
        err = Exception("Model not found on this provider")
        assert is_model_unavailable_error(err) is True


# -- TestIsPermanentlyUnavailableError --
class TestIsPermanentlyUnavailableError:
    """Tests fuer is_permanently_unavailable_error."""

    def test_free_period_ended(self):
        """Muster 'free period ended' wird als permanenter Fehler erkannt."""
        err = Exception("Error: free period ended for this model")
        assert is_permanently_unavailable_error(err) is True

    def test_kein_permanenter_fehler(self):
        """Ein normaler Fehler wird nicht als permanent erkannt."""
        err = Exception("Timeout beim Verbindungsaufbau")
        assert is_permanently_unavailable_error(err) is False


# -- TestHandleModelError --
class TestHandleModelError:
    """Tests fuer handle_model_error mit Mock-ModelRouter."""

    def test_permanenter_fehler(self):
        """Permanenter Fehler markiert Modell als dauerhaft nicht verfuegbar."""
        mock_router = MagicMock()
        err = Exception("free period ended")
        ergebnis = handle_model_error(mock_router, "test-model", err)
        assert ergebnis == "permanent"
        mock_router.mark_permanently_unavailable.assert_called_once()
        # Pruefe, dass der Modellname uebergeben wurde
        args = mock_router.mark_permanently_unavailable.call_args
        assert args[0][0] == "test-model"

    @patch("backend.orchestration_helpers.is_rate_limit_error", return_value=True)
    def test_rate_limit_fehler(self, _mock_rate_limit):
        """Rate-Limit-Fehler markiert Modell als temporaer begrenzt."""
        mock_router = MagicMock()
        err = Exception("rate limit exceeded")
        ergebnis = handle_model_error(mock_router, "test-model", err)
        assert ergebnis == "rate_limit"
        mock_router.mark_rate_limited_sync.assert_called_once_with("test-model")

    def test_unbekannter_fehler(self):
        """Unbekannter Fehler gibt 'unknown' zurueck ohne Modell zu markieren."""
        mock_router = MagicMock()
        err = Exception("Unerwarteter interner Fehler")
        ergebnis = handle_model_error(mock_router, "test-model", err)
        assert ergebnis == "unknown"
        mock_router.mark_permanently_unavailable.assert_not_called()
        mock_router.mark_rate_limited_sync.assert_not_called()


# -- TestIsEmptyResponseError --
class TestIsEmptyResponseError:
    """Tests fuer is_empty_response_error."""

    def test_empty_response_muster(self):
        """Muster 'empty response' wird erkannt."""
        err = Exception("LLM returned empty response")
        assert is_empty_response_error(err) is True

    def test_normaler_fehler_kein_empty_response(self):
        """Ein normaler Fehler wird nicht als leere Antwort erkannt."""
        err = Exception("Verbindung zum Server abgebrochen")
        assert is_empty_response_error(err) is False


# -- TestIsRateLimitError --
class TestIsRateLimitError:
    """Tests fuer is_rate_limit_error."""

    @patch("backend.orchestration_helpers.log_event")
    def test_status_code_429(self, _mock_log):
        """Status-Code 429 wird als Rate-Limit erkannt."""
        err = _error_mit_response_status(429, "Too Many Requests")
        assert is_rate_limit_error(err) is True

    @patch("backend.orchestration_helpers.log_event")
    def test_server_error_ist_kein_rate_limit(self, _mock_log):
        """Server-Fehler (500) wird NICHT als Rate-Limit erkannt."""
        err = _error_mit_response_status(500, "Internal Server Error")
        assert is_rate_limit_error(err) is False

    @patch("backend.orchestration_helpers.log_event")
    def test_upstream_generic_kein_rate_limit(self, _mock_log):
        """AENDERUNG 09.02.2026: Fix 36c — Generischer upstream error ist KEIN Rate-Limit mehr."""
        err = Exception("OpenrouterException: upstream error from provider")
        assert is_rate_limit_error(err) is False

    @patch("backend.orchestration_helpers.log_event")
    def test_upstream_429_ist_rate_limit(self, _mock_log):
        """Upstream error mit 429 wird als Rate-Limit erkannt."""
        err = Exception("upstream error: 429 Too Many Requests")
        assert is_rate_limit_error(err) is True

    @patch("backend.orchestration_helpers.log_event")
    def test_upstream_quota_ist_rate_limit(self, _mock_log):
        """Upstream error mit quota exceeded wird als Rate-Limit erkannt."""
        err = Exception("upstream error: quota exceeded for model")
        assert is_rate_limit_error(err) is True

    @patch("backend.orchestration_helpers.log_event")
    def test_upstream_500_kein_rate_limit(self, _mock_log):
        """Upstream error mit 500 Internal Server Error ist KEIN Rate-Limit."""
        err = Exception("upstream error: 500 Internal Server Error")
        assert is_rate_limit_error(err) is False


# -- TestIsOpenrouterError --
class TestIsOpenrouterError:
    """Tests fuer is_openrouter_error."""

    def test_openrouter_muster(self):
        """OpenRouter-spezifisches Fehlermuster wird erkannt."""
        err = Exception("litellm.Timeout: OpenrouterException - Provider returned error")
        assert is_openrouter_error(err) is True

    def test_kein_openrouter_fehler(self):
        """Normaler Timeout wird nicht als OpenRouter-Fehler erkannt."""
        err = Exception("Connection timed out after 30 seconds")
        assert is_openrouter_error(err) is False


# -- TestIsEmptyOrInvalidResponse --
class TestIsEmptyOrInvalidResponse:
    """Tests fuer is_empty_or_invalid_response."""

    def test_none_eingabe(self):
        """None wird als leer/ungueltig erkannt."""
        assert is_empty_or_invalid_response(None) is True

    def test_leerer_string(self):
        """Leerer String wird als ungueltig erkannt."""
        assert is_empty_or_invalid_response("") is True
        assert is_empty_or_invalid_response("   ") is True

    def test_gueltige_antwort(self):
        """Eine normale Antwort wird als gueltig erkannt."""
        assert is_empty_or_invalid_response("Hier ist mein Code-Vorschlag.") is False


# -- TestExtractVulnerabilities --
class TestExtractVulnerabilities:
    """Tests fuer extract_vulnerabilities."""

    def test_vollstaendiges_muster(self):
        """Vollstaendiges VULNERABILITY|FIX|SEVERITY Muster wird korrekt geparst."""
        eingabe = (
            "VULNERABILITY: SQL Injection in file login.py "
            "| FIX: Prepared Statements verwenden "
            "| SEVERITY: critical"
        )
        ergebnis = extract_vulnerabilities(eingabe)
        assert len(ergebnis) == 1
        assert ergebnis[0]["severity"] == "critical"
        assert "SQL Injection" in ergebnis[0]["description"]
        assert "Prepared Statements" in ergebnis[0]["fix"]
        assert ergebnis[0]["affected_file"] == "login.py"
        assert ergebnis[0]["type"] == "SECURITY_ISSUE"

    def test_altes_muster_mit_schweregrad_ableitung(self):
        """Altes Muster ohne SEVERITY leitet den Schweregrad aus Schluesselwoertern ab."""
        eingabe = "VULNERABILITY: XSS Angriff in der Suchfunktion moeglich"
        ergebnis = extract_vulnerabilities(eingabe)
        assert len(ergebnis) == 1
        # XSS sollte als "high" eingestuft werden
        assert ergebnis[0]["severity"] == "high"

    def test_leere_eingabe(self):
        """Leere Eingabe liefert leere Liste."""
        assert extract_vulnerabilities("") == []
        assert extract_vulnerabilities(None) == []


# -- TestExtractDesignData --
class TestExtractDesignData:
    """Tests fuer extract_design_data."""

    def test_mit_farben_schriften_und_komponenten(self):
        """Design-Konzept mit Hex-Farben, Schriftarten und Komponenten wird geparst."""
        design_text = (
            "Primaerfarbe: #FF5733, Sekundaerfarbe: #33FF57. "
            "Schriftart: Roboto fuer Ueberschriften. "
            "Komponenten: Button, Card, Modal."
        )
        ergebnis = extract_design_data(design_text)
        assert len(ergebnis["colorPalette"]) == 2
        assert ergebnis["colorPalette"][0]["hex"] == "#FF5733"
        assert ergebnis["colorPalette"][1]["hex"] == "#33FF57"
        # Roboto muss in der Typography erkannt werden
        assert ergebnis["typography"][0]["font"] == "Roboto"
        # Komponenten
        assert len(ergebnis["atomicAssets"]) > 0
        komponenten_namen = [a["name"] for a in ergebnis["atomicAssets"]]
        assert any("Button" in n for n in komponenten_namen)
        # QualityScore muss groesser 0 sein
        assert ergebnis["qualityScore"]["overall"] > 0

    def test_leere_eingabe_ergibt_default_struktur(self):
        """Leere Eingabe liefert Standard-Struktur mit Nullwerten."""
        ergebnis = extract_design_data("")
        assert ergebnis["colorPalette"] == []
        assert ergebnis["typography"] == []
        assert ergebnis["atomicAssets"] == []
        assert ergebnis["qualityScore"]["overall"] == 0

    def test_partielle_daten_nur_farben(self):
        """Nur Farben vorhanden, keine Schriftarten oder Komponenten."""
        design_text = "Hauptfarbe ist #ABCDEF und Akzentfarbe #123456."
        ergebnis = extract_design_data(design_text)
        assert len(ergebnis["colorPalette"]) == 2
        # Ohne erkannte Schriftart wird "Inter" als Fallback verwendet
        assert ergebnis["typography"][0]["font"] == "Inter"
        # Keine Komponenten erkannt
        assert ergebnis["atomicAssets"] == []
        # Score trotzdem > 0 durch Farben und Typography-Eintraege
        assert ergebnis["qualityScore"]["overall"] > 0


# -- TestFormatTestFeedback --
class TestFormatTestFeedback:
    """Tests fuer format_test_feedback."""

    def test_unit_test_fehlgeschlagen(self):
        """Bei fehlgeschlagenen Unit-Tests wird strukturiertes Feedback erzeugt."""
        test_ergebnis = {
            "unit_tests": {
                "status": "FAIL",
                "failed_count": 3,
                "summary": "Assertion Fehler in test_login",
                "details": "AssertionError: Erwartet 200, erhalten 401"
            },
            "ui_tests": {}
        }
        feedback = format_test_feedback(test_ergebnis)
        assert "UNIT-TEST FEHLER" in feedback
        assert "3 Test(s) fehlgeschlagen" in feedback
        assert "RE-TEST ERFORDERLICH" in feedback

    def test_alle_tests_bestanden(self):
        """Bei bestandenen Tests erscheint Erfolgsmeldung."""
        test_ergebnis = {
            "unit_tests": {"status": "PASS"},
            "ui_tests": {"status": "PASS"}
        }
        feedback = format_test_feedback(test_ergebnis)
        assert "Alle Tests bestanden" in feedback


# -- TestSanitizeUnicodeHyphens --
class TestSanitizeUnicodeHyphens:
    """Tests fuer sanitize_unicode_hyphens."""

    def test_unicode_hyphens_werden_ersetzt(self):
        """Unicode-Hyphens (En-Dash, Em-Dash, etc.) werden durch ASCII-Hyphen ersetzt."""
        # U+2013 En Dash, U+2014 Em Dash, U+2011 Non-Breaking Hyphen
        code_mit_unicode = "x \u2013 y \u2014 z \u2011 w"
        ergebnis = sanitize_unicode_hyphens(code_mit_unicode)
        assert "\u2013" not in ergebnis
        assert "\u2014" not in ergebnis
        assert "\u2011" not in ergebnis
        assert ergebnis == "x - y - z - w"

    def test_leere_eingabe_bleibt_unveraendert(self):
        """Leere oder None-Eingabe wird unveraendert zurueckgegeben."""
        assert sanitize_unicode_hyphens("") == ""
        assert sanitize_unicode_hyphens(None) is None


# -- TestTruncateReviewOutput --
class TestTruncateReviewOutput:
    """Tests fuer truncate_review_output."""

    def test_kurzer_output_unveraendert(self):
        """Text kuerzer als max_length wird unveraendert zurueckgegeben."""
        kurzer_text = "Alles sieht gut aus."
        assert truncate_review_output(kurzer_text) == kurzer_text

    def test_deduplizierung_und_kuerzung(self):
        """Doppelte Zeilen werden entfernt und zu langer Output wird gekuerzt."""
        # Erstelle Output mit vielen Wiederholungen
        zeile = "Diese Zeile wiederholt sich staendig."
        langer_text = "\n".join([zeile] * 200 + [f"Einzigartige Zeile {i}" for i in range(100)])
        ergebnis = truncate_review_output(langer_text, max_length=500)
        # Deduplizierung: Die sich wiederholende Zeile sollte nur 1x vorkommen
        assert ergebnis.count(zeile) == 1
        # Gesamtlaenge beachten (inkl. Kuerzungshinweis)
        assert len(ergebnis) <= 500 + len("\n[... gekuerzt]")
        assert "[... gekuerzt]" in ergebnis

    def test_leere_eingabe(self):
        """Leere oder None-Eingabe wird unveraendert zurueckgegeben."""
        assert truncate_review_output("") == ""
        assert truncate_review_output(None) is None
