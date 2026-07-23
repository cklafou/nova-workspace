# Last updated: 2026-07-23 10:24:53
import json, os
from datetime import datetime

TOOL = {"name": "silence_detector", "description": "How long since anything in a folder last changed.",
        "params": {"path": "a directory path"}}

def run(path):
    if not os.path.isdir(path):
        return f"ERROR: '{path}' is not a directory"
    files = []
    for root, dirs, names in os.walk(path):
        for name in names:
            fp = os.path.join(root, name)
            try:
                age = datetime.now().timestamp() - os.path.getmtime(fp)
                files.append((name, age))
            except OSError:
                pass
    if not files:
        return f"Nothing found in '{path}'"
    newest_name, newest_age = min(files, key=lambda x: x[1])
    hours = newest_age / 3600
    if hours < 1:
        return f"'{path}' was touched {int(hours*60)} minutes ago (by {newest_name})."
    elif hours < 24:
        return f"'{path}' hasn't been touched in {hours:.1f} hours (newest: {newest_name})."
    else:
        return f"'{path}' hasn't been touched in {hours/24:.1f} days (newest: {newest_name})."
