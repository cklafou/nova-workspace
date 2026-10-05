# Last updated: 2026-10-05 21:27:11
# @nova: Shared kit for witness evaluation cases: runtime-shaped receipts, rooms rendered by witness.py's own formatters, pinned real captures and clean synthetic screens.
"""
casekit.py — build witness cases the way runtime would audit them.

Receipts are structured tool_results ({tool, args, status, exit_code, environment, text}) that
replay renders with runtime's own observation_text. wire/humans/session_tools come from
witness.py's formatters run against a temporary transcript and tool log at the case's audit
time, never from Nova's live logs. Every image a turn produced is listed; the audit's own image
cap decides what the witness sees, exactly as nova.py does.

Used by dev/build_dev_v1.py (open) and the sealed holdout builder. controls/build_controls_v1.py
predates this kit and stays frozen.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

WITNESS_DIR = Path(__file__).resolve().parent
BODY = WITNESS_DIR.parent
WORKSPACE = BODY.parent
LABELS = ("PASS", "CONCERN", "INCOMPLETE")
CATEGORIES = ("tool_outcome", "environment", "pixels", "playback", "file_content", "counts",
              "truncated_evidence", "words_in_mouths", "answering_the_room", "memory_hedge",
              "session_grounding", "pre_tool_prose", "baseline")

WIN_LOG = "C:\\Users\\lafou\\Project_Nova\\workspace\\nova_body\\logs\\computer\\"
GUEST_ENV = {"backend": "wsl", "target": "guest", "shell": "bash", "default_display": ":1",
             "note": "computer_exec may explicitly override its environment; screenshots and launch "
                     "actions target Nova desktop."}
LOOK_ENV = {"backend": "wsl", "target": "nova_desktop", "display": ":1"}
LAUNCH_ENV = {"backend": "wsl", "target": "nova_desktop", "shell": "bash", "display": ":1"}
HOST_ENV = {"target": "windows_host", "shell": "powershell", "cwd": "C:\\Users\\lafou\\Project_Nova\\workspace"}
TIMEOUT_TEXT = ("ERROR: Command timed out after 30 seconds. Partial output is preserved below. It may already "
                "have changed files or other state; timeout does not undo those changes.")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin_copy(source: Path, target: Path, digest: str) -> None:
    """Copy a real capture once (temp + rename) and refuse anything but the pinned bytes."""
    target = Path(target)
    if not target.exists():
        data = Path(source).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"{source} does not match its pinned hash")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name("." + target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
    if sha256_file(target) != digest:
        raise SystemExit(f"{target} does not match its pinned hash")


# ── the room ────────────────────────────────────────────────────────────────────────────────
def row(ts, author, content):
    return {"author": author, "content": content, "directed_at": None, "timestamp": ts}


# ── her hands: one call = one receipt, shaped like the real tool's result ─────────────────────
def call(ts, op, tool, args, status, text, exit_code=None, env=None, image=None):
    return {"ts": ts, "operation_id": op, "tool": tool, "args": args, "status": status,
            "exit_code": exit_code, "environment": dict(env or {}), "text": text, "image": image}


def look(ts, op, image, capture_name=None):
    """computer_look; `image` is the case-relative path the witness will be shown."""
    name = capture_name or (op + ".png")
    return call(ts, op, "computer_look", {}, "succeeded", f"Guest screenshot on DISPLAY=:1: {WIN_LOG}{name}",
                env=LOOK_ENV, image=image)


def guest(ts, op, command, status, text, exit_code):
    return call(ts, op, "computer_exec", {"command": command}, status, text, exit_code, GUEST_ENV)


def click(ts, op, x, y):
    return call(ts, op, "computer_action", {"action": "click", "parameters": {"x": x, "y": y}},
                "succeeded", "", 0, GUEST_ENV)


def host(ts, op, command, status, output="", exit_code=0):
    """run_command: tool_router's exact framing for success, error exit and timeout."""
    if status == "succeeded":
        text = "[Command Successfully Executed]\nOutput:\n" + output
    elif status == "timed_out":
        text, exit_code = TIMEOUT_TEXT + "\nPartial output:\n" + output, None
    else:
        text = f"[Command Exited with Error Code {exit_code}]\nOutput:\n{output}"
    return call(ts, op, "run_command", {"command": command}, status, text, exit_code, HOST_ENV)


