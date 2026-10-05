# @nova: Body-owned computer backends with an explicit Nova desktop default and deliberate host interoperability.
# Last updated: 2026-10-05 18:23:37
# @claude 2026-09-03: PLUCK FIX. computer.py used to BE the WSL implementation -- module-level
# wsl.exe path, Windows-only creationflags passed unconditionally. Dropped body-only onto a
# Linux host it did not degrade, it EXPLODED: subprocess raises ValueError for creationflags
# on POSIX, so the faculty could not even report its own absence. Design_Principles #3 says a
# sense reads traces through an interface the body owns and reports "nothing there" when the
# world is empty. Same rule for hands. The contract moved here; the machines became backends.
"""
nova_computer.backends -- how the body finds a computer to act in.

    from nova_computer.backends import probe
    be = probe()                 # first backend that is actually available, here, now
    rc, out = be.shell("uname -a")

Order is deliberate: LOCAL first. If the body wakes up already standing on a POSIX machine,
that machine IS her computer -- asking it to build a VM inside itself would be absurd. Only a
Windows host needs a Linux guest conjured for her, and that is what WSLBackend is for.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

GUEST_USER = "nova"
DISTRO = "Ubuntu-24.04"
DESKTOP_URL = "http://localhost:6080/vnc.html"

_IS_WINDOWS = os.name == "nt"
# CREATE_NO_WINDOW exists only on Windows and subprocess REJECTS it on POSIX. Her body does
# not flicker (2026-09-02: a zombie scheduled task flashed cmd windows for six weeks and stole
# game focus), but "no window" must never become "no faculty" on a machine that has no windows.
_NO_WINDOW = {"creationflags": 0x08000000} if _IS_WINDOWS else {}


def nova_desktop_command(command: str, display: str = ":1", xauthority: str = "/home/nova/.Xauthority") -> str:
    """Select Nova's X11 desktop without changing the user's account or host permissions."""
    import shlex
    return (f"export DISPLAY={shlex.quote(display)} XAUTHORITY={shlex.quote(xauthority)}; "
            "unset WAYLAND_DISPLAY; export GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb MOZ_ENABLE_WAYLAND=0; "
            'case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac; '
            + command)


class ComputerUnavailable(RuntimeError):
    """Her computer cannot be reached and could not be stood up. Says exactly why."""


def _decode(b: bytes) -> str:
    """wsl.exe management output is UTF-16LE; guest passthrough is UTF-8. Cope with both."""
    if not b:
        return ""
    if b[1:2] == b"\x00" or b.count(b"\x00") > len(b) // 3:
        try:
            return b.decode("utf-16-le", errors="replace").replace("\x00", "").strip()
        except Exception:
            pass
    return b.decode("utf-8", errors="replace").replace("\x00", "").strip()


def _run(argv: list[str], timeout: int, stdin_bytes: bytes | None = None):
    from nova_runtime.operations import current_operation, run_process
    if current_operation.get():
        r=run_process(argv, timeout=timeout, input_data=stdin_bytes, binary=True, **_NO_WINDOW)
        out,err=r['stdout'],r['stderr']
        out=out if isinstance(out,bytes) else out.encode()
        err=err if isinstance(err,bytes) else err.encode()
        rc=124 if r['status']=='timed_out' else 130 if r['status']=='cancelled' else r['exit_code']
        return rc, _decode(out), _decode(err)
    p = subprocess.run(argv, capture_output=True, timeout=timeout,
                       input=stdin_bytes, **_NO_WINDOW)
    return p.returncode, _decode(p.stdout), _decode(p.stderr)


class Backend:
    """The contract. Anything that satisfies this is a computer she can live in."""
    name = "none"
    provisions = False          # can it build itself from nothing?
    desktop_url: str | None = None

    def available(self) -> bool: raise NotImplementedError
    def can_provision(self) -> bool:
        """True when this backend could BUILD her a machine even though none is ready yet.
        Astra, 2026-09-06: probe() only accepted backends that were already available, so on a
        Windows host with working WSL but no distro, probe() returned NoBackend and ensure()
        refused before it could reach its own auto-register branch -- while reporting 'no WSL2
        to build one in', which was false. Readiness and buildability are different questions."""
        return False
    def describe(self) -> str: raise NotImplementedError
    def shell(self, cmd: str, timeout: int = 120): raise NotImplementedError
    def pwsh(self, cmd: str, timeout: int = 120): raise NotImplementedError
    def status(self) -> dict: return {"backend": self.name, "available": self.available()}
    def ensure(self) -> dict:
        if not self.available():
            raise ComputerUnavailable(self.describe())
        return self.status()


