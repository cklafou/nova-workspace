# Last updated: 2026-07-08 19:49:33
# @nova: Project Nova startup orchestrator — health-gates llama-server (:8080) then launches Nova; invoked by NovaStart.cmd.
"""
nova_start.py  --  Project Nova one-shot launcher / orchestrator
================================================================
Double-click NovaStart.cmd (or, once built, NovaStart.exe) and this script:

  1. Starts llama-server.exe (if it isn't already healthy) with the dual-GPU
     tensor split, logging its output to logs/llama/.
  2. Polls http://127.0.0.1:8080/health until llama-server reports ready.
  3. Starts Nova (general_tools/NovaLauncher.py), which brings up the
     nova_chat (8765) server and the desktop window.
  4. Waits for the chat port, then hands off. When the Nova window closes,
     llama-server is shut down too, so one launch == one clean lifecycle.

Everything is logged to logs/launcher/ with timestamps. The console shows a
clean, human-readable step-by-step so you can see exactly what is happening.

This file is also the PyInstaller entry point for NovaStart.exe (see
build_nova_start.cmd).
"""

import os
import sys
import time
import socket
import signal
import shutil
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller bundle: the .exe sits in the workspace root.
    WS = Path(sys.executable).resolve().parent
else:
    WS = Path(__file__).resolve().parent

LLAMA_EXE   = WS / "llama" / "llama-server.exe"
MODEL       = WS / "models" / "qwen3.6" / "Qwen3.6-27B-UD-Q6_K_XL.gguf"   # Qwen 3.6 27B Q6 + MTP (was qwen-27b-q8.gguf, 3.5)
MMPROJ      = WS / "models" / "qwen3.6" / "mmproj-F16.gguf"
NOVA_LAUNCH = WS / "general_tools" / "NovaLauncher.py"
WATCHER     = WS / "general_tools" / "nova_sync" / "watcher.py"
PROMPT_CACHE = WS / "prompt_cache"

LLAMA_PORT = 8080
CHAT_PORT  = 8765
LLAMA_HEALTH = f"http://127.0.0.1:{LLAMA_PORT}/health"

LOG_DIR    = WS / "logs" / "launcher"
LLAMA_LOGS = WS / "logs" / "llama"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LLAMA_LOGS.mkdir(parents=True, exist_ok=True)
_STAMP   = datetime.now().strftime("%Y-%m-%d")
LOG_FILE = LOG_DIR / f"nova_start-{_STAMP}.log"


# ── Logging helpers ─────────────────────────────────────────────────────────--
def log(msg: str, level: str = "INFO") -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')} [{level}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def banner(text: str) -> None:
    bar = "=" * 60
    print("\n" + bar + "\n  " + text + "\n" + bar, flush=True)


