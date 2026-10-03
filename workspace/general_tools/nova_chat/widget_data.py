# Last updated: 2026-10-03 11:27:32
"""Bounded reads for frequently refreshed controller widgets."""
import json
from pathlib import Path


def read_jsonl_tail(path: Path, limit: int = 400, max_bytes: int = 512_000) -> list[dict]:
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            start = max(0, stream.tell() - max_bytes)
            stream.seek(start)
            if start:
                stream.readline()  # discard the partial first record
            lines = stream.read(max_bytes).splitlines()
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except (ValueError, UnicodeDecodeError):
            continue  # a writer may still be finishing its final record
    return rows[-limit:]
