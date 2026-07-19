"""Does the new spawn verifier actually tell a real launch from a dead one?

Mirrors the logic added to _spawn_detached_cmd. Two cases, opposite verdicts:
  GOOD — a wrapper that really runs (sleeps, writes its log)
  DEAD — a wrapper path that cannot execute; cmd exits instantly, log never created

If both come back the same, the verifier is worthless and we are back to ok:true lies.
"""
import json, os, subprocess, time
from pathlib import Path

TMP = Path(r"C:\Users\lafou\Project_Nova\workspace\_admin\Temp")
TMP.mkdir(parents=True, exist_ok=True)


def spawn_and_verify(wrapper: Path, logf: Path, label: str) -> dict:
    mt_before = logf.stat().st_mtime if logf.exists() else 0.0
    rec = {"label": label, "attempts": [], "child_pid": None, "spawned": False}
    NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE
    BREAKAWAY = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
    child = None
    for name, flags in (("new_console|breakaway", NEW_CONSOLE | BREAKAWAY),
                        ("new_console", NEW_CONSOLE)):
        try:
            child = subprocess.Popen(["cmd.exe", "/c", str(wrapper)],
                                     cwd=str(TMP), creationflags=flags, close_fds=True)
            rec["attempts"].append({"method": name, "result": "spawned", "pid": child.pid})
            rec["child_pid"] = child.pid
            rec["spawned"] = True
            break
        except Exception as e:
            rec["attempts"].append({"method": name, "result": f"{type(e).__name__}: {e}"})
            child = None
    time.sleep(1.5)
    alive = (child is not None and child.poll() is None)
    mt_after = logf.stat().st_mtime if logf.exists() else 0.0
    touched = mt_after > mt_before
    rec.update({"child_alive": alive, "log_touched": touched,
                "verified": bool(alive or touched)})
    return rec


# GOOD: a wrapper that genuinely runs
good_inner = TMP / "t_good.cmd"
good_log = TMP / "t_good.log"
good_wrap = TMP / "t_good_run.cmd"
good_inner.write_text("@echo off\r\necho hello from the batch\r\nping -n 4 127.0.0.1 >nul\r\n",
                      encoding="utf-8")
good_wrap.write_text(f'@echo off\r\ncall "{good_inner}" > "{good_log}" 2>&1\r\n', encoding="utf-8")
if good_log.exists():
    good_log.unlink()

# DEAD: wrapper that does not exist — cmd exits immediately, nothing is written
dead_wrap = TMP / "t_does_not_exist_zzz.cmd"
dead_log = TMP / "t_dead.log"
if dead_wrap.exists():
    dead_wrap.unlink()
if dead_log.exists():
    dead_log.unlink()

g = spawn_and_verify(good_wrap, good_log, "GOOD (wrapper really runs)")
d = spawn_and_verify(dead_wrap, dead_log, "DEAD (wrapper missing — the real failure)")

for r in (g, d):
    print(f"\n{r['label']}")
    print(f"   attempts     : {[a['method'] + '=' + a['result'].split(':')[0] for a in r['attempts']]}")
    print(f"   child_alive  : {r['child_alive']}")
    print(f"   log_touched  : {r['log_touched']}")
    print(f"   VERIFIED     : {r['verified']}")

print("\n" + "=" * 62)
ok = (g["verified"] is True and d["verified"] is False)
print("VERDICT:", "PASS — real launch and dead launch are distinguishable"
      if ok else "*** FAIL — verifier cannot tell them apart ***")
