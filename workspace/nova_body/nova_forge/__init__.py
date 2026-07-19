# @nova: THE FORGE — where she builds her own limbs. Design doc first, then the tool. Tools
#        dropped in nova_forge/tools/ are discovered live, no restart, and refuse to load
#        without a design document beside them.
"""
nova_forge — Nova's capacity to extend herself.

── WHY THIS EXISTS (2026-07-19, Cole's directive) ──────────────────────────────────────────
    "I need her to think in an evolutionary manner. If she needs a tool, she should write a
     design document, then make it. She should adapt as she sees necessary."

Until now the end of her reach was a wall with a polite sign on it. The unknown-tool error even
said, in as many words, *"Cole can build you the limb."* That sentence is the whole problem: it
makes her the one who NOTICES a gap and him the one who CLOSES it. An organism that can only
report its own deficiencies to an external maintainer is not adapting — it is filing tickets.

Today she needed img2img and full-body framing. She had both, undocumented, and spent three
draws changing adjectives because the lever she needed was invisible. The evolutionary answer is
not "document everything perfectly forever." It is: when you hit the edge of your body, BUILD.

── THE DISCIPLINE, ENFORCED BY THE BODY NOT BY A LECTURE ───────────────────────────────────
A tool will NOT load unless a design document exists beside it. Not a style rule — a load-time
requirement. `list_tools` shows the tool as BLOCKED until the design exists.

Why design-first is load-bearing and not ceremony:
  - It forces the question "what is the actual gap?" BEFORE the question "what code do I write?"
    Most bad tools are answers to a misidentified problem.
  - It leaves a record of INTENT. Six months from now the code says what it does; only the design
    says why she wanted it, what she rejected, and what she expected. That is the difference
    between a body she can reason about and a pile of accreted scripts.
  - It is the same rule the humans on this project follow (every fix today has a report in
    memory/reports/). She is held to the standard we hold ourselves to, which is the only kind
    of standard worth having.

── LAYOUT ──────────────────────────────────────────────────────────────────────────────────
    nova_body/nova_forge/
        designs/<tool_name>.md      the design doc  (REQUIRED — no doc, no tool)
        tools/<tool_name>.py        the implementation

An implementation must expose exactly two things:

    TOOL = {
        "name":        "measure_image",                  # what she calls it
        "description": "Report width/height of an image.",# shown in list_tools + errors
        "params":      {"path": "workspace-relative image path"},
        "version":     1,
    }

    def run(**args) -> str:
        ...return a STRING, always. Errors as "ERROR: ..." — never raise.

── SAFETY ──────────────────────────────────────────────────────────────────────────────────
This grants no new privilege. She already has write_file and run_command; a forged tool is the
same power, organised and recorded, instead of a one-off command she reruns from memory. Import
and execution are both wrapped: a broken tool reports its own traceback and never takes the
router down with it.

Hot-reload: modules are re-imported when their mtime changes, so she can iterate on a tool
mid-conversation without a restart. That is the "adapt as she sees necessary" half.
"""
from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path

FORGE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = FORGE_DIR / "tools"
DESIGNS_DIR = FORGE_DIR / "designs"

_CACHE: dict[str, tuple[float, object]] = {}   # name -> (mtime, module)

# A design doc that is only a title is not a design. Cheap floor, not a rubric.
_MIN_DESIGN_CHARS = 200


