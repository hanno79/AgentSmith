"""
Author: rahn
Datum: 24.01.2026
Version: 1.1
Beschreibung: Manueller Browser-Test fuer Security-Agent Verhalten.
              Oeffnet Browser, erstellt Test-Aufgabe, beobachtet Security-Feedback.
              
              AENDERUNG 05.02.2026: @pytest.mark.asyncio hinzugefuegt
"""

import pytest
import asyncio
from playwright.async_api import async_playwright
import time


@pytest.mark.asyncio
async def test_security_agent_behavior():
    """
    Testet das Security-Agent Verhalten im Browser.
    Erstellt einen Taschenrechner und beobachtet Security-Feedback.
    """
    print("[START] Starte Browser-Test fuer Security-Agent...")

    async with async_playwright() as p:
        # Browser starten (nicht headless fuer visuelle Ueberpruefung)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # 1. Frontend oeffnen
            print("[1] Oeffne Frontend...")
            await page.goto("http://localhost:5173", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Screenshot der Startseite
            await page.screenshot(path="tests/screenshots/01_startseite.png")
            print("[SCREENSHOT] Startseite")

            # 2. Nach Input-Feld suchen und Aufgabe eingeben
            print("[2] Suche Input-Feld...")

            # KORRIGIERT 24.01.2026: Richtiger Selektor fuer das Input-Feld
            input_selector = 'input[placeholder="What should the team build today?"]'

            try:
                input_field = await page.wait_for_selector(input_selector, timeout=5000)
                if input_field:
                    print(f"[OK] Input gefunden: {input_selector}")
            except:
                print(f"[ERROR] Input-Feld nicht gefunden: {input_selector}")
                input_field = None

            # 3. Aufgabe eingeben
            test_task = "Erstelle einen einfachen Taschenrechner mit HTML, CSS und JavaScript"

            if input_field:
                await input_field.fill(test_task)
                print(f"[OK] Aufgabe eingegeben: {test_task}")
                await page.screenshot(path="tests/screenshots/02_aufgabe_eingegeben.png")

                # 4. Deploy-Button finden und klicken
                deploy_btn = await page.wait_for_selector('button:has-text("Deploy")', timeout=3000)
                if deploy_btn:
                    await deploy_btn.click()
                    print("[OK] Deploy-Button geklickt")
                    await page.wait_for_timeout(2000)
                    await page.screenshot(path="tests/screenshots/03_nach_deploy.png")
                else:
                    print("[ERROR] Deploy-Button nicht gefunden")
            else:
                print("[ERROR] Kann Aufgabe nicht eingeben - Input-Feld fehlt")

            # 5. Warte auf Verarbeitung und beobachte Security-Agent
            print("[3] Warte auf Verarbeitung (max 120 Sekunden)...")

            for i in range(24):  # 24 x 5 Sekunden = 120 Sekunden
                await page.wait_for_timeout(5000)
                await page.screenshot(path=f"tests/screenshots/04_progress_{i+1}.png")

                # Pruefe auf Security-Indikatoren
                page_content = await page.content()

                # Pruefe auf aktive Verarbeitung (Status nicht mehr Idle)
                if "Working" in page_content or "Running" in page_content:
                    print(f"[WORKING] System verarbeitet... (Iteration {i+1})")

                # Pruefe auf VULNERABILITY mit FIX
                if "VULNERABILITY" in page_content:
                    print(f"[SECURITY] Vulnerability erkannt (Iteration {i+1})")
                    if "FIX:" in page_content or "LOESUNG:" in page_content:
                        print("[INFO] Loesungsvorschlaege gefunden!")

                # Pruefe auf CODE-SCAN Badge (neue Feature)
                if "CODE-SCAN" in page_content:
                    print(f"[SECURITY] Code-Scan aktiv (Iteration {i+1})")

                if "SECURE" in page_content:
                    print("[OK] Security-Check bestanden!")
                    break

                if "Success" in page_content or "erfolgreich" in page_content.lower():
                    print("[SUCCESS] Projekt erfolgreich abgeschlossen!")
                    break

                if "Failure" in page_content or "Maximale Retries" in page_content:
                    print("[WARNING] Maximale Retries erreicht")
                    break

                # Pruefe Status
                if "Status: Idle" in page_content and i > 2:
                    print(f"[INFO] System noch im Idle-Status (Iteration {i+1})")

            # 6. Finale Screenshots
            await page.screenshot(path="tests/screenshots/05_final.png")
            print("[SCREENSHOT] Finaler Screenshot gespeichert")

            # 7. Navigiere zum Security Office (falls vorhanden)
            try:
                security_link = await page.query_selector('text=Security')
                if security_link:
                    await security_link.click()
                    await page.wait_for_timeout(2000)
                    await page.screenshot(path="tests/screenshots/06_security_office.png")
                    print("[SCREENSHOT] Security Office Screenshot")
            except:
                pass

            print("\n[DONE] Browser-Test abgeschlossen!")
            print("[INFO] Screenshots gespeichert in: tests/screenshots/")

            # Halte Browser offen fuer manuelle Inspektion
            print("\n[WAIT] Browser bleibt 60 Sekunden offen fuer manuelle Inspektion...")
            await page.wait_for_timeout(60000)

        except Exception as e:
            print(f"[ERROR] Fehler: {e}")
            await page.screenshot(path="tests/screenshots/error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    # Erstelle Screenshots-Verzeichnis
    import os
    os.makedirs("tests/screenshots", exist_ok=True)

    # Fuehre Test aus
    asyncio.run(test_security_agent_behavior())
