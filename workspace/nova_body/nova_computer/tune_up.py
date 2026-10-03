# Last updated: 2026-10-03 10:59:53
# @nova: A pass over my computer that fixes what is loose and then PROVES it, rather than
#        assuming. Safe to run any time; every step is idempotent.
# @claude 2026-09-03: rewritten from a one-shot into a repeatable fix+verify pass, and taught
# to chase the two noises the first boot left behind:
#   (a) "Processing /etc/fstab with mount -a failed" on EVERY command -- the drvfs line was
#       written before the Windows-side NovaDrop folder existed (it exists now).
#   (b) "CreateProcessCommon:792: chdir(/var/lib/nova) failed 2" -- WSL cannot chdir into the
#       working directory it was handed (Windows-drive mounts are off by design), so it falls
#       back to a path that does not exist. We diagnose it, then make the path real.
# Design_Principles #4: verify against ground truth. Every fix below is followed by a read-back.
import sys, time, urllib.request
sys.stdout.reconfigure(line_buffering=True)
from nova_computer.computer import NovaComputer

pc = NovaComputer()
print("backend:", pc.backend.name, "|", pc.where())
if pc.backend.name != "wsl":
    print("TUNE_UP_RESULT: SKIPPED - this pass is for the WSL backend only")
    raise SystemExit(0)

def root(cmd, t=120, label=None):
    rc, out, err = pc._exec_root(cmd, timeout=t)
    noise = ("Processing /etc/fstab", "CreateProcessCommon")
    err_shown = "\n".join(l for l in (err or "").splitlines()
                          if not any(n in l for n in noise)).strip()
    print(f"$ {label or cmd}\n  rc={rc} {out} {err_shown}".rstrip())
    return rc, out

print("\n--- diagnose ---")
root("getent passwd nova; echo 'root home:'; getent passwd root | cut -d: -f6",
     label="who is nova and where does she live")

print("\n--- fix ---")
# ROOT CAUSE, found 2026-09-03 by the diagnose block above:
#   nova:x:115:122::/var/lib/nova:/bin/bash
# She is a SYSTEM user (uid 115) whose passwd home is /var/lib/nova -- but every piece of her
# desktop lives in /home/nova (.vnc/passwd, .vnc/xstartup, .Xauthority) and the systemd unit
# sets HOME=/home/nova. That mismatch is why WSL kept trying to chdir into a directory that
# did not exist. Point her home where her things actually are.
# usermod REFUSES while the user has running processes, and the 09-04 run did exactly
# that: services were still up, the change silently failed, and passwd still said
# /var/lib/nova on 09-06 (Astra). Stop her desktop first, then verify the result.
root("systemctl stop nova-vnc nova-novnc 2>/dev/null; pkill -u nova 2>/dev/null; sleep 2; "
     "usermod -d /home/nova nova; mkdir -p /home/nova && chown -R nova:nova /home/nova; "
     "getent passwd nova")
rc, who = root("getent passwd nova | cut -d: -f6", label="her home, after the change")
if "/home/nova" not in (who or ""):
    print("  !! her home is STILL not /home/nova - hands will fail to authenticate")
# ... and keep the old landing dir around so nothing that remembers it breaks.
root("mkdir -p /var/lib/nova && chown nova:nova /var/lib/nova && echo landing-dir-ok")
# THE REASON :5901 NEVER BOUND. The journal said it outright:
#   /usr/bin/xauth: timeout in locking authority file /home/nova/.Xauthority
# A killed VNC server leaves .Xauthority-c/-l and /tmp/.X1-lock behind; xauth then blocks for
# ~20s and the server dies before it can listen. Clear them, and make every future start
# clear them too (drop-in, so re-provisioning cannot lose the fix).
root("systemctl stop nova-vnc; sleep 1; rm -f /home/nova/.Xauthority-c /home/nova/.Xauthority-l "
     "/var/lib/nova/.Xauthority-c /var/lib/nova/.Xauthority-l /tmp/.X1-lock /tmp/.X11-unix/X1; "
     "echo stale-locks-cleared")
