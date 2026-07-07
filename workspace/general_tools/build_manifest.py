# Last updated: 2026-07-08 08:38:23
# @nova: Generates Nova's Body Manifest — the single derived map of every body part
#        and tool (SELF/core/03_body_manifest.md + SELF/reference/manifest.json).
"""
build_manifest.py — Nova Body Manifest generator
=================================================
Derives a single source of truth for Nova's architecture and writes it into SELF/.

  * Hard facts are DERIVED from code (authoritative): paths, line counts, staleness,
    nova/third-party imports, bound/seen ports, which launcher/orchestrator starts a
    part, and which other parts import it.
  * The ONE non-derivable fact — a part's one-line purpose — is read from a uniform
    in-file `@nova:` token (no sidecar files). Missing purpose = flagged, not invented.
  * Cross-checks flag drift: undescribed parts, dead-part candidates, stale files.

Outputs:  SELF/core/03_body_manifest.md   SELF/reference/manifest.json
Usage:    python general_tools/build_manifest.py [--dry]
"""

import ast, json, re, sys, time
from datetime import datetime
from pathlib import Path

_THIS = Path(__file__).resolve()
GENERAL_TOOLS = _THIS.parent
WORKSPACE_ROOT = GENERAL_TOOLS.parent
sys.path.insert(0, str(GENERAL_TOOLS))
import calls  # reuse the AST call-graph engine
import os as _os


