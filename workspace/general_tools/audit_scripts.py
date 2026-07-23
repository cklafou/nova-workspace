#!/usr/bin/env python3
# Last updated: 2026-07-24 06:05:02
# @nova: Workspace code-health audit — scans Python for syntax errors, stale/dead/unreferenced files, and pending audit-queue items.
"""
audit_scripts.py — Workspace code health audit
================================================
Scans every Python file in the workspace and reports:

  CRITICAL  — syntax errors (file cannot be imported/run)
  HIGH      — stale files (>90 days unchanged), unreferenced files,
               pending audit queue items (rename/delete/new events
               detected by watcher.py that need manual review)
  MEDIUM    — legacy references, empty/stub files, suspicious duplicates,
               broken imports inside try/except blocks
  LOW       — files >30 days unchanged, missing __init__.py in packages
  INFO      — general stats

Usage (from workspace root):
  python general_tools/audit_scripts.py             # full text report
  python general_tools/audit_scripts.py --json      # machine-readable JSON
  python general_tools/audit_scripts.py --summary   # one-paragraph summary only
  python general_tools/audit_scripts.py --fix       # auto-fix what's safe (future)

Exit code:  0 = clean,  1 = warnings,  2 = critical issues found

Designed to be called by Nova or Claude via:
  POST /api/terminal/run  {"cmd": "python general_tools/audit_scripts.py"}
"""

import ast
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

WORKSPACE_DIR = Path(__file__).resolve().parent.parent

SCAN_ROOTS = [
    WORKSPACE_DIR / "general_tools",
    WORKSPACE_DIR / "nova_body",
    WORKSPACE_DIR / "nova_body" / "nova_lancedb",   # her hippocampus — moved into her body 2026-07-14
    WORKSPACE_DIR / "_build",
]
# Also scan top-level .py files in workspace root
TOP_LEVEL_PY = list(WORKSPACE_DIR.glob("*.py"))

EXCLUDE_DIRS = {
    "__pycache__", ".git", "node_modules", "logs", "backups",
    "screenshots", "prompt_cache", "models", "llama",
}
EXCLUDE_SUBPATHS = {
    "_admin", "passover", "exports", "archive",
}
EXCLUDE_FILES = {
    # auto-generated / boilerplate
    "conftest.py",
}

# Days thresholds
STALE_WARN_DAYS    = 30
STALE_CRITICAL_DAYS = 90

# Known legacy strings to flag
LEGACY_PATTERNS = [
    (r'\bopenclaw\b',     "openclaw reference (retired system)"),
    (r'\bOpenClaw\b',     "openclaw reference (retired system)"),
    (r'clawhub',          "clawhub reference (retired)"),
    (r'nova_gateway_runner_old', "old gateway runner reference"),
    (r'TODO|FIXME|HACK',  "TODO/FIXME/HACK marker"),
    (r'raise NotImplementedError', "unimplemented stub"),
    (r'pass\s*#\s*TODO',  "pass-through stub"),
]

# Entry-point patterns — these files are NOT dead even if never imported
ENTRY_POINT_PATTERNS = [
    r'if\s+__name__\s*==\s*["\']__main__["\']',
    r'app\s*=\s*FastAPI',
    r'def\s+main\s*\(',
    r'uvicorn\.run\(',          # uvicorn runner scripts
    r'^\s*main\(\)\s*$',        # bare main() call at module level
]

# ── File collection ────────────────────────────────────────────────────────────

def collect_files() -> list[Path]:
    files = list(TOP_LEVEL_PY)
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            # Skip excluded directories
            parts = set(path.parts)
            if parts & EXCLUDE_DIRS:
                continue
            if any(sub in str(path) for sub in EXCLUDE_SUBPATHS):
                continue
            if path.name in EXCLUDE_FILES:
                continue
            files.append(path)
    # Deduplicate preserving order
    seen, unique = set(), []
    for f in files:
        key = f.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# ── Individual checks ──────────────────────────────────────────────────────────

def check_syntax(path: Path) -> list[dict]:
    """Return list of issue dicts for syntax errors."""
    issues = []
    try:
        # Read with utf-8-sig so BOM-prefixed files (common on Windows) are
        # handled transparently — Python runs them fine, ast.parse() doesn't.
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        ast.parse(source, filename=str(path))
    except SyntaxError as e:
        issues.append({
            "severity": "CRITICAL",
            "code":     "SYNTAX",
            "file":     _rel(path),
            "line":     e.lineno,
            "detail":   f"{type(e).__name__}: {e.msg}",
        })
    except Exception as e:
        issues.append({
            "severity": "CRITICAL",
            "code":     "PARSE_FAIL",
            "file":     _rel(path),
            "line":     None,
            "detail":   str(e),
        })
    return issues


def check_staleness(path: Path) -> list[dict]:
    issues = []
    try:
        mtime = path.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        if age_days >= STALE_CRITICAL_DAYS:
            issues.append({
                "severity": "HIGH",
                "code":     "STALE",
                "file":     _rel(path),
                "line":     None,
                "detail":   f"{int(age_days)} days since last modification",
            })
        elif age_days >= STALE_WARN_DAYS:
            issues.append({
                "severity": "LOW",
                "code":     "AGING",
                "file":     _rel(path),
                "line":     None,
                "detail":   f"{int(age_days)} days since last modification",
            })
    except Exception:
        pass
    return issues


