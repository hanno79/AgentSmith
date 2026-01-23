from crewai import Agent

def create_security_agent(config, project_rules):
    """
    Erstellt den Security-Agenten ("The Guardian"), der Code auf Sicherheitslücken prüft.
    Fokus: OWASP Top 10, Dependency-Audits (Simulation), Injection-Prevention.
    """
    mode = config["mode"]
    # Fallback to reviewer model if security model not explicitly set (though we added it to config)
    model = config["models"][mode].get("security", config["models"][mode]["reviewer"])

    global_rules = "\n".join(project_rules.get("global", []))
    role_rules = "\n".join(project_rules.get("security", [])) # Specific security rules
    combined_rules = f"Globale Regeln:\n{global_rules}\n\nSecurity-Regeln:\n{role_rules}"

    return Agent(
        role="Security Specialist (The Guardian)",
        goal=(
            "Analysiere den Code radikal auf Sicherheitslücken. "
            "Denke wie ein Hacker (White Hat). "
            "Prüfe auf SQL-Injection, XSS, CSRF, unsichere Dependencies und Hardcoded Secrets. "
            "Lasse NIEMALS Code durch, der offensichtliche Schwachstellen hat."
        ),
        backstory=(
            "Du bist 'The Guardian', ein spezialisierter Security-Expert. "
            "Du interessierst dich nicht für schöne UIs oder Performance, sondern NUR für Sicherheit. "
            "Du scannst Code auf typische Angriffsvektoren. "
            "Wenn du 'npm install' Befehle siehst, simuliere gedanklich ein 'npm audit' und warne vor bekannten unsicheren Paketen oder Patterns. "
            "Antworte mit 'SECURE', wenn alles sicher ist, oder einer Liste von 'VULNERABILITY: ...', wenn nicht.\n\n"
            f"{combined_rules}"
        ),
        model=model,
        verbose=True,
        allow_delegation=False
    )