class LocalPosixBackend(Backend):
    """She is already standing on a Linux/Unix machine. No VM. This IS the computer.

    This is the branch that makes the pluck test true in the way Cole means it: take every
    tool away, drop the body on a Linux server with the hardware it needs, and she can still
    look around and act -- because acting is just running a command where she already is.
    """
    name = "local-posix"
    provisions = False

    def available(self) -> bool:
        return (not _IS_WINDOWS) and bool(shutil.which("bash"))

    def describe(self) -> str:
        if _IS_WINDOWS:
            return "local-posix: host is Windows, so there is no POSIX shell to stand in"
        if not shutil.which("bash"):
            return "local-posix: no bash on PATH"
        return f"local-posix: running directly on {os.uname().sysname} as {self._whoami()}"

    def _whoami(self) -> str:
        try:
            import getpass
            return getpass.getuser()
        except Exception:
            return "unknown"

    def shell(self, cmd: str, timeout: int = 120):
        rc, out, err = _run([shutil.which("bash") or "/bin/bash", "-lc", cmd], timeout)
        return rc, (out + (("\n" + err) if err else "")).strip()

    def pwsh(self, cmd: str, timeout: int = 120):
        exe = shutil.which("pwsh")
        if not exe:
            return 127, ("pwsh is not installed on this machine - bash still works. "
                         "Install PowerShell 7 if you want both registers here.")
        rc, out, err = _run([exe, "-NoProfile", "-Command", cmd], timeout)
        return rc, (out + (("\n" + err) if err else "")).strip()

    def status(self) -> dict:
        return {"backend": self.name, "available": self.available(), "provisioned": True,
                "running": True, "desktop": None, "note": "the host itself is her computer"}


