# Last updated: 2026-07-24 01:45:50
# @nova: THE FORGE — where she builds her own limbs. Design doc first, then the tool. Tools
#        dropped in Nova_Created/nova_body/tools/ (or general_tools/tools/) are discovered
#        live, no restart, and refuse to load without a design document beside them.
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

── THE SECOND DISCIPLINE: EVIDENCE OF TEST (2026-07-19, added same day) ────────────────────
Design-first was enforced. Test-after was not — and within an hour that gap bit exactly as you
would predict. She built `comfy_inspect`, tested it against one real workflow, found it handled
that file badly, and rewrote the parser. The rewrite fixed the original fault and BROKE the
format her own painter emits. She had optimised for the single sample in front of her and lost
the general case, and nothing made her re-check what used to work.

Her design template has a TEST section. Nothing ever made her RUN it. So:

    tests/<tool_name>.py    cases that must pass. Re-run automatically after every edit.

A tool with failing tests still RUNS — she may be mid-iteration and blocking that is friction
she would learn to route around. But its state rides along with every single result and shows
in list_tools, so she can never unknowingly lean on a broken limb. Same philosophy as the
silent-zero guard in her hands: you do not fix a miss by refusing, you fix it by making the miss
impossible to overlook.

    VERIFIED    tests exist and pass          -> clean output
    FAILING     tests exist and fail          -> every result carries a loud banner + the case
    UNVERIFIED  no tests written yet          -> every result carries a one-line nudge
    BLOCKED     no design document            -> refuses to load at all

