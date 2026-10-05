# Last updated: 2026-10-05 18:23:37
# @nova: Keeps the updater's small persistent state (last check, remembered decisions, plans, jobs) in one atomic JSON file.
"""Persistent updater state.

One JSON file, written with temp-file + rename so a crash or the sync watcher never sees half
a file. A corrupt file is kept beside the new one (renamed), never silently discarded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading

from . import paths

FILE_NAME = "updater_state.json"
_LOCK = threading.RLock()
_last_problem = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file() -> Path:
    return paths.state_dir() / FILE_NAME


def problem() -> str:
    """A note about state that could not be read, for the status endpoint."""
    return _last_problem


def load() -> dict:
    global _last_problem
    with _LOCK:
        path = _file()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            keep = path.with_name(f"{path.stem}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
            try:
                os.replace(path, keep)
                _last_problem = f"Updater state was unreadable; kept as {keep.name} and started fresh."
            except OSError:
                _last_problem = "Updater state was unreadable and could not be set aside."
            return {}


def save(data: dict) -> None:
    with _LOCK:
        atomic_write_text(_file(), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def mutate(change):
    """Read, apply `change(data)`, write. Returns whatever `change` returns."""
    with _LOCK:
        data = load()
        result = change(data)
        save(data)
        return result


def atomic_write_text(path: Path, text: str, newline: str = "\n") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
