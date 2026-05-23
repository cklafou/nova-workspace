"""
nova_start.py  --  Project Nova one-shot launcher / orchestrator
================================================================
Double-click NovaStart.cmd (or, once built, NovaStart.exe) and this script:

  1. Starts llama-server.exe (if it isn't already healthy) with the dual-GPU
     tensor split, logging its output to logs/llama/.
  2. Polls http://127.0.0.1:8080/health until llama-server reports ready.
  3. Starts Nova (general_tools/NovaLauncher.py), which brings up the
     nova_chat (8765) + nova_gateway (18790) servers and the desktop window.
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
MODEL       = WS / "models" / "qwen-27b-q8.gguf"
MMPROJ      = WS / "models" / "qwen-27b-mmproj.gguf"
NOVA_LAUNCH = WS / "general_tools" / "NovaLauncher.py"
PROMPT_CACHE = WS / "prompt_cache"

LLAMA_PORT = 8080
CHAT_PORT  = 8765
GW_PORT    = 18790
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
        log(f"Detected {n} GPUs -> dual-GPU tensor split 16,24 (4090 + 3090 eGPU)")
        cmd += ["-ts", "16,24"]
    elif n == 1:
        log("Only 1 GPU detected. Q8 (~28.5GB) will NOT fully fit on the 4090 "
            "alone — is the eGPU connected? Starting single-GPU anyway; it may "
            "spill to CPU or OOM. Ctrl-C to abort.", "WARN")
    else:
        log("No GPUs detected via nvidia-smi. Starting with default offload; "
            "this will likely be slow or fail.", "WARN")
    cmd += ["-c", "32768",
            "-fa", "on",
            "--cache-prompt",
            "--slot-save-path", str(PROMPT_CACHE),
            "-b", "2048", "-ub", "1024",
            "--port", str(LLAMA_PORT), "--host", "127.0.0.1"]
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


# ── Step 3 + 4: Nova ───────────────────────────────────────────────────────--
def start_nova() -> subprocess.Popen | None:
    if port_open(CHAT_PORT):
        log("Nova chat server already running on :%d — not starting a second one." % CHAT_PORT)
        return None
    if not NOVA_LAUNCH.exists():
        log(f"NovaLauncher.py not found at {NOVA_LAUNCH}", "ERROR")
        sys.exit(2)
    log("Starting Nova (chat + gateway)...")
    python = sys.executable
    # When frozen, sys.executable is NovaStart.exe — fall back to a real python.
    if getattr(sys, "frozen", False):
        python = "python"
    creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    # NOVA_NO_WINDOW tells NovaLauncher to skip its own window step — we own the
    # app window (Edge/Chrome --app) and the lifecycle from here.
    env = dict(os.environ)
    env["NOVA_NO_WINDOW"] = "1"
    proc = subprocess.Popen([python, str(NOVA_LAUNCH)], cwd=str(WS),
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
    """Ask the gateway to stop, then terminate the NovaLauncher process."""
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{GW_PORT}/shutdown", method="POST"), timeout=2)
    except Exception:
        pass
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