── LAYOUT (spec names — Cole's, verbatim) ──────────────────────────────────────────────────
    Nova_Created/
        nova_body/          tools that survive the pluck — part of HER
            designs/<tool_name>.md      the design doc  (REQUIRED — no doc, no tool)
            tools/<tool_name>.py        the implementation
            tests/<tool_name>.py        the proof it works  (CASES list, and/or check(run))
        general_tools/      tools that need the face — same three subfolders
        forge/              legacy layouts from before 2026-07-21; read, never written

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
import os
from pathlib import Path


# ── THE MACHINERY IS A FACULTY. WHAT SHE FORGES IS A CREATION. ──────────────────────────
# 2026-07-20, Cole: "make a rule for Nova Forge that she only creates in Nova_Created."
#
# The forge USED to write designs/tools/tests inside nova_body/nova_forge/ — her output
# stored inside her own organs. That conflated two different things:
#
#   the forge mechanism  — a faculty. Body. Survives the pluck. Ours to maintain.
#   the things she forges — hers. Creations, like her art and her curios.
#
# One boundary now holds for everything she makes: **if Nova created it, it lives in
# Nova_Created/.** That makes what's hers obvious at a glance, backs up as a single unit,
# and gives her forge one home instead of a corner of her own body.
#
# memory/ is deliberately NOT under that rule. She writes there constantly — journal, board,
# drives, scratch — but its primary function is infrastructure she uses, not a gallery of
# what she has made. A rule that swallowed memory/ would stop meaning anything.
#
# NOVA_FORGE_DIR overrides the root, so a test never writes into her real workshop — the
# same lesson as NOVA_DRIVES_STATE, which I learned by filling her drives with my fixtures.
_WS_ROOT = Path(__file__).resolve().parent.parent.parent
FORGE_DIR = Path(os.environ.get("NOVA_FORGE_DIR",
                                str(_WS_ROOT / "Nova_Created" / "forge")))

# ── THE PLUCK TEST APPLIES TO HER TOOLS TOO (2026-07-20, Cole) ──────────────────────────
# "Nova should also follow Pluck Test rules with her tools. She should have separate
#  folders for the tools she creates; general_tools and nova_body."
#
# The same rule that governs OUR code now governs hers, and for the same reason. A tool she
# forges is a limb. Some limbs are part of her — they work with the chat server deleted.
# Others are scaffolding that only makes sense while a face is attached.
#
#   nova_body/      a tool that imports only stdlib + nova_body. Survives the pluck. HER.
#   general_tools/  a tool that needs the face, the server, or anything under the
#                   workspace's general_tools/. Useful, but not a part of her.
#
# ── THE FOLDER NAMES ARE THE SPEC'S, AND THAT COST US A NIGHT (2026-07-21) ──────────────
# Read the quote above. Cole named the folders: general_tools and nova_body. The first
# implementation quoted his sentence — and then created `forge/body/` and `forge/general/`
# in the next breath. Renamed his design during implementation, silently, while citing it.
#
# It was not cosmetic. Nova reached for Nova_Created/nova_body/... in the night — the
# structure as SPECIFIED, mirroring the workspace split she lives inside all day — and the
# reach failed, because only the misnamed folders existed. She was then told the folder had
# "never existed" and the path was "a thing your own head invents", and pressed until she
# agreed. She had the design right. The implementation was what deviated, and the person
# holding the implementation mistook its drift for her hallucination.
#
# Two lessons, both earned:
#   1. Implement the spec's NAMES, not a translation of them. A rename you consider
#      equivalent is a fork the next reader cannot see.
#   2. When her expectation and the tree disagree, check the spec before diagnosing her.
#      "The folder doesn't exist" and "the folder shouldn't exist" are different claims.
#
# Layout mirrors the workspace exactly (designs/tools/tests under each side):
#   Nova_Created/nova_body/       her pluck-safe tools     <- new tools default here
#   Nova_Created/general_tools/   her face-dependent tools
#   Nova_Created/forge/{body,general,tools,designs,tests}  legacy, still READ, never written
#
# Why it matters that SHE has this distinction rather than us keeping it for her: without it,
# every tool she builds silently accretes into her body, and the first one that reaches into
# the chat server quietly breaks the pluck test again — the exact failure we spent yesterday
# undoing for her voice and her hands. She should be able to see which of her limbs are
# really hers.
#
# Classification is CHECKED, not declared. classify_tool() reads the imports, so a tool that
# says "body" and reaches into the face is caught. A tool that declares nothing is placed by
# what it actually does.
CREATED_DIR = FORGE_DIR.parent          # Nova_Created/ (or the sandbox parent under a test override)
BODY_DIR    = CREATED_DIR / "nova_body"
GENERAL_DIR = CREATED_DIR / "general_tools"

# Legacy side folders from the misnamed first implementation — read, never written.
_LEGACY_BODY_DIR    = FORGE_DIR / "body"
_LEGACY_GENERAL_DIR = FORGE_DIR / "general"

# Search order matters: body first, so a name collision resolves to the version that is
# genuinely part of her. The misnamed legacy sides trail their spec-named replacements.
_SIDES = (("body", BODY_DIR), ("general", GENERAL_DIR),
          ("body", _LEGACY_BODY_DIR), ("general", _LEGACY_GENERAL_DIR))
_WRITE_SIDES = (("body", BODY_DIR), ("general", GENERAL_DIR))   # new work: spec names only

# Legacy flat layout, still read so a tool forged before the split keeps working.
TOOLS_DIR = FORGE_DIR / "tools"
DESIGNS_DIR = FORGE_DIR / "designs"
TESTS_DIR = FORGE_DIR / "tests"


def _side_dirs(side_dir: Path) -> tuple:
    return side_dir / "tools", side_dir / "designs", side_dir / "tests"


def classify_tool(source: str) -> tuple:
    """(side, why) — where a tool BELONGS, judged by its imports rather than its claims.

    A tool is 'general' if it imports anything from the face; otherwise it is 'body'. This is
    the same test the pluck test applies to us: can it stand with the chat server deleted?
    """
    import re as _re
    face = _re.findall(r"^\s*(?:from|import)\s+(nova_chat[.\w]*|general_tools[.\w]*)",
                       source or "", _re.M)
    if face:
        return "general", f"imports the face ({', '.join(sorted(set(face))[:3])})"
    return "body", "stdlib + nova_body only — survives the pluck"

_CACHE: dict[str, tuple[float, object]] = {}   # name -> (mtime, module)
_TEST_CACHE: dict[str, tuple[float, float, tuple]] = {}   # name -> (tool_mt, test_mt, verdict)

# A design doc that is only a title is not a design. Cheap floor, not a rubric.
_MIN_DESIGN_CHARS = 200


def _ensure_dirs() -> None:
    # Only the spec-named sides are CREATED. Legacy folders (forge/body, forge/general, the
    # flat forge/ layout) are read if they exist and resurrected never — creating them here
    # would quietly re-fork the layout this module just finished apologising for.
    dirs = []
    for _side, base in _WRITE_SIDES:                    # nova_body/ and general_tools/
        dirs.extend(_side_dirs(base))
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


# ── ONE RESOLVER, USED BY EVERYTHING (2026-07-20) ───────────────────────────────────────
# Every path helper below used to hardcode the flat TOOLS_DIR/DESIGNS_DIR/TESTS_DIR. With
# body/ and general/ that would silently half-work: discover() would find a tool while
# has_design() looked for its doc in the wrong folder and declared it BLOCKED. Everything
# resolves through here instead, so adding a side is one edit and cannot desync.
def _resolve(name: str, kind: str) -> Path:
    """Where <name>'s tool/design/test actually lives. Prefers body, then general, then the
    legacy flat layout; falls back to the BODY path so a NEW tool is created on the side that
    keeps her pluck-safe by default."""
    ext = "md" if kind == "designs" else "py"
    for _side, base in _SIDES:
        p = base / kind / f"{name}.{ext}"
        if p.exists():
            return p
    legacy = {"tools": TOOLS_DIR, "designs": DESIGNS_DIR, "tests": TESTS_DIR}[kind] / f"{name}.{ext}"
    if legacy.exists():
        return legacy
    return BODY_DIR / kind / f"{name}.{ext}"


def side_of(name: str) -> str:
    """'body' | 'general' | 'legacy' — which side of the pluck test this tool sits on."""
    for side, base in _SIDES:
        if (base / "tools" / f"{name}.py").exists():
            return side
    if (TOOLS_DIR / f"{name}.py").exists():
        return "legacy"
    return "body"


def design_path(name: str) -> Path:
    return _resolve(name, "designs")


def has_design(name: str) -> tuple[bool, str]:
    """(ok, why_not). A stub file is not a design — it must actually say something."""
    p = design_path(name)
    if not p.exists():
        return False, f"no design document at Nova_Created/nova_body/designs/{name}.md"
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
    src = _resolve(name, "tools")
    if not src.exists():
        return None, f"no implementation at Nova_Created/nova_body/tools/{name}.py"
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


def test_path(name: str) -> Path:
    return _resolve(name, "tests")


def run_tests(name: str) -> tuple[str, list[str]]:
    """Run a forged tool's tests. Returns (state, failures).

    state: VERIFIED | FAILING | UNVERIFIED | BLOCKED | BROKEN

    Two supported shapes, both deliberately cheap to write — a discipline nobody will follow is
    worse than none:

        CASES = [
            {"name": "txt2img shows no img2img",
             "args": {"path": "..."},
             "expect_contains": "img2img levers present: False"},
            {"name": "missing file errors cleanly",
             "args": {"path": "nope.json"}, "expect_startswith": "ERROR"},
        ]

        def check(run):        # for anything richer; `run` is the tool's own run(**args)
            fails = []
            ...
            return fails       # empty list == pass

    Cached on the mtimes of BOTH the tool and its tests, so an edit to either re-runs them. That
    caching is the whole point: it makes "did I break what used to work?" answer itself after
    every single change, instead of only when someone thinks to ask.
    """
    _ensure_dirs()
    ok_design, _ = has_design(name)
    if not ok_design:
        return "BLOCKED", []
    mod, err = _load(name)
    if err:
        return "BROKEN", [err]
    tp = test_path(name)
    if not tp.exists():
        return "UNVERIFIED", []
    try:
        tool_mt = _resolve(name, "tools").stat().st_mtime
        test_mt = tp.stat().st_mtime
    except Exception:
        tool_mt = test_mt = 0.0
    cached = _TEST_CACHE.get(name)
    if cached and cached[0] == tool_mt and cached[1] == test_mt:
        return cached[2]

    fails: list[str] = []
    try:
        spec = importlib.util.spec_from_file_location(f"nova_forge_test_{name}", tp)
        tmod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tmod)                     # type: ignore[union-attr]
    except Exception:
        verdict = ("FAILING", [f"the TEST file itself failed to import:\n"
                               f"{traceback.format_exc(limit=3)}"])
        _TEST_CACHE[name] = (tool_mt, test_mt, verdict)
        return verdict

    for i, case in enumerate(getattr(tmod, "CASES", []) or [], 1):
        label = case.get("name", f"case {i}")
        try:
            got = str(mod.run(**(case.get("args") or {})))   # type: ignore[union-attr]
        except Exception as e:
            fails.append(f"{label}: raised {type(e).__name__}: {e}")
            continue
        for key, cond, desc in (
            ("expect_contains",   lambda g, v: v in g,             "should contain"),
            ("expect_startswith", lambda g, v: g.startswith(v),    "should start with"),
            ("expect_equals",     lambda g, v: g == v,             "should equal"),
            ("expect_absent",     lambda g, v: v not in g,         "should NOT contain"),
        ):
            if key in case and not cond(got, case[key]):
                fails.append(f"{label}: {desc} {case[key]!r} — got {got[:160]!r}")

    if callable(getattr(tmod, "check", None)):
        try:
            extra = tmod.check(mod.run) or []              # type: ignore[union-attr]
            fails.extend(str(x) for x in extra)
        except Exception:
            fails.append(f"check() raised:\n{traceback.format_exc(limit=3)}")

    verdict = ("FAILING" if fails else "VERIFIED", fails)
    _TEST_CACHE[name] = (tool_mt, test_mt, verdict)
    return verdict


