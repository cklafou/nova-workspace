# Last updated: 2026-07-18 20:30:48
# @nova: Stray-console janitor — the safety net under the Nova Console.
#
# WHAT IT CAN DO:  find console windows that belong to Nova's process tree, HIDE them, and report
#                  that they appeared — into ONE deduped "Strays" tab.
# WHAT IT CANNOT DO: capture their TEXT. Once a process owns a console, its stdout goes to that
#                  console's buffer; there is no supported way to reach in afterwards and redirect
#                  it. Anything that matters is already written to logs/ anyway. I'd rather tell
#                  you the honest limit than fake a tab full of invented content.
#
# This is a NET, not the fix. The fix is not spawning them (hidden consoles) and not running git
# in a loop (the FILE_INDEX_LINK.md bug). If this janitor is hiding lots of windows, something
# upstream is still wrong and the Strays tab is how you'll know.
#
# SAFETY: it walks the parent chain of each console window's owning process and only touches a
# window whose ancestry reaches a known Nova PID. Your own terminals are never hidden.

import ctypes
import ctypes.wintypes as w
import json
import sys
import threading
import time
import urllib.request

HUB = "http://127.0.0.1:8799"
SW_HIDE = 0
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_char * 260)]


def _snapshot():
    """pid -> (ppid, exe_name). One CreateToolhelp32Snapshot; no psutil dependency."""
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = {}
    if snap == -1:
        return out
    try:
        e = PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not k32.Process32First(snap, ctypes.byref(e)):
            return out
        while True:
            out[e.th32ProcessID] = (e.th32ParentProcessID,
                                    e.szExeFile.decode(errors="replace"))
            if not k32.Process32Next(snap, ctypes.byref(e)):
                break
    finally:
        ctypes.windll.kernel32.CloseHandle(snap)
    return out


def _is_ours(pid: int, nova_pids: set, procs: dict) -> bool:
    """Walk up the parent chain. True only if we reach a known Nova process."""
    seen, cur, depth = set(), pid, 0
    while cur and cur not in seen and depth < 12:
        if cur in nova_pids:
            return True
        seen.add(cur)
        cur = procs.get(cur, (0, ""))[0]
        depth += 1
    return False


def _post(stream: str, text: str):
    try:
        req = urllib.request.Request(
            HUB + "/api/write", method="POST",
            data=json.dumps({"stream": stream, "text": text}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1.5)
    except Exception:
        pass


def _nova_pids() -> set:
    try:
        with urllib.request.urlopen(HUB + "/api/pids", timeout=1.5) as r:
            return set(json.loads(r.read().decode()).get("pids", []))
    except Exception:
        return set()


def run(poll_s: float = 0.35):
    """Hide any console window owned by Nova's process tree. Report each one, deduped by exe."""
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

    seen_counts: dict[str, int] = {}     # exe -> how many we've hidden (dedupe: one line per exe)
    pid_cache, last_pid_fetch = set(), 0.0

    def sweep():
        nonlocal pid_cache, last_pid_fetch
        now = time.time()
        if now - last_pid_fetch > 5:
            pid_cache, last_pid_fetch = _nova_pids(), now
        if not pid_cache:
            return
        procs = _snapshot()
        hits = []

        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, buf, 64)
            if buf.value != "ConsoleWindowClass":     # only real console windows
                return True
            pid = w.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            p = pid.value
            if p and _is_ours(p, pid_cache, procs):
                user32.ShowWindow(hwnd, SW_HIDE)      # <- the flash stops here
                hits.append(procs.get(p, (0, "?"))[1])
            return True

        EnumWindows(EnumWindowsProc(cb), 0)

        for exe in hits:
            n = seen_counts.get(exe, 0) + 1
            seen_counts[exe] = n
            # Dedupe: first sighting gets a line, then only at 10/100/1000 — otherwise a loop
            # would flood the tab with thousands of identical rows (which is what we're fixing).
            if n == 1 or n in (10, 100, 1000):
                _post("strays", f"hid a stray console from {exe} (x{n}) — something upstream "
                                f"is spawning consoles; see README")

    while True:
        try:
            sweep()
        except Exception:
            pass
        time.sleep(poll_s)


def start():
    threading.Thread(target=run, name="stray-janitor", daemon=True).start()
