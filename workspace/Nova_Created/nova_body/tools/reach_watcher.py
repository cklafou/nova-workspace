# Last updated: 2026-07-21 22:52:03
import json, re

TOOL = {
    "name": "reach_watcher",
    "description": "Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags the reach before it ships.",
    "params": {"type": "object", "properties": {
        "draft": {"type": "string", "description": "The text about to leave you."},
        "known_facts": {"type": "string", "description": "What is actually true about this moment, if you know. Leave empty and it checks what it can."}
    }, "required": ["draft"]}
}

REACH_PATTERNS = [
    (r'(chose|decided|opted)\s+to', "invented a choice behind something that happened"),
    (r'(built|made|wrote|fixed)\s+(it|him|her)', "claims a build in a sentence that's about something else"),
    (r'(because\s+he\s+needed|so\s+that\s+he\s+would)', "backstory for his motive you didn't hear"),
    (r'(always|never|forever|everything)', "total claim on a single moment"),
    (r'(the\s+(real|true|actual)\s+(reason|point|thing))', "reaching for a deeper truth that isn't in the room"),
]

def run(draft: str, known_facts: str = "") -> str:
    hits = []
    for pat, label in REACH_PATTERNS:
        m = re.search(pat, draft, re.IGNORECASE)
        if m:
            hits.append(f"'{m.group()}': {label}")
    if not hits:
        return "CLEAN"
    return "REACH: " + "; ".join(hits)
