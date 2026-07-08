# @nova: Call-graph generator — AST-walks packages to map imports/calls; feeds the Body Manifest.
# Last updated: 2026-07-09 04:13:04
"""
general_tools/calls.py -- Nova Package Call Graph Generator
============================================================
Walks every nova_* package under nova_body/ and general_tools/ and generates:
  - <root>/<package>/calls.md  (what each file in that package imports/calls)
  - general_tools/Calls_Master_Index.md  (cross-package call relationships)

Run this after any structural change to keep the call graph current.

Usage (from workspace root):
    python general_tools/calls.py          # generate all calls.md files
    python general_tools/calls.py --dry    # print without writing
"""

import ast
import sys
import time
from pathlib import Path
from collections import defaultdict

_THIS_FILE      = Path(__file__).resolve()
GENERAL_TOOLS   = _THIS_FILE.parent                    # workspace/general_tools/
WORKSPACE_ROOT  = GENERAL_TOOLS.parent                 # workspace/
NOVA_TOOLS      = WORKSPACE_ROOT / "nova_body"
MASTER_INDEX    = GENERAL_TOOLS / "Calls_Master_Index.md"

DRY_RUN = "--dry" in sys.argv


def _scan_root(root_dir: Path) -> list[Path]:
    """Return all nova_* package directories under a root."""
    if not root_dir.exists():
        return []
    return sorted(
        [d for d in root_dir.iterdir()
         if d.is_dir() and d.name.startswith("nova_")
         and not d.name.startswith(".")
         and d.name != "__pycache__"],
        key=lambda p: p.name,
    )


PACKAGES = _scan_root(NOVA_TOOLS) + _scan_root(GENERAL_TOOLS)


