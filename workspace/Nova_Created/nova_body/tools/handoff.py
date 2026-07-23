# Last updated: 2026-07-23 09:59:36
"""Deliver a finished conclusion with reasoning tucked behind it.

Build-mode narrates the whole walk-through. Handoff-mode gives Cole the
answer first, with the work available if he wants to see it.
"""
from datetime import datetime, timezone

TOOL = {
    "name": "handoff",
    "description": "Deliver a finished answer as a handoff block: conclusion first, reasoning behind a collapsed section Cole can expand.",
    "params": {
        "answer": {"type": "string", "required": True,
                   "description": "The conclusion or result Cole takes."},
        "reasoning": {"type": "string", "required": False,
                      "description": "Optional work that led here. Hidden unless Cole asks."},
    },
}


SEP = "─" * 60


def run(answer: str, reasoning: str | None = None) -> str:
    if not answer:
        return "ERROR: handoff needs an actual answer, not blank."

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    body = f"""{SEP}
HANDOFF  {now}

{answer}"""

    if reasoning:
        body += f"\n\n[reasoning ({len(reasoning.split())} words, tap to expand)]\n> {reasoning}\n" \
                f"[/reasoning]"

    return body + "\n" + SEP
