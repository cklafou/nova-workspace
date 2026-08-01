# Last updated: 2026-08-02 06:49:19
"""Scan .py files for TODO comments."""
import os

def run(path: str = ".") -> str:
    results = []
    for root, dirs, files in os.walk(path):
        # skip hidden dirs and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for fname in sorted(files):
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if '# TODO' in line or '#todo' in line.lower():
                            text = line.strip()
                            results.append(f"{fpath}:{i}: {text}")
            except Exception as e:
                results.append(f"{fpath}: ERROR reading: {e}")
    if not results:
        return "No TODO comments found."
    return '\n'.join(results)
