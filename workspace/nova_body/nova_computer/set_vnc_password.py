# Last updated: 2026-10-05 21:27:11
# @nova: Sets the password of my desktop viewer (the Computer widget, noVNC) from desktop_secret.json and proves the server accepts it; logs every step without the password.
"""Set Nova's desktop viewer password. Double-click SET_VNC_PASSWORD.cmd, or from nova_body:
py -3 -m nova_computer.set_vnc_password

The password comes from nova_computer/desktop_secret.json, which Git and the Drive mirror never
upload (both skip *_secret.json). If that file is missing, the password is typed here twice
(hidden) and saved there. provision/vnc_password_guest.py then runs as root inside her computer,
with the password on stdin: it writes TigerVNC's password file and the record first boot keeps in
/root/nova_vnc_password.txt, then logs in to the server the way noVNC does to prove the password
works, restarting her desktop only if the server still refuses. Every step goes to
provision/set_vnc_password.log, without the password.

Classic VNC passwords use only their first 8 characters.
"""
import base64
import getpass
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from nova_computer.computer import NovaComputer

HERE = Path(__file__).resolve().parent
SECRET = HERE / "desktop_secret.json"
GUEST = HERE / "provision" / "vnc_password_guest.py"
LOG = HERE / "provision" / "set_vnc_password.log"
NOISE = ("Processing /etc/fstab", "CreateProcessCommon")


def log(text: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def save_secret(password: str) -> None:
    data = {
        "what": "Password for Nova's desktop viewer: the Computer widget in Nova Chat "
                "(noVNC, http://127.0.0.1:6080/vnc.html).",
        "password": password,
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "apply": "After changing it here, double-click nova_body/nova_computer/SET_VNC_PASSWORD.cmd.",
        "private": "Never uploaded: git and the Drive mirror skip *_secret.json. Never copy the "
                   "password into a journal, note, task or any other file; those are uploaded.",
    }
    tmp = SECRET.with_name(SECRET.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, SECRET)


def load_password():
    if SECRET.exists():
        data = json.loads(SECRET.read_text(encoding="utf-8"))
        if data.get("password"):
            return str(data["password"]), "desktop_secret.json"
    print("No saved password yet. Type the new one (typing is hidden).")
    first = getpass.getpass("  New password: ")
    if not first or first != getpass.getpass("  Type it again: "):
        return None, "the two entries were empty or differed"
    save_secret(first)
    return first, "typed, now saved in desktop_secret.json"


def port_owner(port: int = 6080) -> str:
    """Which Windows program listens on the viewer's port (wslrelay.exe = her computer)."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception as error:
        return f"unknown ({type(error).__name__})"
    pids = sorted({line.split()[-1] for line in out.splitlines()
                   if "LISTENING" in line and re.search(rf"[:.]{port}\s", line)})
    names = []
    for pid in pids:
        try:
            row = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
            names.append(f"{row.split(',')[0].strip(chr(34))} (pid {pid})")
        except Exception:
            names.append(f"pid {pid}")
    return ", ".join(names) or "nothing is listening"


def main() -> int:
    log("--- set the desktop viewer password ---")
    pc = NovaComputer()
    log(f"backend: {pc.backend.name} | {pc.where()}")
    if pc.backend.name != "wsl":
        log("STOPPED: this tool is for her WSL computer. Nothing changed.")
        return 1
    password, source = load_password()
    if not password:
        log(f"STOPPED: no password ({source}). Nothing changed.")
        return 1
    if any(not 32 <= ord(ch) < 127 for ch in password):
        log("STOPPED: use plain keyboard characters only. Nothing changed.")
        return 1
    log(f"password from {source}: {len(password)} characters"
        + (" (VNC checks only the first 8)" if len(password) > 8 else ""))
    log(f"port 6080 (the Computer widget) is served by: {port_owner()}")
    script = base64.b64encode(GUEST.read_bytes()).decode("ascii")
    # No double quotes anywhere, so the line passes through wsl.exe untouched; the password
    # travels on stdin, never on a command line.
    command = (f"printf %s {script} | base64 -d > /root/.nova_vnc_password.py && "
               "python3 /root/.nova_vnc_password.py; rc=$?; rm -f /root/.nova_vnc_password.py; exit $rc")
    be = pc.backend
    rc, out, err = be._w(["-d", be.distro, "-u", "root", "--exec", "bash", "-c", command],
                         timeout=240, stdin_bytes=(password + "\n").encode("ascii"))
    result = None
    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            step = json.loads(line)
        except ValueError:
            continue
        log("her computer: " + json.dumps(step))
        if step.get("step") == "result":
            result = step
    stderr = "\n".join(l for l in (err or "").splitlines() if not any(n in l for n in NOISE)).strip()
    if stderr:
        log("her computer (stderr): " + stderr[-600:])
    if result and result.get("ok"):
        log("DONE: her desktop accepts the password. Open the Computer widget and enter it.")
        return 0
    log(f"NOT DONE (exit {rc}): " + (result.get("detail", "") if result else "no answer from her computer"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