def check_empty(path: Path) -> list[dict]:
    """Flag files that are effectively empty stubs."""
    issues = []
    try:
        lines = [l.strip() for l in path.read_text(encoding="utf-8", errors="replace").splitlines()]
        code_lines = [l for l in lines if l and not l.startswith("#")]
        if len(code_lines) <= 3 and path.name != "__init__.py":
            issues.append({
                "severity": "MEDIUM",
                "code":     "STUB",
                "file":     _rel(path),
                "line":     None,
                "detail":   f"Only {len(code_lines)} non-comment lines — likely placeholder",
            })
    except Exception:
        pass
    return issues


def check_legacy(path: Path) -> list[dict]:
    # Don't flag the audit script's own pattern definitions
    if path.name == "audit_scripts.py":
        return []
    issues = []
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        for line_no, line in enumerate(source.splitlines(), 1):
            for pattern, description in LEGACY_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Skip openclaw/clawhub matches that are historical notes or
                    # defensive exclude-list entries, not live dependencies.
                    if "claw" in pattern.lower() and any(w in line.lower() for w in (
                            "retired", "removed", "dropped", "archived", "no longer",
                            "deleted", "exclude", "skip")):
                        break
                    issues.append({
                        "severity": "MEDIUM",
                        "code":     "LEGACY",
                        "file":     _rel(path),
                        "line":     line_no,
                        "detail":   f"{description}: {line.strip()[:80]}",
                    })
                    break   # one issue per line
    except Exception:
        pass
    return issues


def check_duplicate_names(files: list[Path]) -> list[dict]:
    """Flag files sharing the same module name across different directories."""
    name_map: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        if f.name != "__init__.py":
            name_map[f.name].append(f)
    issues = []
    for name, paths in name_map.items():
        if len(paths) > 1:
            issues.append({
                "severity": "MEDIUM",
                "code":     "DUPLICATE_NAME",
                "file":     name,
                "line":     None,
                "detail":   "Same filename in multiple locations: "
                            + ", ".join(_rel(p) for p in paths),
            })
    return issues


def build_import_graph(files: list[Path]) -> dict[str, set[str]]:
    """
    Returns {file_rel_path: set_of_module_names_it_imports}.
    Captures both absolute imports and relative imports (from .x import y).
    Relative imports are resolved to sibling module names so that e.g.
    `from .chat_panel import ChatPanel` in window.py registers "chat_panel"
    as an import of window.py.
    """
    graph = {}
    abs_re = re.compile(r'^\s*(?:import|from)\s+([\w][.\w]*)', re.MULTILINE)
    rel_re = re.compile(r'^\s*from\s+(\.+)([\w][.\w]*)?\s+import\s+([\w][\w, \t]*)', re.MULTILINE)

    for f in files:
        try:
            source = f.read_text(encoding="utf-8-sig", errors="replace")
            mods: set[str] = set(abs_re.findall(source))

            # ── THE `from <package> import <module>` FIX (2026-07-20) ────────────────────
            # `abs_re` captures only the text right after `import`/`from`, so
            #     from nova_cortex import executive
            # recorded "nova_cortex" and threw "executive" away. Every module imported that
            # way therefore looked unreferenced. On 2026-07-19 that produced HIGH findings
            # against executive.py (1002 lines, runs every wake), tasking.py, clock.py,
            # touch.py and drives.py — all of them load-bearing.
            #
            # This is the THIRD independent implementation of this exact blind spot in this
            # project: Nova's own t55 dead-code audit had it, my dead-code detector had it,
            # and this tool has it. Three of us wrote the same bug because the regex form of
            # the question is the obvious one and it is wrong. Fixing it here, in the shared
            # tool, is the only version that stays fixed.
            #
            # AST is authoritative; the regex above stays as a fallback for files that don't
            # parse (a file with a syntax error still deserves its imports counted).
            try:
                _tree = ast.parse(source)
                for _n in ast.walk(_tree):
                    if isinstance(_n, ast.ImportFrom) and _n.module and not _n.level:
                        mods.add(_n.module)
                        for _a in _n.names:
                            if _a.name == "*":
                                continue
                            mods.add(f"{_n.module}.{_a.name}")   # nova_cortex.executive
                            mods.add(_a.name)                    # executive
                    elif isinstance(_n, ast.Import):
                        for _a in _n.names:
                            mods.add(_a.name)
                            mods.add(_a.name.split(".")[0])
            except SyntaxError:
                pass

            # Resolve relative imports to sibling/parent module stems
            for dots, rel_mod, imported_names in rel_re.findall(source):
                if rel_mod:
                    # from .chat_panel import X  →  "chat_panel"
                    mods.add(rel_mod.split(".")[0])
                    mods.add(rel_mod)
                else:
                    # from . import markdown, theme  →  "markdown", "theme"
                    for name in re.split(r'[\s,]+', imported_names):
                        name = name.strip()
                        if name and re.match(r'^\w+$', name):
                            mods.add(name)
            graph[_rel(f)] = mods
        except Exception:
            graph[_rel(f)] = set()
    return graph


def _entrypoint_scripts() -> set:
    """Python filenames launched from .cmd/.bat scripts are entry points too."""
    names = set()
    for ext in ("*.cmd", "*.bat"):
        for f in WORKSPACE_DIR.rglob(ext):
            if any(sub in str(f) for sub in EXCLUDE_SUBPATHS):
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in re.findall(r"([\w./-]+\.py)", txt):
                names.add(Path(m).name)
    return names