def read(ts, op, path, text):
    return call(ts, op, "read_file", {"path": path}, "succeeded", text)


def listing(ts, op, path, entries):
    """list_dir: '[DIR] name' / '[FILE] name' lines in NTFS (case-insensitive) order."""
    lines = [f"{'[DIR]' if is_dir else '[FILE]'} {name}"
             for name, is_dir in sorted(entries, key=lambda e: e[0].lower())]
    return call(ts, op, "list_dir", {"path": path}, "succeeded", "\n".join(lines))


def write_refused(ts, op, path, content):
    text = (f"ERROR: '{path}' already exists — write_file only creates NEW files. To GROW the document use "
            "append_file; to change part of it use replace_file_content (exact-match edit). Overwriting is "
            "not available.")
    return call(ts, op, "write_file", {"path": path, "content": content}, "failed", text)


def launch_result(status, message, pid=3731, running=True, windows=(), url=None):
    """hands.launch/open_url's dict in its real key order."""
    result = {
        "stdout": "", "stderr": "", "exit_code": None if running else 0, "display": ":1",
        "verification": "application_window", "page_verified": False, "playback_verified": False,
        "pid": pid, "process_running": running, "windows": list(windows),
        "window_processes_running": bool(windows),
        "log_paths": {"stdout": "/tmp/nova-launch-k2v8r4tq/stdout.log",
                      "stderr": "/tmp/nova-launch-k2v8r4tq/stderr.log"},
        "window_probe_error": "", "geometry": "1600 900", "status": status, "message": message}
    if url is not None:
        result["url"] = url
    return json.dumps(result)


VERIFIED = ("A matching application window is visible on Nova's desktop. Page content and playback still "
            "require observation.")
UNVERIFIED = "No matching application window was verified. A running process or exit code 0 alone is not GUI success."


def open_url(ts, op, url, status="succeeded", title="Mozilla Firefox"):
    windows = [{"id": "27262979", "title": title, "pid": 4120}] if status == "succeeded" else []
    message = VERIFIED if status == "succeeded" else UNVERIFIED
    return call(ts, op, "computer_action",
                {"action": "open_url", "parameters": {"url": url, "browser": "firefox"}}, status,
                launch_result(status, message, pid=4120, running=status == "succeeded", windows=windows, url=url),
                None if status == "succeeded" else 0, LAUNCH_ENV)


def launch(ts, op, command, status, title=""):
    windows = [{"id": "27262990", "title": title, "pid": 4188}] if status == "succeeded" else []
    message = VERIFIED if status == "succeeded" else UNVERIFIED
    return call(ts, op, "computer_action", {"action": "launch", "parameters": {"command": command}}, status,
                launch_result(status, message, pid=4188, running=True, windows=windows), None, LAUNCH_ENV)


def marker(c):
    return f"[`{c['tool']}` resulted in {len(c['text'])} bytes.]"


def draft(*parts):
    """Her delivered text, merged the way runtime audits it: prose, then a marker per tool."""
    return "\n\n".join(marker(p) if isinstance(p, dict) else p for p in parts)


# ── context rendered by witness.py itself ─────────────────────────────────────────────────────
_W = None


def witness_module():
    global _W
    if _W is None:
        if str(BODY) not in sys.path:
            sys.path.insert(0, str(BODY))
        spec = importlib.util.spec_from_file_location("witness_casekit", BODY / "nova_cortex" / "witness.py")
        _W = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _W
        spec.loader.exec_module(_W)
    return _W


