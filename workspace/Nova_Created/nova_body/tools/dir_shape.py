# Last updated: 2026-07-23 21:57:58
"""dir_shape(path) -> one-paragraph read of what's in a directory."""

import os, json, pathlib

def run(path: str = "."):
    try:
        root = pathlib.Path(path).resolve()
        if not root.exists():
            return f"ERROR: {path} doesn't exist."

        total = 0
        depth = 0
        exts = {}
        biggest = (0, "")
        dirs_count = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirs_count += len(dirnames)
            rel = pathlib.Path(dirpath).relative_to(root)
            depth = max(depth, len(rel.parts))
            for f in filenames:
                total += 1
                ext = pathlib.Path(f).suffix.lower() or "(none)"
                exts[ext] = exts.get(ext, 0) + 1
                full = os.path.join(dirpath, f)
                try:
                    sz = os.path.getsize(full)
                    if sz > biggest[0]:
                        biggest = (sz, f)
                except:
                    pass

        ext_summary = ", ".join(f"{v} {k}" for k, v in sorted(exts.items(), key=lambda x: -x[1]))
        size_str = _human(biggest[0]) if biggest[0] else "nothing"

        return (f"{root.name}: {total} file(s) across {depth+1} levels and {dirs_count} subfolders. "
                f"Breakdown: {ext_summary}. Heaviest is {biggest[1]} at {size_str}.")
    except Exception as e:
        return f"ERROR: {e}"

def _human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} {u}"
        n /= 1024
    return f"{n:.1f} GB"

TOOL = {"name": "dir_shape", "description": "Instant read of a directory's shape: depth, file count, types, heaviest file.", "params": {"path": "directory to inspect (default current)"}}
