"""
Author: rahn
Datum: 06.02.2026
Version: 1.0
Beschreibung: Tests fuer den FileStatusDetector und die Hilfsfunktion
              get_file_status_summary_for_log. Prueft Dateistatus-Erkennung,
              Patch-Filterung und Logging-Ausgabe.
"""

import os
import pytest

from backend.file_status_detector import FileStatusDetector, get_file_status_summary_for_log


class TestGetFileStatus:
    """Tests fuer die Methode get_file_status."""

    def test_neue_datei(self, tmp_path):
        """Datei existiert nicht auf der Festplatte -> Status 'new'."""
        detector = FileStatusDetector(str(tmp_path))
        status = detector.get_file_status("nicht_vorhanden.py")
        assert status == "new", (
            f"Erwartet: 'new', Erhalten: '{status}' - "
            "Eine nicht existierende Datei muss als 'new' erkannt werden"
        )

    def test_fehlerhafte_datei(self, tmp_path):
        """Datei existiert und ist in error_files -> Status 'error'."""
        # Datei anlegen damit sie existiert
        datei = tmp_path / "fehlerhaft.py"
        datei.write_text("# fehlerhafter code")

        detector = FileStatusDetector(str(tmp_path))
        status = detector.get_file_status("fehlerhaft.py", error_files=["fehlerhaft.py"])
        assert status == "error", (
            f"Erwartet: 'error', Erhalten: '{status}' - "
            "Eine existierende Datei in error_files muss als 'error' erkannt werden"
        )

    def test_korrekte_datei(self, tmp_path):
        """Datei existiert, ist aber nicht in error_files -> Status 'correct'."""
        datei = tmp_path / "korrekt.py"
        datei.write_text("# korrekter code")

        detector = FileStatusDetector(str(tmp_path))
        status = detector.get_file_status("korrekt.py", error_files=[])
        assert status == "correct", (
            f"Erwartet: 'correct', Erhalten: '{status}' - "
            "Eine existierende Datei ohne Fehler muss als 'correct' erkannt werden"
        )

    def test_absoluter_pfad(self, tmp_path):
        """Absoluter Pfad wird direkt verwendet, nicht mit project_path verknuepft."""
        datei = tmp_path / "absolut.py"
        datei.write_text("# absoluter pfad")

        detector = FileStatusDetector(str(tmp_path))
        abs_pfad = str(datei)
        status = detector.get_file_status(abs_pfad)
        assert status == "correct", (
            f"Erwartet: 'correct', Erhalten: '{status}' - "
            "Ein absoluter Pfad zu einer existierenden Datei muss als 'correct' erkannt werden"
        )


class TestGetFilesToPatch:
    """Tests fuer die Methode get_files_to_patch."""

    def test_nur_neue_und_fehlerhafte(self, tmp_path):
        """Nur neue und fehlerhafte Dateien werden zurueckgegeben."""
        # 'korrekt.py' existiert und hat keinen Fehler
        (tmp_path / "korrekt.py").write_text("# ok")
        # 'fehlerhaft.py' existiert und hat einen Fehler
        (tmp_path / "fehlerhaft.py").write_text("# fehler")
        # 'neu.py' existiert nicht

        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "korrekt.py": "# ok",
            "fehlerhaft.py": "# fehler",
            "neu.py": "# neu",
        }
        error_files = ["fehlerhaft.py"]

        ergebnis = detector.get_files_to_patch(current_code, error_files)

        assert "neu.py" in ergebnis, "Neue Dateien muessen in der Patch-Liste sein"
        assert "fehlerhaft.py" in ergebnis, "Fehlerhafte Dateien muessen in der Patch-Liste sein"
        assert "korrekt.py" not in ergebnis, "Korrekte Dateien duerfen nicht in der Patch-Liste sein"
        assert len(ergebnis) == 2, (
            f"Erwartet: 2 Dateien, Erhalten: {len(ergebnis)} - "
            "Nur neue und fehlerhafte Dateien sollen enthalten sein"
        )

    def test_mit_korrekten(self, tmp_path):
        """Mit also_include_correct=True werden alle Dateien einbezogen."""
        (tmp_path / "korrekt.py").write_text("# ok")
        (tmp_path / "fehlerhaft.py").write_text("# fehler")

        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "korrekt.py": "# ok",
            "fehlerhaft.py": "# fehler",
            "neu.py": "# neu",
        }
        error_files = ["fehlerhaft.py"]

        ergebnis = detector.get_files_to_patch(
            current_code, error_files, also_include_correct=True
        )

        assert len(ergebnis) == 3, (
            f"Erwartet: 3 Dateien, Erhalten: {len(ergebnis)} - "
            "Mit also_include_correct=True muessen alle Dateien enthalten sein"
        )
        assert "korrekt.py" in ergebnis, (
            "Korrekte Dateien muessen bei also_include_correct=True enthalten sein"
        )


