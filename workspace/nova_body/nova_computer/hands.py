# @nova: See and control Nova's authenticated desktop; verify application launches with process, window and diagnostic evidence.
# Last updated: 2026-10-05 21:27:11
# @claude 2026-09-04: this is the piece that makes her computer a CONTROLLER instead of a
# room she cannot use. Cole: "a viable virtual environment she can fully control, rather than
# needing to use my peripherals through remote control."
#
# DESIGN DECISION -- no agent, no daemon, no port.
# The obvious build is a little service inside the guest with an HTTP API. I did not do that,
# on purpose. It would be a process that can die, a port that can conflict, a protocol to
# version, and a listening socket on a machine that now has full reach into Cole's disk. Her
# body ALREADY has a reliable channel into her computer (backend.shell). Hands are just
# commands on her own display sent down that same channel: scrot to see, xdotool to act.
# Nothing to start, nothing to crash, nothing to secure. It also stays pluck-clean: on a plain
# Linux host with an X display this works unchanged, with no WSL anywhere in the picture.
"""
nova_computer.hands -- her eyes and hands on her own screen.

    from nova_computer.computer import NovaComputer
    from nova_computer.hands import Hands
    h = Hands(NovaComputer())
    h.available()                 # are scrot/xdotool there, and is her display alive?
    png = h.look()                # bytes of what she is looking at right now
    h.look(save_to="shot.png")    # ...or straight to a file on his disk
    h.click(640, 400); h.type_text("hello"); h.key("ctrl+s")
    h.windows()                   # what is open on her desktop
    h.launch("firefox")           # start something on HER screen

    python -m nova_computer.hands --selftest      # prove she can see and act

Every method returns plain data and never raises for an ordinary failure -- a body part that
throws in the middle of her reaching for something is worse than one that says "I could not".
"""
from __future__ import annotations

import base64
import inspect
import json
import math
from urllib.parse import urlparse

from nova_computer.backends import nova_desktop_command
import shlex
import sys

DISPLAY = ":1"          # her VNC desktop. Cole watches this same display through noVNC.
# Astra, 2026-09-06: available() reported display=dead with scrot=yes xdotool=yes. Setting
# DISPLAY alone is not enough -- X refuses unauthenticated clients, and her cookie lives at
# /home/nova/.Xauthority while her passwd home still says /var/lib/nova, so the shell never
# finds it on its own. The same query with XAUTHORITY set returned "1600 900".
XAUTHORITY = "/home/nova/.Xauthority"
_TOOLS = ("scrot", "xdotool")


