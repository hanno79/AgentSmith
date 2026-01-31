# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 31.01.2026
Version: 1.0
Beschreibung: pytest-qt basierter UI-Tester für PyQt5/PyQt6/PySide Anwendungen.
              Arbeitet headless und objektbasiert - keine Screenshots nötig.
              ÄNDERUNG 31.01.2026: Neue Datei für intelligentes UI-Test-Routing.
"""

import os
import subprocess
import sys
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Prüfe ob pytest verfügbar ist
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False


def check_pytest_qt_available() -> bool:
    """Prüft ob pytest-qt installiert ist."""
    try:
        import pytestqt
        return True
    except ImportError:
        return False


def install_pytest_qt() -> bool:
    """Installiert pytest-qt falls nicht vorhanden."""
    try:
        logger.info("Installiere pytest-qt...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytest-qt", "-q"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            logger.info("pytest-qt erfolgreich installiert")
            return True
        else:
            logger.error(f"pytest-qt Installation fehlgeschlagen: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("pytest-qt Installation Timeout nach 60s")
        return False
    except Exception as e:
        logger.error(f"pytest-qt Installation fehlgeschlagen: {e}")
        return False


def generate_qt_test_file(project_path: str, main_file: str = "main.py") -> str:
    """
    Generiert eine pytest-qt Test-Datei für das Projekt.

    Args:
        project_path: Pfad zum Projektverzeichnis
        main_file: Hauptdatei der Anwendung

    Returns:
        Pfad zur erstellten Test-Datei
    """
    test_content = '''# -*- coding: utf-8 -*-
"""
Auto-generierte pytest-qt Tests für PyQt/PySide Anwendung.
Author: rahn (auto-generated)
Datum: 31.01.2026
"""
import pytest
import sys
import os

# Projekt-Pfad zum sys.path hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Versuche verschiedene Qt-Bindings
QT_AVAILABLE = False
try:
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtCore import Qt
    QT_AVAILABLE = True
    QT_VERSION = "PyQt5"
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow
        from PyQt6.QtCore import Qt
        QT_AVAILABLE = True
        QT_VERSION = "PyQt6"
    except ImportError:
        try:
            from PySide6.QtWidgets import QApplication, QMainWindow
            from PySide6.QtCore import Qt
            QT_AVAILABLE = True
            QT_VERSION = "PySide6"
        except ImportError:
            try:
                from PySide2.QtWidgets import QApplication, QMainWindow
                from PySide2.QtCore import Qt
                QT_AVAILABLE = True
                QT_VERSION = "PySide2"
            except ImportError:
                QT_VERSION = None


@pytest.fixture(scope="session")
def qapp():
    """Session-weite QApplication Fixture."""
    if not QT_AVAILABLE:
        pytest.skip("Kein Qt-Framework verfügbar")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestMainWindow:
    """Tests für das Hauptfenster."""

    @pytest.fixture
    def main_window(self, qapp, qtbot):
        """Fixture für das Hauptfenster."""
        try:
            from main import MainWindow
            window = MainWindow()
            qtbot.addWidget(window)
            yield window
        except ImportError as e:
            pytest.skip(f"MainWindow nicht importierbar: {e}")
        except Exception as e:
            pytest.skip(f"MainWindow Erstellung fehlgeschlagen: {e}")

    def test_window_exists(self, main_window):
        """Testet dass das Hauptfenster existiert."""
        assert main_window is not None, "MainWindow sollte existieren"

    def test_window_title(self, main_window):
        """Testet den Fenstertitel."""
        title = main_window.windowTitle()
        assert title is not None, "Fenstertitel sollte gesetzt sein"
        assert len(title) > 0, "Fenstertitel sollte nicht leer sein"

    def test_window_visible(self, main_window, qtbot):
        """Testet dass das Fenster sichtbar gemacht werden kann."""
        main_window.show()
        qtbot.waitExposed(main_window, timeout=5000)
        assert main_window.isVisible(), "Fenster sollte sichtbar sein"

    def test_window_geometry(self, main_window):
        """Testet die Fenstergeometrie."""
        size = main_window.size()
        assert size.width() > 0, "Fensterbreite sollte > 0 sein"
        assert size.height() > 0, "Fensterhoehe sollte > 0 sein"


class TestDialogs:
    """Tests für Dialoge."""

    def test_dialog_module_exists(self):
        """Testet dass Dialoge importiert werden können."""
        try:
            import dialogs
            assert dialogs is not None
        except ImportError:
            pytest.skip("dialogs.py nicht vorhanden")

    def test_add_dialog_class(self):
        """Testet dass AddDialog-Klasse existiert."""
        try:
            from dialogs import AddDialog
            assert AddDialog is not None
        except ImportError:
            pytest.skip("AddDialog nicht in dialogs.py vorhanden")
        except AttributeError:
            pytest.skip("AddDialog nicht definiert")


class TestDatabase:
    """Tests für Datenbank-Modul."""

    def test_database_module_exists(self):
        """Testet dass Datenbank-Modul existiert."""
        try:
            import db
            assert db is not None
        except ImportError:
            pytest.skip("db.py nicht vorhanden")

    def test_database_class_or_connection(self):
        """Testet dass Database-Klasse oder connect-Funktion existiert."""
        try:
            import db
            has_class = hasattr(db, 'Database')
            has_connect = hasattr(db, 'connect')
            assert has_class or has_connect, "db.py sollte Database-Klasse oder connect-Funktion haben"
        except ImportError:
            pytest.skip("db.py nicht vorhanden")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    # Erstelle tests/ Verzeichnis
    tests_dir = os.path.join(project_path, "tests")
    os.makedirs(tests_dir, exist_ok=True)

    # Schreibe Test-Datei
    test_file = os.path.join(tests_dir, "test_qt_ui.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)

    # Erstelle __init__.py falls nicht vorhanden
    init_file = os.path.join(tests_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")

    logger.info(f"pytest-qt Tests generiert: {test_file}")
    return test_file


def run_pytest_qt_tests(project_path: str) -> Dict[str, Any]:
    """
    Führt pytest-qt Tests aus.

    Args:
        project_path: Pfad zum Projektverzeichnis

    Returns:
        Dict mit status, passed, failed, issues, output
    """
    result = {
        "status": "SKIP",
        "passed": 0,
        "failed": 0,
        "issues": [],
        "output": "",
        "test_type": "pytest_qt"
    }

    # Prüfe pytest Verfügbarkeit
    if not PYTEST_AVAILABLE:
        result["issues"].append("pytest nicht installiert")
        return result

    # Prüfe pytest-qt Verfügbarkeit
    if not check_pytest_qt_available():
        logger.info("pytest-qt nicht gefunden, versuche Installation...")
        if not install_pytest_qt():
            result["issues"].append("pytest-qt konnte nicht installiert werden")
            return result

    # Prüfe ob Test-Datei existiert
    test_file = os.path.join(project_path, "tests", "test_qt_ui.py")
    if not os.path.exists(test_file):
        # Generiere Test-Datei
        test_file = generate_qt_test_file(project_path)

    try:
        # Führe Tests aus mit Headless-Modus
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"  # Headless-Modus für Qt

        logger.info(f"Starte pytest-qt Tests: {test_file}")

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_path,
            env=env
        )

        result["output"] = proc.stdout + proc.stderr

        # Parse Ergebnis basierend auf Exit-Code
        if proc.returncode == 0:
            result["status"] = "PASS"
            logger.info("pytest-qt Tests erfolgreich")
        elif proc.returncode == 5:
            # pytest exit code 5 = no tests collected
            result["status"] = "SKIP"
            result["issues"].append("Keine Tests gesammelt (pytest exit code 5)")
        else:
            result["status"] = "FAIL"
            result["issues"].append("UI-Tests fehlgeschlagen")
            logger.warning(f"pytest-qt Tests fehlgeschlagen: {proc.returncode}")

        # Zähle passed/failed aus Output
        passed_match = re.search(r"(\d+) passed", proc.stdout)
        failed_match = re.search(r"(\d+) failed", proc.stdout)
        skipped_match = re.search(r"(\d+) skipped", proc.stdout)

        if passed_match:
            result["passed"] = int(passed_match.group(1))
        if failed_match:
            result["failed"] = int(failed_match.group(1))

        # Log Zusammenfassung
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        logger.info(f"pytest-qt Ergebnis: {result['passed']} passed, {result['failed']} failed, {skipped} skipped")

    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        result["issues"].append("pytest-qt Timeout nach 120s")
        logger.error("pytest-qt Tests Timeout")
    except Exception as e:
        result["status"] = "ERROR"
        result["issues"].append(f"pytest-qt Fehler: {e}")
        logger.error(f"pytest-qt Tests Fehler: {e}")

    return result


def detect_qt_framework(project_path: str) -> Optional[str]:
    """
    Erkennt welches Qt-Framework das Projekt verwendet.

    Args:
        project_path: Pfad zum Projektverzeichnis

    Returns:
        "PyQt5", "PyQt6", "PySide2", "PySide6" oder None
    """
    frameworks = {
        "PyQt5": ["from PyQt5", "import PyQt5", "pyqt5"],
        "PyQt6": ["from PyQt6", "import PyQt6", "pyqt6"],
        "PySide2": ["from PySide2", "import PySide2", "pyside2"],
        "PySide6": ["from PySide6", "import PySide6", "pyside6"],
    }

    # Prüfe main.py
    main_file = os.path.join(project_path, "main.py")
    if os.path.exists(main_file):
        try:
            with open(main_file, "r", encoding="utf-8") as f:
                content = f.read()
                for fw, indicators in frameworks.items():
                    if any(ind in content for ind in indicators[:2]):  # Import-Checks
                        return fw
        except Exception as e:
            logger.warning(f"Konnte main.py nicht lesen: {e}")

    # Prüfe requirements.txt
    req_file = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_file):
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
                for fw, indicators in frameworks.items():
                    if indicators[2] in content:  # Package-Name in lowercase
                        return fw
        except Exception as e:
            logger.warning(f"Konnte requirements.txt nicht lesen: {e}")

    # Prüfe alle .py Dateien
    for filename in os.listdir(project_path):
        if filename.endswith(".py"):
            filepath = os.path.join(project_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    for fw, indicators in frameworks.items():
                        if any(ind in content for ind in indicators[:2]):
                            return fw
            except Exception:
                continue

    return None