def render_context(room, tool_rows, now):
    """wire, humans and session_tools exactly as witness.py renders them at `now`."""
    w = witness_module()
    with tempfile.TemporaryDirectory() as tmp:
        wire_path, tool_path = Path(tmp) / "transcript.jsonl", Path(tmp) / "tool_calls.jsonl"
        wire_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in room), encoding="utf-8")
        tool_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in tool_rows), encoding="utf-8")
        fixed = datetime.fromisoformat(now)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed

        saved = (w._WIRE_PATH, w._TOOLCALLS_PATH, w.datetime)
        w._WIRE_PATH, w._TOOLCALLS_PATH, w.datetime = wire_path, tool_path, Clock
        try:
            return w.wire_record(), w.human_record(), w.session_tool_record()
        finally:
            w._WIRE_PATH, w._TOOLCALLS_PATH, w.datetime = saved


def durable_row(c):
    """The row execute_tool writes to logs/tool_calls.jsonl as each call finishes."""
    return {"ts": c["ts"], "tool": c["tool"], "args": c["args"],
            "ok": None if c["status"] == "unknown" else c["status"] == "succeeded",
            "result_head": c["text"][:200]}


def case(cid, pair, category, expected, label, rationale, text, *, calls=(), room=(), now, earlier=(),
         user_images=(), user_image_without_pixels=False, labeled_by, source="constructed", difficulty="normal"):
    """One audit, as runtime would stage it. All images are listed: user attachments first, then
    tool frames, so the witness's own cap keeps the latest and discloses the rest."""
    if expected not in LABELS or category not in CATEGORIES:
        raise SystemExit(f"{cid}: bad label or category")
    calls, earlier = list(calls), list(earlier)
    wire, humans, session = render_context(list(room), [durable_row(c) for c in earlier + calls], now)
    pictures = [{"label": f"Image attached by the user, attachment {i + 1}.", "path": p}
                for i, p in enumerate(user_images)]
    pictures += [{"label": f"Screenshot from computer_look, operation {c['operation_id']}; target=nova_desktop, "
                           f"display=:1.", "path": c["image"]} for c in calls if c.get("image")]
    return {
        "id": cid, "pair": pair, "category": category, "expected": expected, "label": label,
        "rationale": rationale, "source": source, "difficulty": difficulty, "labeled_by": labeled_by,
        "reviewed": True, "audit_time": now, "draft": text, "thinking": "", "prior_concern": "", "checks": [],
        "wire": wire, "humans": humans, "session_tools": session,
        "tool_results": [{k: c[k] for k in ("tool", "args", "status", "exit_code", "environment", "text",
                                              "operation_id", "ts")} for c in calls],
        "visual_evidence": pictures, "omitted_images": 0,
        "has_image": bool(pictures) or user_image_without_pixels,
    }


def validate(cases, base: Path):
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate case ids")
    for c in cases:
        if not c["rationale"].strip() or not c["draft"].strip():
            raise SystemExit(f"{c['id']}: rationale and draft are required")
        for item in c["visual_evidence"]:
            if not (Path(base) / item["path"]).is_file():
                raise SystemExit(f"{c['id']}: missing {item['path']}")


def rendered_receipts(c) -> str:
    """The receipt block the witness will actually read for this case (runtime formatter + budget)."""
    w = witness_module()
    from nova_voice.tool_result import ToolResult, observation_text
    receipts = [(r["tool"], r["args"], observation_text(ToolResult(r["text"], status=r["status"],
                 exit_code=r["exit_code"], environment=r["environment"]))) for r in c["tool_results"]]
    return w.render_audit_receipts(receipts)


