# Last updated: 2026-10-03 10:59:53
"""Shared cancellation for generation and the subprocesses it owns."""
from __future__ import annotations

import asyncio
import contextvars
import functools
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field

current_operation = contextvars.ContextVar("nova_operation", default=None)
current_phase = contextvars.ContextVar("nova_phase", default="interactive")


@dataclass
class Operation:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancel: threading.Event = field(default_factory=threading.Event)
    processes: dict = field(default_factory=dict)
    label: str = "generation"
    cleanup: dict = field(default_factory=dict)
    cleanup_errors: list = field(default_factory=list)
    workers: dict = field(default_factory=dict)


class Operations:
    def __init__(self):
        self.active = {}
        self.last_stop = None

    async def run(self, awaitable, label="generation"):
        if current_operation.get() is not None:
            return await awaitable
        op = Operation(label=label)
        token = current_operation.set(op)
        task = asyncio.current_task()
        self.active[op.id] = (op, task)
        try:
            return await awaitable
        finally:
            # A cancelled await does not stop a worker thread. It observes this flag
            # and terminates its process before removing it from the operation.
            op.cancel.set()
            current_operation.reset(token)
            if not op.processes and not op.cleanup and not op.workers:
                self.active.pop(op.id, None)

    def snapshot(self):
        for key, (op, task) in list(self.active.items()):
            for pid, proc in list(op.processes.items()):
                if proc.poll() is not None:
                    op.processes.pop(pid, None)
            if task.done() and not op.processes and not op.cleanup and not op.workers:
                self.active.pop(key, None)
        return [{"id": op.id, "label": op.label,
                 "stop_requested": op.cancel.is_set(),
                 "cleanup_errors": op.cleanup_errors,
                 "guest_operations": list(op.cleanup),
                 "workers": list(op.workers.values()),
                 "process_ids": list(op.processes)} for op, _ in self.active.values()]

    async def stop(self, timeout=5):
        entries = list(self.active.values())
        for op, task in entries:
            op.cancel.set()
            if task is not asyncio.current_task():
                task.cancel()
        deadline = time.monotonic() + timeout
        while self.snapshot() and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        remaining = self.snapshot()
        self.last_stop = {"requested": len(entries), "stopped": not remaining,
                          "remaining": remaining}
        return self.last_stop


operations = Operations()


def supervised(fn):
    @functools.wraps(fn)
    async def wrapped(*args, **kwargs):
        return await operations.run(fn(*args, **kwargs), fn.__name__)
    return wrapped


async def run_in_worker(fn, *args, **kwargs):
    """Keep a worker visible after cancellation of its async caller."""
    op=current_operation.get()
    key=uuid.uuid4().hex
    if op: op.workers[key]=getattr(fn,'__name__','worker')
    def work():
        try:
            if op and op.cancel.is_set():
                raise RuntimeError('Operation cancelled before worker started')
            return fn(*args,**kwargs)
        finally:
            if op: op.workers.pop(key,None)
    future=asyncio.get_running_loop().run_in_executor(None,contextvars.copy_context().run,work)
    # Retrieving exceptions also prevents an abandoned worker's exception going unobserved.
    future.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
    return await asyncio.shield(future)


def run_process(argv, *, cwd=None, timeout=30, startupinfo=None, operation=None,
                binary=False, input_data=None, creationflags=0):
    """Return exit status plus partial output on timeout/cancel; never claim rollback."""
    op = operation or current_operation.get()
    if op and op.cancel.is_set():
        return {"status": "cancelled", "exit_code": None, "stdout": "", "stderr": ""}
    proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.PIPE if input_data is not None else None,
                            text=not binary, encoding=None if binary else "utf-8",
                            errors=None if binary else "replace", startupinfo=startupinfo,
                            creationflags=creationflags,
                            start_new_session=sys.platform != "win32")
    if op:
        op.processes[proc.pid] = proc
    status = None
    deadline = time.monotonic() + timeout
    try:
        while True:
            if op and op.cancel.is_set():
                status = "cancelled"
            elif time.monotonic() >= deadline:
                status = "timed_out"
            if status:
                if op:
                    for name, cleanup in list(op.cleanup.items()):
                        try:
                            cleanup()
                            op.cleanup.pop(name, None)
                        except Exception as e:
                            op.cleanup_errors.append(str(e))
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                   capture_output=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    import os, signal
                    os.killpg(proc.pid, signal.SIGKILL)
                if proc.poll() is None:
                    proc.kill()
                out, err = proc.communicate(timeout=5)
                break
            try:
                out, err = proc.communicate(input=input_data, timeout=min(0.2, max(0.001, deadline-time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                input_data = None
                continue
        return {"status": status or ("succeeded" if proc.returncode == 0 else "failed"),
                "exit_code": proc.returncode, "stdout": out or (b"" if binary else ""), "stderr": err or (b"" if binary else "")}
    finally:
        if op and proc.poll() is not None:
            op.processes.pop(proc.pid, None)