class Hands:
    def __init__(self, computer, display: str = DISPLAY):
        self.pc = computer
        self.display = display

    # ---- plumbing ----------------------------------------------------------------------
    def _run(self, cmd: str, timeout: int = 60):
        """Everything she does goes through her body's existing channel, on her display."""
        return self.pc.bash(nova_desktop_command(cmd, self.display, XAUTHORITY), timeout=timeout)

    def _put(self, text: str, path: str) -> tuple[int, str]:
        """Land arbitrary text inside her computer without it passing through a parser.
        Her words may contain quotes, newlines, emoji, $ and backticks; base64 means none of
        that has to survive three layers of shell. (ping_claude.ps1 lost a whole day to
        exactly this class of bug in July.)"""
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return self._run(f"echo {b64} | base64 -d > {shlex.quote(path)}")

    # ---- is she able to act at all -----------------------------------------------------
    def available(self) -> dict:
        """Honest ladder, same spirit as computer.status(): what works, and what is missing."""
        rc, out = self._run(
            "for t in " + " ".join(_TOOLS) + "; do printf '%s=%s ' $t "
            "$(command -v $t >/dev/null && echo yes || echo no); done; "
            "printf 'display=%s ' $(xdotool getdisplaygeometry >/dev/null 2>&1 "
            "&& echo alive || echo dead); "
            "printf 'size=%s' \"$(xdotool getdisplaygeometry 2>/dev/null | tr ' ' 'x')\"")
        info = dict(p.split("=", 1) for p in out.split() if "=" in p)
        missing = [t for t in _TOOLS if info.get(t) != "yes"]
        info["ready"] = (not missing) and info.get("display") == "alive"
        if missing:
            info["fix"] = ("sudo apt-get install -y " + " ".join(missing) +
                           "   (she can run this herself)")
        return info

    def screen_size(self) -> tuple[int, int] | None:
        rc, out = self._run("xdotool getdisplaygeometry")
        try:
            w, h = out.split()[:2]
            return int(w), int(h)
        except Exception:
            return None

    # ---- seeing ------------------------------------------------------------------------
    def look(self, save_to: str | None = None, quality: int = 90):
        """A picture of her screen, right now.

        Returns PNG bytes by default so this works on ANY backend (base64 over the same
        channel, no shared folder assumed). Pass save_to to write it on the host side instead
        -- cheaper for big screens and handy when Cole wants to look at what she saw.
        """
        rc, out = self._run(
            f"f=$(mktemp /tmp/nova_look_XXXX.png); scrot -o -q {int(quality)} \"$f\" "
            "&& base64 -w0 \"$f\" && rm -f \"$f\"", timeout=90)
        if rc != 0 or not out.strip():
            return None
        try:
            raw = base64.b64decode(out.strip())
        except Exception:
            return None
        if save_to:
            with open(save_to, "wb") as fh:
                fh.write(raw)
            return save_to
        return raw

    # ---- acting ------------------------------------------------------------------------
    def move(self, x: int, y: int):
        return self._run(f"xdotool mousemove {int(x)} {int(y)}")

    def click(self, x: int | None = None, y: int | None = None, button: int = 1):
        pre = f"xdotool mousemove {int(x)} {int(y)} " if x is not None and y is not None else ""
        return self._run(f"{pre}click {int(button)}" if pre
                         else f"xdotool click {int(button)}")

    def double_click(self, x: int | None = None, y: int | None = None):
        pre = f"mousemove {int(x)} {int(y)} " if x is not None and y is not None else ""
        return self._run(f"xdotool {pre}click --repeat 2 --delay 120 1")

    def right_click(self, x: int | None = None, y: int | None = None):
        return self.click(x, y, button=3)

    def drag(self, x1: int, y1: int, x2: int, y2: int):
        return self._run(
            f"xdotool mousemove {int(x1)} {int(y1)} mousedown 1 "
            f"mousemove --sync {int(x2)} {int(y2)} mouseup 1")

    def scroll(self, clicks: int = 3, up: bool = True):
        return self._run(f"xdotool click --repeat {abs(int(clicks))} --delay 60 "
                         f"{4 if up else 5}")

    def type_text(self, text: str, delay_ms: int = 12):
        """Type anything she wants to say, verbatim -- via a file, never the command line."""
        # A unique path per call: a fixed /tmp/nova_type.txt let two concurrent calls
        # overwrite each other's words. And the exit code is captured BEFORE cleanup --
        # `xdotool ...; rm -f ...` returns rm's status, so a failed keystroke looked like
        # success (Astra, 2026-09-06).
        rc, path = self._run("mktemp /tmp/nova_type_XXXXXX.txt")
        path = (path or "/tmp/nova_type.txt").strip().splitlines()[-1]
        rc, err = self._put(text, path)
        if rc != 0:
            return rc, f"could not stage the text: {err}"
        rc, out = self._run(
            f"xdotool type --clearmodifiers --delay {int(delay_ms)} --file {shlex.quote(path)}; "
            f"typed=$?; rm -f {shlex.quote(path)}; exit $typed", timeout=180)
        return rc, (out or ("typed" if rc == 0 else "typing failed"))

    def key(self, combo: str):
        """A key or chord: 'Return', 'ctrl+s', 'alt+F4', 'ctrl+shift+t'."""
        return self._run(f"xdotool key --clearmodifiers {shlex.quote(combo)}")

    # ---- her desktop -------------------------------------------------------------------
    def windows(self) -> list[dict]:
        rc, out = self._run(
            "xdotool search --onlyvisible --name '.*' 2>/dev/null | while read id; do "
            "n=$(xdotool getwindowname $id 2>/dev/null); "
            "g=$(xdotool getwindowgeometry --shell $id 2>/dev/null "
            "| tr '\\n' ' '); [ -n \"$n\" ] && echo \"$id|$n|$g\"; done")
        wins = []
        for line in (out or "").splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                geo = dict(p.split("=", 1) for p in parts[2].split() if "=" in p)
                wins.append({"id": parts[0], "name": parts[1],
                             "x": geo.get("X"), "y": geo.get("Y"),
                             "w": geo.get("WIDTH"), "h": geo.get("HEIGHT")})
        return wins

    def focus(self, window_id: str):
        return self._run(f"xdotool windowactivate {shlex.quote(str(window_id))}")

    def launch(self, command: str, wait: float | None = None):
        """Launch one guest executable and verify a visible application window, not an echo.

        Success proves a matching window exists, never that its page loaded or playback began.
        Shell pipelines/redirection belong in computer_exec. Diagnostics stay in guest temp logs.
        """
        try:
            if not isinstance(command, str) or not command.strip():
                raise ValueError("Provide an executable command as text.")
            argv = shlex.split(command)
            if wait is None:
                from nova_cortex.tunables import get
                wait = get("computer_launch_wait_seconds") or 10
            seconds = float(wait)
            if not argv or not math.isfinite(seconds) or not 0 <= seconds <= 20:
                raise ValueError("Provide an executable command and a wait between 0 and 20 seconds.")
            if any(token in {";", "|", "||", "&&", "&", ">", "2>&1"} for token in argv):
                raise ValueError("Launch takes an executable plus arguments, not shell operators. Use computer_exec for shell scripts.")
            if argv[0].lower().endswith((".exe", ".cmd", ".bat")):
                raise ValueError("This action observes Nova's Linux desktop. Use run_command for an intentional Windows application launch.")
            source = inspect.getsource(_launch_probe)
            script = source + "\nimport json\nprint('NOVA_LAUNCH_RESULT:' + json.dumps(_launch_probe(" + repr(argv) + ", " + repr(seconds) + ")))"
            rc, out = self._run("python3 -c " + shlex.quote(script), timeout=int(seconds) + 30)
            if rc != 0:
                return {"status": "timed_out" if rc == 124 else "cancelled" if rc == 130 else "failed",
                        "exit_code": rc, "stderr": out, "stdout": "", "display": self.display,
                        "message": "The application verifier could not finish; no launch success is claimed."}
            records = [line[len("NOVA_LAUNCH_RESULT:"):] for line in out.splitlines()
                       if line.startswith("NOVA_LAUNCH_RESULT:")]
            if not records:
                return {"status": "unknown", "exit_code": rc, "stdout": "", "stderr": out[-12000:],
                        "display": self.display, "message": "No verifier result received; application state is unknown."}
            result = json.loads(records[-1])
            noise = "\n".join(line for line in out.splitlines() if not line.startswith("NOVA_LAUNCH_RESULT:"))
            if noise:
                result["verifier_diagnostics"] = noise[-12000:]
            if not isinstance(result, dict) or result.get("status") not in {"succeeded", "failed", "unknown"}:
                raise ValueError("Invalid application-verifier response")
            result["display"] = self.display
            return result
        except (ValueError, TypeError) as error:
            return {"status": "failed", "exit_code": None, "stdout": "", "stderr": str(error),
                    "display": self.display, "message": "Application launch was not verified."}

    def open_url(self, url: str, browser: str = "firefox", wait: float | None = None):
        """Open an HTTP(S) page in a new guest browser window; navigation remains unverified."""
        parsed = urlparse(str(url))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {"status": "failed", "exit_code": None, "stdout": "", "stderr": "Use a complete http:// or https:// URL.",
                    "display": self.display, "message": "Browser launch was not attempted."}
        if browser not in {"firefox", "chromium", "chromium-browser", "google-chrome"}:
            return {"status": "failed", "exit_code": None, "stdout": "", "stderr": "Choose firefox, chromium, chromium-browser or google-chrome.",
                    "display": self.display, "message": "Browser launch was not attempted."}
        result = self.launch(shlex.join([browser, "--new-window", str(url)]), wait=wait)
        result.update(url=str(url), page_verified=False, playback_verified=False)
        return result


