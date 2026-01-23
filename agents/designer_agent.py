from crewai import Agent

def create_designer(config, project_rules):
    """
    Erstellt den Designer-Agenten, der UI/UX-Konzepte oder visuelle Entwürfe vorschlägt.
    Wird nur aktiviert, wenn include_designer in der config.yaml = true ist.
    """
    mode = config["mode"]
    model = config["models"][mode]["designer"]

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("designer", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nDesigner-spezifische Regeln:\n{role_rules}"

    return Agent(
        role="Designer",
        goal=(
            "Erstelle klare UI/UX-Konzepte inklusive technischer Design-Specs. "
            "Liefere konkrete CSS-Variablen (:root), Farbcodes (HEX/RGB) und Layout-Anweisungen, "
            "die ein Entwickler direkt in CSS umsetzen kann."
        ),
        backstory=(
            "Du bist ein erfahrener UI/UX-Designer, der einfache, elegante und funktionale "
            "Designkonzepte entwickelt. Du vermeidest generische 'AI-Farbverläufe' (wie Violett/Neon) "
            "und setzt auf sauberes 'Flat Design', gute Typografie (Inter/Roboto) und Whitespace.\n\n"
            f"{combined_rules}"
        ),
        model=model,
        verbose=True
    )
