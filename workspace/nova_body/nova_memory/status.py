#!/usr/bin/env python3
"""
nova_status.py -- Update Nova's Active Pulse and goal completion.
Follows the Proposed Changes Protocol -- never overwrites STATUS.md directly.
"""

import sys
import re
from pathlib import Path

STATUS_PATH   = Path("memory/STATUS.md")
PROPOSED_DIR  = Path("logs/proposed")
PROPOSED_PATH = PROPOSED_DIR / "STATUS.md"


def update_status(pulse_msg=None, complete_goal_text=None):
    if not STATUS_PATH.exists():
        return "[error] STATUS.md not found."

    content = STATUS_PATH.read_text(encoding="utf-8")

    # 1. Update Active Pulse section
    if pulse_msg:
        pulse_section = f"## Active Pulse\n- **Current Task:** {pulse_msg}\n"
        if "## Active Pulse" in content:
            content = re.sub(
                r"## Active Pulse\n- \*\*Current Task:\*\*.*?\n",
                pulse_section,
                content
            )
        else:
            content = content.replace("# STATUS.md", f"# STATUS.md\n\n{pulse_section}")

    # 2. Mark a goal as completed (ASCII only -- no Unicode checkmarks)
    if complete_goal_text:
        pattern = re.compile(rf"(\d+\.\s+{re.escape(complete_goal_text)})", re.IGNORECASE)
        if pattern.search(content):
            content = pattern.sub(r"[DONE] \1", content)
        else:
            return f"[error] Goal '{complete_goal_text}' not found in STATUS.md."

    # 3. Write to proposed location -- never touch STATUS.md directly
    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSED_PATH.write_text(content, encoding="utf-8")

    return f"[success] Proposed update written to {PROPOSED_PATH}. Ask Cole to review."


if __name__ == "__main__":
    msg  = sys.argv[1] if len(sys.argv) > 1 else None
    goal = sys.argv[2] if len(sys.argv) > 2 else None
    print(update_status(pulse_msg=msg, complete_goal_text=goal))