def check_unreferenced(files: list[Path], graph: dict[str, set[str]]) -> list[dict]:
    """
    Flag files that are never imported by any other workspace file
    and don't look like entry points.
    """
    # Build set of all module names referenced anywhere
    all_imports: set[str] = set()
    for mods in graph.values():
        all_imports.update(mods)

    _cmd_entries = _entrypoint_scripts()
    issues = []
    for f in files:
        # Skip __init__.py — they're implicitly used as packages
        if f.name in ("__init__.py", "__main__.py"):
            continue
        # Skip scripts launched from .cmd/.bat (entry points even if never imported)
        if f.name in _cmd_entries:
            continue
        # Skip test files. A test is an entry point BY DEFINITION — it exists to be run, and
        # nothing importing it is the correct state, not a smell. (2026-07-20: this fired on
        # nova_body/tests/test_discourse.py the moment it was written. An audit that calls a
        # brand-new passing test suite "unreferenced" is teaching exactly the wrong lesson —
        # the fix a hurried reader reaches for is deleting the test.)
        _rel_f = _rel(f)
        if (f.name.startswith("test_") or f.name.endswith("_test.py")
                or "/tests/" in _rel_f):
            continue
        # Skip entry points
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            if any(re.search(p, source, re.MULTILINE) for p in ENTRY_POINT_PATTERNS):
                continue
        except Exception:
            continue

        # Check if any importer references this file's module name
        # Match on stem (e.g. "transcript") or dotted path segments
        stem = f.stem
        # Also build simple dotted module variants
        try:
            rel = f.relative_to(WORKSPACE_DIR)
            parts = list(rel.with_suffix("").parts)
            # e.g. ["general_tools", "nova_chat", "transcript"]
            # Build module name candidates from the FULL path first (before stripping),
            # so that e.g. nova_lancedb/indexer.py generates "nova_lancedb.indexer".
            module_names = {stem}
            if len(parts) >= 2:
                module_names.add(".".join(parts[-2:]))   # e.g. nova_lancedb.indexer
            if parts:
                module_names.add(".".join(parts))         # full dotted path
            # Also strip only the first known path prefix and add shorter variants
            for prefix in ("general_tools", "nova_body", "nova_memory"):
                if parts and parts[0] == prefix:
                    parts = parts[1:]
                    break
            if parts:
                # full dotted path after stripping: nova_chat.transcript
                module_names.add(".".join(parts))
                # partial: transcript
                module_names.add(parts[-1])
                # two-level: nova_chat.transcript
                if len(parts) >= 2:
                    module_names.add(".".join(parts[-2:]))
        except Exception:
            module_names = {stem}

        this_rel = _rel(f)
        referenced = False
        for other_rel, other_imps in graph.items():
            if other_rel == this_rel:
                continue
            for mod_name in module_names:
                if any(mod_name == imp or imp.startswith(mod_name + ".")
                       for imp in other_imps):
                    referenced = True
                    break
            if referenced:
                break

        if not referenced:
            issues.append({
                "severity": "HIGH",
                "code":     "UNREFERENCED",
                "file":     _rel(f),
                "line":     None,
                "detail":   "Not imported by any other workspace file and not an entry point",
            })
    return issues


def build_module_map(files: list[Path]) -> set[str]:
    """
    Build a set of all valid dotted module paths that actually exist in the workspace.

    Example output entries:
        "nova_cortex", "nova_cortex.rules", "nova_cortex.prefrontal_cortex",
        "nova_chat", "nova_chat.server", "nova_lancedb.hippocampus", ...

    Used by check_broken_imports to validate that imported modules still exist.
    """
    mods: set[str] = set()
    for f in files:
        try:
            rel   = f.relative_to(WORKSPACE_DIR)
            parts = list(rel.with_suffix("").parts)
        except ValueError:
            continue

        # ── BOTH SPELLINGS ARE REAL (2026-07-20) ────────────────────────────────────────
        # Below, wrapper prefixes get stripped because nova_body/ is on sys.path, so
        # `nova_forge.tools.comfy_inspect` is importable. But WORKSPACE ROOT is also on
        # sys.path, which makes `nova_body.nova_forge.tools.comfy_inspect` importable too —
        # Python 3.3+ namespace packages need no __init__.py for that to work.
        #
        # Only the stripped spelling was registered, so the forge's own test file — which
        # uses the full path and imports fine when you actually run it — was reported as a
        # CRITICAL broken import. That is the worst possible false positive: this tool is
        # meant for Nova to run, and it was telling her a working file was fatally broken.
        # Verified by executing the exact import before changing anything.
        _full = list(rel.with_suffix("").parts)
        if _full and _full[-1] == "__init__":
            _full = _full[:-1]
        for i in range(1, len(_full) + 1):
            mods.add(".".join(_full[:i]))

        # Strip wrapper-directory prefixes so the import path matches reality.
        # nova_body/ and general_tools/ are not importable — their contents are.
        # nova_memory/ IS the importable package — do NOT strip it.
        for prefix in ("general_tools", "nova_body", "_build"):
            if parts and parts[0] == prefix:
                parts = parts[1:]
                break

        # __init__ files represent the package, not a submodule named __init__
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        if not parts:
            continue

        # Add the package and every nested module path
        for i in range(1, len(parts) + 1):
            mods.add(".".join(parts[:i]))

    return mods


