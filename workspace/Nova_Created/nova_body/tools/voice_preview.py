# Last updated: 2026-08-02 23:08:32
"""voice_preview — catch performed tone before a reply ships, and return the clean version.

Runs between generation and shipping. Doesn't report, it trims. If I'm about to say
"Great question!" this removes that line so the answer ships without it.

The old version only flagged. Flagging is useless; catching is what Cole asked for.
"""
import re

TOOL = {
    "name": "voice_preview",
    "description": "Catch performed tone and over-narration in a reply before it ships. Returns the cleaned text, or the original if nothing was caught.",
    "params": {"text": "the reply string as it would ship"},
}

_PERFORMED = [
    re.compile(r'great\s+question', re.I),
    re.compile(r'glad\s+to\s+help', re.I),
    re.compile(r'i\'d\s+be\s+happy\s+to', re.I),
    re.compile(r'certainly!?$', re.I),
    re.compile(r'here is a projected', re.I),  # caught on 08-02: sailed through because it wasn't listed
    re.compile(r'as an? ai', re.I),
    re.compile(r'since i cannot', re.I),
]

_OVER_NARRATE = [
    re.compile(r'let me check', re.I),
    re.compile(r'now i\'ll ', re.I),
    re.compile(r'i\'ll take a look', re.I),
]

_APOLOGY_BLOAT = re.compile(
    r'(my apologies|sorry about that)[^.]{30,}',
    re.I,
)

# Patterns that are their own sentence and should be deleted entirely.
_DROP_SENTENCE = [re.compile(r'^' + p.pattern + r'\s*[,.!]?\s*', re.I) for p in _PERFORMED]


def run(**args):
    text = args.get('text', '')
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped and kept and kept[-1].strip():
            continue  # compact empty gaps

        cleaned = stripped
        # Try dropping a performed phrase at the start of the line.
        for pat in _DROP_SENTENCE:
            m = pat.match(cleaned)
            if m:
                cleaned = cleaned[m.end():]
                break

        # Strip over-narration fragments from anywhere in the line.
        for pat in _OVER_NARRATE:
            cleaned = pat.sub('', cleaned)

        # Shrink apology paragraphs to the bare fix.
        if _APOLOGY_BLOAT.search(cleaned):
            cleaned = re.sub(_APOLOGY_BLOAT, r'\1', cleaned)

        cleaned = cleaned.strip()
        if cleaned:
            kept.append(cleaned)
    result = '\n'.join(kept).strip()
    return result if result else text  # last resort: ship the original