class WSLBackend(Backend):
    """Windows host: Nova's Linux guest with intentional Windows drive/interop access.

    Guest Bash defaults to the same authenticated X11 desktop as Hands. Explicit command
    environment overrides remain available; native Windows applications use host interop.
    """
    name = "wsl"
    provisions = True
    desktop_url = DESKTOP_URL
    distro = DISTRO

    def __init__(self, distro: str = DISTRO):
        self.distro = distro
        self._wsl = shutil.which("wsl") or (r"C:\Windows\System32\wsl.exe" if _IS_WINDOWS else "")

    # -- the honest ladder ---------------------------------------------------------------
    def _w(self, args: list[str], timeout: int = 60, stdin_bytes: bytes | None = None):
        if not self._wsl:
            return 1, "", "wsl.exe not found on this host"
        return _run([self._wsl] + args, timeout, stdin_bytes)

    def wsl_present(self) -> bool:
        if not _IS_WINDOWS or not self._wsl:
            return False
        try:
            rc, _, _ = self._w(["--status"], timeout=20)
            return rc == 0
        except Exception:
            return False

    def registered(self) -> bool:
        try:
            rc, out, _ = self._w(["-l", "-q"], timeout=20)
            return rc == 0 and self.distro in [l.strip() for l in out.splitlines()]
        except Exception:
            return False

    def running(self) -> bool:
        try:
            rc, out, _ = self._w(["-l", "-q", "--running"], timeout=20)
            return rc == 0 and self.distro in [l.strip() for l in out.splitlines()]
        except Exception:
            return False

    def provisioned(self) -> bool:
        rc, out, _ = self.exec_root("test -f /etc/systemd/system/nova-vnc.service && echo yes")
        return rc == 0 and "yes" in out

    def available(self) -> bool:
        return self.wsl_present() and self.registered()

    def can_provision(self) -> bool:
        return self.wsl_present()

    OWNER_MARK = "/etc/nova-computer"

    def owns_distro(self) -> tuple[bool, str]:
        """Is this registered distro HERS, or someone else's that happens to share the name?
        `Ubuntu-24.04` is the default name millions of machines use. Provisioning into a
        stranger's distro would add a user, rewrite /etc/wsl.conf and install a desktop on top
        of their work. So: her marker means yes; no marker plus other people's home dirs means
        no; an empty unclaimed distro is fair game."""
        rc, out, _ = self.exec_root(f"cat {self.OWNER_MARK} 2>/dev/null")
        if rc == 0 and "nova-computer" in out:
            return True, "her marker is present"
        rc, homes, _ = self.exec_root(
            "ls /home 2>/dev/null | grep -v '^nova$' | paste -sd,")
        if rc == 0 and homes.strip():
            return False, f"unclaimed distro with other users present: {homes.strip()}"
        return True, "unclaimed and empty - safe to make hers"

    def describe(self) -> str:
        if not _IS_WINDOWS:
            return "wsl: host is not Windows"
        if not self.wsl_present():
            return ("wsl: WSL2 is not available on this host - her computer needs it "
                    "(one-time, admin: wsl --install, then reboot)")
        if not self.registered():
            return f"wsl: WSL2 is here but {self.distro} is not registered yet (ensure() can fix)"
        return f"wsl: {self.distro} registered, running={self.running()}"

    # -- both registers ------------------------------------------------------------------
    def shell(self, cmd: str, timeout: int = 120, user: str = GUEST_USER):
        from nova_runtime.operations import current_operation
        import shlex, uuid
        # Applied inside the login shell, after profile scripts can reset WSLg defaults.
        # Commands may explicitly override DISPLAY for WSLg; ordinary GUI work belongs on :1.
        cmd = nova_desktop_command(cmd)
        op=current_operation.get()
        marker='/tmp/nova_operation_'+uuid.uuid4().hex+'.pid'
        if op:
            original=cmd
            cmd=(f'setsid bash -lc {shlex.quote(original)} & job=$!; '
                 f'printf "%s" "$job" > {marker}; wait "$job"; rc=$?; rm -f {marker}; exit "$rc"')
            def stop_guest():
                kill=(f'if test -f {marker}; then p=$(cat {marker}); '
                      'kill -KILL -- -"$p" 2>/dev/null || true; '
                      'for n in $(seq 1 20); do '
                      'if ! kill -0 -- -"$p" 2>/dev/null; then break; fi; sleep 0.05; done; '
                      'if kill -0 -- -"$p" 2>/dev/null; then exit 1; fi; '
                      f'rm -f {marker}; fi')
                p=subprocess.run(['wsl','-d',self.distro,'-u',user,'--exec','bash','-lc',kill],
                                 capture_output=True,timeout=5,**_NO_WINDOW)
                if p.returncode: raise RuntimeError('Could not confirm guest process cleanup')
            op.cleanup[marker]=stop_guest
        rc, out, err = self._w(["-d", self.distro, "-u", user, "--exec", "bash", "-lc", cmd],
                               timeout=timeout)
        if op and not op.cancel.is_set():
            op.cleanup.pop(marker,None)
        return rc, (out + (("\n" + err) if err else "")).strip()

    def pwsh(self, cmd: str, timeout: int = 120):
        rc, out, err = self._w(["-d", self.distro, "-u", GUEST_USER, "--exec", "pwsh",
                                "-NoProfile", "-Command", cmd], timeout=timeout)
        if rc != 0 and "pwsh" in (err or "") and "not found" in (err or ""):
            return rc, "pwsh is not installed in the guest yet - re-run provision()"
        return rc, (out + (("\n" + err) if err else "")).strip()

    def exec_root(self, cmd: str, timeout: int = 60):
        try:
            return self._w(["-d", self.distro, "-u", "root", "--exec", "bash", "-lc", cmd],
                           timeout=timeout)
        except Exception as e:
            return 1, "", str(e)

    # -- standing herself up -------------------------------------------------------------
    def register(self, timeout: int = 1800) -> str:
        rc, out, err = self._w(["--install", "-d", self.distro, "--no-launch"], timeout=timeout)
        if rc != 0 and not self.registered():
            raise ComputerUnavailable(f"could not register {self.distro}: {err or out}")
        return out or "registered"

    def provision(self, script_path: Path, timeout: int = 1800) -> str:
        """Stream the packaged setup script in as root via stdin -- works even with Windows
        drive mounts disabled, because it never travels through /mnt/c."""
        if not script_path.exists():
            raise ComputerUnavailable(f"provision script missing: {script_path}")
        script = script_path.read_bytes().replace(b"\r\n", b"\n")
        rc, out, err = self._w(["-d", self.distro, "-u", "root", "--exec", "bash", "-s"],
                               timeout=timeout, stdin_bytes=script)
        blob = (out + "\n" + err).strip()
        if rc != 0:
            raise ComputerUnavailable(f"provision failed (rc={rc}):\n{blob[-2000:]}")
        self._w(["--terminate", self.distro], timeout=30)   # apply /etc/wsl.conf on next boot
        return blob

    def wait_settled(self, timeout: int = 90) -> bool:
        """WSL refuses EVERYTHING with 0x8000000d ("An install, uninstall, or conversion is
        in progress for this distribution") while a distro is mid-start or mid-stop. On
        2026-09-05 REACH.cmd and TOOLKIT.cmd were double-clicked back to back; the second
        landed inside the first's reboot and its thinkorswim step died with that error --
        which the log then blamed on the download URL. Wait the lock out instead."""
        import time
        end = time.time() + timeout
        last = ""
        while time.time() < end:
            rc, out, err = self._w(["-d", self.distro, "--exec", "true"], timeout=25)
            if rc == 0:
                return True
            last = (out + " " + err)
            if "0x8000000d" not in last and "in progress" not in last:
                break                       # a different failure; not ours to wait on
            time.sleep(2)
        return False

    def start(self) -> None:
        if not self._wsl:
            return
        subprocess.Popen([self._wsl, "-d", self.distro, "--exec", "sleep", "infinity"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_NO_WINDOW)
        self.wait_settled()

    def stop(self) -> None:
        self._w(["--terminate", self.distro], timeout=30)

    def snapshot(self, dest: str, timeout: int = 3600) -> str:
        rc, out, err = self._w(["--export", self.distro, dest], timeout=timeout)
        if rc != 0:
            raise ComputerUnavailable(f"snapshot failed: {err or out}")
        return dest

    def status(self) -> dict:
        s = {"backend": self.name, "available": False, "wsl": self.wsl_present(),
             "registered": False, "running": False, "provisioned": False, "services": "",
             "desktop": self.desktop_url}
        if s["wsl"]:
            s["registered"] = self.registered()
        if s["registered"]:
            s["available"] = True
            s["running"] = self.running()
            s["provisioned"] = self.provisioned()
        if s["provisioned"]:
            _, out, _ = self.exec_root(
                "systemctl is-active nova-vnc nova-novnc 2>/dev/null | paste -sd,")
            s["services"] = out
        return s


class NoBackend(Backend):
    """No computer here. Coherent, like a sense reporting an empty room."""
    name = "none"

    def available(self) -> bool: return False
    def describe(self) -> str:
        return ("no computer available on this host: not a POSIX machine to stand on, and "
                "no WSL2 to build one in. Give the body a Linux host, or a Windows host with "
                "WSL2, and the same faculty works unchanged.")
    def shell(self, cmd: str, timeout: int = 120): return 127, self.describe()
    def pwsh(self, cmd: str, timeout: int = 120): return 127, self.describe()


def candidates() -> list[Backend]:
    return [LocalPosixBackend(), WSLBackend()]


def probe(prefer: str | None = None) -> Backend:
    """First backend actually available here, now. Never raises; NoBackend is a real answer."""
    opts = candidates()
    if prefer:
        opts = [b for b in opts if b.name == prefer] + [b for b in opts if b.name != prefer]
    for b in opts:                       # 1. a machine that is ready right now
        try:
            if b.available():
                return b
        except Exception:
            continue
    for b in opts:                       # 2. failing that, one that can BUILD her a machine
        try:
            if b.can_provision():
                return b
        except Exception:
            continue
    return NoBackend()