def _launch_probe(argv, wait):
    """Runs inside the guest. Keep self-contained so its exact source can cross the backend."""
    import json
    import os
    from pathlib import Path
    import signal
    import shutil
    import subprocess
    import tempfile
    import time

    def query(arguments):
        try:
            p = subprocess.run(arguments, capture_output=True, text=True, timeout=3)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as error:
            return 127, "", str(error)

    def windows():
        rc, ids, error = query(["xdotool", "search", "--onlyvisible", "--name", "."])
        if rc not in (0, 1):
            return [], error or ids or "Could not enumerate X11 windows"
        rows = []
        for window in ids.splitlines()[:80]:
            if not window.isdecimal():
                continue
            _, title, _ = query(["xdotool", "getwindowname", window])
            _, owner, _ = query(["xdotool", "getwindowpid", window])
            rows.append({"id": window, "title": title, "pid": int(owner) if owner.isdecimal() else None})
        return rows, ""

    def process_info():
        parents, names = {}, {}
        try:
            entries = list(Path("/proc").iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if not entry.name.isdecimal():
                continue
            try:
                status = dict(line.split(":", 1) for line in (entry / "status").read_text().splitlines() if ":" in line)
                parents[int(entry.name)] = int(status.get("PPid", "0"))
                names[int(entry.name)] = status.get("Name", "").strip().lower()
            except (OSError, ValueError):
                pass
        return parents, names

    # Firefox's official launcher execs the adjacent firefox-bin. A process Name is
    # mutable/truncated and does not identify its executable; compare actual file IDs.
    executable_files = []
    selected = shutil.which(argv[0])
    if selected:
        resolved = Path(selected).resolve()
        executable_files.append(resolved)
        if resolved.name == "firefox":
            executable_files.append(resolved.with_name("firefox-bin"))
    executable_ids = set()
    for candidate in executable_files:
        try:
            info = candidate.stat()
            if candidate.is_file():
                executable_ids.add((info.st_dev, info.st_ino))
        except OSError:
            pass

    def owns_requested_executable(pid):
        try:
            info = (Path("/proc") / str(pid) / "exe").stat()
            return (info.st_dev, info.st_ino) in executable_ids
        except OSError:
            return False

    rc, geometry, error = query(["xdotool", "getdisplaygeometry"])
    base = {"stdout": "", "stderr": error, "exit_code": None, "display": os.environ.get("DISPLAY"),
            "verification": "application_window", "page_verified": False, "playback_verified": False}
    if rc != 0:
        return dict(base, status="failed", message="Nova's authenticated display is unavailable; no application was launched.", exit_code=rc)
    before, before_error = windows()
    initial_ids = {row["id"] for row in before}
    log_dir = Path(tempfile.mkdtemp(prefix="nova-launch-"))
    stdout_path, stderr_path = log_dir / "stdout.log", log_dir / "stderr.log"
    # Remain in the tool operation's process group, so cancellation can still clean it up.
    # Ignore terminal hangup only; a completed GUI tool intentionally leaves its application open.
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file)
    except OSError as error:
        return dict(base, status="failed", exit_code=127, stderr=str(error), message="The guest executable could not be started.")
    tracked = {proc.pid}
    deadline = time.monotonic() + wait
    matched, after_error = [], ""
    while True:
        parents, names = process_info()
        changed = True
        while changed:
            expanded = tracked | {pid for pid, parent in parents.items() if parent in tracked}
            changed = expanded != tracked
            tracked = expanded
        after, after_error = windows()
        # Existing browser instances may receive --new-window and let the launcher exit.
        # Accept only a newly observed window owned by the requested executable in that case.
        running = set(parents)
        if proc.poll() is None:
            running.add(proc.pid)
        matched = [row for row in after if row["pid"] in running and
                   (row["pid"] in tracked or
                    (not before_error and row["id"] not in initial_ids and owns_requested_executable(row["pid"])))]
        if matched or proc.poll() is not None and proc.returncode != 0 or time.monotonic() >= deadline:
            break
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    def tail(path):
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 12000))
            return stream.read(12000).decode("utf-8", errors="replace")
    code = proc.poll()
    base.update(pid=proc.pid, process_running=code is None, exit_code=code, windows=matched,
                window_processes_running=bool(matched),
                stdout=tail(stdout_path), stderr=tail(stderr_path),
                log_paths={"stdout": str(stdout_path), "stderr": str(stderr_path)},
                window_probe_error=before_error or after_error, geometry=geometry)
    if code is not None and code != 0:
        return dict(base, status="failed", message="The application process exited with an error; diagnostics are preserved.")
    if matched:
        return dict(base, status="succeeded", message="A matching application window is visible on Nova's desktop. Page content and playback still require observation.")
    return dict(base, status="unknown", message="No matching application window was verified. A running process or exit code 0 alone is not GUI success.")


