#!/usr/bin/env python3
# Last updated: 2026-07-09 00:06:18
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
    WORKSPACE_DIR / "nova_lancedb",   # workspace-root semantic-memory package
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


SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
SEV_ICON  = {"CRITICAL": "✗ ", "HIGH": "⚠ ", "MEDIUM": "△ ", "LOW": "·", "INFO": "·"}


# ── Main ──────────────────────────────────────────────────────────────────────

def run_audit() -> dict:
    files = collect_files()
    all_issues: list[dict] = []

    # Per-file checks
    for f in files:
        all_issues += check_syntax(f)
        all_issues += check_staleness(f)
        all_issues += check_empty(f)
        all_issues += check_legacy(f)

    # Cross-file checks
    all_issues += check_duplicate_names(files)
    graph      = build_import_graph(files)
    module_map = build_module_map(files)
    all_issues += check_broken_imports(files, module_map)
    all_issues += check_unreferenced(files, graph)
    all_issues += check_missing_init(files)

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
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
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

    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
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