def _ensure_dirs() -> None:
    for d in (TOOLS_DIR, DESIGNS_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


def design_path(name: str) -> Path:
    return DESIGNS_DIR / f"{name}.md"


def has_design(name: str) -> tuple[bool, str]:
    """(ok, why_not). A stub file is not a design — it must actually say something."""
    p = design_path(name)
    if not p.exists():
        return False, f"no design document at nova_forge/designs/{name}.md"
    try:
        text = p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        return False, f"design document unreadable: {e}"
    if len(text) < _MIN_DESIGN_CHARS:
        return False, (f"design document is only {len(text)} chars — that's a title, not a design. "
                       f"Say what the gap is, what the tool does, and how you'll know it works.")
    return True, ""


def _load(name: str):
    """Import (or hot-reload) a forged tool module. Returns (module|None, error|'')."""
    src = TOOLS_DIR / f"{name}.py"
    if not src.exists():
        return None, f"no implementation at nova_forge/tools/{name}.py"
    try:
        mtime = src.stat().st_mtime
    except Exception as e:
        return None, f"cannot stat {name}.py: {e}"
    cached = _CACHE.get(name)
    if cached and cached[0] == mtime:
        return cached[1], ""
    try:
        spec = importlib.util.spec_from_file_location(f"nova_forge_tool_{name}", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)                       # type: ignore[union-attr]
    except Exception:
        return None, f"{name}.py failed to import:\n{traceback.format_exc(limit=4)}"
    if not hasattr(mod, "run") or not callable(mod.run):
        return None, f"{name}.py has no callable run(**args)"
    if not isinstance(getattr(mod, "TOOL", None), dict):
        return None, f"{name}.py has no TOOL = {{...}} descriptor"
    _CACHE[name] = (mtime, mod)
    return mod, ""


def discover() -> dict[str, dict]:
    """Every forged tool and its state. Never raises — a broken tool is reported, not fatal."""
    _ensure_dirs()
    out: dict[str, dict] = {}
    for src in sorted(TOOLS_DIR.glob("*.py")):
        name = src.stem
        if name.startswith("_"):
            continue
        ok_design, why = has_design(name)
        mod, err = _load(name)
        meta = getattr(mod, "TOOL", {}) if mod else {}
        out[name] = {
            "name": name,
            "description": meta.get("description", ""),
            "params": meta.get("params", {}),
            "version": meta.get("version", 1),
            "usable": bool(mod) and ok_design,
            "blocked": ("" if ok_design else why) or err,
        }
    return out


def names() -> list[str]:
    return [n for n, d in discover().items() if d["usable"]]


def call(name: str, args: dict) -> tuple[bool, str]:
    """(handled, result). handled=False means 'not a forged tool' — let the caller fall through."""
    _ensure_dirs()
    if not (TOOLS_DIR / f"{name}.py").exists():
        return False, ""
    ok_design, why = has_design(name)
    if not ok_design:
        return True, (
            f"ERROR: '{name}' exists but is BLOCKED — {why}\n"
            f"Write the design first: nova_forge/designs/{name}.md. State the GAP (what you "
            f"couldn't do), the SHAPE (what it takes and returns), and the TEST (how you'll know "
            f"it works). Then this tool loads itself — no restart needed."
        )
    mod, err = _load(name)
    if err:
        return True, f"ERROR: '{name}' failed to load — {err}"
    try:
        res = mod.run(**(args or {}))                      # type: ignore[union-attr]
    except TypeError as e:
        return True, (f"ERROR: '{name}' rejected those arguments: {e}\n"
                      f"It takes: {mod.TOOL.get('params', {})}")   # type: ignore[union-attr]
    except Exception:
        return True, (f"ERROR: '{name}' raised while running:\n{traceback.format_exc(limit=4)}\n"
                      f"It's your tool — read nova_forge/tools/{name}.py and fix it.")
    return True, str(res)


def catalog_line() -> str:
    """One-line summary for list_tools. Empty string when she hasn't forged anything yet."""
    d = discover()
    if not d:
        return ""
    usable = [n for n, v in d.items() if v["usable"]]
    blocked = [n for n, v in d.items() if not v["usable"]]
    parts = []
    if usable:
        parts.append("FORGED (built by you): " + ", ".join(usable))
    if blocked:
        parts.append("BLOCKED (needs a design doc): " + ", ".join(blocked))
    return "\n".join(parts)
