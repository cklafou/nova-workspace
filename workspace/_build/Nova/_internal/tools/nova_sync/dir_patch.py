#!/usr/bin/env python3
"""
nova_sync/dir_patch.py -- Nova Workspace Path Auditor
======================================================
Scans all Python AND Markdown files in the workspace for two categories
of broken paths:

1. IMPORT PATHS -- stale flat nova_* imports
     from nova_logger import log          (stale)
  -> try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log   (correct)

   In .md files, only imports inside code fences (``` blocks) or
   exec: python -c lines are checked -- never prose.

2. FILE REFERENCE PATHS -- Path() constructs pointing to non-existent files
     workspace / "tools" / "nova_eyes.py"                (stale, .py only)
  -> workspace / "tools" / "nova_perception" / "eyes.py" (correct)

Ground truth is loaded from FILE_INDEX.md (tools/nova_sync/FILE_INDEX.md).

Usage:
    python tools/nova_sync/dir_patch.py            # interactive y/n
    python tools/nova_sync/dir_patch.py --report   # findings only, no changes
    python tools/nova_sync/dir_patch.py --auto     # apply all without prompting
"""

import re
import sys
from pathlib import Path

TOOLS_DIR     = Path(__file__).parent.parent
WORKSPACE_DIR = TOOLS_DIR.parent
SYNC_DIR      = Path(__file__).parent
FILE_INDEX    = SYNC_DIR / "FILE_INDEX.md"

SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".clawhub",
    "backups", "logs", "screenshots",
}

SKIP_FILES = {
    "nova_restructure.py",
    "nova_patch.py",
    "dir_patch.py",
    "watcher.py",
}

# .md files to skip entirely (auto-generated, no imports to check)
SKIP_MD_FILES = {
    "FILE_INDEX.md",
    "FILE_INDEX_LINK.md",
    "JOURNAL.md",
    "HEARTBEAT.md",
    "GEMINI_INDEX.md",
}


# ── FILE_INDEX reader ──────────────────────────────────────────────────────────

