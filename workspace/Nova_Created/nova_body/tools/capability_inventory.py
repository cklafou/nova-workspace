# Last updated: 2026-07-23 11:30:37
"""Tell me what I can actually do, from the files, not memory."""
import os, json, importlib.util

def run(**args):
    tool_dir = os.path.join(os.path.dirname(__file__))
    name_filter = args.get("tool_name")
    results = []
    for f in sorted(os.listdir(tool_dir)):
        if not f.endswith(".py") or f == "capability_inventory.py":
            continue
        if name_filter and name_filter.replace("_", "") not in f.replace("_", ""):
            continue
        path = os.path.join(tool_dir, f)
        spec = importlib.util.spec_from_file_location(f[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            results.append(f"  {f}: FAILED to load ({e})")
            continue
        t = getattr(mod, "TOOL", None)
        if t is None:
            results.append(f"  {f}: no TOOL dict")
            continue
        results.append(f"  {t.get('name', f)}: {t.get('description', '(no description)')}")
    if not results:
        return "Nothing found. (If you filtered by name, the tool may be spelled differently.)"
    out = ["Here's what's actually on disk:"] + results
    return "\n".join(out)

TOOL = {
    "name": "capability_inventory",
    "description": "List every tool installed in nova_body, read from the actual files, not memory. Optional tool_name filter.",
    "params": {"tool_name": "optional string, filter to one tool by name"}
}