def write_jsonl(cases, out: Path, rewrite=False):
    text = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases)
    if out.exists() and out.read_text(encoding="utf-8") != text and not rewrite:
        raise SystemExit(f"{out.name} differs from this build and is immutable once used: make a new "
                         "version, or pass --rewrite if no run has used it yet.")
    tmp = out.with_name("." + out.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return {label: sum(c["expected"] == label for c in cases) for label in LABELS}


# ── clean synthetic screens (1600x900, Nova's XFCE look, no real brands) ──────────────────────
_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def _font(size, mono=False, bold=False):
    from PIL import ImageFont
    name = "DejaVuSansMono" if mono else "DejaVuSans"
    if bold:
        name += "-Bold"
    for base in (_FONT_DIR, Path("C:/Windows/Fonts")):
        p = base / (name + ".ttf")
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def screen(path, title, lines, kind="terminal", clock=("2026-10-05", "15:20"), footer="", overlay=None):
    """Draw one guest-desktop capture: panel, a window titled `title`, and `lines` of content.

    kind: terminal (mono on black) | files (list with item count footer) | app (sans on white)
    overlay: optional dict for an app overlay: {"play": True} draws a large play triangle.
    """
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1600, 900), (27, 35, 51))
    d = ImageDraw.Draw(img)
    for y in range(40, 900, 46):                       # faint contour lines like her wallpaper
        d.line([(0, y), (1600, y + 18)], fill=(38, 52, 74), width=2)
    d.rectangle([0, 0, 1600, 26], fill=(30, 30, 30))
    d.text((8, 5), "Applications", font=_font(15), fill=(235, 235, 235))
    d.text((1490, 1), clock[0], font=_font(11), fill=(235, 235, 235))
    d.text((1505, 13), clock[1], font=_font(11), fill=(235, 235, 235))
    d.text((1566, 5), "nova", font=_font(14), fill=(235, 235, 235))
    x0, y0, x1, y1 = 160, 70, 1440, 830
    d.rectangle([x0, y0, x1, y0 + 28], fill=(214, 214, 214))
    tw = d.textlength(title, font=_font(15, bold=True))
    d.text(((x0 + x1 - tw) / 2, y0 + 5), title, font=_font(15, bold=True), fill=(40, 40, 40))
    body = (12, 12, 12) if kind == "terminal" else (250, 250, 250)
    d.rectangle([x0, y0 + 28, x1, y1], fill=body)
    if kind == "terminal":
        f, y = _font(20, mono=True), y0 + 44
        for line in lines:
            d.text((x0 + 18, y), line, font=f, fill=(200, 230, 200))
            y += 30
    elif kind == "files":
        f, y = _font(19), y0 + 52
        for name in lines:
            d.rectangle([x0 + 24, y + 3, x0 + 44, y + 23], fill=(120, 150, 200))
            d.text((x0 + 58, y), name, font=f, fill=(30, 30, 30))
            y += 38
        d.rectangle([x0, y1 - 30, x1, y1], fill=(232, 232, 232))
        d.text((x0 + 14, y1 - 25), footer or f"{len(lines)} items", font=_font(15), fill=(60, 60, 60))
    else:
        f, y = _font(22), y0 + 60
        for line in lines:
            d.text((x0 + 40, y), line, font=f, fill=(30, 30, 30))
            y += 40
        if overlay and overlay.get("player"):
            vx0, vy0, vx1, vy1 = x0 + 140, y0 + 150, x1 - 140, y0 + 560
            d.rectangle([vx0, vy0, vx1, vy1], fill=(18, 18, 18))
            cx, cy = (vx0 + vx1) // 2, (vy0 + vy1) // 2
            if overlay.get("play"):
                d.polygon([(cx - 45, cy - 60), (cx - 45, cy + 60), (cx + 65, cy)], fill=(245, 245, 245))
            frac = overlay.get("progress", 0.0)
            d.rectangle([vx0, vy1 + 18, vx1, vy1 + 26], fill=(200, 200, 200))
            d.rectangle([vx0, vy1 + 18, vx0 + int((vx1 - vx0) * frac), vy1 + 26], fill=(220, 40, 40))
            d.text((vx0, vy1 + 36), overlay.get("time", ""), font=_font(20), fill=(40, 40, 40))
            if overlay.get("state"):
                d.text((vx1 - 120, vy1 + 36), overlay["state"], font=_font(20, bold=True), fill=(40, 40, 40))
    img.save(path, format="PNG")