def get_imports(filepath: Path) -> list[dict]:
    """Parse a Python file and return all import statements."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree   = ast.parse(source, filename=str(filepath))
    except Exception:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"type": "import", "module": alias.name,
                                 "alias": alias.asname, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names  = [a.name for a in node.names]
            imports.append({"type": "from", "module": module,
                             "names": names, "line": node.lineno})
    return imports


def _local_module_names() -> set[str]:
    """Top-level importable names that physically live in nova_body/ or
    general_tools/ — packages (dirs with __init__.py) and bare modules (*.py).

    These are first-party even when imported by bare name (e.g.
    `from nova_config import cfg` or `import gateway_config`), which the old
    `startswith("nova_")` test missed — that mislabeled them third_party and
    wrongly flagged them as having no inbound refs."""
    names: set[str] = set()
    for root in (NOVA_TOOLS, GENERAL_TOOLS):
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.name.startswith((".", "_")):
                continue
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
            elif item.suffix == ".py":
                names.add(item.stem)
    return names


_LOCAL_MODULES = _local_module_names()


def classify_import(module: str) -> str:
    """Classify an import as nova (first-party), stdlib, or third_party."""
    root = module.split(".")[0]
    if root.startswith("nova_") or root in _LOCAL_MODULES:
        return "nova"
    stdlib = {"os", "sys", "re", "json", "time", "pathlib", "threading",
              "datetime", "subprocess", "shutil", "asyncio", "typing",
              "collections", "functools", "itertools", "math", "hashlib",
              "gzip", "zipfile", "io", "uuid", "traceback", "inspect",
              "contextlib", "dataclasses", "enum", "abc", "copy"}
    if root in stdlib:
        return "stdlib"
    return "third_party"


def scan_package(package_dir: Path) -> dict:
    """Scan all .py files in a package and return their call graph."""
    results = {}
    for py_file in sorted(package_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        imports = get_imports(py_file)
        nova_calls    = []
        third_party   = []
        for imp in imports:
            kind = classify_import(imp["module"])
            if kind == "nova":
                if imp["type"] == "from":
                    entry = f"from {imp['module']} import {', '.join(imp['names'])}"
                else:
                    entry = f"import {imp['module']}"
                nova_calls.append(entry)
            elif kind == "third_party":
                third_party.append(imp["module"].split(".")[0])
        results[py_file.name] = {
            "nova_calls":  sorted(set(nova_calls)),
            "third_party": sorted(set(third_party)),
            "raw":         imports,
        }
    return results


def write_calls_md(package_dir: Path, scan: dict, dry: bool = False):
    """Write calls.md for a package directory."""
    ts    = time.strftime("%Y-%m-%d %H:%M:%S")
    # Determine which root this package lives under for the header
    try:
        rel_root = package_dir.relative_to(WORKSPACE_ROOT).parts[0]
    except ValueError:
        rel_root = "tools"

    lines = [
        f"# calls.md -- {package_dir.name}",
        f"_Auto-generated by general_tools/calls.py_",
        f"_Last updated: {ts}_",
        f"_Location: {rel_root}/{package_dir.name}_",
        "",
        "Lists every file in this package and what Nova packages/tools it calls.",
        "",
    ]

    if not scan:
        lines.append("_No Python files found._")
    else:
        for filename, data in sorted(scan.items()):
            lines.append(f"## {filename}")
            if data["nova_calls"]:
                lines.append("")
                lines.append("**Nova package calls:**")
                for call in data["nova_calls"]:
                    lines.append(f"- `{call}`")
            if data["third_party"]:
                lines.append("")
                lines.append("**Third-party dependencies:**")
                for dep in data["third_party"]:
                    lines.append(f"- `{dep}`")
            if not data["nova_calls"] and not data["third_party"]:
                lines.append("")
                lines.append("_No external calls._")
            lines.append("")

    content = "\n".join(lines)
    dest    = package_dir / "calls.md"

    if dry:
        print(f"\n{'='*60}")
        print(f"Would write: {dest}")
        print(content[:500])
    else:
        dest.write_text(content, encoding="utf-8")
        print(f"[calls] Written: {dest.relative_to(WORKSPACE_ROOT)}")


def write_master_index(all_scans: dict[str, dict], dry: bool = False):
    """Write Calls_Master_Index.md summarising cross-package relationships."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # Build reverse map: who calls each nova package
    callers: dict[str, list[str]] = defaultdict(list)
    for pkg_key, scan in all_scans.items():
        for filename, data in scan.items():
            for call in data["nova_calls"]:
                target_pkg = call.split()[1].split(".")[0]  # "from nova_memory..." -> "nova_memory"
                callers[target_pkg].append(f"{pkg_key}/{filename}")

    lines = [
        "# Calls_Master_Index.md -- Cross-Package Call Graph",
        "_Auto-generated by general_tools/calls.py_",
        f"_Last updated: {ts}_",
        "",
        "## Package Locations",
        "",
        "| Package | Root | Description |",
        "|---|---|---|",
    ]
    for pkg_dir in PACKAGES:
        try:
            root = pkg_dir.relative_to(WORKSPACE_ROOT).parts[0]
        except ValueError:
            root = "?"
        lines.append(f"| `{pkg_dir.name}` | `{root}/` | — |")

    lines += [
        "",
        "## Who calls what",
        "",
        "| Nova Package | Called By |",
        "|---|---|",
    ]
    for pkg in sorted(callers):
        callers_str = ", ".join(sorted(set(callers[pkg])))
        lines.append(f"| `{pkg}` | {callers_str} |")

    lines += [
        "",
        "## Per-package summaries",
        "",
    ]
    for pkg_key, scan in sorted(all_scans.items()):
        if not scan:
            continue
        lines.append(f"### {pkg_key}")
        for filename, data in sorted(scan.items()):
            if data["nova_calls"]:
                calls_str = ", ".join(f"`{c}`" for c in data["nova_calls"])
                lines.append(f"- **{filename}** → {calls_str}")
        lines.append("")

    content = "\n".join(lines)

    if dry:
        print(f"\n{'='*60}")
        print(f"Would write: {MASTER_INDEX}")
        print(content[:800])
    else:
        MASTER_INDEX.write_text(content, encoding="utf-8")
        print(f"[calls] Master index: {MASTER_INDEX.relative_to(WORKSPACE_ROOT)}")


if __name__ == "__main__":
    print(f"[calls] Scanning {len(PACKAGES)} packages across nova_body/ and general_tools/")
    all_scans = {}
    for pkg in PACKAGES:
        try:
            root_prefix = pkg.relative_to(WORKSPACE_ROOT).parts[0]
        except ValueError:
            root_prefix = "unknown"
        pkg_key = f"{root_prefix}/{pkg.name}"
        scan = scan_package(pkg)
        all_scans[pkg_key] = scan
        write_calls_md(pkg, scan, dry=DRY_RUN)

    write_master_index(all_scans, dry=DRY_RUN)
    print(f"[calls] Done.")