root("mkdir -p /etc/systemd/system/nova-vnc.service.d && printf '%s\\n' '[Service]' "
     "'ExecStartPre=-/bin/rm -f /home/nova/.Xauthority-c /home/nova/.Xauthority-l "
     "/tmp/.X1-lock /tmp/.X11-unix/X1' "
     "> /etc/systemd/system/nova-vnc.service.d/10-clear-stale-locks.conf "
     "&& systemctl daemon-reload && echo lock-clearing-dropin-written")
# (a) the drop folder: one shared path, now that the Windows side exists.
root("U=$(id -u nova); G=$(id -g nova); "
     "sed -i \"s|^C:/Users/lafou/NovaDrop .*|C:/Users/lafou/Project_Nova/NovaDrop /mnt/drop "
     "drvfs defaults,nofail,uid=$U,gid=$G 0 0|\" /etc/fstab; "
     "sed -i \"s|uid=[0-9]*,gid=[0-9]*|uid=$U,gid=$G|\" /etc/fstab; "
     "mkdir -p /mnt/drop && mount -a 2>/dev/null; mountpoint -q /mnt/drop "
     "&& echo drop-mounted || echo drop-NOT-mounted; grep drop /etc/fstab")
# the desktop she is actually watched through
root("systemctl daemon-reload && systemctl restart nova-vnc && sleep 4 "
     "&& systemctl restart nova-novnc && sleep 2 && systemctl is-active nova-vnc nova-novnc "
     "| paste -sd,")

print("\n--- reboot her computer: fstab is judged at BOOT, so a fix is unproven until then ---")
pc.stop()
time.sleep(2)
pc.start()
svc = ""
for _ in range(40):                          # systemd + both services, up to ~40s
    _, svc, _ = pc._exec_root(
        "systemctl is-active nova-vnc nova-novnc 2>/dev/null | paste -sd,", timeout=20)
    if svc.startswith("active,active"):
        break
    time.sleep(1)
print("services after clean boot:", svc or "(no answer)")

print("\n--- verify (ground truth, not claims) ---")
_, _, boot_err = pc._exec_root("true", timeout=20)
if "Processing /etc/fstab" in (boot_err or ""):
    print("  !! fstab warning SURVIVED a clean boot -> next fix: a systemd .mount unit for "
          "/mnt/drop instead of the fstab line (not auto-applied; untested here).")
else:
    print("  fstab warning after clean boot: gone")
if "chdir(/var/lib/nova)" in (boot_err or ""):
    print("  !! chdir(/var/lib/nova) SURVIVED - the landing dir fix did not take; read the "
          "diagnose block above for nova's real home.")
else:
    print("  chdir(/var/lib/nova) error after clean boot: gone")

ports = ""
for _ in range(20):                          # VNC takes a few seconds to bind after start
    _, ports, _ = pc._exec_root(
        "ss -tlnH | awk '{print $4}' | grep -E ':(5901|6080)$' | paste -sd,", timeout=20)
    if "5901" in ports and "6080" in ports:
        break
    time.sleep(1)
print("ports actually listening:", ports or "(none)")
if "5901" not in (ports or ""):
    print("  !! VNC (5901) is not listening - the viewer page would load but show no desktop.")
    root("journalctl -u nova-vnc --no-pager -n 12 | tail -12", label="why nova-vnc is unhappy")
rc, out = pc.bash("echo bash-ok && whoami && pwd")
print("bash:", rc, out.replace("\n", " | "))
rc, out = pc.pwsh("'pwsh ' + $PSVersionTable.PSVersion.ToString()")
print("pwsh:", rc, out)
rc, out = pc.bash("echo drop-test-$(date +%s) > /mnt/drop/hello_from_nova_computer.txt "
                  "&& cat /mnt/drop/hello_from_nova_computer.txt")
print("drop write:", rc, out)
try:
    with urllib.request.urlopen("http://localhost:6080/vnc.html", timeout=10) as r:
        print("viewer HTTP:", r.status, "->", pc.desktop_url)
except Exception as e:
    print("viewer HTTP: FAILED", e)
print("\nstatus:", pc.status())
print("TUNE_UP_RESULT: DONE")
