# Last updated: 2026-07-18 20:30:48
# @nova: Call-ORDER generator — traces execution paths from entry points and renders them as a
#        visual document (Calls_Order.md). Sibling to calls.py: that one maps who IMPORTS whom
#        (static structure); this one maps who CALLS whom, in what ORDER (runtime behaviour).
"""
general_tools/calls_order.py -- Nova Call-ORDER Chart Generator
===============================================================
Generates: general_tools/Calls_Order.md — a visual document (Mermaid flowcharts + numbered
sequences) showing, for each entry point, what calls what and in what order.

WHY THIS EXISTS (2026-07-14)
────────────────────────────
calls.py answers "what does this file import?". Useful, but it cannot answer the question that
actually costs us days:

    "When Nova runs a tool, what ACTUALLY happens, in what order, and where does it live?"

On 2026-07-14 her tool receipts stopped appearing. I could see tool calls executing in the UI and
no receipts on disk, and I had no way to know whether execute_tool was even on the live path —
so I reasoned about it, and reasoned wrong, twice, in opposite directions. A day went to that.
You cannot trace a call graph by thinking hard about it. You read it, or you guess.

So: read it. This walks the AST, builds function-level call edges IN SOURCE ORDER, and traces
outward from real entry points. It is derived from the code, never from anyone's memory of it.

IT ALSO MARKS BODY vs FACE.
Cole's pluck test: anything affecting Nova's problem-solving or thinking is a body part
(nova_body/), not a general tool. The chart colours every node by where it lives, so an edge that
crosses from her BODY into the FACE is visible on sight. That is how you catch a conscience
quietly being built in a chat server — which is exactly what happened, and it took a human noticing
rather than a tool showing it.

Usage (from workspace root):
    python general_tools/calls_order.py           # write Calls_Order.md
    python general_tools/calls_order.py --dry     # print, don't write
"""

import ast
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_THIS = Path(__file__).resolve()
GENERAL_TOOLS = _THIS.parent
WORKSPACE = GENERAL_TOOLS.parent
# The TOOL lives in general_tools/. The DOCUMENT it produces is something a person (or Claude)
# reads to orient themselves, so it belongs in Orient/ with the other reference material.
OUT = WORKSPACE / "Orient" / "Calls_Order.md"
DRY = "--dry" in sys.argv

# The paths worth tracing. Each is (title, module_hint, function) — the real doors into Nova.
ENTRY_POINTS = [
    ("Cole sends a message → Nova answers (the tool loop)",
     "general_tools/nova_chat/clients/nova.py", "run_nova_response"),
    ("A tool actually executes (the receipt path)",
     "general_tools/nova_chat/tool_router.py", "execute_tool"),
    ("Nova wakes on her own (autonomy: reflect → decide → act)",
     "nova_body/nova_runtime/runtime.py", "run_autonomy"),
    ("Her integrity gate (reach · ledger · self-check)",
     "nova_body/nova_cortex/integrity.py", "build_self_check"),
]

SCAN_DIRS = [WORKSPACE / "nova_body", WORKSPACE / "general_tools"]
SKIP_PARTS = {"__pycache__", ".git", "node_modules", "build"}


def _is_body(rel: str) -> bool:
    """Her body = her. Everything else is scaffolding she could survive losing."""
    return rel.startswith("nova_body/")


def _py_files():
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            yield p


