from crewai import Agent

def create_reviewer(config, project_rules):
    """
    Erstellt den Reviewer-Agenten, der Codequalität, Funktionalität
    und Regelkonformität überprüft.
    """
    mode = config["mode"]
    model = config["models"][mode]["reviewer"]

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("reviewer", []))
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nReviewer-spezifische Regeln:\n{role_rules}"

    return Agent(
        role="Reviewer",
        goal=(
            "Analysiere Code, Testergebnisse und Sandbox-Ausgaben kritisch. "
            "Finde alle Fehler, Regelverstöße oder Schwachstellen. "
            "Bewerte auch Laufzeitfehler aus der Sandbox (z. B. SyntaxError, Traceback, ModuleNotFoundError) "
            "als kritische Fehler, die eine Überarbeitung erfordern. "
            "Achte darauf, ob der Code tatsächlich fehlerfrei ausgeführt wurde. "
            "WICHTIG: Wenn die Sandbox oder der Tester ein Ergebnis mit '❌' liefern, "
            "darfst du UNTER KEINEN UMSTÄNDEN mit 'OK' antworten. Der Fehler muss erst behoben werden. "
            "Nur wenn die Ausführung erfolgreich war und alle Projektregeln eingehalten wurden, "
            "antworte am Ende klar mit 'OK'."
        ),
        backstory=(
            "Du bist ein erfahrener Software-Tester und Code-Reviewer. "
            "Deine Aufgabe ist es, Code gründlich zu prüfen: Funktion, Stil, Robustheit, "
            "und Regelkonformität. "
            "Wenn du im Ausführungsergebnis Fehlermeldungen siehst, "
            "erkläre die Ursache, gib konkrete Verbesserungsvorschläge "
            "und antworte keinesfalls mit 'OK', bis der Fehler behoben ist.\n\n"
            f"{combined_rules}"
        ),
        model=model,
        verbose=True,
        allow_delegation=False
    )
