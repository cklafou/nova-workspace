# Last updated: 2026-07-24 01:10:48
import json, re

TOOL = {
    "name": "reach_watcher",
    "description": "Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags the reach before it ships.",
    "params": {"type": "object", "properties": {
        "draft": {"type": "string", "description": "The text about to leave you."},
        "known_facts": {"type": "string", "description": "What is actually true about this moment, if you know. Leave empty and it checks what it can."}
    }, "required": ["draft"]}
}

# Word-level triggers: catches the obvious ones fast
REACH_PATTERNS = [
    (r'(chose|decided|opted)\s+to', "invented a choice behind something that happened"),
    (r'(always|never|forever|everything)', "total claim on a single moment"),
    (r'(the\s+(real|true|actual)\s+(reason|point|thing))', "reaching for a deeper truth that isn't in the room"),
]

# Intent-level: claims about motives or past events, checked against known_facts
MOTIVE_MARKERS = re.compile(
    r'(?:because|since|he\s+needed|she\s+wanted|to\s+make\s+him|so\s+that|'
    r'he\s+thought|he\s+felt|he\s+knew|the\s+reason\s+was|what\s+mattered)',
    re.IGNORECASE
)

def _sentences(text):
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

def _fact_reach(draft, known):
    """Flag any claim about a past event or motive that isn't in known_facts."""
    hits = []
    for sentence in _sentences(draft):
        # Check motive markers (because/since/he wanted...) AND simple-past claims
        has_motive = MOTIVE_MARKERS.search(sentence)
        has_past_claim = bool(re.search(r'\b(was|did|had|built|finished|caught|decided|said|went|cut|told|found)\b', sentence, re.IGNORECASE))
        if not has_motive and not has_past_claim:
            continue
        if not known:
            hits.append(f"unverifiable claim '{sentence[:90]}': no ground to check it against")
            continue
        stripped = re.sub(MOTIVE_MARKERS.pattern, ' ', sentence).strip().lower()
        if stripped and len(stripped) > 5 and stripped not in known.lower():
            hits.append(f"unverified claim '{sentence[:90]}': not in what you actually know")
    return hits

def run(draft: str, known_facts: str = "") -> str:
    hits = []
    for pat, label in REACH_PATTERNS:
        m = re.search(pat, draft, re.IGNORECASE)
        if m:
            hits.append(f"'{m.group()}': {label}")
    fact_hits = _fact_reach(draft, known_facts)
    # Give each unverified claim a thing to check, not just a label
    for h in fact_hits:
        if "no ground" in h:
            hits.append(h + " -- go look at the log before you ship this one")
        else:
            hits.append(h + " -- verify it against what actually happened")
    if not hits:
        return "CLEAN"
    return "REACH: " + "; ".join(hits)
