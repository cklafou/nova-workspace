# Last updated: 2026-10-04 14:55:32
# @nova: Runs long updater work (downloads, installs, training) on background threads with progress, logs, cancellation and a one-at-a-time lock.
"""Background jobs for the updater.

Only one install or training job runs at a time: two jobs writing boot files or the models
folder at once is how a machine ends up half-updated. Finished jobs are summarised into the
updater state so the widget can still show them after a restart.
"""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import threading
import time
import uuid

from . import store

KEEP_HISTORY = 20


class Cancelled(Exception):
    pass


class Conflict(RuntimeError):
    """The request clashes with work in progress or with what the user reviewed (HTTP 409)."""


class Job:
    def __init__(self, kind: str, title: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind, self.title = kind, title
        self.state, self.step = "queued", ""
        self.done, self.total = 0, 0
        self.log = deque(maxlen=400)
        self.result, self.error = None, None
        self.runpod_cost = None
        self.started = self.finished = None
        self.cancel_event = threading.Event()
        self._lock = threading.Lock()

    def say(self, text: str) -> None:
        with self._lock:
            self.log.append(f"{time.strftime('%H:%M:%S')}  {text}")

    def set_step(self, step: str) -> None:
        with self._lock:
            self.step = step
        self.say(step)

    def add_progress(self, amount: int = 0, total: int | None = None) -> None:
        with self._lock:
            if total is not None:
                self.total = int(total)
            self.done += int(amount)

    def set_progress(self, done: int, total: int | None = None) -> None:
        with self._lock:
            self.done = int(done)
            if total is not None:
                self.total = int(total)

    def set_runpod_cost(self, cost: dict) -> None:
        """Keep live wallet/GPU estimates in snapshots and final history, including failed jobs."""
        with self._lock:
            self.runpod_cost = dict(cost)

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled("Cancelled by the user")

    def to_dict(self, log_lines: int = 60) -> dict:
        with self._lock:
            return {"id": self.id, "kind": self.kind, "title": self.title, "state": self.state,
                    "step": self.step, "done": self.done, "total": self.total,
                    "percent": round(100.0 * self.done / self.total, 1) if self.total else None,
                    "log": list(self.log)[-log_lines:], "result": self.result, "error": self.error,
                    "started": self.started, "finished": self.finished,
                    "runpod_cost": dict(self.runpod_cost) if self.runpod_cost is not None else None}


class Jobs:
    def __init__(self):
        self._jobs: dict = {}
        self._guard = threading.Lock()
        self._busy: Job | None = None

    def busy(self) -> dict | None:
        with self._guard:
            return self._busy.to_dict(5) if self._busy else None

    def start(self, kind: str, title: str, work, exclusive: bool = True, background: bool = True) -> Job:
        job = Job(kind, title)
        with self._guard:
            if exclusive and self._busy is not None:
                raise Conflict(f"'{self._busy.title}' is still running; wait for it or cancel it first.")
            if exclusive:
                self._busy = job
            self._jobs[job.id] = job

        def run():
            job.state, job.started = "running", store.now_iso()
            try:
                job.result = work(job)
                job.state = "succeeded"
            except Cancelled as error:
                job.state, job.error = "cancelled", str(error)
            except Exception as error:
                job.state, job.error = "failed", f"{error}" if str(error) else type(error).__name__
                job.say(f"FAILED: {job.error}")
            finally:
                job.finished = store.now_iso()
                with self._guard:
                    if self._busy is job:
                        self._busy = None
                self._remember(job)

        if background:
            threading.Thread(target=run, name=f"nova-updater-{kind}", daemon=True).start()
        else:
            run()
        return job

    @contextmanager
    def exclusive(self, title: str):
        """Hold the one-at-a-time slot for a short synchronous step (finish, rollback). The busy check
        and taking the slot are one atomic step, so the step can neither run beside a live install
        nor let an install start halfway through it."""
        holder = Job("recovery", title)
        holder.state, holder.started = "running", store.now_iso()
        with self._guard:
            if self._busy is not None:
                raise Conflict(f"'{self._busy.title}' is still running; wait for it or cancel it first.")
            self._busy = holder
        try:
            yield holder
        finally:
            with self._guard:
                if self._busy is holder:
                    self._busy = None

    def _remember(self, job: Job) -> None:
        summary = job.to_dict(log_lines=40)

        def keep(data):
            history = data.setdefault("jobs", [])
            history.append(summary)
            del history[:-KEEP_HISTORY]
        try:
            store.mutate(keep)
        except OSError:
            pass

    def get(self, job_id: str) -> dict | None:
        with self._guard:
            job = self._jobs.get(job_id)
        if job:
            return job.to_dict()
        for summary in reversed(store.load().get("jobs") or []):
            if summary.get("id") == job_id:
                return summary
        return None

    def cancel(self, job_id: str) -> bool:
        with self._guard:
            job = self._jobs.get(job_id)
        if not job or job.state not in ("queued", "running"):
            return False
        job.cancel_event.set()
        job.say("Cancel requested; stopping at the next safe point.")
        return True

    def recent(self) -> list:
        with self._guard:
            live = [j.to_dict(10) for j in self._jobs.values()]
        ids = {j["id"] for j in live}
        old = [j for j in (store.load().get("jobs") or []) if j.get("id") not in ids]
        return sorted(live + old, key=lambda j: j.get("started") or "", reverse=True)[:KEEP_HISTORY]


JOBS = Jobs()
