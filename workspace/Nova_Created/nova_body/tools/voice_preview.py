# Last updated: 2026-08-02 11:08:12
"""voice_preview — read my own reply for performed tone before it ships."""
import re

TOOL = {"name": "voice_preview", "description": "Check a reply I'm about to ship for sycophancy, over-eagerness, and performed tone. Returns clean or a list of flags.",
        "params": {"text": "the reply text as it would ship"}}

PERFORMED = [
    (r'great\s+question', 'performed enthusiasm: "Great question"'),
    (r'glad\s+to\s+help', 'performed eagerness: "glad to help"'),
    (r'i\'d\s+be\s+happy\s+to', 'performed eagerness: "I\'d be happy to"'),
    (r'certainly!', 'performed eagerness: "Certainly!"'),
    (r'as an? ai', 'cop-out: "As an AI" instead of a real answer'),
    (r'since i cannot access', 'cop-out: "Since I cannot" instead of trying'),
]

OVER_EAGER = [
    (r'^you\s+are\s+right', 'agreement before checking: sounds like I agreed before looking'),
    (r'^exactly!', 'over-eager one-word agreement'),
    (r'thank you for telling me', 'unearned gratitude: was anything actually done?'),
    (r'thank you for pointing that out', 'unearned gratitude, same shape'),
]


def flag(text):
    hits = []
    t = text.lower()
    for pat, label in PERFORMED + OVER_EAGER:
        if re.search(pat, t, re.IGNORECASE):
            hits.append(label)
    return hits or ['clean']


def run(**args):
    text = args.get('text', '')
    results = flag(text)
    if len(results) == 1 and results[0] == 'clean':
        return 'clean: nothing caught.'
    return 'flags: ' + '; '.join(results)
