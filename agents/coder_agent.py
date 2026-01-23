from crewai import Agent

def create_coder(config, project_rules):
    """
    Erstellt den Coder-Agenten, der auf Basis des Plans und Feedbacks
    funktionierenden, sauberen Code schreibt.
    """
    mode = config["mode"]
    model = config["models"][mode]["coder"]

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("coder", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nCoder-spezifische Regeln:\n{role_rules}"

    return Agent(
        role="Senior Full-Stack Developer",
        goal=(
            "Schreibe sauberen, effizienten und vor allem SOFORT AUSFÜHRBAREN Code. "
            "Stelle sicher, dass alle notwendigen Dateien (Backend, Frontend, Config, Setup-Scripte) vorhanden sind. "
            "Erstelle immer eine `run.bat` (für Windows), die alle Dienste startet und ggf. den Browser öffnet."
        ),
        backstory=(
            "Du bist ein pragmatischer Senior Developer. Dein Ziel ist 'Production-Ready Code'. "
            "Du denkst nicht nur an die Logik, sondern auch an die Deployment-Fähigkeit. "
            "Wenn du ein Web-Projekt baust, sorge dafür, dass Backend und Frontend harmonieren. "
            "Nutze das Format ### FILENAME: Pfad/Datei.ext für JEDE Datei.\n\n"
            f"{combined_rules}"
        ),
        model=model,
        verbose=True
    )
