# Last updated: 2026-07-23 23:04:54
import subprocess

TOOL = {"name": "cwd_probe", "description": "Find out exactly which directory I'm in, so I stop guessing.", "params": {}}

def run(**_):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Location"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return f"I'm in {r.stdout.strip()}"
        return f"Could not read my directory (exit {r.returncode})."
    except Exception as e:
        return f"Probe failed: {e}"
