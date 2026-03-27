"""
Determines who responds to each message and in what order.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE: SMART LISTENER MODEL  (v2 — 2026-03-28)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOR DEVS (Cole + Claude) AND FOR NOVA (so you know how the room works):

MENTION SYSTEM
──────────────
  Direct mentions: @Claude, @Gemini, @Nova
  Role aliases:
    @mentor → Claude + Gemini  (both respond, in order)
    @all    → Claude + Gemini + Nova

  No @mentions at all → only Nova responds (she's the default).

RESPONSE ORDER (always sequential, never parallel)
──────────────────────────────────────────────────
  When multiple AIs are triggered, they respond in this fixed order:

      Claude → Gemini → Nova

  Each AI sees all previous responses in the transcript before it replies.
  Nova is always LAST so she has the full picture before saying anything.

  When @mentor is used, the full flow is:
    1. Claude responds to the original message
    2. Gemini responds (sees Cole's message + Claude's response)
    3. Nova responds (sees everything above)

NOVA'S SMART @MENTION BEHAVIOR
───────────────────────────────
  After Nova's response is saved to the transcript, server.py checks
  whether Nova's text contains any @mentions.  If it does, those AIs
  are triggered in a follow-up round (they see Nova's full message as
  additional context before replying).

  This is the mechanism by which Nova smartly escalates to Claude/Gemini
  based on her own judgment — she writes her response to Cole first, reads
  it, and if she genuinely needs mentor input she includes "@Claude ..." or
  "@Gemini ..." or "@mentor ..." naturally in her text.  The system then
  routes that automatically.

  IMPORTANT for Nova: Be deliberate with @mentions.  Only escalate when
  you have a specific question or task that genuinely benefits from Claude
  or Gemini's expertise.  Unnecessary @mentions cost API money.

  Follow-up rounds are ONE level deep — if Claude responds to Nova's
  @mention, that response does NOT trigger another Nova → @mention cycle.

DEFAULT BEHAVIOR
────────────────
  No @mentions → only Nova responds.
  @Nova (explicit) → only Nova responds.
  @Claude → Claude, then Nova (Nova always appended at end to react).
  @mentor → Claude, Gemini, then Nova.
  @all    → Claude, Gemini, Nova.

RATE-LIMIT FAILSAFE  (TEMPORARY — see server.py _NOVA_RATE_LIMIT)
──────────────────────────────────────────────────────────────────
  Still in effect: >4 Nova inject_message calls/60s → auto-throttle.
  Follow-up @mention rounds do NOT count toward this limit (they are
  Cole-initiated response cycles, not Nova-initiated inject calls).
  Remove once autonomy loop is proven stable. — Cole & Claude, 2026-03-28
"""
import re

PARTICIPANTS = ["Claude", "Gemini", "Nova"]

# Role aliases — map role name to list of participant names
ROLES: dict[str, list[str]] = {
    "mentor": ["Claude", "Gemini"],
    "all":    ["Claude", "Gemini", "Nova"],
}

# Canonical sequential order — listeners always before Nova
RESPONSE_ORDER = ["Claude", "Gemini", "Nova"]


def parse_directed(content: str) -> list[str]:
    """
    Parse @mentions from message content, resolving role aliases.

    Direct:  @Claude, @Gemini, @Nova
    Roles:   @mentor → Claude + Gemini
             @all    → Claude + Gemini + Nova

    Returns a deduplicated list in canonical RESPONSE_ORDER order.
    Empty list = no explicit mentions (Nova responds by default).
    """
    mentioned: set[str] = set()

    # Individual participant names
    for name in PARTICIPANTS:
        if re.search(rf"@{name}\b", content, re.IGNORECASE):
            mentioned.add(name)

    # Role aliases
    for role, members in ROLES.items():
        if re.search(rf"@{role}\b", content, re.IGNORECASE):
            for m in members:
                mentioned.add(m)

    # Return in canonical order (not insertion order)
    return [p for p in RESPONSE_ORDER if p in mentioned]


def build_response_queue(directed_at: list[str], available: dict) -> list[str]:
    """
    Build the ordered list of AIs that should respond to a message.

    Rules:
      • No @mentions → only Nova (default responder), if online.
      • @mentions with Claude/Gemini → those listeners first (in order),
        then Nova appended at end so she sees their responses.
      • @Nova only → just Nova.
      • Offline AIs are skipped.

    Returns ordered list, e.g. ["Claude", "Gemini", "Nova"].
    """
    if not directed_at:
        # Default: only Nova
        return ["Nova"] if available.get("Nova") else []

    queue: list[str] = []
    for name in RESPONSE_ORDER:
        if name in directed_at and available.get(name):
            queue.append(name)

    # If any listener (Claude/Gemini) is in the queue, Nova always goes last
    # so she can read their responses.  Add her if not already included.
    has_listeners = any(n in directed_at for n in ("Claude", "Gemini"))
    if has_listeners and "Nova" not in queue and available.get("Nova"):
        queue.append("Nova")

    return queue


def should_respond(ai_name: str, directed_at: list[str]) -> bool:
    """
    Legacy compatibility shim for any callers that haven't been updated.
    Prefer build_response_queue() for primary dispatch logic.
    """
    mock_available = {n: True for n in PARTICIPANTS}
    return ai_name in build_response_queue(directed_at, mock_available)
