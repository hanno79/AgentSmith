import json
from datetime import datetime

LOGFILE = "crew_log.jsonl"

def log_event(agent_name: str, action: str, content: str):
    """Schreibt einen Logeintrag mit Zeitstempel in crew_log.jsonl."""
    # Safety Check: If content is not string, convert it
    if not isinstance(content, str):
        content = str(content)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent_name,
        "action": action,
        "content": content.strip()[:5000], # Limit content length
    }
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"❌ LOG ERROR: {e}")
    
    # Optional: Print to console if needed (already handled by Rich in main, but good as backup)
    # print(f"[LOG] {entry['timestamp']} – {agent_name}: {action}")
