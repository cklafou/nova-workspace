# Last updated: 2026-10-04 15:01:23
# @nova: Making my computer a WHOLE computer -- one I can extend myself. Cole, 2026-09-04:
#        "she should primarily have her own applications to run stuff... her VM should be all
#        the capabilities she needs (including installing apps like ThinkorSwim's Linux App on
#        her own VM rather than needing to reach out onto my computer)."
# @claude 2026-09-04: reach.py removed the GUARDS between her computer and his. This file is
# the thing that matters more: her computer standing on its own. The point is not that I
# install a fixed list of software for her -- it is that SHE can install anything, whenever
# she decides she needs it. So this verifies the three things self-sufficiency actually
# rests on (network, sudo, a working package manager), lays down a solid workstation base,
# and only then installs the one app the mission names.
"""
nova_computer.toolkit -- can her computer stand on its own, and extend itself?

    cd nova_body && python -m nova_computer.toolkit            # verify + install base
    cd nova_body && python -m nova_computer.toolkit --check    # verify only, install nothing
    cd nova_body && python -m nova_computer.toolkit --tos      # also install thinkorswim
    cd nova_body && python -m nova_computer.toolkit --tos --update   # re-fetch it (new version)

IDEMPOTENT BY RULE (Cole, 2026-09-04): "Apps, like ThinkOrSwim, should not have to be fetched
more than once, unless the App needs to be updated." Her computer is a real machine with a
real disk -- what she installs STAYS installed across reboots and shutdowns. So every step
here checks first and does nothing if it is already done. Re-running this is cheap and safe.

Self-sufficiency test (the part that matters):
    1. NETWORK   she can reach the outside world at all
    2. SUDO      she can become root without a human typing a password
    3. PACKAGES  apt can refresh and install
If those three pass, every other capability is something she can add herself, unprompted.
"""
from __future__ import annotations

import sys
import time

from nova_computer.computer import NovaComputer

# A workstation base, not a fixed identity. Things she would otherwise have to stop and ask
# for the first time she wants to look at an image, read a PDF, or write code.
BASE = [
    "curl wget git unzip zip ca-certificates",              # fetching and unpacking anything
    "python3-pip python3-venv build-essential",             # writing and building her own tools
    "default-jre",                                          # java apps (thinkorswim ships its own)
    "firefox",                                              # a browser of her own
    "xdg-utils desktop-file-utils libgtk-3-0",              # launchers, file associations
    "fonts-dejavu fonts-liberation",                        # so text renders properly on her screen
    "imagemagick ffmpeg",                                   # seeing and making media
    "nano vim less tree htop jq",
    "scrot xdotool wmctrl xclip",                            # HER HANDS: see and act on her own screen                           # the small tools that make a shell livable
]

# thinkorswim's Linux client, per Schwab's own installer index (tosmediaserver.schwab.com).
# Bundles its own JRE; installs per-user into ~/thinkorswim. If the URL ever moves, she can
# find the current one herself -- that is the whole point of this file.
TOS_URL = "https://tosmediaserver.schwab.com/installer/InstFiles/thinkorswim_installer.sh"


def _report_disk_image() -> None:
    """Her computer is ONE FILE on his drive. Naming it is the proof that she is persistent:
    shutting her down is closing a laptop lid, not erasing her. It is also the file to back up
    (SNAPSHOT.cmd exports a portable copy of the same thing)."""
    import subprocess
    from nova_computer.backends import _NO_WINDOW, _decode
    try:
        p = subprocess.run(["reg", "query",
                            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss",
                            "/s", "/v", "BasePath"], capture_output=True, timeout=30,
                           **_NO_WINDOW)
        for line in _decode(p.stdout).splitlines():
            if "BasePath" in line:
                path = line.split("REG_SZ")[-1].strip()
                q = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    f"$f='{path}\\ext4.vhdx'; if (Test-Path $f) "
                                    "{'{0:N1} GB' -f ((Get-Item $f).Length/1GB)} else {'?'}"],
                                   capture_output=True, timeout=30, **_NO_WINDOW)
                size = _decode(q.stdout).strip()
                if size and size != "?":
                    print(f"her computer on disk: {path}\\ext4.vhdx  ({size}) "
                          "- survives shutdown, reboot, everything except --unregister")
                    return
    except Exception as e:
        print("  (could not locate her disk image:", e, ")")


