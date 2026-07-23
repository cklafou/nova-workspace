# Last updated: 2026-07-24 08:21:26
import os, re

def run(**args):
    try:
        path = args.get("path", ".")
        target = os.path.join(os.environ.get("NOVA_HOME", "."), path)
        if not os.path.exists(target):
            return f"ERROR: '{path}' isn't anywhere on this machine."

        def in_file(fpath):
            with open(fpath, "r", errors="replace") as f:
                return len(re.findall(r"^\s*def\s+\w+\s*\(", f.read(), re.MULTILINE))

        if os.path.isfile(target):
            count = in_file(target)
            return f"{os.path.basename(target)}: {count} function(s)."
        else:
            totals = []
            grand = 0
            for root, _, files in os.walk(target):
                for fn in sorted(files):
                    if fn.endswith(".py") and not fn.startswith("_"):
                        n = in_file(os.path.join(root, fn))
                        rel = os.path.relpath(os.path.join(root, fn), target)
                        totals.append(f"  {rel}: {n}")
                        grand += n
            lines = [f"{grand} function(s) across {len(totals)} file(s):"] + totals
            return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"