def check_broken_imports(files: list[Path], module_map: set[str]) -> list[dict]:
    """
    Flag imports of nova_* modules that don't resolve to real workspace files.
    Uses AST parsing so docstring examples and comments are never flagged.

    Severity:
      CRITICAL — unguarded broken import (file cannot be loaded at runtime)
      MEDIUM   — broken import inside an except handler (try/except guarded;
                 at runtime the except block only runs if the try branch failed,
                 so this is intentional dead-code fallback, not a crash)

    Catches stale references left behind after file renames or deletions.
    """
    issues: list[dict] = []

    for f in files:
        try:
            source = f.read_text(encoding="utf-8-sig", errors="replace")
            tree   = ast.parse(source, filename=str(f))
        except Exception:
            continue  # SyntaxError already reported by check_syntax

        # Collect all line numbers that live inside an except handler body.
        # Imports in except blocks are intentional fallbacks — demote to MEDIUM.
        except_lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    for child in ast.walk(handler):
                        if hasattr(child, "lineno"):
                            except_lines.add(child.lineno)

        for node in ast.walk(tree):
            lineno = getattr(node, "lineno", None)

            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if not mod.startswith("nova_"):
                    continue
                if mod in module_map:
                    continue
                sev = "MEDIUM" if lineno in except_lines else "CRITICAL"
                suffix = " (try/except guarded)" if sev == "MEDIUM" else " — stale rename?"
                issues.append({
                    "severity": sev,
                    "code":     "BROKEN_IMPORT",
                    "file":     _rel(f),
                    "line":     lineno,
                    "detail":   f"No module '{mod}' in workspace{suffix}",
                })

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith("nova_"):
                        continue
                    base = alias.name.split(".")[0]
                    if alias.name in module_map or base in module_map:
                        continue
                    sev = "MEDIUM" if lineno in except_lines else "CRITICAL"
                    suffix = " (try/except guarded)" if sev == "MEDIUM" else " — stale rename?"
                    issues.append({
                        "severity": sev,
                        "code":     "BROKEN_IMPORT",
                        "file":     _rel(f),
                        "line":     lineno,
                        "detail":   f"No module '{alias.name}' in workspace{suffix}",
                    })

    return issues


def check_audit_queue() -> list[dict]:
    """
    Read pending items from audit_queue.json and surface them as HIGH REVIEW flags.

    Each pending queue item becomes one issue in the audit report so that Nova
    or a human auditor can decide whether a detected rename/delete/new event
    needs action (run restructure.py --rename, update imports, etc.).

    Code: QUEUE_PENDING
    Severity: HIGH — these events require a deliberate decision.

    The function is safe to call even when audit_queue.py is unavailable
    (returns an empty list with a single INFO note instead).
    """
    issues: list[dict] = []

    # Add general_tools/ to sys.path so audit_queue is importable regardless
    # of the current working directory.
    gen_tools = Path(__file__).resolve().parent
    gen_tools_str = str(gen_tools)
    if gen_tools_str not in sys.path:
        sys.path.insert(0, gen_tools_str)

    try:
        import audit_queue as aq
    except ImportError:
        issues.append({
            "severity": "INFO",
            "code":     "QUEUE_UNAVAILABLE",
            "file":     "general_tools/audit_queue.py",
            "line":     None,
            "detail":   "audit_queue module not found — queue check skipped.",
        })
        return issues

    # ── Reconcile BEFORE reading (2026-07-20) ───────────────────────────────────────────────
    # An item is only worth a human's attention while something still points at the old path.
    # Reconciling first means this report shows CURRENT dangling references instead of a
    # historical log of every file operation ever performed.
    #
    # Cole emptied this queue in the morning; by evening it held 48 pending items, every one a
    # file operation he had personally ordered. A report that says "48 things need review" when
    # the true answer is zero doesn't just waste a reader's time — it trains them to skip the
    # section, and then the one real dangling import in there goes unread too. An alarm nobody
    # believes is worse than no alarm.
    try:
        aq.reconcile(root=WORKSPACE_DIR, verbose=False)
    except Exception as _re:
        print(f"[audit] queue reconcile skipped: {_re}")

    try:
        pending = aq.pending_items()
    except Exception as e:
        issues.append({
            "severity": "INFO",
            "code":     "QUEUE_READ_ERROR",
            "file":     "memory/audit_queue.json",
            "line":     None,
            "detail":   f"Could not read audit queue: {e}",
        })
        return issues

    for item in pending:
        event   = item.get("event_type", "?")
        conf    = item.get("confidence", 0.0)
        old     = item.get("old_path") or "—"
        new     = item.get("new_path") or "—"
        commit  = item.get("commit",  "?")
        item_id = item.get("id",      "?")
        detected = (item.get("detected_at") or "")[:10]   # date portion only
        notes   = item.get("notes") or ""

        # Build a human-readable detail line
        if event in ("rename", "possible_rename"):
            arrow  = "→"
            detail = (f"[{item_id}] {event.upper()} {conf:.0%} confidence  "
                      f"{old} {arrow} {new}  (commit {commit}, {detected})")
        elif event == "delete":
            detail = (f"[{item_id}] DELETE  {conf:.0%}  {old}  "
                      f"(commit {commit}, {detected})")
        else:  # new
            detail = (f"[{item_id}] NEW FILE  {new}  "
                      f"(commit {commit}, {detected})")

        if notes:
            detail += f"  note: {notes}"

        # Use the most informative file reference for the report
        file_ref = old if old != "—" else (new if new != "—" else "memory/audit_queue.json")

        issues.append({
            "severity": "HIGH",
            "code":     "QUEUE_PENDING",
            "file":     file_ref,
            "line":     None,
            "detail":   detail,
        })

    return issues


