# @nova: Body-owned computer facade for guest commands, intentional host reach and observable desktop actions.
# Last updated: 2026-10-06 03:19:20
# @claude 2026-09-03: PLUCK PASS. This file used to BE the WSL implementation. Now it is the
# faculty, and backends.py holds the machines. Design_Principles #2: the body must never
# depend on a specific tool -- and by the same logic it must not depend on a specific HOST.
# Take every tool away, drop her on a Linux server with the hardware, and she can still look
# around and act, because probe() finds the machine she is already standing on.
"""
nova_computer.computer -- the faculty of having a computer to act in.

    from nova_computer.computer import NovaComputer, ComputerUnavailable
    pc = NovaComputer()
    pc.where()                 # which kind of computer she has here, in one honest sentence
    pc.ensure()                # make it exist and answer, or say exactly why not
    rc, out = pc.bash("uname -a && whoami")
    rc, out = pc.pwsh("Get-Date")           # BOTH registers: bash and pwsh
    pc.snapshot(r"...\\baseline.tar")   # images HER machine only - NOT his files
    pc.status()                # honest ladder, whatever the backend

Cole watches and interrupts at http://localhost:6080/vnc.html when the backend has a desktop.
SCAFFOLDED (phase 2): in-guest eyes/hands agent (screenshot + input injection) for
nova_senses.eyes to look through. Exec, provisioning, snapshots, probing are LIVE.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from nova_computer.backends import (           # noqa: F401  (re-exported on purpose)
    Backend, ComputerUnavailable, DESKTOP_URL, DISTRO, GUEST_USER,
    LocalPosixBackend, NoBackend, WSLBackend, probe, _NO_WINDOW, _decode,
)

_PROVISION = Path(__file__).resolve().parent / "provision" / "setup_guest.sh"


class NovaComputer:
    """Her computer, whatever shape it takes on this host.

    The public surface is deliberately identical on every backend -- bash(), pwsh(),
    status(), ensure() -- so nothing that uses her computer has to know or care whether it
    is a WSL guest, a bare Linux host, or (honestly) nothing at all.
    """

    def __init__(self, prefer: str | None = None):
        self.backend: Backend = probe(prefer)

    # ---- which world am I in -----------------------------------------------------------
    @property
    def desktop_url(self) -> str | None:
        return self.backend.desktop_url

    @property
    def distro(self) -> str:
        return getattr(self.backend, "distro", "-")

    def where(self) -> str:
        """One sentence, always true, never a guess."""
        return self.backend.describe()

    def rescan(self, prefer: str | None = None) -> Backend:
        """Re-probe -- the world can change under her (WSL installed, distro registered)."""
        self.backend = probe(prefer)
        return self.backend

    # ---- speaking both registers -------------------------------------------------------
    def bash(self, cmd: str, timeout: int = 120, user: str = GUEST_USER):
        """Run Bash in her computer; WSL defaults to her authenticated :1 X11 desktop.

        Explicit DISPLAY overrides remain possible. Returns (rc, combined output).
        """
        be = self.backend
        if isinstance(be, WSLBackend):
            return be.shell(cmd, timeout=timeout, user=user)
        return be.shell(cmd, timeout=timeout)

    # She reaches for Linux first (Qwen was raised on it) and only translates when forced.
    # Both registers exist here so she never has to translate again.
    sh = bash

    def pwsh(self, cmd: str, timeout: int = 120):
        """Run a PowerShell 7 command in her computer (pwsh runs on Linux too)."""
        return self.backend.pwsh(cmd, timeout=timeout)

    def _exec_root(self, cmd: str, timeout: int = 60):
        """Privileged exec, (rc, out, err). Kept for first_boot/tune_up compatibility."""
        fn = getattr(self.backend, "exec_root", None)
        if fn is not None:
            return fn(cmd, timeout=timeout)
        # A local POSIX host is not hers to own: try passwordless sudo, and if that is not
        # granted say so plainly rather than pretending the command ran.
        if isinstance(self.backend, LocalPosixBackend) and shutil.which("sudo"):
            try:
                p = subprocess.run(["sudo", "-n", "bash", "-lc", cmd], capture_output=True,
                                   timeout=timeout, **_NO_WINDOW)
                return p.returncode, _decode(p.stdout), _decode(p.stderr)
            except Exception as e:
                return 1, "", str(e)
        return 1, "", ("no privileged exec on this backend "
                       f"({self.backend.name}) - run it unprivileged with bash() instead")

    # ---- the honest ladder -------------------------------------------------------------
    def status(self) -> dict:
        s = self.backend.status()
        s.setdefault("desktop", self.backend.desktop_url)
        s["where"] = self.backend.describe()
        return s

    # Kept so older callers keep working on the WSL backend.
    def wsl_present(self) -> bool:
        return bool(getattr(self.backend, "wsl_present", lambda: False)())

    def registered(self) -> bool:
        return bool(getattr(self.backend, "registered", lambda: False)())

    def running(self) -> bool:
        fn = getattr(self.backend, "running", None)
        return bool(fn()) if fn else self.backend.available()

    def provisioned(self) -> bool:
        fn = getattr(self.backend, "provisioned", None)
        return bool(fn()) if fn else self.backend.available()

    # ---- standing herself up -----------------------------------------------------------
    def register(self, timeout: int = 1800) -> str:
        fn = getattr(self.backend, "register", None)
        if fn is None:
            raise ComputerUnavailable(f"{self.backend.name} backend has nothing to register")
        return fn(timeout=timeout)

    def provision(self, timeout: int = 1800) -> str:
        fn = getattr(self.backend, "provision", None)
        if fn is None:
            raise ComputerUnavailable(
                f"{self.backend.name} backend is not provisioned by us - it is the host itself")
        return fn(_PROVISION, timeout=timeout)

    def start(self) -> None:
        fn = getattr(self.backend, "start", None)
        if fn:
            fn()

    def stop(self) -> None:
        fn = getattr(self.backend, "stop", None)
        if fn:
            fn()

    def snapshot(self, dest: str, timeout: int = 3600) -> str:
        fn = getattr(self.backend, "snapshot", None)
        if fn is None:
            raise ComputerUnavailable(
                f"{self.backend.name} backend cannot snapshot itself from the inside")
        return fn(dest, timeout=timeout)

    def ensure(self, auto_register: bool = True) -> dict:
        """The pluck path: make her computer exist and answer, or say exactly why not.

        Every branch below is reachable on SOME host, which is the point. On a Linux box it
        short-circuits at the first check because she is already home.
        """
        be = self.backend
        if isinstance(be, NoBackend):
            raise ComputerUnavailable(be.describe())

        if isinstance(be, WSLBackend):
            if not be.wsl_present():
                raise ComputerUnavailable(be.describe())
            if not be.registered():
                if not auto_register:
                    raise ComputerUnavailable(f"distro {be.distro} not registered on this host")
                be.register()
            if not be.provisioned():
                mine, why = be.owns_distro()
                if not mine:
                    raise ComputerUnavailable(
                        f"{be.distro} is registered but does not look like hers ({why}). "
                        "Provisioning would add a user, rewrite /etc/wsl.conf and install a "
                        "desktop on top of it. Rename hers, or unregister that distro first.")
                be.provision(_PROVISION)
            if not be.running():
                be.start()

        rc, out = self.bash("echo alive && uname -r")
        if rc != 0 or "alive" not in out:
            raise ComputerUnavailable(f"computer did not answer ({be.name}): {out}")
        return self.status()
