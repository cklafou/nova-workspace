# @nova: Changes the password of my desktop viewer (the Computer widget, noVNC). Cole types it in this window; it is never written into the project.
"""Change the VNC password for Nova's desktop. Double-click SET_VNC_PASSWORD.cmd, or from nova_body:
py -3 -m nova_computer.set_vnc_password

Her desktop is TigerVNC (:1) inside her WSL computer, shown through noVNC on port 6080. The new
password is typed twice here (hidden) and reaches the guest on stdin, never on a command line. It
replaces /home/nova/.vnc/passwd (TigerVNC's obfuscated form) and the plain record first boot keeps in
/root/nova_vnc_password.txt, and is then read back. TigerVNC reads the file at every login, so her
desktop keeps running.

Classic VNC passwords use only their first 8 characters: a longer one still works when typed in
full, but the characters after the eighth are not checked.
"""
import getpass
import sys

from nova_computer.computer import NovaComputer

# No double quotes, so the line passes through wsl.exe's command-line parsing untouched. IFS is
# emptied and globbing is off (set -f), so the unquoted $p stays one word whatever it contains.
GUEST = (
    "set -ef; IFS= read -r p; IFS=; test ${#p} -gt 0; umask 077; "
    "install -d -m 700 -o nova -g nova /home/nova/.vnc; "
    "t=$(mktemp /home/nova/.vnc/passwd.XXXXXX); printf '%s\\n' $p | vncpasswd -f > $t; "
    "chown nova:nova $t; chmod 600 $t; mv -f $t /home/nova/.vnc/passwd; "
    "if test -f /home/nova/.config/tigervnc/passwd; then cp -p /home/nova/.vnc/passwd /home/nova/.config/tigervnc/passwd; fi; "
    "printf '%s\\n' $p > /root/nova_vnc_password.txt; chmod 600 /root/nova_vnc_password.txt; "
    "printf '%s\\n' $p | vncpasswd -f | cmp -s - /home/nova/.vnc/passwd && echo VNC_PASSWORD_SET"
)
NOISE = ("Processing /etc/fstab", "CreateProcessCommon")


def main() -> int:
    pc = NovaComputer()
    if pc.backend.name != "wsl":
        print(f"Nothing changed: this tool is for her WSL computer ({pc.where()}).")
        return 1
    print("New password for Nova's desktop (the Computer widget). Typing is hidden.")
    first = getpass.getpass("  New password: ")
    if not first:
        print("Nothing changed: the password is empty.")
        return 1
    if any(not 32 <= ord(ch) < 127 for ch in first):
        print("Nothing changed: use plain keyboard characters (letters, digits, symbols, spaces).")
        return 1
    if getpass.getpass("  Type it again: ") != first:
        print("Nothing changed: the two entries differ.")
        return 1
    be = pc.backend
    rc, out, err = be._w(["-d", be.distro, "-u", "root", "--exec", "bash", "-c", GUEST],
                         timeout=90, stdin_bytes=(first + "\n").encode("ascii"))
    if rc == 0 and "VNC_PASSWORD_SET" in out:
        print("Done. The Computer widget now takes the new password; her desktop kept running.")
        if len(first) > 8:
            print("Note: VNC checks only the first 8 characters. Typing the whole password still works.")
        return 0
    detail = "\n".join(l for l in (err or out or "").splitlines() if not any(n in l for n in NOISE)).strip()
    print(f"Could not confirm the change (exit {rc}). {detail[-400:]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