# ── Port / health checks ───────────────────────────────────────────────────--
def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def llama_healthy(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(LLAMA_HEALTH, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# ── GPU detection — choose the tensor split ────────────────────────────────--
def detect_gpu_count() -> int:
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                           text=True, timeout=8)
        if r.returncode == 0:
            return len([ln for ln in r.stdout.splitlines() if ln.strip().startswith("GPU ")])
    except Exception as e:
        log(f"nvidia-smi check failed: {e}", "WARN")
    return 0


def build_llama_cmd() -> list:
    """Assemble the llama-server command, adapting to the number of GPUs.
    Built in order so the GPU flags always sit in valid positions."""
    n = detect_gpu_count()
    cmd = [str(LLAMA_EXE),
           "-m", str(MODEL),
           "--mmproj", str(MMPROJ),
           "-ngl", "999"]
    if n >= 2:
        log(f"Detected {n} GPUs -> dual-GPU tensor split 12,28 (4090 + 3090 eGPU)")
        log("Rationale: 4090 also carries mmproj + Python overhead, so it gets the")
        log("           smaller share (30%) to keep ~4-5GB headroom for compute spikes.")
        cmd += ["-ts", "12,28"]
    elif n == 1:
        log("Only 1 GPU detected — the eGPU (3090) is NOT enumerated. The 27B Q8 "
            "model (~28.5GB) will not fit on the 4090 alone (16GB); attempting to "
            "load anyway always ends in CUDA OOM mid-inference. Aborting startup "
            "so the chat host doesn't keep getting 500s from a broken model.", "ERROR")
        log("Fix: check eGPU connection (OCuLink), run nvidia-smi to confirm both "
            "cards visible, then re-run NovaStart.", "ERROR")
        sys.exit(2)
    else:
        log("No GPUs detected via nvidia-smi. Aborting startup — CPU offload of a "
            "27B Q8 model is unworkable for live use.", "ERROR")
        log("Fix: install/restart NVIDIA drivers so nvidia-smi resolves, then re-run.", "ERROR")
        sys.exit(2)
    cmd += ["-c", "65536",               # 32K starved her: the ~24K-token always-on self-model + memory block left negative room for live conversation, so she "forgot what was just said / looped to her first memory". Qwen 3.6 native ctx is 262144, so 64K is free of rope-scaling. MUST match nova_client _truncate_to_context ctx_limit.
            "--parallel", "1",           # one slot → her single conversation gets the FULL 64K window (and frees KV VRAM the idle parallel slots were holding)
            "-fa", "on",
            "--jinja",                       # Qwen 3.6 REQUIRES its chat template applied (do NOT carry over the 3.5 'no --chat-template' rule)
            "--reasoning-format", "deepseek", # parse <think> into reasoning_content (nova_client reads that field) → no </think> leaking into chat
            # MTP DISABLED 2026-07-08: draft-mtp dropped tokens ("going to" -> "going") with the LoRA
            # active — the un-adapted MTP draft head diverges from the LoRA'd model, worse at higher
            # scale. Re-add these two lines to restore ~1.4-2x speculative-decoding speed if desired.
            # "--spec-type", "draft-mtp",
            # "--spec-draft-n-max", "2",
            "--cache-prompt",
            "--slot-save-path", str(PROMPT_CACHE),
            "-b", "2048", "-ub", "1024",
            "--port", str(LLAMA_PORT), "--host", "127.0.0.1"]
    # Nova-core: personality LoRA. The Nova Chat LoRA menu's "equip" writes memory/active_lora.json
    # ({"rel": "models/qwen3.6/<file>.gguf", "scale": W}) to pick WHICH adapter boots and at what
    # weight; absent/invalid -> the v2 default below (so boot is unchanged until you pick one).
    # Rides in the BASE command so any KoELS specialist swap stacks ON TOP of her personality.
    # Conditional on the file existing so a missing adapter never blocks startup (bare base fallback).
    _sel_rel, _sel_scale = "models/qwen3.6/nova_core_v2_e2.gguf", 0.6
    _active = WS / "memory" / "active_lora.json"
    if _active.exists():
        try:
            import json as _json
            _d = _json.loads(_active.read_text(encoding="utf-8"))
            if _d.get("rel") and (WS / _d["rel"]).exists():
                _sel_rel, _sel_scale = str(_d["rel"]), float(_d.get("scale", 1.0))
        except Exception:
            pass
    _nova_core = WS / _sel_rel
    if _nova_core.exists():
        # This llama build wants ONE arg in "FNAME:SCALE" form (not two args). Use a workspace-
        # relative path (cwd is WS) so the Windows drive-colon (C:\) can't confuse the FNAME:SCALE
        # split — only the scale colon remains.
        _rel = _nova_core.relative_to(WS).as_posix()
        cmd += ["--lora-scaled", f"{_rel}:{_sel_scale}"]
        log(f"Nova-core personality adapter: {_rel}:{_sel_scale}")
    # KoELS: preload a persisted boot --lora set if one exists (koels_lora_args.json = clean arg
    # list; mirrors start_llama_qwen36.cmd's %KOELS_LORA% hook). Absent = Nova-core only.
    _lora_json = WS / "memory" / "koels_lora_args.json"
    if _lora_json.exists():
        try:
            import json as _json
            cmd += _json.loads(_lora_json.read_text(encoding="utf-8")).get("args", [])
        except Exception:
            pass
    return cmd


# ── Step 1 + 2: llama-server ───────────────────────────────────────────────--
def start_llama() -> subprocess.Popen | None:
    if llama_healthy():
        log("llama-server already healthy on :%d — reusing it." % LLAMA_PORT)
        return None
    if port_open(LLAMA_PORT):
        log("Something is on :%d but /health is not 200 yet — waiting on it." % LLAMA_PORT)
        return None
    if not LLAMA_EXE.exists():
        log(f"llama-server.exe not found at {LLAMA_EXE}", "ERROR")
        sys.exit(2)
    if not MODEL.exists():
        log(f"Model not found at {MODEL}", "ERROR")
        sys.exit(2)

    PROMPT_CACHE.mkdir(parents=True, exist_ok=True)
    llama_log = LLAMA_LOGS / f"llama-{_STAMP}.log"
    log(f"Starting llama-server. Output -> {llama_log.relative_to(WS)}")
    cmd = build_llama_cmd()

    # New console window on Windows so its lifecycle is visible/independent.
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE
    lf = open(llama_log, "a", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd, cwd=str(WS), stdout=lf, stderr=subprocess.STDOUT,
                            creationflags=creationflags)
    return proc


def wait_for_llama(timeout_s: int = 300) -> bool:
    banner("Loading the model — this can take a minute for the 27B Q8 weights")
    deadline = time.time() + timeout_s
    dots = 0
    while time.time() < deadline:
        if llama_healthy():
            print(flush=True)
            log("llama-server is HEALTHY on :%d" % LLAMA_PORT)
            return True
        dots += 1
        print("  loading model" + "." * (dots % 6) + "      ", end="\r", flush=True)
        time.sleep(2)
    print(flush=True)
    log("llama-server did not become healthy within %ds." % timeout_s, "ERROR")
    return False


# ── Pick a Python that actually has Nova's server deps ─────────────────────--
def _pick_python() -> list | None:
    """`py -3` can point at a Python without Nova's deps (uvicorn/fastapi), which
    makes nova_chat fail to start. Probe candidates and return the first that can
    import them, as a command list (e.g. ['py','-3.10']). None if nothing works."""
    cands = []
    if not getattr(sys, "frozen", False):
        cands.append([sys.executable])          # the interpreter running this launcher
    for v in ("3.10", "3.11", "3.12", "3"):
        cands.append(["py", f"-{v}"])
    cands += [["python"], ["python3"]]
    seen = set()
    for c in cands:
        key = tuple(c)
        if key in seen:
            continue
        seen.add(key)
        try:
            r = subprocess.run(c + ["-c", "import uvicorn, fastapi"],
                               capture_output=True, timeout=20)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return None


# ── Step 3 + 4: Nova ───────────────────────────────────────────────────────--
def start_nova() -> subprocess.Popen | None:
    if port_open(CHAT_PORT):
        log("Nova chat server already running on :%d — not starting a second one." % CHAT_PORT)
        return None
    if not NOVA_LAUNCH.exists():
        log(f"NovaLauncher.py not found at {NOVA_LAUNCH}", "ERROR")
        sys.exit(2)
    log("Starting Nova...")
    py = _pick_python()
    if py is None:
        log("No Python with Nova's server deps (uvicorn + fastapi) was found.", "ERROR")
        log("Fix: install them into your Python — e.g.  py -3 -m pip install uvicorn fastapi", "ERROR")
        log("If you have several Pythons, install into the one that already has lancedb / "
            "sentence-transformers (that's the one Nova has been running on).", "ERROR")
        input("Press Enter to exit...")
        return None
    log(f"Using Python: {' '.join(py)}")
    creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    # NOVA_NO_WINDOW tells NovaLauncher to skip its own window step — we own the
    # app window (Edge/Chrome --app) and the lifecycle from here.
    env = dict(os.environ)
    env["NOVA_NO_WINDOW"] = "1"
    proc = subprocess.Popen(py + [str(NOVA_LAUNCH)], cwd=str(WS),
                            creationflags=creationflags, env=env)
    return proc


# ── App window (Edge/Chrome --app) — reliable, no GUI deps ──────────────────--
_app_profile_dir = None
_BROWSER_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def open_app_window():
    """Open Nova as a standalone, chromeless app window. Uses a FRESH per-launch
    profile dir so Chrome always starts its own instance — a shared profile lets
    a leftover Chrome hijack the --app request, making the launched process exit
    instantly (which used to shut the launcher down early). Returns the Popen."""
    global _app_profile_dir
    browser = next((p for p in _BROWSER_CANDIDATES if p.exists()), None)
    if not browser:
        log("No Chrome/Edge found for app-window mode. Nova UI is at "
            f"http://127.0.0.1:{CHAT_PORT}", "WARN")
        return None
    # Best-effort cleanup of stale per-launch profiles from previous runs.
    try:
        for old in WS.glob(".nova_app_profile*"):
            shutil.rmtree(old, ignore_errors=True)
    except Exception:
        pass
    _app_profile_dir = WS / f".nova_app_profile_{os.getpid()}"
    _app_profile_dir.mkdir(parents=True, exist_ok=True)
    log(f"Opening Nova app window via {browser.name}")
    args = [str(browser),
            f"--app=http://127.0.0.1:{CHAT_PORT}",
            f"--user-data-dir={_app_profile_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--new-window",
            "--window-size=1500,950"]
    try:
        return subprocess.Popen(args)
    except Exception as e:
        log(f"Could not open app window: {e}", "ERROR")
        return None


def _shutdown_nova(proc) -> None:
    """Terminate the NovaLauncher process."""
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def wait_for_nova(timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if port_open(CHAT_PORT):
            log("Nova chat is UP on http://127.0.0.1:%d" % CHAT_PORT)
            return True
        time.sleep(1)
    log("Nova chat did not come up within %ds — check logs/nova_launcher.log" % timeout_s, "ERROR")
    return False


def stop_llama(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        log("Stopping llama-server...")
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ── File watcher (manifest refresh + auto-commit) ──────────────────────────--
def start_watcher() -> subprocess.Popen | None:
    """Launch the file watcher as part of the stack. It regenerates Nova's Body
    Manifest on change (keeping SELF/ current) and auto-commits/pushes the
    workspace. Set NOVA_NO_WATCHER=1 to skip. Runs in its own process group so it
    can be stopped gracefully (avoids leaving a git index.lock)."""
    if os.environ.get("NOVA_NO_WATCHER"):
        log("NOVA_NO_WATCHER set — skipping the file watcher.")
        return None
    if not WATCHER.exists():
        log(f"watcher.py not found at {WATCHER} — skipping.", "WARN")
        return None
    py = _pick_python()
    if py is None:
        log("No suitable Python for the watcher — skipping.", "WARN")
        return None
    log("Starting file watcher (manifest refresh + auto-commit)...")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        return subprocess.Popen(py + [str(WATCHER)], cwd=str(WS),
                                creationflags=creationflags)
    except Exception as e:
        log(f"Could not start watcher: {e}", "WARN")
        return None


def stop_watcher(proc: subprocess.Popen | None) -> None:
    """Stop the watcher gracefully so its observer/git push can finish and it does
    not leave a stale .git/index.lock behind."""
    if not proc or proc.poll() is not None:
        return
    log("Stopping file watcher...")
    try:
        if sys.platform == "win32":
            # CTRL_BREAK triggers watcher.py's KeyboardInterrupt -> observer.stop().
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                proc.wait(timeout=8)
                return
            except Exception:
                pass
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ── Main ───────────────────────────────────────────────────────────────────--
def main() -> None:
    banner("PROJECT NOVA  --  one-click launcher")
    log(f"Workspace: {WS}")

    llama_proc = start_llama()
    if not wait_for_llama():
        log("Aborting: model not ready. llama-server console is left open for inspection.", "ERROR")
        input("Press Enter to exit...")
        return

    nova_proc = start_nova()
    if not wait_for_nova():
        log("Proceeding to open the app window anyway; it may show a connection error.", "WARN")

    app_proc = open_app_window()
    watcher_proc = start_watcher()

    banner("Nova is running.  Close the Nova app window to shut everything down.")

    # Own the lifecycle: block on the app window; clean up when it closes.
    try:
        if app_proc is not None:
            _t0 = time.time()
            app_proc.wait()                 # blocks until the app window closes
            if time.time() - _t0 < 5:
                # The browser process exited almost immediately — it handed the
                # window off to another instance, so the window is actually still
                # open. Do NOT shut down; keep Nova alive and wait on the server.
                log("App window handed off to an existing browser — keeping Nova "
                    "alive. Close THIS launcher window (or Ctrl+C) to stop Nova.", "WARN")
                if nova_proc is not None:
                    nova_proc.wait()
                else:
                    while port_open(CHAT_PORT):
                        time.sleep(5)
            else:
                log("Nova app window closed.")
        elif nova_proc is not None:
            nova_proc.wait()
        else:
            while True:
                time.sleep(5)
                if not port_open(CHAT_PORT):
                    log("Nova chat port closed — exiting.")
                    break
    except KeyboardInterrupt:
        log("Interrupted by user.")
    finally:
        stop_watcher(watcher_proc)
        _shutdown_nova(nova_proc)
        stop_llama(llama_proc)
        try:
            if _app_profile_dir:
                shutil.rmtree(_app_profile_dir, ignore_errors=True)
        except Exception:
            pass
        log("Shutdown complete.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"Fatal launcher error: {e}", "ERROR")
        try:
            input("Press Enter to exit...")
        except Exception:
            time.sleep(5)
