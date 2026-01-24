# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.01.2026
Version: 3.1
Beschreibung: Multi-Agenten Proof-of-Concept - Haupteinstiegspunkt.
              Orchestriert alle Agenten mit iterativem Feedback-Loop, Logging und Regelüberwachung.
"""

import os
import json
import time
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Lade .env aus dem Projektverzeichnis (nicht CWD!)
# Dies stellt sicher, dass die .env gefunden wird, unabhängig vom Arbeitsverzeichnis
_project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_project_root, ".env"), override=True)

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

# 🧩 Importiere Agenten
from agents.meta_orchestrator_agent import MetaOrchestratorV2
from agents.coder_agent import create_coder
from agents.designer_agent import create_designer
from agents.reviewer_agent import create_reviewer
from agents.tester_agent import create_tester, test_web_ui, summarize_ui_result
from agents.orchestrator_agent import create_orchestrator
from agents.researcher_agent import create_researcher
from agents.database_designer_agent import create_database_designer
from agents.techstack_architect_agent import create_techstack_architect
from agents.security_agent import create_security_agent
from agents.memory_agent import (
    update_memory, get_lessons_for_prompt, learn_from_error,
    extract_error_pattern, generate_tags_from_context
)
from sandbox_runner import run_sandbox
from logger_utils import log_event # Added Logger
from security_utils import safe_join_path, sanitize_filename, validate_shell_command
from exceptions import SecurityError

# CrewAI Imports
from crewai import Task, Crew

# Rich-Console Setup
console = Console()

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_multi_file_output(project_path: str, code_output: str, default_filename: str):
    """
    Parst den Output des Coders und speichert mehrere Dateien,
    wenn das Format ### FILENAME: ... gefunden wird.
    Sonst Fallback auf default_filename.
    """
    import re
    # Pattern: ### [KEYWORD:] Pfad/zur/Datei.ext
    # Wir machen den Präfix (FILENAME:, FILE:, PATH:) optional und fangen nur den Pfad ein.
    pattern = r"###\s*(?:[\w\s]+:\s*)?(.+?)\s*[\r\n]+"
    parts = re.split(pattern, code_output)
    
    # Wenn kein Split (oder nur 1 Teil), dann kein Multi-File-Format
    if len(parts) < 2:
        # Fallback: Alles in eine Datei
        file_path = os.path.join(project_path, default_filename)
        # Bugfix: Sicherstellen, dass der Ordner existiert
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_output)
        return [file_path]

    created_files = []
    # Start bei Index 1, da Index 0 der Preamble ist
    for i in range(1, len(parts), 2):
        raw_filename = parts[i].strip()
        content = parts[i+1].strip()

        # SECURITY FIX: Nutze sichere Sanitization (entfernt Präfixe, .., illegale Zeichen)
        filename = sanitize_filename(raw_filename)

        # Überspringe leere Dateinamen nach Sanitization
        if not filename:
            console.print(f"[yellow]⚠️ Ungültiger Dateiname übersprungen: {raw_filename[:50]}[/yellow]")
            continue

        # Code-Blöcke entfernen
        content = content.replace("```html", "").replace("```python", "").replace("```css", "").replace("```javascript", "").replace("```json", "").replace("```", "")

        # Markdown-Artefakte (---, ***, ===) an Zeilenanfang/-ende entfernen
        lines = content.splitlines()
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Falls Zeile nur aus -, * oder = besteht (mind. 3), überspringen (Markdown-Trenner)
            if re.match(r"^[-*=]{3,}$", stripped):
                continue
            cleaned_lines.append(line)
        content = "\n".join(cleaned_lines).strip()

        # SECURITY FIX: Nutze safe_join_path mit Containment-Check
        try:
            full_path = safe_join_path(project_path, filename)
        except SecurityError as e:
            console.print(f"[red]⚠️ Sicherheitswarnung - Datei übersprungen: {e}[/red]")
            log_event("Security", "Path Traversal Blocked", f"Filename: {raw_filename}")
            continue

        # Sicherstellen, dass der Ordner existiert
        dir_name = os.path.dirname(full_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        created_files.append(filename)
        
    return created_files

def main():
    console.print("[bold cyan]🤖 Willkommen zum Multi-Agenten-System v3.1 (Self-Healing & Logs)[/bold cyan]")
    
    # Konfiguration laden
    try:
        config = load_config()
    except Exception as e:
        console.print(f"[bold red]❌ Fehler beim Laden der config.yaml: {e}[/bold red]")
        return
    
    # Absoluten Pfad verwenden für konsistentes Verhalten
    base_dir = os.path.dirname(os.path.abspath(__file__))
    memory_path = os.path.join(base_dir, "memory", "global_memory.json")
    os.makedirs(os.path.join(base_dir, "memory"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "projects"), exist_ok=True)

    # Session-State
    project_path = None
    output_path = None
    tech_blueprint = {
        "project_type": "static_html",
        "database": None,
        "frontend": "embedded",
        "reasoning": "Initial state"
    }
    database_schema = "Kein Datenbank-Schema."
    design_concept = "Kein Design-Konzept."
    current_code = ""
    is_first_run = True

    while True:
        try:
            # User Input
            if is_first_run:
                user_goal = console.input("[bold blue]Was soll entwickelt werden? [/bold blue]").strip()
            else:
                console.print("\n[bold green]--------------------------------------------------[/bold green]")
                user_goal = console.input("[bold green]Was soll als Nächstes geändert werden? (exit zum Beenden): [/bold green]").strip()
            
            if not user_goal or user_goal.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Beende Multi-Agenten-System. Auf Wiedersehen![/yellow]")
                break

            log_event("System", "Input Received", f"Goal: {user_goal} (First Run: {is_first_run})")

            # 🔎 RESEARCH PHASE (Nur beim ersten Mal)
            start_context = ""
            if is_first_run:
                try:
                    res_agent = create_researcher(config, config.get("templates", {}).get("webapp", {}))
                    console.print(Panel.fit("Researcher sucht Kontext...", title="🔎 Research", border_style="green"))
                    res_task = Task(
                        description=f"Suche technische Details für: {user_goal}",
                        expected_output="Zusammenfassung.",
                        agent=res_agent
                    )
                    research_result = res_task.execute_sync()
                    start_context = f"\n\nRecherche-Ergebnisse:\n{research_result}"
                except Exception as e:
                    console.print(f"[yellow]⚠️ Research übersprungen: {e}[/yellow]")

            # 🧠 META-ORCHESTRATOR
            meta_orchestrator = MetaOrchestratorV2()
            plan_data = meta_orchestrator.orchestrate(user_goal + start_context)

            console.print(Panel.fit(
                json.dumps(plan_data["analysis"], indent=2, ensure_ascii=False),
                title="🧠 Analyseergebnis",
                border_style="cyan"
            ))

            # 📦 PROJEKTSTRUKTUR (Nur beim ersten Mal)
            if is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = f"project_{timestamp}"
                # Absoluten Pfad verwenden für konsistentes Verhalten
                project_path = os.path.join(base_dir, "projects", project_name)
                os.makedirs(project_path, exist_ok=True)
                
                # 🛠️ TECHSTACK
                if "techstack_architect" in plan_data["plan"]:
                    console.print(Panel.fit("TechStack-Architect analysiert...", title="🛠️ TechStack", border_style="yellow"))
                    agent_techstack = create_techstack_architect(config, config.get("templates", {}).get(config.get("project_type", "webapp"), {}))
                    techstack_task = Task(
                        description=f"Entscheide TechStack für: {user_goal}",
                        expected_output="JSON-Blueprint.",
                        agent=agent_techstack
                    )
                    techstack_result = str(techstack_task.execute_sync())
                    try:
                        import re
                        json_match = re.search(r'\{[^{}]*"project_type"[^{}]*\}', techstack_result, re.DOTALL)
                        if json_match:
                            tech_blueprint = json.loads(json_match.group())
                    except: pass
                    
                    with open(os.path.join(project_path, "tech_blueprint.json"), "w", encoding="utf-8") as f:
                        json.dump(tech_blueprint, f, indent=2, ensure_ascii=False)
                        
                    # Deps & Scripts
                    dependencies = tech_blueprint.get("dependencies", [])
                    package_file = tech_blueprint.get("package_file", "requirements.txt")
                    if dependencies:
                        # SECURITY FIX: Validiere package_file gegen Path Traversal
                        try:
                            req_path = safe_join_path(project_path, sanitize_filename(package_file))
                        except SecurityError as e:
                            console.print(f"[yellow]⚠️ Ungültiger package_file Pfad ignoriert: {e}[/yellow]")
                            req_path = os.path.join(project_path, "requirements.txt")  # Sicherer Fallback
                            package_file = "requirements.txt"

                        if package_file == "package.json":
                            pkg_content = {"name": project_name, "version": "1.0.0", "dependencies": {dep: "*" for dep in dependencies}}
                            with open(req_path, "w", encoding="utf-8") as f: json.dump(pkg_content, f, indent=2)
                        else:
                            with open(req_path, "w", encoding="utf-8") as f: f.write("\n".join(dependencies))

                    # run.bat - SECURITY FIX: Validiere Befehle gegen Command Injection
                    run_cmd = tech_blueprint.get("run_command", "")
                    install_cmd = tech_blueprint.get("install_command", "")

                    # Validiere run_command
                    if run_cmd and not validate_shell_command(run_cmd):
                        console.print(f"[yellow]⚠️ Ungültiger run_command ignoriert: {run_cmd[:50]}[/yellow]")
                        log_event("Security", "Command Injection Blocked", f"run_command: {run_cmd}")
                        run_cmd = ""

                    # Validiere install_command
                    if install_cmd and not validate_shell_command(install_cmd):
                        console.print(f"[yellow]⚠️ Ungültiger install_command ignoriert: {install_cmd[:50]}[/yellow]")
                        log_event("Security", "Command Injection Blocked", f"install_command: {install_cmd}")
                        install_cmd = ""

                    run_bat_content = "@echo off\n"
                    if tech_blueprint.get("language") == "python":
                        run_bat_content += "if not exist venv ( python -m venv venv )\ncall venv\\Scripts\\activate\n"
                    if install_cmd:
                        run_bat_content += f"call {install_cmd}\n"
                    if run_cmd:
                        run_bat_content += f"{run_cmd}\n"
                    else:
                        run_bat_content += f"start {project_name}.html\n"
                    run_bat_content += "pause\n"
                    with open(os.path.join(project_path, "run.bat"), "w", encoding="utf-8") as f: f.write(run_bat_content)

                # Output-Pfad deduction
                run_cmd = tech_blueprint.get("run_command", "")
                if "python" in run_cmd:
                    if "app.py" in run_cmd: output_path = os.path.join(project_path, "app.py")
                    elif "main.py" in run_cmd: output_path = os.path.join(project_path, "main.py")
                    else: output_path = os.path.join(project_path, "script.py")
                elif "node" in run_cmd: output_path = os.path.join(project_path, "index.js")
                elif "html" in run_cmd: output_path = os.path.join(project_path, f"{project_name}.html")
                else: output_path = os.path.join(project_path, "main_code.txt")

            # 🧩 AGENTEN
            project_type = tech_blueprint.get("project_type", config.get("project_type", "webapp"))
            project_rules = config.get("templates", {}).get(project_type, {})
            
            agent_coder = create_coder(config, project_rules)
            agent_reviewer = create_reviewer(config, project_rules)
            agent_orchestrator = create_orchestrator(config, project_rules)
            agent_security = create_security_agent(config, project_rules)
            
            # Memory
            lessons = get_lessons_for_prompt(memory_path, tech_stack=project_type)
            if lessons: 
                if "global" not in project_rules: project_rules["global"] = []
                project_rules["global"].append("\n*** LESSONS LEARNED ***\n" + lessons)

            # Design & DB (Nur beim ersten Mal)
            if is_first_run:
                if "database_designer" in plan_data["plan"]:
                    agent_db = create_database_designer(config, project_rules)
                    if agent_db:
                        task_db = Task(
                            description=f"Erstelle ein Datenbank-Schema für: {user_goal}",
                            expected_output="Schema-Definition",
                            agent=agent_db
                        )
                        database_schema = str(task_db.execute_sync())
                
                if "designer" in plan_data["plan"] and config.get("include_designer"):
                    agent_des = create_designer(config, project_rules)
                    if agent_des:
                        task_des = Task(
                            description=f"Erstelle ein Design-Konzept für: {user_goal}",
                            expected_output="Design-Konzept",
                            agent=agent_des
                        )
                        design_concept = str(task_des.execute_sync())

            # 🔄 DEV LOOP
            max_retries = config.get("max_retries", 3)
            feedback = ""
            success = False
            iteration = 0

            while iteration < max_retries:
                console.print(f"[bold yellow]🔄 Iteration {iteration+1} / {max_retries}[/bold yellow]")
                
                c_prompt = f"Ziel: {user_goal}\nTech: {tech_blueprint}\nDB: {database_schema[:200]}\n"
                if not is_first_run: c_prompt += f"\nCode-Status:\n{current_code}\n"
                if feedback: c_prompt += f"\nFehler: {feedback}\n"
                c_prompt += "Gib den Output im ### FILENAME: Format aus."

                task_coder = Task(description=c_prompt, expected_output="Source Code", agent=agent_coder)
                current_code = str(task_coder.execute_sync()).strip()
                
                # Save
                def_file = os.path.basename(output_path) if output_path else "main.py"
                created_files = save_multi_file_output(project_path, current_code, def_file)
                console.print(f"[blue]Dateien: {created_files}[/blue]")

                # Sandbox
                c_main = current_code
                if output_path and os.path.exists(output_path):
                    with open(output_path, "r", encoding="utf-8") as f: c_main = f.read()
                
                sandbox_result = run_sandbox(c_main)
                console.print(f"[cyan]Sandbox:[/cyan] {sandbox_result}")

                # Review
                r_prompt = f"Check Code: {current_code[:200]}\nSandbox: {sandbox_result}\nAntworte mit OK oder Fehlern."
                task_review = Task(description=r_prompt, expected_output="Feedback", agent=agent_reviewer)
                review_output = str(task_review.execute_sync())
                
                # Memory: Zeichne Iteration auf
                update_memory(memory_path, current_code, review_output, sandbox_result)

                if "OK" in review_output:
                    success = True
                    console.print("[dim]Memory: Erfolgreiche Iteration aufgezeichnet.[/dim]")
                    break
                else:
                    feedback = review_output
                    # Memory: Lerne aus Fehlern
                    if "❌" in sandbox_result or "error" in feedback.lower():
                        error_msg = extract_error_pattern(sandbox_result if "❌" in sandbox_result else feedback)
                        tags = generate_tags_from_context(tech_blueprint, error_msg)
                        learn_result = learn_from_error(memory_path, error_msg, tags)
                        console.print(f"[dim]Memory: {learn_result}[/dim]")
                    iteration += 1

            # Abschluss Aktuelle Runde
            is_first_run = False
            if success:
                console.print("[bold green]✅ Erfolg![/bold green]")

                # 🛡️ SECURITY SCAN (nach erfolgreichem Review)
                try:
                    console.print(Panel.fit("Security Agent prüft Code...", title="🛡️ Security Scan", border_style="red"))
                    # Erstelle Tasks pro Datei statt Truncation
                    import re
                    # Parse Code-Output um Dateien zu extrahieren
                    code_pattern = r"###\s*(?:[\w\s]+:\s*)?(.+?)\s*[\r\n]+"
                    code_parts = re.split(code_pattern, current_code)
                    security_results = []
                    
                    if len(code_parts) >= 2:
                        # Multi-File Format
                        for i in range(1, len(code_parts), 2):
                            filename = code_parts[i].strip()
                            file_content = code_parts[i+1].strip() if i+1 < len(code_parts) else ""
                            if filename and file_content:
                                security_task = Task(
                                    description=f"Prüfe die Datei '{filename}' auf Sicherheitslücken (SQL Injection, XSS, CSRF, Hardcoded Secrets):\n\n{file_content}",
                                    expected_output="SECURE oder Liste von VULNERABILITY: ...",
                                    agent=agent_security
                                )
                                result = str(security_task.execute_sync())
                                security_results.append(f"Datei: {filename}\n{result}")
                    else:
                        # Single-File Format - verwende vollständigen Code
                        if len(current_code) > 100000:  # Warnung bei sehr großem Code
                            log_event("Security", "Warning", f"Code sehr groß ({len(current_code)} Zeichen), vollständiger Scan kann lange dauern")
                        security_task = Task(
                            description=f"Prüfe den folgenden Code auf Sicherheitslücken (SQL Injection, XSS, CSRF, Hardcoded Secrets):\n\n{current_code}",
                            expected_output="SECURE oder Liste von VULNERABILITY: ...",
                            agent=agent_security
                        )
                        security_results.append(str(security_task.execute_sync()))
                    
                    # Sicherstellen dass security_result immer definiert ist
                    security_result = "\n\n".join(security_results) if security_results else "Keine Dateien zum Scannen gefunden."
                    log_event("Security", "Scan Complete", security_result[:1000])

                    if "VULNERABILITY" in security_result.upper():
                        console.print(Panel.fit(
                            security_result[:2000],
                            title="⚠️ Sicherheitswarnung",
                            border_style="yellow"
                        ))
                        # Optional: Speichere Security-Report
                        security_report_path = os.path.join(project_path, "SECURITY_REPORT.md")
                        with open(security_report_path, "w", encoding="utf-8") as f:
                            f.write(f"# Security Report\n\n{security_result}")
                        console.print(f"[yellow]Security-Report gespeichert: {security_report_path}[/yellow]")
                    else:
                        console.print("[bold green]🛡️ Security Check: SECURE[/bold green]")
                except Exception as e:
                    console.print(f"[yellow]⚠️ Security-Scan übersprungen: {e}[/yellow]")

                # 📝 README generieren
                if agent_orchestrator:
                    doc_task = Task(description=f"README für {user_goal}", expected_output="Markdown", agent=agent_orchestrator)
                    doc = doc_task.execute_sync()
                    with open(os.path.join(project_path, "README.md"), "w", encoding="utf-8") as f: f.write(str(doc))
            else:
                console.print("[bold red]❌ Fehlgeschlagen nach Retries.[/bold red]")
                # Memory: Lerne aus ungelösten Fehlern
                if feedback:
                    error_msg = extract_error_pattern(feedback)
                    tags = generate_tags_from_context(tech_blueprint, feedback)
                    tags.append("unresolved")
                    learn_result = learn_from_error(memory_path, error_msg, tags)
                    console.print(f"[dim]Memory: Ungelöst - {learn_result}[/dim]")

        except Exception as e:
            import traceback
            console.print(f"[bold red]💥 Ein kritischer Fehler ist aufgetreten:[/bold red] {e}")
            console.print(traceback.format_exc())
            # Falls wir im is_first_run stecken geblieben sind, vielleicht zurücksetzen oder abbrechen?
            # Wir lassen die Schleife laufen, damit der User es nochmal versuchen kann.

if __name__ == "__main__":
    main()