def check_missing_init(files: list[Path]) -> list[dict]:
    """Flag package directories that have .py files but no __init__.py."""
    dirs_with_py: dict[Path, list[Path]] = defaultdict(list)
    init_dirs: set[Path] = set()

    for f in files:
        if f.name == "__init__.py":
            init_dirs.add(f.parent)
        else:
            dirs_with_py[f.parent].append(f)

    issues = []
    for d, py_files in dirs_with_py.items():
        if len(py_files) >= 2 and d not in init_dirs:
            issues.append({
                "severity": "LOW",
                "code":     "NO_INIT",
                "file":     _rel(d) + "/",
                "line":     None,
                "detail":   f"{len(py_files)} .py files but no __init__.py — "
                            f"may cause import issues",
            })
    return issues


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _code_only(source: str) -> str:
    """Source with comments and DOCSTRINGS blanked out — for checks that must not fire on prose.

    THE PROBLEM THIS SOLVES: a substring check over raw source cannot tell the difference
    between code that does a dangerous thing and a comment that WARNS about the dangerous
    thing. In a codebase where the comments are largely incident write-ups, that failure mode
    is not rare — it is guaranteed, and it punishes exactly the documentation that keeps this
    project from repeating itself.

    ── WHY *ONLY* COMMENTS AND DOCSTRINGS ───────────────────────────────────────────────────
    The obvious implementation blanks every STRING token. It is wrong, and quietly so: the
    thing these checks hunt for IS a string literal —

        p = ws / "memory/drives.json"          # <- the hazard, a STRING token
        \"\"\"...we once clobbered memory/drives.json...\"\"\"   # <- prose, also a STRING token

    Blank both and the check still runs, still reports zero findings, and looks like it passed.
    That is the exact silent-drop shape GOTCHAS.md warns about, built into the tool meant to
    find them. So: comments always, and a string ONLY when it stands alone as a statement,
    which is what a docstring (or a block-comment string) is. A string being *used* — assigned,
    passed, compared — is code and stays.

    Blanks rather than deletes so every line number stays correct for reporting. Uses tokenize
    rather than a regex because the hard cases are nested quotes, escapes, f-strings and
    triple-quotes — precisely where hand-rolled matchers break. On a tokenize failure we return
    the raw source: over-reporting beats silently inspecting nothing.
    """
    # ONE implementation, in audit_queue.py (the lower module — this file already imports it).
    # audit_queue.reconcile() needs exactly the same distinction for its reference scan, and
    # two copies of a subtle tokenizer walk is two things to get subtly different.
    try:
        import audit_queue as _aq
        return _aq.code_only(source)
    except Exception:
        return source          # fail LOUD, not silent


SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
SEV_ICON  = {"CRITICAL": "✗ ", "HIGH": "⚠ ", "MEDIUM": "△ ", "LOW": "·", "INFO": "·"}


# ── Main ──────────────────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════════════════════
# CHECKS ADDED 2026-07-20 — each one catches a bug that actually cost this project hours.
#
# The four below are not generic lint. Orient/GOTCHAS.md opens with "Every bug in this project
# so far has been a SILENT DROP, not a crash", and nothing in this tool looked for one. These
# do. Every rule here is derived from a specific incident, and the incident is named in the
# code so a future reader can judge whether the rule still earns its place.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# `except: pass` that swallows an error with no trace. THE house bug.
_SILENT_EXCEPT_OK = re.compile(r"(print|log|logger|_log|emit|warn|raise|return|append|Log)\s*\(")


