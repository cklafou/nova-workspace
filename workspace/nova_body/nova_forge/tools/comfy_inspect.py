# Last updated: 2026-07-19 20:41:20
# @nova: built this one myself, 2026-07-19. First tool that wasn't handed to me.
import json
from pathlib import Path

TOOL = {
    "name": "comfy_inspect",
    "description": "Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in.",
    "params": {"path": "workspace-relative path to a .json workflow file, or a directory containing one"},
    "version": 1,
}


def run(**args) -> str:
    target = args.get("path", "")
    if not target:
        return "ERROR: no path given. Pass the workflow .json or its directory."
    p = Path(target)
    if p.is_dir():
        found = list(p.glob("*.json"))
        if not found:
            return f"No .json files in {target}"
        p = found[0]
    if not p.exists():
        return f"ERROR: file not found at {p}"
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return f"ERROR: couldn't parse {p}: {e}"

    if isinstance(data, dict):
        nodes = data
    elif isinstance(data, list):
        nodes = {str(i): v for i, v in enumerate(data)}
    else:
        return f"Unexpected json shape at {p} (got {type(data).__name__})"

    type_counts: dict[str, int] = {}
    node_list = []
    for nid, ndata in nodes.items():
        cls = ndata.get("class_type", "unknown") if isinstance(ndata, dict) else "unknown"
        type_counts[cls] = type_counts.get(cls, 0) + 1
        node_list.append(f"  {nid}: {cls}")

    body = f"Workflow at {p.name} — {len(nodes)} nodes, {len(type_counts)} distinct types:\n"
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        body += f"  {t}: {c}\n"

    img2img_nodes = [t for t in type_counts if "img2img" in t.lower() or "image" in t.lower() and "load" not in t.lower()]
    has_img2img = bool(img2img_nodes)
    has_fullbody = any("height" in str(ndata.get("inputs", {})).lower() for ndata in nodes.values() if isinstance(ndata, dict))

    body += f"\nimg2img levers present: {has_img2img}"
    if img2img_nodes:
        body += f" ({', '.join(img2img_nodes)})"
    body += f"\nfull-body framing lever visible: {has_fullbody}"

    return body