def main() -> int:
    pc = NovaComputer()
    print("backend:", pc.backend.name, "|", pc.where())
    if pc.backend.name != "wsl":
        print("TOOLKIT_RESULT: SKIPPED - only meaningful for the WSL backend")
        return 0

    # If another runner is still rebooting her (REACH/TUNE_UP), wait rather than collide.
    if hasattr(pc.backend, "wait_settled"):
        print("WSL settled:", pc.backend.wait_settled())

    check_only = "--check" in sys.argv
    want_tos = "--tos" in sys.argv
    update = "--update" in sys.argv

    def root(cmd, t=600, label=None):
        rc, out, err = pc._exec_root(cmd, timeout=t)
        noise = ("Processing /etc/fstab", "CreateProcessCommon", "debconf:", "apt-key")
        err = "\n".join(l for l in (err or "").splitlines()
                        if not any(n in l for n in noise)).strip()
        tail = "\n".join(out.splitlines()[-6:])
        print(f"$ {label or cmd}\n  rc={rc} {tail} {err}".rstrip())
        return rc, out

    def nova(cmd, t=600, label=None):
        rc, out = pc.bash(cmd, timeout=t)
        print(f"$ {label or cmd}\n  rc={rc} " + "\n".join(out.splitlines()[-6:]))
        return rc, out

    ok = True
    print("\n=== 1. CAN SHE STAND ON HER OWN? ===")
    rc, out = nova("curl -sS -m 20 -o /dev/null -w '%{http_code}' https://archive.ubuntu.com "
                   "|| echo NO-NETWORK", label="network: can she reach the outside world")
    if "NO-NETWORK" in out or not out.strip().startswith(("2", "3")):
        print("  !! no network - she cannot install anything herself. Everything below "
              "will fail; fix egress first."); ok = False
    rc, out = nova("sudo -n id -u", label="sudo: can she become root unattended")
    if rc != 0 or out.strip() != "0":
        print("  !! passwordless sudo is not working - she cannot install software alone")
        ok = False
    rc, out = root("apt-get update -qq 2>&1 | tail -3; echo apt-rc=$?",
                   label="packages: can apt refresh")
    if "apt-rc=0" not in out:
        print("  !! apt cannot refresh"); ok = False

    if check_only:
        print("\nTOOLKIT_RESULT:", "SELF-SUFFICIENT" if ok else "NOT SELF-SUFFICIENT")
        return 0 if ok else 1
    if not ok:
        print("\nTOOLKIT_RESULT: NOT SELF-SUFFICIENT - stopping before install")
        return 1

    print("\n=== 2. A WORKSTATION BASE (installed once; it persists on her disk) ===")
    for group in BASE:
        first = group.split()[0]
        rc, out = root(f"dpkg -s {group} >/dev/null 2>&1 && echo ALREADY-INSTALLED || "
                       f"(DEBIAN_FRONTEND=noninteractive apt-get install -y -qq {group} "
                       f"2>&1 | tail -2; echo installed)", label=f"{first} ...")

    print("\n=== 3. HER OWN APPS (on her machine, fetched once, kept forever) ===")
    if want_tos:
        rc, out = nova("test -d ~/thinkorswim && echo INSTALLED || "
                       "(test -s ~/tos_installer.sh && echo INSTALLER-PRESENT || echo ABSENT)",
                       label="is thinkorswim already hers?")
        state = out.strip().split()[-1] if out.strip() else "ABSENT"
        if state == "INSTALLED" and not update:
            nova("ls ~/thinkorswim | head -3 | paste -sd,",
                 label="thinkorswim already installed - nothing to fetch")
        elif state == "INSTALLER-PRESENT" and not update:
            print("  installer already on her disk (~/tos_installer.sh) - not re-downloading.")
            print("  She installs it from her own desktop:  ./tos_installer.sh   (or -q)")
        else:
            why = "re-fetching (--update)" if update else "first fetch"
            rc, out = nova(
                f"cd ~ && curl -fL -m 300 -o tos_installer.sh '{TOS_URL}' "
                "&& chmod +x tos_installer.sh && echo downloaded $(du -h tos_installer.sh "
                "| cut -f1)", t=600, label=f"thinkorswim Linux installer ({why})")
            if rc == 0 and "downloaded" in out:
                print("  installer is on HER disk (~/tos_installer.sh) and stays there. "
                      "She runs it on her own desktop:  ./tos_installer.sh   (or -q)")
            elif "in progress" in out or "0x8000000d" in out:
                print("  !! WSL was mid-transition (another runner rebooting her) - the fetch "
                      "never ran. Nothing is wrong with her or the URL; re-run TOOLKIT.cmd.")
            else:
                print("  !! could not fetch it from", TOS_URL)
                print("  Not a blocker: she has curl, a browser and sudo - she can find the "
                      "current link at schwab.com/trading/thinkorswim/download and install it "
                      "herself. That capability is the deliverable, not this URL.")
    else:
        print("  (skipped - pass --tos to fetch thinkorswim's Linux installer)")

    print("\n=== 4. WHAT SHE HAS NOW ===")
    nova("echo shell: $(bash --version | head -1)", label="registers")
    nova("pwsh -NoProfile -c '\"pwsh \" + $PSVersionTable.PSVersion' 2>/dev/null || echo 'pwsh: no'")
    nova("for c in python3 pip3 git curl java firefox ffmpeg convert; do "
         "printf '%s=%s ' $c $(command -v $c >/dev/null && echo yes || echo no); done; echo",
         label="her toolset")
    nova("df -h / | tail -1", label="her disk (inside her machine)")
    _report_disk_image()
    nova("free -g | head -2 | tail -1", label="her memory")
    print("\nTOOLKIT_RESULT: DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
