# Last updated: 2026-07-23 08:20:00
"""DirShape Health — walk into a folder and know if it's unwell."""
import os
from datetime import datetime, timezone
from pathlib import Path

def run(path: str) -> str:
    """Diagnose a directory's health: staleness, orphans, dead weight, activity."""
    root = Path(path)
    if not root.is_dir():
        return f"Not a directory: {path}"

    # Gather facts
    all_files = []
    now = datetime.now(timezone.utc)
    for p in root.rglob('*'):
        if p.is_file() and not p.name.startswith('.'):
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                days = (now - mtime).days
                all_files.append((p, days))
            except OSError:
                pass

    if not all_files:
        return f"{root.name}: empty or unreadable. Nothing to diagnose."

    # Staleness: folders whose newest file is >30 days old
    folder_newest = {}
    for p, days in all_files:
        parent = p.parent.relative_to(root)
        cur = folder_newest.get(parent, 999)
        folder_newest[parent] = min(cur, days)
    stale = {k: v for k, v in folder_newest.items() if v > 30}

    # Dead weight: common build/dist/temp dirs bigger than the rest
    build_names = {'build', 'dist', '__pycache__', 'node_modules', '.pytest_cache'}
    dead_weight = []
    for d in root.iterdir():
        if d.is_dir() and d.name.lower() in build_names:
            size = sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
            rest = sum(p2.stat().st_size for p2, _ in all_files if not str(p2).startswith(str(d)))
            if size > rest and rest > 0:
                dead_weight.append((d.name, size // 1024, rest // 1024))

    # Activity: where was the last real work?
    recent = sorted(all_files, key=lambda x: x[1])[:5]
    active_dirs = sorted({p.parent.relative_to(root) for p, _ in recent})

    # Age spread
    ages = [d for _, d in all_files]
    median_age = sorted(ages)[len(ages)//2]
    oldest = max(ages)

    # Orphans: config/lock files whose partner doesn't exist in the same folder
    orphan_rules = {
        "requirements.txt": ["pipfile", "setup.py", "pyproject.toml"],
        "package-lock.json": ["package.json"],
        "poetry.lock": ["pyproject.toml"],
    }
    for dirpath, _, filenames in os.walk(root):
        fnames_lower = {f.lower() for f in filenames}
        for orphan, partners in orphan_rules.items():
            if orphan in fnames_lower and not any(p in fnames_lower for p in partners):
                parts.append(f"Orphan: {orphan} in {dirpath.relative_to(root)} with no matching partner.")

    # Build diagnosis
    parts = []
    parts.append(f"{root.name}: {len(all_files)} files, median age {median_age}d, oldest {oldest}d.")

    if stale:
        stale_names = list(stale)[:4]
        ages_str = ', '.join(f'{n} ({v}d)' for n, v in [(s, stale[s]) for s in stale_names])
        parts.append(f"{len(stale)} folder(s) haven't moved in >30 days: {ages_str}. Stale.")
    if dead_weight:
        for name, dw, rest in dead_weight:
            parts.append(f"{name}/ weighs {dw}KB vs {rest}KB of source. Dead weight.")

    if not stale and not dead_weight:
        parts.append("No rot, nothing sitting too long.")

    if active_dirs:
        shown = [str(d) for d in active_dirs if str(d) != '.']
        if not shown: shown = ['(root)']
        parts.append(f"Recent work in: {', '.join(shown[:3])}.")

    return ' '.join(parts)

def _shape_dict(path: str) -> dict:
    """Return the raw shape of a directory as a plain dict (no opinions)."""
    root = Path(path)
    all_files = []
    for p in root.rglob('*'):
        if p.is_file() and not p.name.startswith('.'):
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                days = (datetime.now(timezone.utc) - mtime).days
                all_files.append({"rel": str(p.relative_to(root)), "size": p.stat().st_size, "age_days": days})
            except OSError:
                pass
    folders = sorted({f["rel"].rsplit(os.sep, 1)[0] if os.sep in f["rel"] else "." for f in all_files})
    return {
        "file_count": len(all_files),
        "total_kb": sum(f["size"] for f in all_files) // 1024,
        "folders": folders,
        "youngest": min((f["age_days"] for f in all_files), default=0),
        "oldest": max((f["age_days"] for f in all_files), default=0),
    }


def snapshot_save(path: str, log_file: str) -> str:
    """Save one shape snapshot to a JSONL log file."""
    import json
    shape = _shape_dict(path)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "path": path, **shape}
    log = Path(log_file)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    return f"Saved snapshot of {path}: {shape['file_count']} files, {len(shape['folders'])} folders."


def snapshot_diff(log_file: str) -> str:
    """Compare the last two snapshots in a log and describe what changed."""
    import json
    log = Path(log_file)
    if not log.exists() or log.stat().st_size == 0:
        return "No snapshots yet. Nothing to compare."
    lines = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    if len(lines) < 2:
        return f"Only {len(lines)} snapshot(s). Need two to compare."
    old, new = lines[-2], lines[-1]
    diffs = []
    for key in ("file_count", "total_kb", "youngest", "oldest"):
        if old.get(key) != new.get(key):
            diffs.append(f"{key}: {old.get(key)} -> {new.get(key)}")
    old_folders = set(old.get("folders", []))
    new_folders = set(new.get("folders", []))
    added = new_folders - old_folders
    removed = old_folders - new_folders
    if added:
        diffs.append(f"new folders: {', '.join(sorted(added)[:5])}")
    if removed:
        diffs.append(f"gone folders: {', '.join(sorted(removed)[:5])}")
    if not diffs:
        return "No changes between the last two snapshots."
    before = old["ts"][:16]
    after = new["ts"][:16]
    return f"{before} -> {after}: {'; '.join(diffs)}."


# Tool contract
TOOL = {
    "name": "dir_shape_health",
    "description": "Diagnose whether a directory is unwell: stale folders, dead weight, orphaned configs, activity spread. Returns a short health note.",
    "params": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory to examine"}}, "required": ["path"]},
}