class TestGetStatusSummary:
    """Tests fuer die Methode get_status_summary."""

    def test_zusammenfassung(self, tmp_path):
        """Drei Dateien in drei verschiedenen Kategorien."""
        (tmp_path / "korrekt.py").write_text("# ok")
        (tmp_path / "fehlerhaft.py").write_text("# fehler")
        # 'neu.py' existiert nicht

        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "korrekt.py": "# ok",
            "fehlerhaft.py": "# fehler",
            "neu.py": "# neu",
        }
        error_files = ["fehlerhaft.py"]

        summary = detector.get_status_summary(current_code, error_files)

        assert "neu.py" in summary["new"], "neu.py muss im Status 'new' sein"
        assert "fehlerhaft.py" in summary["error"], "fehlerhaft.py muss im Status 'error' sein"
        assert "korrekt.py" in summary["correct"], "korrekt.py muss im Status 'correct' sein"

    def test_leeres_projekt(self, tmp_path):
        """Leeres Code-Dict ergibt leere Listen in allen Kategorien."""
        detector = FileStatusDetector(str(tmp_path))
        summary = detector.get_status_summary({}, error_files=[])

        assert summary["new"] == [], "Leeres Projekt: 'new' muss leer sein"
        assert summary["error"] == [], "Leeres Projekt: 'error' muss leer sein"
        assert summary["correct"] == [], "Leeres Projekt: 'correct' muss leer sein"


class TestFilterCodeForPatch:
    """Tests fuer die Methode filter_code_for_patch."""

    def test_exakter_match(self, tmp_path):
        """Dateipfad stimmt exakt mit der Patch-Liste ueberein."""
        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "main.py": "print('hello')",
            "utils.py": "def helper(): pass",
            "config.py": "DEBUG = True",
        }
        files_to_patch = ["main.py", "config.py"]

        ergebnis = detector.filter_code_for_patch(current_code, files_to_patch)

        assert "main.py" in ergebnis, "main.py muss im gefilterten Ergebnis sein"
        assert "config.py" in ergebnis, "config.py muss im gefilterten Ergebnis sein"
        assert "utils.py" not in ergebnis, "utils.py darf nicht im gefilterten Ergebnis sein"
        assert ergebnis["main.py"] == "print('hello')", (
            "Der Inhalt der gefilterten Datei muss erhalten bleiben"
        )

    def test_pfad_varianten(self, tmp_path):
        """Pfade mit / und \\ Prefix werden korrekt zugeordnet."""
        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "src/main.py": "print('hello')",
            "src\\utils.py": "def helper(): pass",
        }
        files_to_patch = ["main.py", "utils.py"]

        ergebnis = detector.filter_code_for_patch(current_code, files_to_patch)

        assert "src/main.py" in ergebnis, (
            "src/main.py muss ueber /-Prefix-Match gefunden werden"
        )
        assert "src\\utils.py" in ergebnis, (
            "src\\utils.py muss ueber \\-Prefix-Match gefunden werden"
        )


class TestGetPatchRatio:
    """Tests fuer die Methode get_patch_ratio."""

    def test_berechnung(self, tmp_path):
        """2 von 4 Dateien zu patchen ergibt Ratio 0.5."""
        (tmp_path / "ok1.py").write_text("# ok")
        (tmp_path / "ok2.py").write_text("# ok")
        (tmp_path / "fehler.py").write_text("# fehler")
        # 'neu.py' existiert nicht

        detector = FileStatusDetector(str(tmp_path))
        current_code = {
            "ok1.py": "# ok",
            "ok2.py": "# ok",
            "fehler.py": "# fehler",
            "neu.py": "# neu",
        }
        error_files = ["fehler.py"]

        ratio = detector.get_patch_ratio(current_code, error_files)

        assert ratio == pytest.approx(0.5), (
            f"Erwartet: 0.5, Erhalten: {ratio} - "
            "2 von 4 Dateien zu patchen muss Ratio 0.5 ergeben"
        )

    def test_leeres_projekt(self, tmp_path):
        """Leeres Code-Dict ergibt Ratio 0.0."""
        detector = FileStatusDetector(str(tmp_path))
        ratio = detector.get_patch_ratio({})

        assert ratio == 0.0, (
            f"Erwartet: 0.0, Erhalten: {ratio} - "
            "Ein leeres Projekt muss Patch-Ratio 0.0 haben"
        )


class TestGetFileStatusSummaryForLog:
    """Tests fuer die Hilfsfunktion get_file_status_summary_for_log."""

    def test_formatierung(self, tmp_path):
        """Prueft das korrekte Log-Format mit allen Bestandteilen."""
        (tmp_path / "korrekt.py").write_text("# ok")
        (tmp_path / "fehlerhaft.py").write_text("# fehler")
        # 'neu.py' existiert nicht

        current_code = {
            "korrekt.py": "# ok",
            "fehlerhaft.py": "# fehler",
            "neu.py": "# neu",
        }
        error_files = ["fehlerhaft.py"]

        ergebnis = get_file_status_summary_for_log(
            str(tmp_path), current_code, error_files
        )

        assert "New: 1" in ergebnis, "Log muss 'New: 1' enthalten"
        assert "Error: 1" in ergebnis, "Log muss 'Error: 1' enthalten"
        assert "Correct: 1" in ergebnis, "Log muss 'Correct: 1' enthalten"
        assert "Patch-Ratio: 66.7%" in ergebnis, (
            f"Log muss 'Patch-Ratio: 66.7%' enthalten, erhalten: '{ergebnis}'"
        )
        # Pruefe das Trennzeichen-Format
        assert " | " in ergebnis, "Log-Teile muessen mit ' | ' getrennt sein"
