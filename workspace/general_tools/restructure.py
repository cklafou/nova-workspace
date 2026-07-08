# Last updated: 2026-07-09 00:06:18
# @nova: Restructure checker — detects stale path references after a directory move and offers interactive fixes.
"""
general_tools/restructure.py  --  Nova Restructure Checker
===========================================================
Detects stale path references after a directory restructure and offers
interactive confirmation before applying fixes.

How it works
------------
1. Scans nova_body/ and general_tools/ to build the ACTUAL package-location map
2. Searches every .py, .md, .cmd, .bat, .json, .txt, .spec file in the
   workspace for references that no longer match actual locations
3. Presents a numbered list of detected mismatches with proposed replacements
4. You confirm each fix (y/n) or accept/skip all at once
5. Applies confirmed replacements in-place
6. Optionally re-runs general_tools/calls.py to refresh the call graph

Usage (from workspace root)
----------------------------
    python general_tools/restructure.py          # interactive mode
    python general_tools/restructure.py --dry    # show findings, no writes
    python general_tools/restructure.py --all    # confirm all fixes automatically
    python general_tools/restructure.py --scan   # scan only, no fix prompts

    # After renaming a file within a package, fix all references:
    python general_tools/restructure.py --rename nova_core.brain=nova_core.prefrontal_cortex --all
    python general_tools/restructure.py --rename nova_perception.explorer=nova_senses.proprioception --dry

AI usage
--------
    exec: python general_tools/restructure.py --all
    # Run after any restructure to auto-apply all detected fixes.

    exec: python general_tools/restructure.py --rename nova_core.brain=nova_core.prefrontal_cortex --all
    # Run after renaming a file to fix all stale import/path references.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from collections import defaultdict
from typing import NamedTuple

# ---- Paths ------------------------------------------------------------------
_THIS         = Path(__file__).resolve()
GENERAL_TOOLS = _THIS.parent                     # workspace/general_tools/
WORKSPACE     = GENERAL_TOOLS.parent             # workspace/
NOVA_TOOLS    = WORKSPACE / "nova_body"

DRY  = "--dry"  in sys.argv
ALL  = "--all"  in sys.argv
SCAN = "--scan" in sys.argv

# ---- Rename flag (--rename old_module=new_module) ----------------------------
# Example: --rename nova_core.brain=nova_core.prefrontal_cortex
_RENAME_RAW: str | None = None
for _i, _a in enumerate(sys.argv):
    if _a == "--rename" and _i + 1 < len(sys.argv) and not sys.argv[_i + 1].startswith("--"):
        _RENAME_RAW = sys.argv[_i + 1]
        break
    if _a.startswith("--rename="):
        _RENAME_RAW = _a[len("--rename="):]
        break

RENAME_OLD: str | None = None
RENAME_NEW: str | None = None
if _RENAME_RAW and "=" in _RENAME_RAW:
    RENAME_OLD, RENAME_NEW = _RENAME_RAW.split("=", 1)

# ---- File extensions to scan ------------------------------------------------
SCAN_EXTS = {".py", ".md", ".cmd", ".bat", ".json", ".txt", ".spec"}

# Directories to skip entirely (matched against any path component)
SKIP_DIRS = {
    "__pycache__", ".git", "_build", "node_modules", ".venv", "venv",
    "prompt_cache", "logs", "models", "llama", "dist", "Thoughts",
    "passover",  # historical session archives -- never modify
    "_admin",    # session logs / live updates -- do not rewrite history
}

# ---- Step 1: Discover actual package locations ------------------------------

def discover_packages() -> dict[str, Path]:
    """
    Returns {package_name: parent_dir} for every nova_* directory found
    under nova_body/ and general_tools/.
    Example: {"nova_memory": Path(".../nova_body"),
              "nova_chat":   Path(".../general_tools")}
    """
    pkg_map: dict[str, Path] = {}
    for root in (NOVA_TOOLS, GENERAL_TOOLS):
        if not root.exists():
            continue
        for d in root.iterdir():
            if (d.is_dir()
                    and d.name.startswith("nova_")
                    and not d.name.startswith(".")
                    and d.name != "__pycache__"):
                pkg_map[d.name] = root
    return pkg_map


# ---- Step 2: Build patterns to search for ----------------------------------

class Pattern(NamedTuple):
    description: str
    regex:       re.Pattern
    make_replacement: object  # callable(match, pkg_map) -> str | None


def _root_name(root: Path) -> str:
    return root.relative_to(WORKSPACE).parts[0]


def _build_patterns(pkg_map: dict[str, Path]) -> list[Pattern]:
    patterns: list[Pattern] = []

    # A) "tools/nova_*" path strings
    for pkg, correct_root in pkg_map.items():
        correct = f"{_root_name(correct_root)}/{pkg}"
        stale   = f"tools/{pkg}"
        # Use negative lookbehind so we don't match 'tools/' inside
        # 'general_tools/' or 'nova_body/' after a prior fix run.
        rx = re.compile(r'(?<![a-zA-Z0-9_])' + re.escape(stale))
        def _make_repl(fix=correct):
            def _repl(m, _pkg_map):
                return fix
            return _repl
        patterns.append(Pattern(
            description=f'"{stale}" -> "{correct}"',
            regex=rx,
            make_replacement=_make_repl(),
        ))

    # B) sys.path.insert(0, 'tools') / sys.path.insert(0, "tools")
    _sys_path_rx = re.compile(
        r"""sys\.path\.insert\s*\(\s*0\s*,\s*['"]tools['"]\s*\)"""
    )
    def _sys_path_repl(m, _pkg_map):
        return (
            "sys.path.insert(0, 'nova_body')\n"
            "sys.path.insert(0, 'general_tools')"
        )
    patterns.append(Pattern(
        description="sys.path.insert(0, 'tools') -> dual insert for nova_tools + general_tools",
        regex=_sys_path_rx,
        make_replacement=_sys_path_repl,
    ))

    # C) workspace/tools/ in URLs or long paths
    _ws_tools_rx = re.compile(r'workspace/tools/(nova_[^/\s\'">(\)]+)')
    def _ws_tools_repl(m, p_map):
        pkg_partial = m.group(1).split("/")[0]
        for pkg, root in p_map.items():
            if pkg_partial == pkg or pkg_partial.startswith(pkg):
                new_root = _root_name(root)
                return m.group(0).replace("workspace/tools/", f"workspace/{new_root}/")
        return None
    patterns.append(Pattern(
        description='workspace/tools/<pkg> -> workspace/<correct_root>/<pkg>',
        regex=_ws_tools_rx,
        make_replacement=_ws_tools_repl,
    ))

    # D/E/F) Module rename patterns (--rename old=new)
    if RENAME_OLD and RENAME_NEW:
        patterns.extend(_build_rename_patterns(RENAME_OLD, RENAME_NEW))

    return patterns


def _build_rename_patterns(old_mod: str, new_mod: str) -> list[Pattern]:
    """
    Build patterns to detect and fix a file-level rename within or across packages.

    old_mod / new_mod: dotted module paths, e.g. "nova_core.brain"
                       Handles single-level modules too: "brain"

    Generates three pattern types:

      D  Dotted reference:    nova_core.brain  →  nova_core.prefrontal_cortex
         Catches: from nova_core.brain import *, import nova_core.brain,
                  "nova_core.brain" in strings/docs

      E  Path-style reference: nova_core/brain  →  nova_core/prefrontal_cortex
         Catches: nova_core/brain.py, nova_core/brain (path strings),
                  exec: python .../nova_core/brain.py

      F  Bare import (same-package rename only):
         from nova_core import brain  →  from nova_core import prefrontal_cortex
    """
    old_path = old_mod.replace(".", "/")
    new_path = new_mod.replace(".", "/")

    old_pkg  = old_mod.rsplit(".", 1)[0] if "." in old_mod else ""
    old_name = old_mod.rsplit(".", 1)[1] if "." in old_mod else old_mod
    new_pkg  = new_mod.rsplit(".", 1)[0] if "." in new_mod else ""
    new_name = new_mod.rsplit(".", 1)[1] if "." in new_mod else new_mod

    rename_patterns: list[Pattern] = []

    # D — dotted form: nova_core.brain  →  nova_core.prefrontal_cortex
    # Word-boundary anchors prevent matching nova_core.brain_v2 etc.
    _rx_dot = re.compile(r'(?<![.\w])' + re.escape(old_mod) + r'(?![.\w])')
    def _make_dot(new=new_mod):
        def _r(m, _pm):
            return new
        return _r
    rename_patterns.append(Pattern(
        description=f'"{old_mod}" -> "{new_mod}" (dotted module reference)',
        regex=_rx_dot,
        make_replacement=_make_dot(),
    ))

    # E — path form: nova_core/brain  →  nova_core/prefrontal_cortex
    # Catches with or without .py suffix (the anchor is the directory separator)
    _rx_path = re.compile(r'(?<![/\w])' + re.escape(old_path) + r'(?![/\w])')
    def _make_path(new=new_path):
        def _r(m, _pm):
            return new
        return _r
    rename_patterns.append(Pattern(
        description=f'"{old_path}" -> "{new_path}" (path-style reference)',
        regex=_rx_path,
        make_replacement=_make_path(),
    ))

    # F — bare import form (only when renaming within the same package)
    #   from nova_core import brain  →  from nova_core import prefrontal_cortex
    #   Also catches comma-separated: "import brain, rules" — matches just "brain"
    if old_pkg and old_pkg == new_pkg:
        _rx_bare = re.compile(
            r'(from\s+' + re.escape(old_pkg) + r'\s+import\s+(?:[\w]+,\s*)*)'
            + r'(?<!\w)' + re.escape(old_name) + r'(?!\w)'
        )
        def _make_bare(grp1_plus_old=old_name, new=new_name):
            def _r(m, _pm):
                # group(1) is "from pkg import " (and any preceding names)
                # group(0) is the full match including old_name at the end
                return m.group(0)[: m.end() - m.start() - len(grp1_plus_old)] + new
            return _r

        # Simpler approach: replace old_name only at the end of the match
        def _make_bare_repl(old=old_name, new=new_name):
            def _r(m, _pm):
                full = m.group(0)
                # Replace the last occurrence of old_name in the match
                idx = full.rfind(old)
                if idx == -1:
                    return full
                return full[:idx] + new + full[idx + len(old):]
            return _r

        rename_patterns.append(Pattern(
            description=(f'"from {old_pkg} import ... {old_name}" -> '
                         f'"from {new_pkg} import ... {new_name}"'),
            regex=_rx_bare,
            make_replacement=_make_bare_repl(),
        ))

    return rename_patterns


# ---- Step 3: Scan files -----------------------------------------------------

class Finding(NamedTuple):
    file:          Path
    line_no:       int
    line_text:     str
    old_text:      str
    new_text:      str
    pattern_desc:  str


def scan_workspace(patterns: list[Pattern], pkg_map: dict[str, Path]) -> list[Finding]:
    """Walk workspace using os.walk so we can prune skip-dirs without traversing them."""
    findings: list[Finding] = []

    for root_str, dirs, files in os.walk(str(WORKSPACE)):
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        root_path = Path(root_str)
        for filename in files:
            if Path(filename).suffix.lower() not in SCAN_EXTS:
                continue
            filepath = root_path / filename
            if filepath.resolve() == _THIS.resolve():
                continue

            try:
                text = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = text.splitlines()
            for lineno, line in enumerate(lines, start=1):
                for pat in patterns:
                    for m in pat.regex.finditer(line):
                        new_text = pat.make_replacement(m, pkg_map)
                        if new_text is None or new_text == m.group(0):
                            continue
                        findings.append(Finding(
                            file         = filepath,
                            line_no      = lineno,
                            line_text    = line.rstrip(),
                            old_text     = m.group(0),
                            new_text     = new_text,
                            pattern_desc = pat.description,
                        ))

    seen   = set()
    unique = []
    for f in findings:
        key = (f.file, f.line_no, f.old_text, f.new_text)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return sorted(unique, key=lambda f: (str(f.file), f.line_no))


# ---- Step 4: Present findings -----------------------------------------------

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def present_findings(findings: list[Finding]) -> None:
    if not findings:
        print("\n  No stale references detected. Everything looks up-to-date.")
        return

    by_file: dict[Path, list[Finding]] = defaultdict(list)
    for f in findings:
        by_file[f.file].append(f)

    print(f"\n{'-'*70}")
    print(f"  RESTRUCTURE CHECKER -- {len(findings)} stale reference(s) found")
    print(f"{'-'*70}\n")

    idx = 1
    for filepath, file_findings in by_file.items():
        print(f"  {_rel(filepath)}")
        for f in file_findings:
            print(f"  [{idx:>3}]  line {f.line_no}")
            print(f"         Pattern : {f.pattern_desc}")
            print(f"         OLD     : {f.old_text}")
            print(f"         NEW     : {f.new_text}")
            ctx = f.line_text.strip()
            if len(ctx) > 100:
                ctx = ctx[:97] + "..."
            print(f"         Context : {ctx}")
            print()
            idx += 1
        print()


# ---- Step 5: Apply fixes ----------------------------------------------------

def _confirm(prompt: str) -> str:
    return input(prompt).strip().lower()


def apply_fixes(findings: list[Finding], dry: bool = False, auto_all: bool = False) -> int:
    if not findings:
        return 0

    by_file: dict[Path, list[Finding]] = defaultdict(list)
    approved: dict[tuple, bool] = {}

    if SCAN:
        print("  (scan-only mode -- no fixes applied)")
        return 0

    if not auto_all:
        print("-" * 70)
        print("  Confirm fixes  (y=yes  n=no  a=approve all remaining  s=skip all)")
        print("-" * 70)

    idx = 1
    skip_rest    = False
    approve_rest = False

    for f in findings:
        key = (f.file, f.line_no, f.old_text, f.new_text)
        if auto_all or approve_rest:
            approved[key] = True
        elif skip_rest or dry:
            approved[key] = False
        else:
            answer = _confirm(
                f"  [{idx:>3}]  {_rel(f.file)}:{f.line_no}  "
                f"'{f.old_text}' -> '{f.new_text}'  [y/n/a/s]? "
            )
            if answer in ("a", "all"):
                approved[key] = True
                approve_rest  = True
            elif answer in ("s", "skip"):
                approved[key] = False
                skip_rest     = True
            else:
                approved[key] = answer in ("y", "yes", "")
        idx += 1

    for f in findings:
        key = (f.file, f.line_no, f.old_text, f.new_text)
        if approved.get(key):
            by_file[f.file].append(f)

    if dry:
        n_approved = sum(1 for v in approved.values() if v)
        print(f"\n  [dry-run] Would apply {n_approved}/{len(findings)} fix(es).")
        return 0

    modified = 0
    for filepath, file_findings in by_file.items():
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  [!] Could not read {_rel(filepath)}: {e}")
            continue

        new_content = content
        for f in file_findings:
            new_content = new_content.replace(f.old_text, f.new_text)

        if new_content != content:
            filepath.write_text(new_content, encoding="utf-8")
            print(f"  OK  Updated: {_rel(filepath)}  ({len(file_findings)} fix(es))")
            modified += 1

    return modified


# ---- Step 6: Resolve matching audit queue items after a --rename ------------

def _mod_to_workspace_rel(dotted_mod: str, pkg_map: dict[str, Path]) -> str | None:
    """
    Convert a dotted module path like "nova_core.brain" to a workspace-relative
    file path like "nova_body/nova_core/brain.py", using pkg_map to find the
    correct root directory.

    Returns None if the top-level package isn't known.
    """
    parts = dotted_mod.split(".", 1)
    pkg   = parts[0]
    rest  = parts[1].replace(".", "/") if len(parts) > 1 else ""

    if pkg not in pkg_map:
        return None

    root     = pkg_map[pkg]                      # e.g. Path(".../nova_body")
    root_rel = _root_name(root)                  # e.g. "nova_body"
    rel_path = f"{root_rel}/{pkg}/{rest}.py" if rest else f"{root_rel}/{pkg}.py"
    return rel_path


def _resolve_queue_after_rename(pkg_map: dict[str, Path], resolved_by: str) -> None:
    """
    After a successful --rename run, mark any pending audit_queue items whose
    old_path / new_path match the rename as resolved.

    Imports audit_queue lazily so restructure.py stays usable even if the
    queue module is missing (early bootstrap).
    """
    if not (RENAME_OLD and RENAME_NEW):
        return

    old_rel = _mod_to_workspace_rel(RENAME_OLD, pkg_map)
    new_rel = _mod_to_workspace_rel(RENAME_NEW, pkg_map)

    if old_rel is None and new_rel is None:
        print("[restructure] audit_queue: could not derive file paths from rename spec — skipping queue resolution.")
        return

    # Add general_tools/ to sys.path so audit_queue is importable
    gen_tools_str = str(GENERAL_TOOLS)
    if gen_tools_str not in sys.path:
        sys.path.insert(0, gen_tools_str)

    try:
        import audit_queue as aq
    except ImportError as e:
        print(f"[restructure] audit_queue not available — skipping queue resolution ({e}).")
        return

    count = aq.resolve_by_paths(
        old_path=old_rel,
        new_path=new_rel,
        resolved_by=resolved_by,
    )

    if count:
        print(f"[restructure] audit_queue: resolved {count} pending item(s) "
              f"({old_rel} → {new_rel}).")
    else:
        print(f"[restructure] audit_queue: no pending items matched "
              f"({old_rel} → {new_rel}).")


# ---- Step 7: Optionally refresh call graph ----------------------------------

def refresh_calls(modified: int) -> None:
    if modified == 0 or DRY or SCAN:
        return
    calls_py = GENERAL_TOOLS / "calls.py"
    if not calls_py.exists():
        return

    answer = "y" if ALL else _confirm(
        "\n  Refresh call graph? (runs general_tools/calls.py)  [y/n]? "
    )
    if answer in ("y", "yes", ""):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(calls_py)],
            cwd=str(WORKSPACE),
            capture_output=False,
        )
        if result.returncode == 0:
            print("  OK  Call graph refreshed.")
        else:
            print("  [!] calls.py exited with errors -- check output above.")


