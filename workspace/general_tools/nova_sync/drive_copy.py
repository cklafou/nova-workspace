# @nova: Keeps Nova_Drive/read a text copy of the last commit, so Cole can read Nova from a Drive-only PC.
# Last updated: 2026-10-04 15:01:23
"""Nova_Drive: Nova, readable from a computer that can reach Google Drive and nothing else.

Cole works on Nova from a work PC with only a browser. Google Drive for Desktop used to sync all of
Project_Nova for that. It cannot skip subfolders, so it uploaded .git, the sealed model weights and
token files, and its temp folder inside the repository stopped autosave for 35 hours on 2026-10-01
(Orient, OPERATIONS.md, "Lessons from incidents" 7). Since 2026-10-03 Drive for Desktop syncs only
Project_Nova/Nova_Drive:

    read/   The text files of the last commit under workspace/, plus AGENTS.md: code, docs, Orient,
            configs, her notes. Git already leaves out secrets, weights and logs; this also leaves
            out binaries, node_modules and anything over 5 MB. Refreshed after every autosave. It is
            a copy: anything edited here is overwritten by the next refresh.
    inbox/  Whatever Cole writes away from this PC. This module never modifies or deletes it.

Reads git only (rev-parse, ls-tree, cat-file), writes each file atomically (temp file + rename),
and deletes only files it wrote itself, as recorded in read/.nova_export.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".cmd", ".bat", ".ps1", ".sh", ".js",
                 ".html", ".css", ".toml", ".yaml", ".yml", ".cfg", ".ini", ".csv", ".svg"}
SKIP_PARTS = {"node_modules", "__pycache__", ".git", ".venv", "venv"}
MAX_BYTES = 5 * 1024 * 1024
MANIFEST = ".nova_export.json"
README = """Nova_Drive: Project Nova, readable from anywhere Google Drive works.

read\\   A copy of the code, docs and notes from the last autosave on Cole's PC. Start with
        read\\Orient\\README.md. Edits here are overwritten, so don't work in this folder.
inbox\\  Put anything you write away from that PC here. Nothing touches it automatically;
        Claude and Codex are told to look here when you mention it.

Made by workspace\\general_tools\\nova_sync\\drive_copy.py, which the watcher runs after each autosave.
"""


def _git(repo, *args, data=None):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.run(["git", *args], cwd=str(repo), input=data, capture_output=True,
                          check=True, env=env).stdout


def wanted(path: str, size: int) -> bool:
    p = Path(path)
    parts = tuple(part.casefold() for part in p.parts)
    if parts[:1] == ("workspace",):
        parts = parts[1:]
    if parts[:2] == ("temp", "collaboration"):
        return False  # Defense in depth even if a transport file was accidentally committed.
    return (size <= MAX_BYTES and p.suffix.lower() in TEXT_SUFFIXES
            and not SKIP_PARTS.intersection(parts))


def _dest(read: Path, path: str) -> Path:
    return read / (path[len("workspace/"):] if path.startswith("workspace/") else path)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name[:40] + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _blobs(repo, oids):
    """Yield (oid, bytes) for each oid, in order, from one `git cat-file --batch` call."""
    out = _git(repo, "cat-file", "--batch", data=("\n".join(oids) + "\n").encode())
    pos = 0
    for _ in oids:
        end = out.index(b"\n", pos)
        oid, kind, size = out[pos:end].split()
        size = int(size)
        yield oid.decode(), out[end + 1:end + 1 + size]
        pos = end + 1 + size + 1


def export(repo, root=None, time_budget=None) -> dict:
    """Bring root/read up to the repository's HEAD. Safe to call often: with nothing new it does
    one `git rev-parse` and returns. With `time_budget` (seconds) it stops early and resumes on
    the next call."""
    repo = Path(repo)
    root = Path(root) if root else repo / "Nova_Drive"
    read, inbox = root / "read", root / "inbox"
    read.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    if not (root / "README.txt").exists():
        _write(root / "README.txt", README.replace("\n", "\r\n").encode("utf-8"))
    head = _git(repo, "rev-parse", "HEAD").decode().strip()
    mpath = read / MANIFEST
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    files = manifest.get("files", {})
    if manifest.get("head") == head and manifest.get("complete"):
        return {"head": head, "changed": 0, "removed": 0, "complete": True}

    tree = {}
    for entry in _git(repo, "ls-tree", "-r", "-l", "-z", "HEAD", "--", "workspace", "AGENTS.md").split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        _mode, kind, oid, size = meta.split()
        path = path.decode("utf-8", "surrogateescape")
        if kind == b"blob" and size.isdigit() and wanted(path, int(size)):
            tree[path] = oid.decode()

    started, changed, removed, complete = time.monotonic(), 0, 0, True
    todo = sorted(p for p, oid in tree.items() if files.get(p) != oid)
    for i in range(0, len(todo), 200):
        if time_budget and time.monotonic() - started > time_budget:
            complete = False
            break
        chunk = todo[i:i + 200]
        for path, (oid, data) in zip(chunk, _blobs(repo, [tree[p] for p in chunk])):
            _write(_dest(read, path), data)
            files[path] = oid
            changed += 1
        _write(mpath, json.dumps({"head": head, "complete": False, "files": files}, indent=1).encode())
    if complete:
        for path in [p for p in files if p not in tree]:
            try:
                _dest(read, path).unlink(missing_ok=True)
                del files[path]
                removed += 1
            except OSError:
                complete = False           # retried next time; nothing outside `files` is touched
    _write(mpath, json.dumps({"head": head, "complete": complete, "files": files}, indent=1).encode())
    return {"head": head, "changed": changed, "removed": removed, "complete": complete}


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve()
    print(export(here.parents[3], time_budget=float(sys.argv[1]) if len(sys.argv) > 1 else None))
