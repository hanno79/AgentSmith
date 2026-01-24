# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 1.0
Beschreibung: Tester Agent - Führt UI-Tests mit Playwright durch und erkennt visuelle Unterschiede.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
import time
from crewai import Agent


class UITestResult(TypedDict):
    """Typdefinition für UI-Testergebnisse."""
    status: str  # "OK", "FAIL", "REVIEW", "BASELINE", "ERROR"
    issues: List[str]
    screenshot: Optional[str]


def create_tester(config: Dict[str, Any], project_rules: Dict[str, List[str]]) -> Agent:
    """
    Erstellt den Tester-Agenten, der UI-Tests durchführt.

    Args:
        config: Anwendungskonfiguration mit mode und models
        project_rules: Dictionary mit globalen und rollenspezifischen Regeln

    Returns:
        Konfigurierte CrewAI Agent-Instanz
    """
    mode = config["mode"]
    # Fallback to reviewer model if tester model not specified
    model = config["models"][mode].get("tester", config["models"][mode]["reviewer"])

    return Agent(
        role="Tester",
        goal="Überprüfe die Benutzeroberfläche auf visuelle Fehler und Funktionalität.",
        backstory=(
            "Du bist ein detailgenauer Tester. Du nutzt Tools wie Playwright, "
            "um Screenshots zu vergleichen und die Funktionalität von Webseiten zu prüfen."
        ),
        llm=model,
        verbose=True
    )

def test_web_ui(file_path: str) -> UITestResult:
    """
    Führt UI-Tests mit Playwright durch, erstellt Screenshots und erkennt visuelle Unterschiede.
    Gibt ein Dictionary mit Testergebnissen zurück.
    """
    file_url = Path(file_path).absolute().as_uri()
    project_dir = Path(file_path).parent
    screenshots_dir = project_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshots_dir / f"ui_test_{timestamp}.png"
    baseline_path = screenshots_dir / "baseline.png"

    result = {
        "status": "OK",
        "issues": [],
        "screenshot": str(screenshot_path)
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # KRITISCH: Global Timeout setzen, um Hänger zu verhindern
            page.set_default_timeout(10000)  # 10 Sekunden max

            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text))

            # Goto mit Timeout und schnellerem wait_until (domcontentloaded statt networkidle)
            page.goto(file_url, timeout=10000, wait_until="domcontentloaded")

            # Optionales networkidle mit kurzem Timeout (3s) - blockiert nicht bei fehlenden Ressourcen
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass  # OK, DOM ist bereits geladen - Screenshot kann trotzdem erstellt werden

            # Screenshot
            page.screenshot(path=screenshot_path, full_page=True)
            browser.close()

        # Grundlegende Checks
        if not Path(screenshot_path).exists():
            result["issues"].append("❌ Kein Screenshot erstellt.")
        if any("error" in msg.lower() for msg in console_errors):
            result["issues"].append("❌ JavaScript-Fehler im DOM-Log erkannt.")

        # Pixelvergleich (nur wenn Baseline vorhanden)
        if baseline_path.exists():
            diff_img = compare_images(baseline_path, screenshot_path)
            if diff_img:
                diff_path = screenshots_dir / f"diff_{timestamp}.png"
                diff_img.save(diff_path)
                result["issues"].append(f"⚠️ Visuelle Änderung erkannt – siehe {diff_path}")
                result["status"] = "REVIEW"
        else:
            # Erste Version → als Baseline speichern
            Path(screenshot_path).replace(baseline_path)
            result["issues"].append("🟢 Neue Baseline gespeichert.")
            result["status"] = "BASELINE"

        if result["issues"]:
            if any(x.startswith("❌") for x in result["issues"]):
                result["status"] = "FAIL"
        return result

    except Exception as e:
        return {"status": "ERROR", "issues": [f"❌ Playwright-Fehler: {e}"], "screenshot": None}


def compare_images(baseline_path: Path, new_path: Path) -> Optional[Image.Image]:
    """Vergleicht zwei Screenshots Pixel-für-Pixel und gibt eine Differenz-Map zurück, falls Unterschiede existieren."""
    base_img = Image.open(baseline_path).convert("RGB")
    new_img = Image.open(new_path).convert("RGB")
    
    # Normalisiere Bildgrößen falls unterschiedlich
    if base_img.size != new_img.size:
        target_size = (max(base_img.width, new_img.width), max(base_img.height, new_img.height))
        # Erstelle neue Leinwände mit schwarzem Hintergrund
        normalized_base = Image.new("RGB", target_size, (0, 0, 0))
        normalized_new = Image.new("RGB", target_size, (0, 0, 0))
        # Füge Bilder in die Leinwände ein (oben links)
        normalized_base.paste(base_img, (0, 0))
        normalized_new.paste(new_img, (0, 0))
        base_img = normalized_base
        new_img = normalized_new
    
    diff = ImageChops.difference(base_img, new_img)
    return diff if diff.getbbox() else None

def summarize_ui_result(ui_result: UITestResult) -> str:
    """
    Liefert eine kurze textuelle Zusammenfassung der Testergebnisse
    für den Designer-Agenten oder den Memory-Agenten.
    """
    summary = f"Testergebnis: {ui_result['status']}. "
    if ui_result["issues"]:
        summary += "Probleme: " + "; ".join(ui_result["issues"])
    else:
        summary += "Keine visuellen Probleme erkannt."
    return summary