# ---- Main -------------------------------------------------------------------

def main():
    print(f"\n[restructure] Discovering packages in nova_body/ and general_tools/...")
    pkg_map = discover_packages()

    if not pkg_map:
        print("[restructure] No nova_* packages found -- nothing to check.")
        sys.exit(0)

    print(f"[restructure] Found {len(pkg_map)} packages:")
    for name, root in sorted(pkg_map.items()):
        print(f"    {_root_name(root)}/{name}")

    if RENAME_OLD and RENAME_NEW:
        print(f"\n[restructure] Rename mode: {RENAME_OLD} -> {RENAME_NEW}")

    patterns = _build_patterns(pkg_map)
    print(f"\n[restructure] Scanning workspace for {len(patterns)} stale-reference pattern(s)...")
    findings = scan_workspace(patterns, pkg_map)

    present_findings(findings)

    if DRY:
        print(f"[restructure] Dry run -- {len(findings)} finding(s). No files written.")
        return

    if SCAN:
        print(f"[restructure] Scan complete -- {len(findings)} finding(s).")
        return

    modified = apply_fixes(findings, dry=DRY, auto_all=ALL)

    if modified:
        print(f"\n[restructure] Done -- {modified} file(s) updated.")
        # After a rename run, resolve matching audit queue items automatically.
        if RENAME_OLD and RENAME_NEW and not DRY:
            _resolve_queue_after_rename(
                pkg_map,
                resolved_by=(
                    f"restructure.py --rename {RENAME_OLD}={RENAME_NEW}"
                    + (" --all" if ALL else "")
                ),
            )
        refresh_calls(modified)
    else:
        print(f"\n[restructure] No changes written.")
        # Even with no text changes, try to resolve the queue (e.g. the rename
        # already had no stale references but the queue still has a pending item).
        if RENAME_OLD and RENAME_NEW and not DRY:
            _resolve_queue_after_rename(
                pkg_map,
                resolved_by=(
                    f"restructure.py --rename {RENAME_OLD}={RENAME_NEW} (no refs found)"
                ),
            )


if __name__ == "__main__":
    main()
