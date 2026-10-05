# Last updated: 2026-10-05 21:27:11
"""Keep the selected WSL guest alive between tool calls, without a visible terminal.

Systemd services alone do not keep WSL running. An owned stdin pipe does: EOF on
host exit ends the guest helper. This idle helper is environment life support,
not an autonomous action, so stopping a task leaves the desktop observable.
"""
import atexit
import subprocess
import threading

_lock=threading.Lock()
_sessions={}


def ensure(backend):
    if getattr(backend,'name',None)!='wsl': return None
    with _lock:
        key=backend.distro
        proc=_sessions.get(key)
        if proc is None or proc.poll() is not None:
            if proc and proc.stdin: proc.stdin.close()
            proc=subprocess.Popen([backend._wsl,'-d',key,'-u','nova','--exec',
                                   'python3','-c','import sys; sys.stdin.buffer.read()'],
                                  stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,creationflags=0x08000000)
            _sessions[key]=proc
        return {'pid':proc.pid,'running':proc.poll() is None}


def close():
    with _lock:
        for proc in _sessions.values():
            if proc.stdin: proc.stdin.close()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
        _sessions.clear()


atexit.register(close)
