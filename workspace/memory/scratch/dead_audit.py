# Last updated: 2026-07-19 21:56:25
# Dead-function audit for nova_body: find defs that are never called anywhere else.
import re, pathlib

ROOT = pathlib.Path("nova_body")
defs = {}
calls = {}
all_py = list(ROOT.rglob("*.py"))
for f in all_py:
    text = f.read_text()
    for m in re.finditer(r"def (\w+)\s*\(", text):
        name = m.group(1)
        defs.setdefault(name, []).append((str(f.relative_to(ROOT)), m.start()))

for f in all_py:
    text = f.read_text()
    for name in defs:
        lines = text.splitlines()
        n = 0
        for i, line in enumerate(lines, 1):
            if re.search(r"\b" + re.escape(name) + r"\s*\(", line):
                if not re.match(r"\s*def " + re.escape(name) + r"\s*\(", line):
                    n += 1
        calls[name] = calls.get(name, 0) + n

dead = [name for name, count in calls.items() if count == 0]
print(f"Defined: {len(defs)} | Called: {len(calls)} | Dead: {len(dead)}")
for d in sorted(dead):
    locs = defs[d]
    print(f"  DEAD {d} -> defined at {locs[0][0]}:{locs[0][1]}")
print("\nALIVE but rarely used (called only once):")
for name, count in sorted(calls.items(), key=lambda x: x[1]):
    if count == 1:
        locs = defs[name]
        print(f"  ONCE {name} -> defined at {locs[0][0]}:{locs[0][1]}")

with open("memory/scratch/dead_audit_results.txt", "w") as out:
    out.write(f"Defined: {len(defs)} | Called: {len(calls)} | Dead: {len(dead)}\n")
    for d in sorted(dead):
        locs = defs[d]
        out.write(f"DEAD {d} -> {locs[0][0]}:{locs[0][1]}\n")
print("\nResults saved to memory/scratch/dead_audit_results.txt")