def _selftest() -> int:
    from nova_computer.computer import NovaComputer
    pc = NovaComputer()
    print("computer:", pc.backend.name, "|", pc.where())
    if pc.backend.name == "none":
        print("HANDS_RESULT: SKIPPED - no computer here"); return 0
    h = Hands(pc)
    info = h.available()
    print("hands:", info)
    if not info.get("ready"):
        print("HANDS_RESULT: NOT READY -", info.get("fix", "her display is not up"))
        return 1
    print("screen:", h.screen_size())
    img = h.look()
    print("look():", f"{len(img)} bytes of PNG" if img else "FAILED")
    print("windows:", [w["name"] for w in h.windows()][:8])
    # A harmless, visible proof that she can actually act: nudge the pointer and read it back.
    h.move(400, 300)
    rc, pos = h._run("xdotool getmouselocation")
    print("moved pointer ->", pos)
    # This used to compute `ok` and then report on the screenshot alone, so a pointer that
    # never moved still passed. Both halves count now: she must SEE and ACT.
    moved = "x:400" in pos.replace(" ", "")
    print("  saw its own screen:", bool(img), "| moved its own pointer:", moved)
    ok = bool(img) and moved
    print("HANDS_RESULT:", "DONE" if ok else "INCOMPLETE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest() if "--selftest" in sys.argv else _selftest())
