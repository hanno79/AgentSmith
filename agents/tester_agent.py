from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
import time
from crewai import Agent

def create_tester(config, project_rules):
    """
    Erstellt den Tester-Agenten, der UI-Tests durchführt.
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
        model=model,
        verbose=True
    )

def test_web_ui(file_path: str) -> dict:
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
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text))
            page.goto(file_url)
            page.wait_for_load_state("networkidle")

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


def compare_images(baseline_path: Path, new_path: Path):
    """Vergleicht zwei Screenshots Pixel-für-Pixel und gibt eine Differenz-Map zurück, falls Unterschiede existieren."""
    base_img = Image.open(baseline_path).convert("RGB")
    new_img = Image.open(new_path).convert("RGB")
    diff = ImageChops.difference(base_img, new_img)
    return diff if diff.getbbox() else None

def summarize_ui_result(ui_result: dict) -> str:
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
