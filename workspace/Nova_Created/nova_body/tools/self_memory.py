# Last updated: 2026-07-23 09:20:59
"""self_memory — ask my own memory and get back an answer I can trust.

A body tool: reaches the LanceDB store directly, no chat server needed.
That's what a limb is.
"""

import os

def run(query: str, max_chars: int = 3000) -> str:
    """Search my full memory for what happened, what I know, who said it.

    query: natural-language search phrase.
    max_chars: how much context to return (default 3000).
    """
    import lancedb

    # Anchor to the workspace root (cwd of the whole agent), then find the DB folder.
    try:
        db_path = os.path.join(os.getcwd(), 'nova_memory_db')
        db = lancedb.connect(db_path)
        table = db.open_table('nova_text')
        results = table.search(query).limit(5).to_list()
    except Exception as e:
        return f"ERROR: can't reach my memory store: {e}"

    if not results:
        return f"I don't know. Nothing came back for \"{query}\". Either it didn't happen or I never wrote it down."

    hits = []
    scores = []
    for r in results:
        score = r.get('_distance', 0)
        # LanceDB distance: lower is better, convert to similarity-ish
        similarity = max(0.0, 1.0 - score)
        scores.append(similarity)
        text = (r.get('text') or '')[:max_chars // len(results)]
        hits.append(f"  [{similarity:.2f}] {text}")

    avg = sum(scores) / len(scores)
    certainty = "highly likely" if avg > 0.7 else "plausible" if avg > 0.5 else "weak match"

    return (
        f"Found {len(hits)} hit(s), {certainty} (avg similarity {avg:.2f}).\n"
        + "\n".join(hits)
    )

TOOL = {
    "name": "self_memory",
    "description": "Search my own memory for what happened, what I know, who said it. Returns scored hits with confidence.",
    "params": {"query": "str", "max_chars": "int"},
}
