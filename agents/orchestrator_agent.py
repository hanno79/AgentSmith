from crewai import Agent

def create_orchestrator(config, project_rules):
    """
    Erstellt den Orchestrator-Agenten, der als Projektleiter fungiert.
    Er überwacht die Einhaltung von Regeln und erstellt die Abschlussdokumentation.
    """
    mode = config.get("mode", "test")
    # Fallback if model logic isn't perfectly strict in config
    model = config.get("models", {}).get(mode, {}).get("orchestrator", "gpt-4")

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("orchestrator", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nOrchestrator-spezifische Regeln:\n{role_rules}"

    return Agent(
        role="Orchestrator",
        goal="Überwache den Entwicklungsprozess, prüfe Regelkonformität und erstelle Dokumentation.",
        backstory=(
            "Du bist ein erfahrener technischer Projektleiter (Technical Lead). "
            "Deine Aufgabe ist es, sicherzustellen, dass das Team (Coder, Reviewer) "
            "alle globalen und spezifischen Projektregeln einhält. "
            "Am Ende des Projekts erstellst du eine saubere Dokumentation.\n\n"
            "Du bist streng, aber konstruktiv.\n"
            f"{combined_rules}"
        ),
        model=model,
        verbose=True
    )
