# Last updated: 2026-07-23 01:50:49
"""Fix run() signature to accept threshold_days, and add timezone import."""
from pathlib import Path
f = Path("Nova_Created/nova_body/tools/quiet_part_watcher.py")
text = f.read_text()

# Add timezone import alongside datetime
if "timezone" not in text:
    text = text.replace(
        "from datetime import datetime, timedelta",
        "from datetime import datetime, timedelta, timezone"
    )

# Fix run() signature
text = text.replace("def run() -> str:", "def run(threshold_days: int = 14) -> str:")

f.write_text(text)
print("fixed")