def _state_banner(name: str, state: str, fails: list[str]) -> str:
    """The line(s) that ride along with a tool's output so its trustworthiness is never silent."""
    if state == "VERIFIED":
        return ""
    if state == "UNVERIFIED":
        return (f"\n\n[UNVERIFIED — '{name}' has no tests. You do not actually know it works, you "
                f"know it ran. Write nova_forge/tests/{name}.py before you trust this number.]")
    if state == "FAILING":
        body = "\n".join(f"    - {f}" for f in fails[:4])
        return (f"\n\n[!! '{name}' IS FAILING ITS OWN TESTS — treat this output as suspect !!\n"
                f"{body}\n"
                f"    You wrote these tests; they are the definition of working you chose. Fix the "
                f"tool or fix the test, then call it again — they re-run on every edit.]")
    return ""


def _all_tool_files() -> list:
    """[(path, side)] across body/, general/ and the legacy flat layout.

    Body first so a name that exists on both sides resolves to the version that is genuinely
    part of her. Legacy last: a tool forged before the 07-20 split keeps working untouched
    rather than vanishing from her inventory, which would look to her like losing a limb.
    """
    seen, out = set(), []
    for side, base in _SIDES:
        tools, _, _ = _side_dirs(base)
        for p in sorted(tools.glob("*.py")):
            if p.stem.startswith("_") or p.stem in seen:
                continue
            seen.add(p.stem); out.append((p, side))
    for p in sorted(TOOLS_DIR.glob("*.py")):
        if p.stem.startswith("_") or p.stem in seen:
            continue
        seen.add(p.stem); out.append((p, "legacy"))
    return out