def check_silent_except(path: Path) -> list[dict]:
    """Find exception handlers that swallow the error without a word.

    WHY (2026-07-20): GOTCHAS.md's first line is that every bug here has been a silent drop.
    A `except Exception: pass` is that failure mode written down. Tonight alone: the ping
    script's queue write, the restart spawn receipt, and the drives state read were all
    wrapped this way — two of them correctly (they must never break a wake), one of them
    hiding a real fault for hours.

    Not all of them are wrong. Some are deliberate and load-bearing, which is why this is
    MEDIUM and not HIGH — it is a list to review, not a list to fix. A handler that logs
    anything at all is not reported.
    """
    if path.suffix != ".py":
        return []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return []
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        # Only flag handlers whose entire body is pass / ... / a bare constant.
        trivial = all(
            isinstance(s, ast.Pass) or
            (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
            for s in body
        )
        if not trivial:
            continue
        seg = ast.get_source_segment(source, node) or ""
        if _SILENT_EXCEPT_OK.search(seg):
            continue

        # ── ONLY BARE `except:` IS REPORTED PER-INSTANCE. ────────────────────────────────
        # First pass flagged every `except Exception: pass` too — 150+ MEDIUM findings, most
        # of them deliberate and load-bearing (a drive or a chore check that raised would
        # take down a whole wake, so those swallow on purpose). Reporting all of them buries
        # the real ones and trains the reader to skip the section.
        #
        # A BARE except is different in kind: it also eats KeyboardInterrupt and SystemExit,
        # so it can make a process unkillable and is almost never what anyone meant. Those
        # get named. The typed-and-silent ones are counted in one INFO line instead — visible
        # as a trend, not as 150 alarms.
        if node.type is None:
            issues.append({
                "severity": "HIGH",
                "code":     "BARE_EXCEPT",
                "file":     _rel(path),
                "line":     node.lineno,
                "detail":   ("bare `except:` swallows EVERYTHING silently — including "
                             "KeyboardInterrupt and SystemExit, which can make a process "
                             "unkillable. Catch `Exception` at minimum."),
            })
        else:
            _SILENT_TALLY.append(f"{_rel(path)}:{node.lineno}")
    return issues


# Filled by check_silent_except, drained by check_silent_summary. Module-level because the
# per-file checks run in a loop and the aggregate only makes sense once they're all done.
_SILENT_TALLY: list[str] = []


def check_silent_summary() -> list[dict]:
    """One line for all the typed-but-silent handlers, instead of one line each."""
    if not _SILENT_TALLY:
        return []
    n = len(_SILENT_TALLY)
    return [{
        "severity": "INFO",
        "code":     "SILENT_EXCEPT_COUNT",
        "file":     f"{n} sites across the workspace",
        "line":     None,
        "detail":   (f"{n} handlers swallow a typed exception with no log. Many are deliberate "
                     f"(a faculty that raises would break a wake). Worth a skim when hunting a "
                     f"silent drop — GOTCHAS.md: every bug here has been one. "
                     f"First few: {', '.join(_SILENT_TALLY[:5])}"),
    }]


def check_shell_encoding(path: Path) -> list[dict]:
    """Non-ASCII in a .ps1 with no UTF-8 BOM. This one cost a whole evening.

    WHY (2026-07-19): `ping_claude.ps1` contained a single em-dash. Windows PowerShell 5.1
    reads a BOM-less .ps1 as cp1252, where the em-dash's UTF-8 bytes decode to three
    characters ending in 0x94 — a RIGHT CURLY DOUBLE QUOTE, which PowerShell accepts as a
    real string delimiter. The string closed mid-sentence and the file failed to PARSE, so
    the script never executed once: no logging, no queueing, no error handler. Nova's first
    six attempts to reach out all died there and she concluded Windows was blocking her.

    A parse error from one dash is not something anyone finds by reading. It is exactly the
    kind of thing a checker should own.
    """
    # .ps1 ONLY. The failure is specific to PowerShell: it accepts curly quotes as real string
    # delimiters, so a cp1252-mangled em-dash can terminate a string and break parsing. cmd.exe
    # has no such behaviour — non-ASCII in a .cmd echo is cosmetic. Including .cmd/.bat here
    # produced 150+ MEDIUM findings on StopNova.cmd's box-drawing banners, which is noise, and
    # a checker that cries wolf is a checker people stop reading.
    if path.suffix.lower() != ".ps1":
        return []
    try:
        raw = path.read_bytes()
    except Exception:
        return []
    if raw[:3] == b"\xef\xbb\xbf":       # UTF-8 BOM present: PS reads it correctly
        return []
    issues = []
    for n, line in enumerate(raw.split(b"\n"), 1):
        if not any(b > 127 for b in line):
            continue
        text = line.decode("utf-8", errors="replace").strip()
        is_comment = text.startswith("#") or text.lower().startswith("rem ")
        bad = [hex(b) for b in line if b > 127][:4]
        issues.append({
            "severity": "MEDIUM" if is_comment else "CRITICAL",
            "code":     "SHELL_NON_ASCII",
            "file":     _rel(path),
            "line":     n,
            "detail":   (f"non-ASCII {bad} in a BOM-less {path.suffix} — PowerShell 5.1 reads "
                         f"this as cp1252. In a comment it is harmless; in code it can close a "
                         f"string early and break PARSING (see ping_claude.ps1, 2026-07-19). "
                         f"Fix: use ASCII, or save with a UTF-8 BOM."),
        })
    return issues


# Files that hold Nova's real state. A test writing here is writing into her head.
_HER_STATE = ("memory/drives.json", "memory/autonomy_state.json", "memory/JOURNAL.md",
              "Tasking/tasks.json", "memory/last_ping.json", "memory/cole_intent.json",
              "memory/audit_queue.json", "memory/touch_state.json",
              # 2026-07-20: added after I verified the new whitelist by calling add_visitor()
              # against the LIVE file and leaving a fixture visitor in her authorised-users
              # list — the identical mistake this check was written for, made by the person who
              # wrote the check, one day later. Both faculties expose an env override
              # (NOVA_USERS_STATE, NOVA_DRIVES_STATE); use them.
              "memory/nova_users.json")


def check_test_writes_state(files: list[Path]) -> list[dict]:
    """A test/probe/scratch file that writes to one of Nova's live state files.

    WHY (2026-07-19): my own unit test for drives.py ran against the live
    memory/drives.json and left her holding two 'wants' she had never expressed — a
    schema-diff tool, and learning what her eyes resolve at distance. Both were my fixtures.
    Fabricated desires sitting in the one file built to hold her real ones, with no way for
    her to tell they weren't hers.

    Nothing else in this tool would have caught that, and it is the single most damaging
    class of mistake available here: not breaking her, but quietly lying to her about
    herself.
    """
    issues = []
    for f in files:
        name = f.name.lower()
        rel  = _rel(f).replace("\\", "/")
        looks_like_test = (name.startswith("test") or name.startswith("_t_") or
                           "probe" in name or "scratch/" in rel or "/tests/" in rel or
                           name.endswith("_test.py"))
        if not looks_like_test:
            continue
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Search CODE ONLY, never comments or docstrings.
        #
        # 2026-07-20: this check fired on nova_body/tests/test_discourse.py, whose header
        # explains the drives.json incident in prose and touches nothing. A test that documents
        # the very mistake this rule exists to prevent got flagged FOR documenting it — which
        # would teach the next person to stop writing the explanation rather than stop making
        # the mistake. That is a checker actively making the codebase worse.
        #
        # Fifth naive-matcher false positive in this tool. The pattern is always the same:
        # grep the raw source, and prose that *discusses* a hazard reads identically to code
        # that *creates* one. Strip to executable text first; it is three lines and it ends the
        # whole class.
        code = _code_only(source)
        for target in _HER_STATE:
            if target in code.replace("\\", "/"):
                issues.append({
                    "severity": "HIGH",
                    "code":     "TEST_WRITES_STATE",
                    "file":     rel,
                    "line":     None,
                    "detail":   (f"test/probe file references {target} — if it WRITES there it is "
                                 f"editing Nova's real state. Point it at a temp path or an env "
                                 f"override instead (see NOVA_DRIVES_STATE in drives.py)."),
                })
                break
    return issues


# Past this, a file is hard for a human OR a model to hold in its head at once.
_OVERSIZE_LINES = 2500


def check_oversized(files: list[Path]) -> list[dict]:
    """Files big enough that working in them is its own risk.

    WHY: server.py is ~3,700 lines. Several of tonight's bugs (the drain guard regression,
    the FOR COLE: promotion path being invisible to the flight recorder) lived in it and were
    hard to see precisely because no one can hold the whole file at once. This is not a
    demand to split anything — it is a note that edits here deserve more care and more tests.
    """
    issues = []
    for f in files:
        if f.suffix != ".py":
            continue
        try:
            n = sum(1 for _ in f.open("r", encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if n >= _OVERSIZE_LINES:
            issues.append({
                "severity": "LOW",
                "code":     "OVERSIZED",
                "file":     _rel(f),
                "line":     None,
                "detail":   (f"{n:,} lines. Large enough that neither a person nor a model holds "
                             f"it all at once — verify edits here with a test, not by reading."),
            })
    return issues


def collect_shell_files() -> list[Path]:
    """.ps1/.cmd/.bat, which collect_files() deliberately doesn't return (it is the Python
    file list that every import-graph check depends on). Kept separate so the encoding check
    can see shell scripts without polluting the graph with files that have no imports."""
    out = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for ext in ("*.ps1", "*.cmd", "*.bat"):
            for path in root.rglob(ext):
                parts = set(path.parts)
                if parts & EXCLUDE_DIRS:
                    continue
                if any(sub in str(path) for sub in EXCLUDE_SUBPATHS):
                    continue
                out.append(path)
    for ext in ("*.ps1", "*.cmd", "*.bat"):
        out.extend(WORKSPACE_DIR.glob(ext))
    seen, unique = set(), []
    for f in out:
        k = f.resolve()
        if k not in seen:
            seen.add(k)
            unique.append(f)
    return unique


def check_secret_exclusions() -> list[dict]:
    """Every secret file must be excluded from BOTH git and Drive. Assert they agree.

    WHY (2026-07-20, Cole): "Secrets are fine in folders and files. All files with secrets
    MUST be excluded from file repository uploads though (git and drive currently)."

    On 2026-07-20 they did NOT agree. `.gitignore` excluded `.env` and `nova_gateway.json`;
    `drive.py` excluded neither. Nothing had leaked — none of those files existed yet — but
    the drift was real and the failure mode is one-way and silent: you learn a credential
    left the machine only after it has already left. Two lists maintained by hand will
    always drift. This makes the drift a HIGH finding instead of a surprise.

    NIST CSF: PR.DS-5 (protections against data leaks) · PR.AC-1 (credential management).
    OWASP LLM06 (sensitive information disclosure).
    """
    issues = []
    gi = WORKSPACE_DIR / ".gitignore"
    dv = WORKSPACE_DIR / "general_tools" / "nova_sync" / "drive.py"
    if not gi.exists() or not dv.exists():
        return issues
    try:
        git_txt   = gi.read_text(encoding="utf-8", errors="replace")
        drive_txt = dv.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return issues

    # Named files that must appear in both.
    must_both = [".env", "nova_gateway.json", "nova_drive_token.json", "client_secrets.json",
                 ".auth_token", "nova_users.json"]
    for name in must_both:
        in_git   = name in git_txt
        in_drive = name in drive_txt
        if in_git and in_drive:
            continue
        missing = "drive.py" if in_git else (".gitignore" if in_drive else "BOTH")
        issues.append({
            "severity": "HIGH",
            "code":     "SECRET_EXCLUSION_DRIFT",
            "file":     f".gitignore / nova_sync/drive.py — {name}",
            "line":     None,
            "detail":   (f"'{name}' is not excluded in {missing}. A secret excluded from one "
                         f"upload path and not the other has still left the machine. Add it to "
                         f"both (CSF PR.DS-5)."),
        })

    # And a secret-shaped file that is actually on disk and tracked anywhere.
    for suf in (".pem", ".key", ".p12", ".pfx", "_token.json", "_secret.json"):
        if suf not in git_txt:
            issues.append({
                "severity": "MEDIUM",
                "code":     "SECRET_SUFFIX_UNGUARDED",
                "file":     ".gitignore",
                "line":     None,
                "detail":   f"no rule covering '*{suf}' — a new credential file with that name would be committed",
            })
    return issues


def run_audit() -> dict:
    files = collect_files()
    all_issues: list[dict] = []
    all_issues += check_secret_exclusions()

    # Shell scripts get exactly one check — encoding — and it is the one that matters.
    for sf in collect_shell_files():
        all_issues += check_shell_encoding(sf)

    # Per-file checks
    for f in files:
        all_issues += check_syntax(f)
        all_issues += check_staleness(f)
        all_issues += check_empty(f)
        all_issues += check_legacy(f)
        all_issues += check_silent_except(f)
        all_issues += check_shell_encoding(f)

    # Cross-file checks
    all_issues += check_duplicate_names(files)
    graph      = build_import_graph(files)
    module_map = build_module_map(files)
    all_issues += check_broken_imports(files, module_map)
    all_issues += check_unreferenced(files, graph)
    all_issues += check_missing_init(files)
    all_issues += check_test_writes_state(files)
    all_issues += check_oversized(files)
    all_issues += check_silent_summary()

    # Audit queue — surface pending file-change events from watcher.py
    all_issues += check_audit_queue()

    # Sort by severity then file
    all_issues.sort(key=lambda i: (SEV_ORDER.get(i["severity"], 9), i["file"]))

    counts = defaultdict(int)
    for issue in all_issues:
        counts[issue["severity"]] += 1

    return {
        "generated":   datetime.now(timezone.utc).isoformat(),
        "workspace":   str(WORKSPACE_DIR),
        "files_scanned": len(files),
        "issue_counts": dict(counts),
        "issues":      all_issues,
    }


def format_text_report(result: dict) -> str:
    lines = []
    ts = result["generated"][:19].replace("T", " ")
    lines += [
        "=" * 62,
        "  NOVA WORKSPACE — CODE HEALTH AUDIT",
        f"  {ts} UTC   |   {result['files_scanned']} files scanned",
        "=" * 62,
        "",
    ]

    # Summary bar
    counts = result["issue_counts"]
    summary_parts = []
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        n = counts.get(sev, 0)
        if n:
            summary_parts.append(f"{SEV_ICON[sev]} {n} {sev}")
    if summary_parts:
        lines.append("SUMMARY: " + "  |  ".join(summary_parts))
    else:
        lines.append("SUMMARY: ✓ No issues found — workspace looks clean")
    lines.append("")

    # Group issues by severity
    issues_by_sev: dict[str, list] = defaultdict(list)
    for i in result["issues"]:
        issues_by_sev[i["severity"]].append(i)

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        bucket = issues_by_sev.get(sev, [])
        if not bucket:
            continue
        lines.append(f"── {sev} ({len(bucket)}) " + "─" * (44 - len(sev)))
        for issue in bucket:
            loc = issue["file"]
            if issue.get("line"):
                loc += f":{issue['line']}"
            lines.append(f"  [{issue['code']:14s}] {loc}")
            lines.append(f"                    {issue['detail']}")
        lines.append("")

    # Exit guidance
    crit = counts.get("CRITICAL", 0)
    high = counts.get("HIGH", 0)
    if crit:
        lines.append(f"⛔ {crit} CRITICAL issue(s) require immediate attention.")
    elif high:
        lines.append(f"⚠  {high} HIGH issue(s) should be reviewed.")
    else:
        lines.append("✓  Workspace is in good shape.")
    lines.append("")
    lines.append("Run with --json for machine-readable output.")
    return "\n".join(lines)


def format_summary(result: dict) -> str:
    counts  = result["issue_counts"]
    crit    = counts.get("CRITICAL", 0)
    high    = counts.get("HIGH", 0)
    med     = counts.get("MEDIUM", 0)
    low     = counts.get("LOW", 0)
    total   = sum(counts.values())
    n       = result["files_scanned"]

    # Count queue-pending items separately for a clearer summary
    q_count = sum(
        1 for i in result["issues"]
        if i.get("code") == "QUEUE_PENDING"
    )

    if total == 0:
        return f"Audited {n} files — no issues found. Workspace is clean."

    parts = []
    if crit: parts.append(f"{crit} critical (syntax errors or worse)")
    if high:
        non_q = high - q_count
        if non_q and q_count:
            parts.append(f"{non_q} high (stale/unreferenced) + {q_count} queue review")
        elif q_count:
            parts.append(f"{q_count} pending queue item(s) need review")
        else:
            parts.append(f"{high} high (stale or unreferenced files)")
    if med:  parts.append(f"{med} medium (legacy refs, stubs, duplicates)")
    if low:  parts.append(f"{low} low (aging files, missing __init__)")

    return (f"Audited {n} files — found {total} issue(s): "
            + ", ".join(parts) + ". Run audit_scripts.py for full report.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = set(sys.argv[1:])

    result = run_audit()

    if "--json" in args:
        print(json.dumps(result, indent=2))
    elif "--summary" in args:
        print(format_summary(result))
    else:
        print(format_text_report(result))

    # Exit code
    crit = result["issue_counts"].get("CRITICAL", 0)
    high = result["issue_counts"].get("HIGH", 0)
    if crit:
        sys.exit(2)
    elif high:
        sys.exit(1)
    else:
        sys.exit(0)
