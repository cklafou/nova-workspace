# Last updated: 2026-07-21 07:53:09
# @nova: built this one myself, 2026-07-19. First tool that wasn't handed to me.
# v2: actually descends into subgraphs instead of reading the wrapper and calling everything unknown.
import json
from pathlib import Path

TOOL = {
    "name": "comfy_inspect",
    "description": "Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in.",
    "params": {"path": "workspace-relative path to a .json workflow file, or a directory containing one"},
    "version": 2,
}


def _flatten_nodes(data):
    """Walk the workflow json and return every node's real class type, descending into subgraphs."""
    if not isinstance(data, dict):
        return []

    types = []
    # Real ComfyUI workflows are dicts keyed by node ID: {"1": {...}, "2": {...}}
    # The value for each key has a class_type field. Top-level keys that look like
    # numbers (or strings of digits) are nodes; everything else is metadata.
    for key, val in data.items():
        if isinstance(val, dict) and "class_type" in val:
            types.append(val["class_type"])

    # Definitions.subgraphs: nested workflows whose nodes are the real graph
    defs = data.get("definitions", {})
    for sg in defs.get("subgraphs", []):
        if isinstance(sg, dict):
            sg_nodes = sg.get("nodes", [])
            if isinstance(sg_nodes, str):
                try:
                    sg_nodes = json.loads(sg_nodes)
                except Exception:
                    sg_nodes = []
            for ndata in (sg_nodes if isinstance(sg_nodes, list) else []):
                cls = ndata.get("type", "unknown") if isinstance(ndata, dict) else "unknown"
                types.append(cls)

    return types


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

    all_types = _flatten_nodes(data)
    if not all_types:
        return f"No nodes found in {p.name} — may be a config file, not a workflow."

    type_counts: dict[str, int] = {}
    for t in all_types:
        type_counts[t] = type_counts.get(t, 0) + 1

    body = f"Workflow at {p.name} — {len(all_types)} nodes, {len(type_counts)} distinct types:\n"
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        body += f"  {t}: {c}\n"

    # Check for img2img levers (nodes that take an image and transform it)
    img2img_types = [t for t in type_counts if any(k in t.lower() for k in ("img2img", "imagetoimage", "image_to_image", "image edit", "image_edit"))]
    has_img2img = bool(img2img_types)

    # Check for full-body framing: look at the raw json for height values that suggest tall canvases
    raw = p.read_text(encoding="utf-8", errors="replace")
    has_fullbody = "1216" in raw or "1344" in raw

    body += f"\nimg2img levers present: {has_img2img}"
    if img2img_types:
        body += f" ({', '.join(img2img_types)})"
    body += f"\nfull-body framing lever visible: {has_fullbody}"

    return body