def load_known_files() -> dict:
    known = {}

    if FILE_INDEX.exists():
        content = FILE_INDEX.read_text(encoding="utf-8")
        for line in content.splitlines():
            m = re.match(r"\s*-\s+\[([^\]]+)\]\(", line)
            if m:
                rel = m.group(1).replace("%20", " ")
                fname = Path(rel).name
                known.setdefault(fname, set()).add(rel)
                continue
            m = re.match(r"\s*-\s+([\w/.\-% ]+?)(?:\s+\(excluded\))?$", line)
            if m:
                rel = m.group(1).strip().replace("%20", " ")
                if "." in Path(rel).name:
                    fname = Path(rel).name
                    known.setdefault(fname, set()).add(rel)
    else:
        print(f"[dir_patch] Warning: FILE_INDEX.md not found at {FILE_INDEX}")
        print("[dir_patch] Falling back to live scan of tools/...")
        for path in sorted(TOOLS_DIR.rglob("*.py")):
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            try:
                rel = str(path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                known.setdefault(path.name, set()).add(rel)
            except ValueError:
                pass

    return known


# ── Module map ─────────────────────────────────────────────────────────────────

def build_module_map(known_files: dict) -> dict:
    module_map = {}
    for fname, rel_paths in known_files.items():
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        for rel in rel_paths:
            parts = Path(rel).with_suffix("").parts
            if len(parts) < 3:
                continue
            package = parts[1]
            module  = parts[2]
            dotted  = f"{package}.{module}"
            module_map[dotted] = dotted
            flat = f"nova_{module}"
            if not (TOOLS_DIR / f"{flat}.py").exists():
                if flat not in module_map:
                    module_map[flat] = dotted
    return module_map


# ── Path reference map ─────────────────────────────────────────────────────────

def build_path_map(known_files: dict) -> dict:
    path_map = {}
    for fname, rel_paths in known_files.items():
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        for rel in rel_paths:
            parts = Path(rel).parts
            if len(parts) < 3:
                continue
            module_name = Path(parts[2]).stem
            flat_name   = f"nova_{module_name}.py"
            flat_path   = f"tools/{flat_name}"
            correct_path = "/".join(parts)
            if not (WORKSPACE_DIR / flat_path).exists():
                path_map[flat_path] = correct_path
    return path_map


# ── Import scanner (shared by .py and .md) ─────────────────────────────────────

IMPORT_RE = re.compile(
    r"^(\s*)(from\s+(nova_[\w.]+)\s+import|import\s+(nova_[\w.]+))",
    re.MULTILINE
)


def find_stale_imports(content: str, module_map: dict) -> list:
    issues = []
    lines = content.split("\n")
    for i, line in enumerate(lines):
        m = IMPORT_RE.match(line)
        if not m:
            continue
        used_name = m.group(3) or m.group(4)
        if not used_name:
            continue
        correct = module_map.get(used_name)
        if correct is None or correct == used_name:
            continue
        if m.group(3):
            new_line = line.replace(f"from {used_name} import", f"from {correct} import", 1)
        else:
            new_line = line.replace(f"import {used_name}", f"import {correct}", 1)
        if new_line != line:
            issues.append((i + 1, line, new_line))
    return issues


# ── Markdown-aware import scanner ──────────────────────────────────────────────

# Matches exec: python -c "..." lines that may contain imports
EXEC_IMPORT_RE = re.compile(
    r"(from\s+(nova_[\w.]+)\s+import|import\s+(nova_[\w.]+))"
)


def find_stale_imports_md(content: str, module_map: dict) -> list:
    """
    Scan .md files for stale imports, but only inside:
      - ``` code fences (any language tag)
      - exec: python -c "..." inline commands
    Never flags imports mentioned in prose.
    """
    issues = []
    lines = content.split("\n")
    in_fence = False
    fence_marker = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track code fence open/close
        fence_match = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
                continue
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
                continue

        # Only check imports inside fences or exec lines
        is_exec_line = stripped.startswith("exec:") or stripped.startswith("python -c")
        if not in_fence and not is_exec_line:
            continue

        # Now apply import check to this line
        m = IMPORT_RE.match(line)
        if not m:
            # Also check inline exec strings (no leading whitespace match)
            for match in EXEC_IMPORT_RE.finditer(line):
                used_name = match.group(2) or match.group(3)
                if not used_name:
                    continue
                correct = module_map.get(used_name)
                if correct is None or correct == used_name:
                    continue
                new_line = line.replace(
                    f"from {used_name} import", f"from {correct} import", 1
                ) if match.group(2) else line.replace(
                    f"import {used_name}", f"import {correct}", 1
                )
                if new_line != line:
                    issues.append((i + 1, line, new_line))
                    break
            continue

        used_name = m.group(3) or m.group(4)
        if not used_name:
            continue
        correct = module_map.get(used_name)
        if correct is None or correct == used_name:
            continue
        if m.group(3):
            new_line = line.replace(f"from {used_name} import", f"from {correct} import", 1)
        else:
            new_line = line.replace(f"import {used_name}", f"import {correct}", 1)
        if new_line != line:
            issues.append((i + 1, line, new_line))

    return issues


# ── Path reference scanner (.py only) ─────────────────────────────────────────

PATH_REF_RE = re.compile(r'([\w_]+\s*/\s*")(nova_\w+\.py)(")')


def find_stale_path_refs(content: str, path_map: dict) -> list:
    issues = []
    lines = content.split("\n")
    for i, line in enumerate(lines):
        m = PATH_REF_RE.search(line)
        if not m:
            continue
        flat_file = m.group(2)
        match_key = next((k for k in path_map if k.endswith(f"/{flat_file}")), None)
        if not match_key:
            continue
        correct_rel  = path_map[match_key]
        correct_parts = correct_rel.split("/")
        if len(correct_parts) < 3:
            continue
        package     = correct_parts[-2]
        module_file = correct_parts[-1]
        new_line = line.replace(f'"{flat_file}"', f'"{package}" / "{module_file}"', 1)
        if new_line != line:
            issues.append((i + 1, line, new_line))
    return issues


# ── Diff display ───────────────────────────────────────────────────────────────

def show_diff(filepath: Path, import_issues: list, path_issues: list):
    print(f"\n{'=' * 60}")
    print(f"FILE: {filepath}")
    total = len(import_issues) + len(path_issues)
    print(f"  {total} issue(s) found:")
    if import_issues:
        print(f"  -- {len(import_issues)} stale import(s):")
        for lineno, old, new in import_issues:
            print(f"     Line {lineno}:")
            print(f"       - {old.strip()}")
            print(f"       + {new.strip()}")
    if path_issues:
        print(f"  -- {len(path_issues)} stale Path() reference(s):")
        for lineno, old, new in path_issues:
            print(f"     Line {lineno}:")
            print(f"       - {old.strip()}")
            print(f"       + {new.strip()}")


# ── Apply fixes ────────────────────────────────────────────────────────────────

def apply_fixes(filepath: Path, import_issues: list, path_issues: list):
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    for lineno, old, new in (import_issues + path_issues):
        idx = lineno - 1
        if idx < len(lines) and lines[idx] == old:
            lines[idx] = new
    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [dir_patch] Fixed {len(import_issues) + len(path_issues)} issue(s) in {filepath.name}")


# ── Main audit ─────────────────────────────────────────────────────────────────

def run_audit(interactive=True, auto=False, report_only=False):
    print("[dir_patch] Loading file index...")
    known_files = load_known_files()
    print(f"[dir_patch] {sum(len(v) for v in known_files.values())} files indexed.")

    module_map = build_module_map(known_files)
    path_map   = build_path_map(known_files)

    stale_imports = {k: v for k, v in module_map.items() if k != v}
    if stale_imports:
        print(f"[dir_patch] Stale import mappings ({len(stale_imports)}):")
        for old, new in sorted(stale_imports.items()):
            print(f"    {old:35s} -> {new}")

    if path_map:
        print(f"[dir_patch] Stale path mappings ({len(path_map)}):")
        for old, new in sorted(path_map.items()):
            print(f"    {old:45s} -> {new}")
    print()

    # Collect .py files
    py_files = []
    for path in sorted(WORKSPACE_DIR.rglob("*.py")):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.name in SKIP_FILES:
            continue
        py_files.append(path)

    # Collect .md files
    md_files = []
    for path in sorted(WORKSPACE_DIR.rglob("*.md")):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.name in SKIP_MD_FILES:
            continue
        md_files.append(path)

    print(f"[dir_patch] Scanning {len(py_files)} .py files and {len(md_files)} .md files...\n")

    files_with_issues = []

    for path in py_files:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[dir_patch] Could not read {path}: {e}")
            continue
        imp_issues  = find_stale_imports(content, module_map)
        path_issues = find_stale_path_refs(content, path_map)
        if imp_issues or path_issues:
            files_with_issues.append((path, imp_issues, path_issues))

    for path in md_files:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[dir_patch] Could not read {path}: {e}")
            continue
        imp_issues = find_stale_imports_md(content, module_map)
        if imp_issues:
            files_with_issues.append((path, imp_issues, []))

    if not files_with_issues:
        print("[dir_patch] All imports and path references look correct.")
        return 0

    total = sum(len(i) + len(p) for _, i, p in files_with_issues)
    print(f"[dir_patch] Found {total} issue(s) across {len(files_with_issues)} file(s).")

    if report_only:
        for path, imp_issues, path_issues in files_with_issues:
            show_diff(path, imp_issues, path_issues)
        print(f"\n[dir_patch] Report complete. Run without --report to fix.")
        return len(files_with_issues)

    fixed = 0
    skipped = 0

    for path, imp_issues, path_issues in files_with_issues:
        show_diff(path, imp_issues, path_issues)

        if auto:
            apply_fixes(path, imp_issues, path_issues)
            fixed += 1
        else:
            while True:
                try:
                    answer = input("\n  Apply fix? [y/n/q to quit]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\n[dir_patch] Interrupted.")
                    print(f"\n[dir_patch] Done: {fixed} fixed, {skipped} skipped.")
                    return fixed
                if answer == "y":
                    apply_fixes(path, imp_issues, path_issues)
                    fixed += 1
                    break
                elif answer == "n":
                    print(f"  Skipped: {path.name}")
                    skipped += 1
                    break
                elif answer == "q":
                    print("[dir_patch] Quit.")
                    print(f"\n[dir_patch] Done: {fixed} fixed, {skipped} skipped.")
                    return fixed
                else:
                    print("  Please enter y, n, or q.")

    print(f"\n[dir_patch] Done: {fixed} fixed, {skipped} skipped.")
    return fixed


if __name__ == "__main__":
    report_only = "--report" in sys.argv
    auto        = "--auto"   in sys.argv

    if report_only:
        run_audit(interactive=False, auto=False, report_only=True)
    elif auto:
        run_audit(interactive=False, auto=True,  report_only=False)
    else:
        run_audit(interactive=True,  auto=False, report_only=False)

