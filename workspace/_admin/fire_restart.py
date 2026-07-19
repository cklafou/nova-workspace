"""Fire the already-written restart wrapper using the launch method just proven to work
(CREATE_NEW_CONSOLE | CREATE_BREAKAWAY_FROM_JOB), and VERIFY it started before exiting.

Breakaway is the point: this process is a child of the chat server, and the server is
about to be killed by the very batch we are launching. Without breakaway the relauncher
can die with its parent — which is the leading suspect for why the restart silently did
nothing at 14:25 today.
"""
import json, subprocess, time
from pathlib import Path

TMP = Path(r"C:\Users\lafou\Project_Nova\workspace\_admin\Temp")
WS = Path(r"C:\Users\lafou\Project_Nova\workspace")
wrapper = TMP / "nova_restart_run.cmd"
logf = TMP / "nova_restart.log"

if not wrapper.exists():
    print("ABORT: no wrapper at", wrapper)
    raise SystemExit(1)

mt_before = logf.stat().st_mtime if logf.exists() else 0.0
NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE
BREAKAWAY = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)

child, used = None, None
for name, flags in (("new_console|breakaway", NEW_CONSOLE | BREAKAWAY),
                    ("new_console", NEW_CONSOLE)):
    try:
        child = subprocess.Popen(["cmd.exe", "/c", str(wrapper)], cwd=str(WS),
                                 creationflags=flags, close_fds=True)
        used = name
        break
    except Exception as e:
        print(f"  {name}: {type(e).__name__}: {e}")

print("method:", used, "pid:", getattr(child, "pid", None))
time.sleep(1.5)
alive = child is not None and child.poll() is None
mt_after = logf.stat().st_mtime if logf.exists() else 0.0
print("child_alive:", alive, " log_touched:", mt_after > mt_before)
print("VERIFIED:", bool(alive or (mt_after > mt_before)))