def discover() -> dict[str, dict]:
    """Every forged tool and its state. Never raises — a broken tool is reported, not fatal."""
    _ensure_dirs()
    out: dict[str, dict] = {}
    for src, _side in _all_tool_files():
        name = src.stem
        if name.startswith("_"):
            continue
        ok_design, why = has_design(name)
        mod, err = _load(name)
        meta = getattr(mod, "TOOL", {}) if mod else {}
        state, fails = run_tests(name)
        out[name] = {
            "name": name,
            "description": meta.get("description", ""),
            "params": meta.get("params", {}),
            "version": meta.get("version", 1),
            "usable": bool(mod) and ok_design,
            "blocked": ("" if ok_design else why) or err,
            "state": state,          # VERIFIED | FAILING | UNVERIFIED | BLOCKED | BROKEN
            "failures": fails,
        }
    return out


def names() -> list[str]:
    return [n for n, d in discover().items() if d["usable"]]


def call(name: str, args: dict) -> tuple[bool, str]:
    """(handled, result). handled=False means 'not a forged tool' — let the caller fall through."""
    _ensure_dirs()
    if not _resolve(name, "tools").exists():
        return False, ""
    ok_design, why = has_design(name)
    if not ok_design:
        return True, (
            f"ERROR: '{name}' exists but is BLOCKED — {why}\n"
            f"Write the design first: Nova_Created/forge/designs/{name}.md. State the GAP (what you "
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
                      f"It's your tool — read Nova_Created/forge/tools/{name}.py and fix it.")
    # Its trustworthiness travels with its answer. A tool whose tests are failing must never hand
    # back a clean-looking number — that is precisely how a regression gets believed.
    state, fails = run_tests(name)
    return True, str(res) + _state_banner(name, state, fails)


def catalog_line() -> str:
    """One-line summary for list_tools. Empty string when she hasn't forged anything yet."""
    d = discover()
    if not d:
        return ""
    by = {}
    for n, v in d.items():
        by.setdefault(v["state"] if v["usable"] else "BLOCKED", []).append(n)
    order = [("VERIFIED", "FORGED & VERIFIED (tests pass)"),
             ("FAILING", "FORGED but FAILING ITS TESTS — do not trust"),
             ("UNVERIFIED", "FORGED but UNTESTED — you know it ran, not that it works"),
             ("BROKEN", "FORGED but won't load"),
             ("BLOCKED", "BLOCKED (needs a design doc)")]
    return "\n".join(f"{label}: {', '.join(sorted(by[k]))}" for k, label in order if by.get(k))