def _atomic_write(path, text):
    """Write text atomically (temp + os.replace) so a concurrent reader
    (build_nova_context_block, or another regen) never sees a half-written file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    _os.replace(tmp, path)

NOVA_BODY = WORKSPACE_ROOT / "nova_body"
SELF_DIR = WORKSPACE_ROOT / "SELF"
CORE_DIR = SELF_DIR / "core"
REF_DIR = SELF_DIR / "reference"
DRY_RUN = "--dry" in sys.argv

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", "backups", "screenshots",
                ".clawhub", "_archive", "_admin"}
KNOWN_PORTS = {"8080", "8765"}
STALE_DAYS = 90
TOKEN = "@nova:"
BIND_PATTERNS = [
    r"uvicorn\.run\([^)]*?port\s*=\s*(\d{4,5})",
    r"\.run\([^)]*?port\s*=\s*(\d{4,5})",
    r"--port[ =]+(\d{4,5})",
    r"\.bind\(\([^)]*?(\d{4,5})",
    r"host\s*=[^,]+,\s*port\s*=\s*(\d{4,5})",
    r"listen\([^)]*?(\d{4,5})",
]


def _aignore() -> set[str]:
    out = set()
    for cand in (WORKSPACE_ROOT / ".aignore", WORKSPACE_ROOT.parent / ".aignore"):
        if cand.exists():
            for ln in cand.read_text("utf-8", errors="replace").splitlines():
                ln = ln.strip().rstrip("/")
                if ln and not ln.startswith("#"):
                    out.add(ln[10:] if ln.startswith("workspace/") else ln)
    return out


AIGNORE = _aignore()


def _excluded(p: Path) -> bool:
    if set(p.parts) & EXCLUDE_DIRS or any(s.startswith("_archive") for s in p.parts):
        return True
    try:
        rel = p.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        rel = p.as_posix()
    return any(rel == ig or rel.startswith(ig + "/") for ig in AIGNORE)


def _full(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="replace")
    except Exception:
        return ""


def _find_token(path: Path) -> str | None:
    head = "\n".join(_full(path).splitlines()[:60])
    m = re.search(re.escape(TOKEN) + r"\s*(.+)", head)
    if not m:
        return None
    val = m.group(1).strip().rstrip("-->").rstrip().strip('"').strip()
    return val or None


def _lines(path: Path) -> int:
    return _full(path).count("\n") + (1 if _full(path) else 0)


def _age_days(path: Path) -> int:
    try:
        return int((time.time() - path.stat().st_mtime) / 86400)
    except Exception:
        return -1


def _ports(texts: list[str]) -> tuple[list[str], list[str]]:
    bind, seen = set(), set()
    for t in texts:
        for pat in BIND_PATTERNS:
            for m in re.finditer(pat, t):
                bind.add(m.group(1))
        for m in re.finditer(r"(?i)port\D{0,4}(\d{3,5})", t):
            seen.add(m.group(1))
        for k in KNOWN_PORTS:
            if k in t:
                seen.add(k)
    return sorted(bind), sorted(seen)


def _py(d: Path) -> list[Path]:
    return [f for f in d.rglob("*.py") if not _excluded(f)]


def _imports(py_files: list[Path]) -> tuple[list[str], list[str]]:
    nova, third = set(), set()
    for f in py_files:
        for imp in calls.get_imports(f):
            k = calls.classify_import(imp["module"])
            if k == "nova":
                nova.add(imp["module"].split(".")[0])
            elif k == "third_party":
                third.add(imp["module"].split(".")[0])
    return sorted(nova), sorted(third)


def _purpose(files: list[Path]) -> str | None:
    order = sorted(files, key=lambda f: (
        0 if f.name == "__init__.py" else
        1 if f.stem in ("server", "main", "__main__", f.parent.name) else 2,
        len(f.parts)))
    for f in order:
        p = _find_token(f)
        if p:
            return p
    return None


def discover() -> list[dict]:
    parts = []

    def pkg(d: Path, kind: str):
        pys = _py(d)
        if not pys:
            return
        nova, third = _imports(pys)
        bind, seen = _ports([_full(f) for f in pys])
        parts.append({
            "name": d.name, "kind": kind,
            "path": d.relative_to(WORKSPACE_ROOT).as_posix(),
            "purpose": _purpose(pys + list(d.glob("*.cmd"))),
            "files": len(pys), "lines": sum(_lines(f) for f in pys),
            "age_days": min((_age_days(f) for f in pys), default=-1),
            "ports_bind": bind, "ports_seen": seen,
            "nova_imports": nova, "third_party": third,
        })

    def single(f: Path, kind: str):
        nova, third = _imports([f]) if f.suffix == ".py" else ([], [])
        bind, seen = _ports([_full(f)])
        parts.append({
            "name": f.name, "kind": kind,
            "path": f.relative_to(WORKSPACE_ROOT).as_posix(),
            "purpose": _find_token(f),
            "files": 1, "lines": _lines(f), "age_days": _age_days(f),
            "ports_bind": bind, "ports_seen": seen,
            "nova_imports": nova, "third_party": third,
        })

    for root in (NOVA_BODY, GENERAL_TOOLS):
        if root.exists():
            for d in sorted(root.iterdir()):
                if d.is_dir() and not d.name.startswith(".") and not _excluded(d):
                    pkg(d, "body_part" if root.name == "nova_body" else "tool")
    for f in sorted(GENERAL_TOOLS.glob("*.py")):
        if not _excluded(f):
            single(f, "tool")
    lance = WORKSPACE_ROOT / "nova_lancedb"
    if lance.exists() and _py(lance):
        pkg(lance, "body_part")
    for f in sorted(WORKSPACE_ROOT.glob("*.py")):       # root orchestrators
        if not _excluded(f):
            single(f, "entrypoint")
    for f in sorted(WORKSPACE_ROOT.glob("*.cmd")):      # launchers
        single(f, "launcher")
    return parts


def cross_check(parts: list[dict]) -> dict:
    for p in parts:
        p["referenced_by"] = sorted({q["name"] for q in parts
                                     if p["name"] in q.get("nova_imports", []) and q is not p})
    # Launchers AND root entrypoints can "start" other parts (by name/path in their text)
    starters = {p["name"]: _full(WORKSPACE_ROOT / p["path"])
                for p in parts if p["kind"] in ("launcher", "entrypoint")}
    for p in parts:
        stem = p["name"].rsplit(".", 1)[0]
        p["launched_by"] = sorted([s for s, t in starters.items()
                                   if s != p["name"] and (stem in t or p["path"] in t)])

    undescribed, dead, stale = [], [], []
    for p in parts:
        flags = []
        if not p.get("purpose"):
            flags.append("undescribed"); undescribed.append(p["name"])
        if p["kind"] in ("body_part", "tool") and p["files"] and \
           not p["referenced_by"] and not p["launched_by"] and p["name"] != _THIS.name:
            flags.append("no_inbound_refs"); dead.append(p["name"])
        if p["age_days"] >= STALE_DAYS:
            flags.append(f"stale_{p['age_days']}d"); stale.append(p["name"])
        p["flags"] = flags
    return {"undescribed": undescribed, "dead_part_candidates": dead, "stale": stale}


def build() -> dict:
    parts = discover()
    parts.sort(key=lambda p: (p["kind"], p["name"]))
    flags = cross_check(parts)
    return {"generated": datetime.now().isoformat(timespec="seconds"),
            "workspace": str(WORKSPACE_ROOT), "part_count": len(parts),
            "described": sum(1 for p in parts if p.get("purpose")),
            "flags": flags, "parts": parts}


def render_md(m: dict) -> str:
    L = ["# Nova Body Manifest",
         f"_Auto-generated by general_tools/build_manifest.py — {m['generated']}. "
         f"DO NOT EDIT BY HAND._",
         f"_Parts: {m['part_count']} ({m['described']} described, "
         f"{len(m['flags']['undescribed'])} undescribed)._", ""]
    titles = {"entrypoint": "Entrypoints / orchestrators",
              "body_part": "Body parts (nova_body)", "tool": "Tools (general_tools)",
              "launcher": "Launchers (.cmd)"}
    by = {}
    for p in m["parts"]:
        by.setdefault(p["kind"], []).append(p)
    for kind in ("entrypoint", "body_part", "tool", "launcher"):
        if kind not in by:
            continue
        L += [f"## {titles.get(kind, kind)}", ""]
        for p in by[kind]:
            L.append(f"### {p['name']}  `{p['path']}`")
            L.append(p["purpose"] or "_(undescribed — needs an @nova: line)_")
            f = []
            if p["ports_bind"]:
                f.append(f"binds: {', '.join(p['ports_bind'])}")
            elif p["ports_seen"]:
                f.append(f"ports seen: {', '.join(p['ports_seen'])}")
            if p.get("referenced_by"):
                f.append(f"used by: {', '.join(p['referenced_by'])}")
            if p.get("launched_by"):
                f.append(f"started by: {', '.join(p['launched_by'])}")
            f.append(f"{p['files']} file(s), {p['lines']} lines")
            if p["flags"]:
                f.append("flags: " + ", ".join(p["flags"]))
            L += [f"<sub>{' · '.join(f)}</sub>", ""]
    fl = m["flags"]
    L += ["## Drift / attention", "",
          f"- Undescribed ({len(fl['undescribed'])}): {', '.join(fl['undescribed']) or 'none'}",
          f"- No inbound refs ({len(fl['dead_part_candidates'])}): {', '.join(fl['dead_part_candidates']) or 'none'}",
          f"- Stale >{STALE_DAYS}d ({len(fl['stale'])}): {', '.join(fl['stale']) or 'none'}", ""]
    return "\n".join(L)


def generate_start_here():
    """Auto-build SELF/core/00_START_HERE.md as a read-order index of core/*.md,
    so the boot order is a filesystem property (numeric prefixes), not a hand-kept
    doc. Each entry's label is the file's first H1 heading."""
    files = sorted(p for p in CORE_DIR.glob("*.md") if p.name != "00_START_HERE.md")
    L = ["# SELF — Nova's Sense of Self (READ IN ORDER)", "",
         "This folder is who I am and how I work. On boot and on every context refresh",
         "I load `SELF/core/` in numeric order. These are the first things I read:", ""]
    n = 1
    for p in files:
        title = p.stem
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("# "):
                title = ln[2:].strip()
                break
        L.append(f"{n}. `{p.name}` — {title}")
        n += 1
    L += ["",
          "Deeper reference (loaded on demand, not every turn) lives in `SELF/reference/`",
          "(NCL grammar, upgrade protocol, heartbeat, full manifest.json). My working",
          "memory — what I'm doing right now — lives in `memory/` (STATUS, JOURNAL, COLE).",
          "",
          "_Auto-generated by general_tools/build_manifest.py. Rule: if it isn't in `SELF/`,",
          "it isn't part of my constant self-model._"]
    _atomic_write(CORE_DIR / "00_START_HERE.md", "\n".join(L) + "\n")


def main():
    m = build()
    md = render_md(m)
    if DRY_RUN:
        print(md)
        return
    CORE_DIR.mkdir(parents=True, exist_ok=True)
    REF_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(CORE_DIR / "03_body_manifest.md", md)
    generate_start_here()
    _atomic_write(REF_DIR / "manifest.json", json.dumps(m, indent=2, ensure_ascii=False))
    print(f"[manifest] {m['part_count']} parts ({m['described']} described) "
          f"-> SELF/core/03_body_manifest.md ; full -> SELF/reference/manifest.json")


if __name__ == "__main__":
    main()
