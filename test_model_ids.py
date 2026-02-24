"""Temporaeres Skript zum Testen der Claude Model-IDs."""
import subprocess, os, sys

claude = "C:/Users/rahn/AppData/Roaming/npm/claude.cmd"
env = os.environ.copy()
env.pop("CLAUDECODE", None)

models = [
    ("opus-4-6", "claude-opus-4-6"),
    ("sonnet-4-6", "claude-sonnet-4-6"),
    ("haiku-4-5", "claude-haiku-4-5-20251001"),
    ("old-haiku", "claude-3-5-haiku-20241022"),
    ("old-opus", "claude-opus-4-1-20250805"),
    ("old-sonnet", "claude-sonnet-4-20250514"),
]

for name, model_id in models:
    try:
        r = subprocess.run(
            [claude, "-p", "sag nur OK", "--output-format", "text", "--max-turns", "1", "--model", model_id],
            capture_output=True, text=True, timeout=45, env=env
        )
        status = "OK" if r.returncode == 0 else f"FAIL(rc={r.returncode})"
        out = r.stdout.strip()[:80]
        err = r.stderr.strip()[:150] if r.stderr else ""
        print(f"{name:15s} | {model_id:35s} | {status:10s} | out={out}")
        if err:
            print(f"{'':15s} | {'':35s} | {'':10s} | err={err}")
    except subprocess.TimeoutExpired:
        print(f"{name:15s} | {model_id:35s} | TIMEOUT")
    except Exception as e:
        print(f"{name:15s} | {model_id:35s} | ERROR: {e}")
    sys.stdout.flush()
