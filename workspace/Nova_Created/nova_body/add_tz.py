# Last updated: 2026-07-23 01:51:13
from pathlib import Path
f = Path("Nova_Created/nova_body/tools/quiet_part_watcher.py")
t = f.read_text()
t = t.replace("from datetime import datetime, timedelta", "from datetime import datetime, timedelta, timezone")
f.write_text(t)
print("timezone added")
