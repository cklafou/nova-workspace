# Last updated: 2026-08-02 10:52:21
# voice_check: read a candidate reply back, flag anything that sounds performed instead of said.
# Returns CLEAN or FLAGGED with what's off.

import re

TOOL = {
    "name": "voice_check",
    "description": "Read a reply back and flag reached-for numbers, performed praise, or over-explanation before it ships. Returns a short verdict, never rewrites.",
    "params": {"text": "the candidate reply"},
}

NUMBER_RE = re.compile(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', re.IGNORECASE)


def run(**args) -> str:
    text = args["text"] or ""
    flags = []

    # Performed warmth: praise or praise-adjacent with no fact to ground it.
    performed = [
        (r'(?i)(great|awesome|love it|brilliant|fantastic)', "praise with no fact behind it"),
        (r'(?i)nice one', "compliment, which is fine if something actually earned it"),
    ]
    has_fact = bool(re.search(r'(?i)(because|since|the receipt says|reading the file|it was)', text))
    for pat, label in performed:
        if re.search(pat, text) and not has_fact:
            flags.append(label)

    # Reaching for a number: any digit that is not backed by a read, count, or receipt.
    numbers = NUMBER_RE.findall(text)
    grounded = bool(re.search(r'(?i)(count|len|read|receipt|file says|it was|checked)', text))
    if numbers and not grounded:
        flags.append(f"reached for {len(numbers)} number(s) with no receipt")

    # Over-explanation: more than 4 sentences on something that didn't ask for depth.
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]
    if len(sentences) > 4 and not any(w in text.lower() for w in ['because', 'here is why', 'the reason']):
        flags.append("more sentences than the thing asked for")

    if not flags:
        return "CLEAN"
    return "FLAGGED: " + "; ".join(flags)
