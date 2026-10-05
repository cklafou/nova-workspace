# Last updated: 2026-10-05 21:27:11
# @nova: How far my computer reaches into Cole's. He decided (2026-09-04) that my machine is
#        not a cage but my HANDS into his: his whole drive, read-write, at /mnt/c, and every
#        Windows program callable from my shell. My own X display is what keeps his mouse,
#        keyboard and focus untouched -- not a wall around his files.
# @claude 2026-09-04: this REVERSES the 09-02 sandbox (automount off / interop off). Stated
# plainly because a future session will read the old comments and think this is a regression:
# it is not, it is Cole's explicit decision, taken with the trade-offs on the table. The
# remaining safety net is SNAPSHOT.cmd, not isolation.
#   CAVEAT he accepted: a Windows GUI app she launches renders on HIS desktop and takes focus.
#   Her own Linux apps run on her display and never do.
"""
nova_computer.reach -- set and verify how far her computer reaches into the host.

    cd nova_body && python -m nova_computer.reach          # apply + verify
    cd nova_body && python -m nova_computer.reach --show    # just report, change nothing

Config goes in via base64 so nothing she or Cole ever writes has to survive three layers of
shell quoting (wsl.exe -> bash -lc -> heredoc). That class of bug already cost this project a
day once (an em-dash in ping_claude.ps1).
"""
from __future__ import annotations

import base64
import sys
import time

from nova_computer.computer import NovaComputer

WSL_CONF = """[boot]
systemd=true

[user]
default=nova

# 2026-09-04, Cole: her computer is his computer, seen through her own environment.
# Whole drive, read-write. metadata = real Linux permissions on Windows files.
[automount]
enabled=true
root=/mnt/
options="metadata,uid={uid},gid={gid},umask=22,fmask=11"
mountFsTab=true

# Full interop: any Windows program is callable from her shell, Windows PATH included.
[interop]
enabled=true
appendWindowsPath=true

[network]
hostname=nova-computer
"""


def main() -> int:
    pc = NovaComputer()
    print("backend:", pc.backend.name, "|", pc.where())
    if pc.backend.name != "wsl":
        print("REACH_RESULT: SKIPPED - only meaningful for the WSL backend")
        return 0

    def root(cmd, t=120, label=None):
        rc, out, err = pc._exec_root(cmd, timeout=t)
        noise = ("Processing /etc/fstab", "CreateProcessCommon")
        err = "\n".join(l for l in (err or "").splitlines()
                        if not any(n in l for n in noise)).strip()
        print(f"$ {label or cmd}\n  rc={rc} {out} {err}".rstrip())
        return rc, out

    print("\n--- before ---")
    root("cat /etc/wsl.conf")
    if "--show" in sys.argv:
        root("ls /mnt/ ; echo ---; ls /mnt/c 2>/dev/null | head -5 || echo 'C: not mounted'")
        print("REACH_RESULT: SHOWN (nothing changed)")
        return 0

    rc, ids = root("echo $(id -u nova):$(id -g nova)", label="nova's real uid:gid")
    uid, _, gid = (ids.strip() or "115:122").partition(":")

    print("\n--- apply ---")
    conf = WSL_CONF.format(uid=uid.strip(), gid=gid.strip())
    b64 = base64.b64encode(conf.encode("utf-8")).decode("ascii")
    root(f"echo {b64} | base64 -d > /etc/wsl.conf && cat /etc/wsl.conf",
         label="write /etc/wsl.conf (automount+interop ON)")

    print("\n--- reboot her computer (wsl.conf is read at boot) ---")
    pc.stop()
    time.sleep(3)
    pc.start()                              # start() now waits out WSL's transition lock
    print("her computer is back:", pc.backend.wait_settled())
    svc = ""
    for _ in range(40):
        _, svc, _ = pc._exec_root(
            "systemctl is-active nova-vnc nova-novnc 2>/dev/null | paste -sd,", timeout=20)
        if svc.startswith("active,active"):
            break
        time.sleep(1)
    print("desktop services after reboot:", svc or "(no answer)")

    print("\n--- verify (ground truth, not claims) ---")
    ok = True
    rc, out = pc.bash("ls /mnt/ | paste -sd,")
    print("mounts:", out)
    if "c" not in out.split(","):
        print("  !! C: is NOT mounted"); ok = False

    rc, out = pc.bash("ls /mnt/c/Users/lafou | head -8 | paste -sd,")
    print("his profile, as she sees it:", out or "(unreadable)")
    ok = ok and rc == 0 and bool(out)

    rc, out = pc.bash("T=/mnt/c/Users/lafou/Project_Nova/NovaDrop/reach_write_test.txt; "
                      "echo reach-ok-$(date +%s) > $T && cat $T && rm -f $T && echo removed")
    print("write to his disk:", rc, out.replace("\n", " | "))
    ok = ok and rc == 0 and "reach-ok" in out

    rc, out = pc.bash("cd /mnt/c && cmd.exe /c echo interop-ok 2>&1 | tr -d '\\r'")
    print("launch a Windows program (cmd.exe):", rc, out)
    ok = ok and "interop-ok" in out

    rc, out = pc.bash("cd /mnt/c && powershell.exe -NoProfile -Command "
                      "\"$PSVersionTable.PSVersion.Major\" 2>&1 | tr -d '\\r'")
    print("host PowerShell reachable:", rc, out)

    rc, out = pc.bash("echo $PATH | tr ':' '\\n' | grep -ci '/mnt/c/' || true")
    print("Windows PATH entries visible to her:", out)

    rc, out = pc.bash("echo her-own-display: ${DISPLAY:-none}; "
                      "ls /tmp/.X11-unix/ 2>/dev/null | paste -sd,")
    print("her display (his screen stays hers-free):", out.replace("\n", " | "))

    print("\nstatus:", pc.status())
    print("REACH_RESULT:", "DONE" if ok else "INCOMPLETE - see the !! lines above")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as e:            # the 09-05 run ended mid-reboot with NO result line
        import traceback; traceback.print_exc()
        print("REACH_RESULT: FAILED -", e)
        raise SystemExit(1)
