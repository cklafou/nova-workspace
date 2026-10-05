# Last updated: 2026-10-06 03:19:20
# @nova: Runs as root inside my computer to set my desktop viewer's VNC password and prove the server accepts it; sent by set_vnc_password.py.
"""Set the VNC password of Nova's desktop and prove it with a real login.

Sent by ``set_vnc_password.py`` and run as root inside her WSL computer. The new password arrives
on stdin (never on a command line); everything printed is JSON without the password. Steps:

1. Find the password file the running TigerVNC server was started with (default
   /home/nova/.vnc/passwd), and note whether it already holds this password.
2. Replace it (TigerVNC's obfuscated 8-byte form, owner nova, 0600) and the plain record that
   first boot keeps in /root/nova_vnc_password.txt.
3. Log in to 127.0.0.1:5901 with the RFB VncAuth handshake, exactly as noVNC does. TigerVNC
   re-reads the file at every login, so this normally passes at once. If it is refused (five
   failed logins from one address make TigerVNC block it for a while, and noVNC's websockify is
   that address) or rejected, restart nova-vnc and nova-novnc, then log in again.
"""
import json
import os
import pwd
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time

PORT = 5901
DEFAULT_FILE = "/home/nova/.vnc/passwd"
RECORD = "/root/nova_vnc_password.txt"

# ---- DES, encryption only: all VNC authentication needs -----------------------------------
_PC1 = [57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35,27,19,11,3,60,52,44,36,
        63,55,47,39,31,23,15,7,62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,28,20,12,4]
_PC2 = [14,17,11,24,1,5,3,28,15,6,21,10,23,19,12,4,26,8,16,7,27,20,13,2,
        41,52,31,37,47,55,30,40,51,45,33,48,44,49,39,56,34,53,46,42,50,36,29,32]
_SHIFTS = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]
_IP = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,
       57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7]
_FP = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,
       36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25]
_E = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,12,13,14,15,16,17,
      16,17,18,19,20,21,20,21,22,23,24,25,24,25,26,27,28,29,28,29,30,31,32,1]
_P = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25]
_S = [
 [14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7,0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,
  4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0,15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13],
 [15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10,3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5,
  0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15,13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9],
 [10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8,13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,
  13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7,1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12],
 [7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15,13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,
  10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4,3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14],
 [2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9,14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,
  4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14,11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3],
 [12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11,10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,
  9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6,4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13],
 [4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1,13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,
  1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2,6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12],
 [13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7,1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,
  7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8,2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11],
]


def _permute(value, table, width):
    out = 0
    for pos in table:
        out = (out << 1) | ((value >> (width - pos)) & 1)
    return out


def des_encrypt(key8, block8):
    k = _permute(int.from_bytes(key8, "big"), _PC1, 64)
    c, d = k >> 28, k & 0xFFFFFFF
    subkeys = []
    for shift in _SHIFTS:
        c = ((c << shift) | (c >> (28 - shift))) & 0xFFFFFFF
        d = ((d << shift) | (d >> (28 - shift))) & 0xFFFFFFF
        subkeys.append(_permute((c << 28) | d, _PC2, 56))
    b = _permute(int.from_bytes(block8, "big"), _IP, 64)
    left, right = b >> 32, b & 0xFFFFFFFF
    for sk in subkeys:
        x = _permute(right, _E, 32) ^ sk
        f = 0
        for i in range(8):
            six = (x >> (42 - 6 * i)) & 0x3F
            row = ((six & 0x20) >> 4) | (six & 1)
            f = (f << 4) | _S[i][row * 16 + ((six >> 1) & 0xF)]
        left, right = right, left ^ _permute(f, _P, 32)
    return _permute((right << 32) | left, _FP, 64).to_bytes(8, "big")


def vnc_response(password, challenge):
    """DES-encrypt the 16-byte challenge with the password's first 8 bytes, each byte
    bit-reversed (VNC's long-standing quirk)."""
    key = (password.encode("latin-1") + b"\0" * 8)[:8]
    key = bytes(int(format(b, "08b")[::-1], 2) for b in key)
    return des_encrypt(key, challenge[:8]) + des_encrypt(key, challenge[8:16])


