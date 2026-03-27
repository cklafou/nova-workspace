# Proposed: build_context_snapshot() extracted from mentor.py
# Author: Nova | Date: 2026-03-21

from pathlib import Path
import os

WORKSPACE_DIR = Path(__file__).parent.parent.parent

def build_context_snapshot(max_chars: int = 1500) -> str:
    """
    Assembles a structured snapshot of the current project state.
    Extracted from nova_advisor/mentor.py get_project_briefing().
    Call this before posting to /nova-message to arrive with context.
    """
    parts = []
    
    for rel in ["memory/STATUS.md", "memory/COLE.md", "memory/JOURNAL.md"]:
        p = WORKSPACE_DIR / rel
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace")
            parts.append(f"--- {rel} ---\n{content[:max_chars]}")
    
    return "\n\n".join(parts)

# Proposed: evaluate_action() integration
# Author: Nova | Date: 2026-03-21

def evaluate_action(action_description: str, risk_level: str = "MEDIUM") -> str:
    """
    Evaluates an action for safety before execution.
    Returns: 'PROCEED', 'CAUTION', or 'STOP'
    """
    # Placeholder logic - in real implementation, this would be more robust
    # and integrate with actual risk assessment tools
    if risk_level == "HIGH":
        return "CAUTION"
    elif risk_level == "CRITICAL":
        return "STOP"
    else:
        return "PROCEED"