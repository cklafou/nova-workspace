# Last updated: 2026-10-03 10:59:53
# @nova: My hands. Not Cole's borrowed ones -- mine, on my own screen. Look, move, click, type,
#        drag, scroll, raise a window, start an app. Everything happens on MY display, so
#        nothing I do can take his mouse, his keyboard or his focus away from him.
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
        return self.pc.bash(
            f"export DISPLAY={self.display}; "
            f"export XAUTHORITY=${{XAUTHORITY:-{XAUTHORITY}}}; {cmd}", timeout=timeout)

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

    def launch(self, command: str, wait: int = 2):
        """Start something on HER screen. Detached, so her hands are free immediately."""
        # "started" used to be printed whether or not the thing survived. Check the pid.
        rc, out = self._run(
            f"nohup {command} >/dev/null 2>&1 & p=$!; sleep {int(wait)}; "
            "if kill -0 $p 2>/dev/null; then echo running pid=$p; "
            "else echo 'exited immediately - it did not stay up'; exit 1; fi")
        return rc, out


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