# ---- one real login, as noVNC does it -------------------------------------------------------
def _recv(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("the server closed the connection")
        data += chunk
    return data


def _reason(sock):
    try:
        return _recv(sock, struct.unpack(">I", _recv(sock, 4))[0]).decode("utf-8", "replace")
    except Exception:
        return ""


def try_login(password, port=PORT):
    """('ok' | 'rejected' | 'refused' | 'no-vncauth' | 'no-server' | 'error', detail)."""
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
    except OSError as error:
        return "no-server", str(error)
    try:
        with sock:
            version = _recv(sock, 12)
            if version.startswith(b"RFB 003.003"):
                # TigerVNC answers a blocked address with a 3.3 greeting and a failure.
                sock.sendall(b"RFB 003.003\n")
                if struct.unpack(">I", _recv(sock, 4))[0] == 0:
                    return "refused", _reason(sock) or "connection refused"
                return "error", "unexpected RFB 3.3 security type"
            sock.sendall(b"RFB 003.008\n")
            count = _recv(sock, 1)[0]
            if count == 0:
                return "refused", _reason(sock) or "connection refused"
            types = list(_recv(sock, count))
            if 2 not in types:
                return "no-vncauth", f"the server offers security types {types}"
            sock.sendall(b"\x02")
            sock.sendall(vnc_response(password, _recv(sock, 16)))
            if struct.unpack(">I", _recv(sock, 4))[0] == 0:
                return "ok", version.decode("ascii", "replace").strip()
            return "rejected", _reason(sock) or "authentication failed"
    except Exception as error:
        return "error", f"{type(error).__name__}: {error}"


# ---- the change ------------------------------------------------------------------------------
def say(step, **fields):
    print(json.dumps(dict(step=step, **fields)), flush=True)


def server_password_files():
    try:
        lines = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True,
                               timeout=10).stdout.splitlines()
    except Exception:
        lines = []
    servers = [line.strip() for line in lines if re.search(r"(^|/)X(tiger)?vnc\b", line.split(" ")[0])]
    files = []
    for line in servers:
        files += re.findall(r"-(?:PasswordFile|rfbauth|passwd)(?:=|\s+)(\S+)", line)
    return servers, files


def obfuscate(password):
    return subprocess.run(["vncpasswd", "-f"], input=(password + "\n").encode("ascii"),
                          capture_output=True, check=True, timeout=10).stdout[:8]


def write_passwd(path, data):
    owner = pwd.getpwnam("nova")
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".passwd.")
    try:
        os.write(fd, data)
        os.fchmod(fd, 0o600)
        os.fchown(fd, owner.pw_uid, owner.pw_gid)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def restart_desktop():
    done = []
    for unit in ("nova-vnc", "nova-novnc"):
        r = subprocess.run(["systemctl", "restart", unit], capture_output=True, text=True, timeout=90)
        done.append({"unit": unit, "rc": r.returncode, "err": r.stderr.strip()[-200:]})
        if unit == "nova-vnc":
            for _ in range(30):
                time.sleep(1)
                try:
                    socket.create_connection(("127.0.0.1", PORT), timeout=2).close()
                    break
                except OSError:
                    continue
    time.sleep(2)
    return done


def main():
    password = sys.stdin.readline().rstrip("\r\n")
    if not password or any(not 32 <= ord(ch) < 127 for ch in password):
        say("result", ok=False, status="bad-password", detail="empty, or not plain keyboard characters")
        return 2
    want = obfuscate(password)
    servers, files = server_password_files()
    say("server", running=bool(servers), command=servers[:2], password_files=files)
    targets = list(dict.fromkeys([DEFAULT_FILE] + files))
    before = {}
    for path in targets:
        try:
            with open(path, "rb") as handle:
                before[path] = "already this password" if handle.read(8) == want else "different"
        except FileNotFoundError:
            before[path] = "missing"
    try:
        with open(RECORD, encoding="utf-8") as handle:
            record = "already this password" if handle.read().strip() == password else "different"
    except FileNotFoundError:
        record = "missing"
    say("before", files=before, record=record)
    for path in targets:
        write_passwd(path, want)
    fd = os.open(RECORD, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (password + "\n").encode("ascii"))
    finally:
        os.close(fd)
    os.chmod(RECORD, 0o600)
    say("written", files=targets, record=RECORD)
    status, detail = try_login(password)
    say("login_test", status=status, detail=detail)
    if status != "ok":
        say("restart", units=restart_desktop())
        status, detail = try_login(password)
        say("login_test", status=status, detail=detail, after_restart=True)
    say("result", ok=status == "ok", status=status, detail=detail, longer_than_8=len(password) > 8)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
