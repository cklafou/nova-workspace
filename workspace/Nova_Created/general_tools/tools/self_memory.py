# self_memory — ask my own memory whether I actually know something
# Last updated: 2026-07-23 07:36:35

TOOL = {
    "name": "self_memory",
    "description": "Ask my own memory a question. Returns the answer with a confidence note, or says I don't know instead of making one up.",
    "params": {"query": "natural-language question about my own past"},
}

import sys; sys.path.insert(0, ".")
from nova_chat.tools.memory_search import run as memory_search

def run(query):
    """Ask my own memory a question and get back what's in there.

    Returns the answer with a confidence note, or says I don't know
    instead of making one up. That second part is the whole reason this exists.
    """
    results = memory_search(query=query)

    if not results:
        return "I don't know. Nothing came back on that."

    answers = [r for r in results if r.get('answer')]
    sources = len(set(r.get('source', 'unknown') for r in results))

    # Confidence is how many ways I remember it, not how loudly one source says it.
    confidence = min(sources / 3.0, 1.0) if sources else 0.0

    answer = answers[0]['answer'] if answers else None
    if not answer:
        return "I don't know. Nothing came back on that."

    how_sure = ("sure", "pretty sure", "somewhat sure", "guessing")[max(0, min(3, int((1 - confidence) * 4)))]
    return f"{answer} ({how_sure}, {sources} source{'s' if sources != 1 else ''})"
