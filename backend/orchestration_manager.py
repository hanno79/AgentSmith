import os
import json
import yaml
import re
import traceback
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List

# Agenten-Struktur (muss evtl. Pfade anpassen)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.meta_orchestrator_agent import MetaOrchestratorV2
from agents.coder_agent import create_coder
from agents.designer_agent import create_designer
from agents.reviewer_agent import create_reviewer
from agents.orchestrator_agent import create_orchestrator
from agents.researcher_agent import create_researcher
from agents.database_designer_agent import create_database_designer
from agents.techstack_architect_agent import create_techstack_architect
from agents.security_agent import create_security_agent
from agents.tester_agent import create_tester, test_web_ui, summarize_ui_result
from agents.memory_agent import update_memory, get_lessons_for_prompt
from sandbox_runner import run_sandbox
from logger_utils import log_event

from crewai import Task

class OrchestrationManager:
    def __init__(self, config_path: str = "config.yaml"):
        # Sicherstellen, dass Basis-Verzeichnisse existieren
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(os.path.join(self.base_dir, "projects"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "memory"), exist_ok=True)

        self.config_path = config_path
        self.config = self._load_config()
        self.project_path = None
        self.output_path = None
        self.tech_blueprint = {}
        self.database_schema = "Kein Datenbank-Schema."
        self.design_concept = "Kein Design-Konzept."
        self.current_code = ""
        self.is_first_run = True
        
        # Callback für UI-Updates
        self.on_log: Optional[Callable[[str, str, str], None]] = None

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _ui_log(self, agent: str, event: str, message: str):
        if self.on_log:
            self.on_log(agent, event, message)
        log_event(agent, event, message)

    def run_task(self, user_goal: str):
        try:
            self._ui_log("System", "Task Start", f"Goal: {user_goal}")
            
            # 🔎 RESEARCH PHASE (Nur beim ersten Mal)
            start_context = ""
            if self.is_first_run:
                try:
                    self._ui_log("Researcher", "Status", "Sucht Kontext...")
                    res_agent = create_researcher(self.config, self.config.get("templates", {}).get("webapp", {}))
                    res_task = Task(
                        description=f"Suche technische Details für: {user_goal}",
                        expected_output="Zusammenfassung.",
                        agent=res_agent
                    )
                    research_result = str(res_task.execute_sync())
                    start_context = f"\n\nRecherche-Ergebnisse:\n{research_result}"
                    self._ui_log("Researcher", "Result", "Recherche abgeschlossen.")
                except Exception as e:
                    self._ui_log("System", "Warning", f"Research übersprungen: {e}")

            # 🧠 META-ORCHESTRATOR
            self._ui_log("Orchestrator", "Status", "Analysiere Intent...")
            meta_orchestrator = MetaOrchestratorV2()
            plan_data = meta_orchestrator.orchestrate(user_goal + start_context)
            self._ui_log("Orchestrator", "Analysis", json.dumps(plan_data["analysis"]))

            # 📦 PROJEKTSTRUKTUR (Nur beim ersten Mal)
            if self.is_first_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = f"project_{timestamp}"
                # Absoluten Pfad verwenden für konsistentes Verhalten
                self.project_path = os.path.join(self.base_dir, "projects", project_name)
                os.makedirs(self.project_path, exist_ok=True)
                
                # 🛠️ TECHSTACK
                if "techstack_architect" in plan_data["plan"]:
                    self._ui_log("TechArchitect", "Status", "Analysiere TechStack...")
                    agent_techstack = create_techstack_architect(self.config, self.config.get("templates", {}).get("webapp", {}))
                    techstack_task = Task(
                        description=f"Entscheide TechStack für: {user_goal}",
                        expected_output="JSON-Blueprint.",
                        agent=agent_techstack
                    )
                    techstack_result = str(techstack_task.execute_sync())
                    try:
                        json_match = re.search(r'\{[^{}]*"project_type"[^{}]*\}', techstack_result, re.DOTALL)
                        if json_match:
                            self.tech_blueprint = json.loads(json_match.group())
                    except: 
                        self.tech_blueprint = {"project_type": "static_html"}
                    
                    self._ui_log("TechArchitect", "Blueprint", json.dumps(self.tech_blueprint))
                    
                    with open(os.path.join(self.project_path, "tech_blueprint.json"), "w", encoding="utf-8") as f:
                        json.dump(self.tech_blueprint, f, indent=2, ensure_ascii=False)

                # Output-Pfad deduction
                run_cmd = self.tech_blueprint.get("run_command", "")
                if "python" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "app.py")
                elif "node" in run_cmd:
                    self.output_path = os.path.join(self.project_path, "index.js")
                else:
                    self.output_path = os.path.join(self.project_path, "index.html")

                # REFINEMENT: Erstelle eine intelligente run.bat
                _pt = self.tech_blueprint.get("project_type", "webapp")
                run_bat_path = os.path.join(self.project_path, "run.bat")
                run_bat_content = "@echo off\n"
                run_bat_content += "echo Launching Multi-Agent Project...\n"
                
                # Check for dependencies
                if self.tech_blueprint.get("language") == "python":
                    run_bat_content += "if not exist venv ( python -m venv venv )\n"
                    run_bat_content += "call venv\\Scripts\\activate\n"
                    if self.tech_blueprint.get("install_command"):
                        run_bat_content += f"call {self.tech_blueprint['install_command']}\n"
                elif self.tech_blueprint.get("language") == "javascript":
                    if self.tech_blueprint.get("install_command"):
                        run_bat_content += f"call {self.tech_blueprint['install_command']}\n"

                # Browser opening
                if _pt == "webapp" or self.output_path.endswith(".html"):
                    # URL ermitteln (default localhost:5000 für Flask, :8000 für FastAPI/Uvicorn, oder file://)
                    url = "index.html"
                    if "flask" in str(self.tech_blueprint).lower(): url = "http://localhost:5000"
                    elif "fastapi" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
                    elif "uvicorn" in str(self.tech_blueprint).lower(): url = "http://localhost:8000"
                    
                    if url.startswith("http"):
                        run_bat_content += f"start {url}\n"
                    else:
                        run_bat_content += f"start {os.path.basename(self.output_path)}\n"

                # Execute main command
                if run_cmd:
                    run_bat_content += f"{run_cmd}\n"
                
                run_bat_content += "pause\n"
                
                with open(run_bat_path, "w", encoding="utf-8") as f:
                    f.write(run_bat_content)
                self._ui_log("System", "Config", "run.bat created.")

            # 🧩 AGENTEN INITIALISIERUNG
            project_type = self.tech_blueprint.get("project_type", "webapp")
            project_rules = self.config.get("templates", {}).get(project_type, {})
            
            agent_coder = create_coder(self.config, project_rules)
            agent_reviewer = create_reviewer(self.config, project_rules)
            agent_tester = create_tester(self.config, project_rules)
            
            # Design & DB (Nur beim ersten Mal)
            if self.is_first_run:
                if "database_designer" in plan_data["plan"]:
                    self._ui_log("DBDesigner", "Status", "Erstelle Schema...")
                    agent_db = create_database_designer(self.config, project_rules)
                    if agent_db:
                        task_db = Task(description=f"Schema für {user_goal}", expected_output="Schema", agent=agent_db)
                        self.database_schema = str(task_db.execute_sync())
                
                if "designer" in plan_data["plan"]:
                    self._ui_log("Designer", "Status", "Erstelle Design-Konzept...")
                    agent_des = create_designer(self.config, project_rules)
                    if agent_des:
                        task_des = Task(description=f"Design für {user_goal}", expected_output="Konzept", agent=agent_des)
                        self.design_concept = str(task_des.execute_sync())

            # 🔄 DEV LOOP
            max_retries = self.config.get("max_retries", 3)
            feedback = ""
            iteration = 0
            success = False

            while iteration < max_retries:
                self._ui_log("Coder", "Iteration", f"{iteration+1} / {max_retries}")
                
                c_prompt = f"Ziel: {user_goal}\nTech: {self.tech_blueprint}\nDB: {self.database_schema[:200]}\n"
                if not self.is_first_run: c_prompt += f"\nAlt-Code:\n{self.current_code}\n"
                if feedback: c_prompt += f"\nKorrektur: {feedback}\n"
                c_prompt += "Format: ### FILENAME: path/to/file.ext"

                task_coder = Task(description=c_prompt, expected_output="Code", agent=agent_coder)
                self.current_code = str(task_coder.execute_sync()).strip()
                
                # Speichern
                from main import save_multi_file_output
                def_file = os.path.basename(self.output_path)
                created_files = save_multi_file_output(self.project_path, self.current_code, def_file)
                self._ui_log("Coder", "Files", f"Created: {', '.join(created_files)}")

                # Sandbox
                sandbox_result = run_sandbox(self.current_code)
                self._ui_log("Sandbox", "Result", sandbox_result)
                sandbox_failed = sandbox_result.startswith("❌")

                # UI Testing (Playwright) - nur wenn relevant
                test_summary = "Keine UI-Tests durchgeführt."
                if project_type == "webapp" or (self.output_path and self.output_path.endswith((".html", ".js"))):
                    self._ui_log("Tester", "Status", "Starte UI-Tests...")
                    try:
                        ui_result = test_web_ui(self.output_path)
                        test_summary = summarize_ui_result(ui_result)
                        self._ui_log("Tester", "Result", test_summary)
                        if ui_result["status"] == "FAIL":
                            sandbox_failed = True # UI-Fehler blockieren auch
                    except Exception as te:
                        test_summary = f"❌ Test-Runner Fehler: {te}"
                        self._ui_log("Tester", "Error", test_summary)
                        sandbox_failed = True

                # Review
                r_prompt = f"Review Code: {self.current_code[:500]}\nSandbox: {sandbox_result}\nTester: {test_summary}"
                task_review = Task(description=r_prompt, expected_output="OK/Feedback", agent=agent_reviewer)
                review_output = str(task_review.execute_sync())
                
                # STRIKTER CHECK: Wenn Sandbox/Tester '❌' liefert, darf Reviewer nicht 'OK' sagen
                if "OK" in review_output.upper() and not sandbox_failed:
                    success = True
                    self._ui_log("Reviewer", "Status", "Code OK.")
                    break
                else:
                    feedback = review_output
                    if sandbox_failed and "OK" in review_output.upper():
                        feedback = f"KRITISCHER FEHLER: Die Sandbox oder der Tester hat Fehler (❌) gemeldet, aber du hast OK gesagt. Bitte analysiere die Fehlermeldungen erneut:\n{sandbox_result}\n{test_summary}"
                    
                    self._ui_log("Reviewer", "Feedback", feedback)
                    iteration += 1

            self.is_first_run = False
            if success:
                self._ui_log("System", "Success", "Projekt erfolgreich erstellt/geändert.")
            else:
                self._ui_log("System", "Failure", "Maximale Retries erreicht.")

        except Exception as e:
            err = f"Fehler: {e}\n{traceback.format_exc()}"
            self._ui_log("System", "Error", err)
            raise e