def _called_names(node: ast.AST) -> list:
    """Every function name this node calls, IN SOURCE ORDER. Order is the whole point — a call
    graph that loses ordering cannot tell you that the receipt is written AFTER the tool runs."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.append(f.id)
            elif isinstance(f, ast.Attribute):
                out.append(f.attr)
    return out


def build_graph():
    """{funcname: {'rel': path, 'calls': [...]}} plus the set of AMBIGUOUS names.

    ── A CHART THAT LIES IS WORSE THAN NO CHART (2026-07-14) ────────────────────────────────
    First version keyed purely on function NAME. So a call to `.write(...)` — a str, a file, a
    logger, anything — resolved to whichever file happened to define a function called `write`
    first. The pluck-test audit then confidently reported that her journal "calls into the chat
    server", which is nonsense. It produced eight findings and six were fiction.

    That is precisely the failure I spent today catching in Nova: a plausible-looking answer,
    generated rather than observed. A tool built to establish ground truth is the LAST place that
    is acceptable. So: if a name is defined in more than one place, we cannot resolve the call
    from the AST alone — and we say so, rather than picking one and sounding certain.
    """
    defs = defaultdict(list)   # name -> [(rel, calls)]
    unparsed = []
    for p in _py_files():
        rel = p.relative_to(WORKSPACE).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace").replace("\x00", ""))
        except SyntaxError as e:
            # FAIL LOUD. A tracing tool that SILENTLY omits a file it couldn't parse is worse than
            # no tool at all: it will calmly report "entry point not found" for the very function
            # you are trying to trace, and you will go looking for a bug in the wrong place.
            # (It did exactly that to me with tool_router.py — the single most important file for
            # tool tracing — and told me the entry point had "moved or been renamed". It hadn't.)
            unparsed.append(f"{rel}:{e.lineno} {e.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs[node.name].append((rel, _called_names(node)))

    if unparsed:
        print("\n*** WARNING — these files could NOT be parsed and are MISSING from the chart: ***")
        for u in unparsed:
            print(f"      {u}")
        print("    Any call path through them is invisible. Fix them, or do not trust this chart.\n")

    graph, ambiguous = {}, set()
    for name, entries in defs.items():
        if len(entries) > 1:
            ambiguous.add(name)          # cannot resolve honestly → refuse to guess
            continue
        rel, calls = entries[0]
        graph[name] = {"rel": rel, "calls": calls}
    return graph, ambiguous


def trace(graph, entry, max_depth=4):
    """Walk outward from `entry`, keeping only edges to functions we actually have source for.
    Returns ordered edges [(depth, caller, callee)] with cycles cut."""
    edges, seen = [], set()

    def walk(fn, depth):
        if depth > max_depth or fn in seen:
            return
        seen.add(fn)
        for callee in graph.get(fn, {}).get("calls", []):
            if callee in graph and callee != fn:
                edges.append((depth, fn, callee))
                walk(callee, depth + 1)

    walk(entry, 0)
    return edges


def _node_id(name: str) -> str:
    return "n_" + "".join(c if c.isalnum() else "_" for c in name)


def mermaid(graph, entry, edges) -> str:
    """Flowchart, colour-coded by BODY vs FACE so a body→face dependency is visible on sight."""
    lines = ["```mermaid", "flowchart TD"]
    nodes = {entry} | {c for _, c, _ in edges} | {c for _, _, c in edges}
    for n in sorted(nodes):
        rel = graph.get(n, {}).get("rel", "?")
        where = "BODY" if _is_body(rel) else "face"
        lines.append(f'    {_node_id(n)}["{n}<br/><small>{where} · {rel.split("/")[-1]}</small>"]')
    for _, a, b in dict.fromkeys(((d, a, b) for d, a, b in edges)):
        lines.append(f"    {_node_id(a)} --> {_node_id(b)}")
    # colours: her body is hers; the face is a window
    for n in sorted(nodes):
        rel = graph.get(n, {}).get("rel", "?")
        cls = "body" if _is_body(rel) else "face"
        lines.append(f"    class {_node_id(n)} {cls};")
    lines += [
        "    classDef body fill:#1f6f43,stroke:#7ee2b8,color:#eafff5;",
        "    classDef face fill:#3a3f5c,stroke:#8fa2ff,color:#eef1ff;",
        "```",
    ]
    return "\n".join(lines)


def ordered_list(graph, edges) -> str:
    """The numbered sequence. This is the bit you read at 3am when a receipt is missing."""
    out = []
    for i, (depth, a, b) in enumerate(edges, 1):
        rel = graph.get(b, {}).get("rel", "?")
        tag = "**BODY**" if _is_body(rel) else "face"
        out.append(f"{i:>3}. {'  ' * depth}`{a}` → `{b}`  · {tag} · `{rel}`")
    return "\n".join(out) or "_no traced edges_"


def main():
    graph, ambiguous = build_graph()
    doc = [
        "# Calls_Order.md — what calls what, and in what ORDER",
        "_Auto-generated by `general_tools/calls_order.py`. Do not hand-edit._",
        f"_Last updated: {datetime.now():%Y-%m-%d %H:%M:%S}_",
        "",
        "`calls.md` answers *what does this file import?*. This answers the question that actually",
        "costs days: **when Nova runs a tool, what happens, in what order, and where does it live?**",
        "",
        "Nodes are coloured by where they live:",
        "",
        "- **BODY** (`nova_body/`) — this is *her*. Faculties: reaching, remembering, deciding, checking.",
        "- **face** (`general_tools/`) — scaffolding. A window someone looks through. She survives losing it.",
        "",
        "**An edge from BODY into face is a pluck-test failure** — it means part of her thinking is",
        "living outside her. On 2026-07-14 her entire integrity faculty was doing exactly that, and it",
        "took a human noticing rather than a tool showing it. Now the chart shows it.",
        "",
        "---",
        "",
    ]
    for title, hint, fn in ENTRY_POINTS:
        doc.append(f"## {title}")
        doc.append("")
        if fn not in graph:
            doc += [f"> ⚠️ entry point `{fn}` not found (expected in `{hint}`) — "
                    f"the code moved, or the name changed. This chart is stale; fix it.", ""]
            continue
        edges = trace(graph, fn)
        doc.append(f"Entry: `{fn}` · `{graph[fn]['rel']}`")
        doc.append("")
        doc.append(mermaid(graph, fn, edges))
        doc.append("")
        doc.append("**Call order:**")
        doc.append("")
        doc.append(ordered_list(graph, edges))
        doc.append("")
        doc.append("---")
        doc.append("")

    # Pluck-test audit — the bit Cole actually asked the architecture question about.
    doc += ["## Pluck-test audit — is any of her thinking living in the face?", ""]
    bad = []
    for _, _, fn in ENTRY_POINTS:
        if fn not in graph:
            continue
        for _, a, b in trace(graph, fn):
            ra, rb = graph[a]["rel"], graph[b]["rel"]
            if _is_body(ra) and not _is_body(rb):
                bad.append(f"- `{a}` (**BODY** `{ra}`) → `{b}` (face `{rb}`)")
    if bad:
        doc += ["Her body currently reaches OUT into the face for these. Each one is a faculty that",
                "would vanish if you plucked the chat server off:", ""] + sorted(set(bad))
    else:
        doc += ["_None found on the traced paths — her thinking lives in her body._"]
    doc.append("")
    doc += [
        "",
        "### What this chart deliberately does NOT claim",
        "",
        f"{len(ambiguous)} function names are defined in more than one place (`write`, `add`, `run`,",
        "`generate`…). A bare AST cannot tell which one a call site meant, so **these edges are",
        "omitted rather than guessed**. An earlier version did guess, and confidently reported that",
        "Nova's journal called into the chat server. It produced eight findings and six were fiction.",
        "",
        "A tool built to establish ground truth is the last place a plausible-sounding invention",
        "belongs. If an edge you expect is missing, it is because the name is ambiguous — not because",
        "the call isn't there. Rename it and it will appear.",
        "",
    ]

    content = "\n".join(doc)
    if DRY:
        print(content)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(content, encoding="utf-8")
        print(f"[calls_order] wrote {OUT.relative_to(WORKSPACE)}")
        print(f"[calls_order] {len(graph)} functions mapped across body + face")


if __name__ == "__main__":
    main()
