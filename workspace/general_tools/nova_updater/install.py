# @nova: Executes an install plan: resumable verified downloads, model switch with a real load check and rollback, then trash quarantine of what it replaced.
"""Carry out a confirmed plan.

Order matters, and every step can be undone until the last:
  1. Download each file to models/.incoming/<name>.part (resumes), verify size + sha256,
     then rename into models/<family>/.
  2. Switch the boot files (active_model.txt, active_mmproj.txt, and active_lora.txt when the
     old personality LoRA belongs to another base) after saving their exact old text.
  3. Restart the model server and confirm the NEW file is the one loaded (llama-server /props),
     not merely that something answers /health. If not, restore the old boot files and restart.
  4. Only after (3) succeeds, move replaced files to _admin/Trash/<stamp>_model_update/ with a
     manifest. Nothing is ever deleted. If the model server is not running (chat-only mode),
     (3)-(4) wait for `finish_pending()` after the next model start.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

from . import current, jobs, naming, net, paths, store

CHUNK = 4 * 1024 * 1024


class InstallError(RuntimeError):
    pass


def _abs(rel: str) -> Path:
    path = Path(rel)
    return path if path.is_absolute() else paths.workspace() / rel


def launcher_path(rel: str) -> str:
    """The launcher runs from the workspace with Windows paths."""
    return rel.replace("/", "\\")


def write_boot(name: str, text: str | None) -> None:
    target = paths.boot_file(name)
    if text is None:
        if target.exists():
            target.unlink()
        return
    store.atomic_write_text(target, text if text.endswith("\n") else text + "\r\n", newline="")


def _hash_file(path: Path, job: jobs.Job | None) -> "hashlib._Hash":
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                return digest
            digest.update(block)
            if job:
                job.check_cancel()


def download(item: dict, job: jobs.Job, opener=net.open_stream, headers=None) -> Path:
    dest = _abs(item["dest"])
    size, expected = item.get("size"), (item.get("sha256") or "").lower() or None
    if dest.is_file() and size is not None and dest.stat().st_size == size:
        job.say(f"{dest.name}: already present ({size / 1024**3:.2f} GiB)")
        if expected:
            job.set_step(f"Verifying {dest.name}")
            if _hash_file(dest, job).hexdigest() != expected:
                raise InstallError(f"{dest.name} is present but its sha256 does not match the published one.")
        job.add_progress(size)
        return dest
    staging = paths.staging_dir()
    staging.mkdir(parents=True, exist_ok=True)
    part = staging / (dest.name + ".part")
    start = part.stat().st_size if part.exists() else 0
    if size is not None and start > size:
        os.replace(part, part.with_suffix(".part.bad"))
        start = 0
    digest = _hash_file(part, job) if start else hashlib.sha256()
    job.set_step(f"Downloading {dest.name}" + (f" (resuming at {start / 1024**3:.2f} GiB)" if start else ""))
    response, resumed = opener(item["url"], start, headers)
    if start and not resumed:
        job.say("Server ignored the resume request; starting this file over.")
        start, digest = 0, hashlib.sha256()
    job.add_progress(start)
    try:
        with open(part, "ab" if start else "wb") as handle:
            while True:
                job.check_cancel()
                block = response.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                job.add_progress(len(block))
    finally:
        response.close()
    got = part.stat().st_size
    if size is not None and got != size:
        raise InstallError(f"{dest.name}: got {got} bytes, expected {size}. Run the update again to resume.")
    if expected and digest.hexdigest() != expected:
        os.replace(part, part.with_suffix(".part.bad"))
        raise InstallError(f"{dest.name}: sha256 mismatch; the download was set aside as .part.bad.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(part, dest)
    job.say(f"{dest.name}: verified and installed")
    return dest


def loaded_model(port: int = 8080, timeout: float = 3.0) -> str | None:
    """File name llama-server reports as loaded (via /props), or None if it is not answering."""
    for route in ("/props", "/v1/models"):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=timeout) as response:
                data = json.loads(response.read(1 << 20).decode("utf-8"))
        except Exception:
            continue
        path = data.get("model_path") if isinstance(data, dict) else None
        if not path and isinstance(data, dict) and data.get("data"):
            path = (data["data"][0] or {}).get("id")
        if path:
            return Path(str(path).replace("\\", "/")).name
    return None


def wait_until_loaded(expected_name: str, timeout: float = 900.0, poll: float = 5.0, probe=loaded_model,
                      job: jobs.Job | None = None) -> tuple:
    deadline = time.monotonic() + timeout
    seen = None
    while time.monotonic() < deadline:
        if job:
            job.check_cancel()
        seen = probe()
        if seen and seen.lower() == expected_name.lower():
            return True, seen
        time.sleep(max(0.0, min(poll, deadline - time.monotonic())))
    return False, seen


def quarantine(rel_paths, label: str = "model_update", plan_id: str = "") -> dict:
    """Move files into _admin/Trash/<stamp>_<label>/ keeping their relative paths. Never deletes."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    root = paths.trash_root() / f"{stamp}_{label}"
    moved, problems = [], []
    for rel in rel_paths:
        source = _abs(rel)
        if not source.exists():
            problems.append(f"{rel}: already gone")
            continue
        target = root / Path(rel.replace("\\", "/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(source, target)
        except OSError:
            shutil.move(str(source), str(target))
        moved.append({"from": rel, "to": paths.display(target)})
    if moved or problems:
        root.mkdir(parents=True, exist_ok=True)
        store.atomic_write_text(root / "manifest.json", json.dumps(
            {"plan": plan_id, "at": store.now_iso(), "moved": moved, "problems": problems,
             "restore": "Move each 'to' back to its 'from' path."}, indent=2) + "\n")
    return {"folder": paths.display(root), "moved": moved, "problems": problems}


def _switch_boot(plan: dict, job: jobs.Job) -> dict:
    snapshot = current.snapshot_boot_files()
    old_folder = current.active_model().get("folder") or ""
    write_boot("active_model.txt", launcher_path(plan["boot"]["model"]))
    write_boot("active_mmproj.txt", launcher_path(plan["boot"]["mmproj"]) if plan["boot"].get("mmproj") else "none")
    mode = (plan.get("lora") or {}).get("mode", "none")
    if mode in ("none", "train"):
        write_boot("active_lora.txt", "none")
        job.say("Personality LoRA off until one trained for this model is installed.")
    if snapshot.get("koels_lora_args.txt") and plan.get("family") != old_folder:
        write_boot("koels_lora_args.txt", None)
        job.say("KoELS specialist adapters cleared: they were trained for the previous base model.")
    job.say(f"Boot files now point at {plan['boot']['model']}")
    return snapshot


def _restore_boot(snapshot: dict) -> None:
    for name, text in snapshot.items():
        write_boot(name, text)


def execute(plan: dict, job: jobs.Job, restart=None, probe=loaded_model, opener=net.open_stream,
            headers=None, load_timeout: float = 900.0, poll: float = 5.0) -> dict:
    if plan.get("blocking"):
        raise InstallError("This plan has blocking problems: " + "; ".join(plan["blocking"]))
    total = sum(d.get("size") or 0 for d in plan["downloads"])
    job.set_progress(0, total)
    installed = [paths.display(download(item, job, opener, headers)) for item in plan["downloads"]]
    result = {"installed": installed, "activated": False, "verified": False, "quarantine": None,
              "pending": None}
    if not plan.get("activate"):
        job.set_step("Downloaded. Nova still runs her current model (activate was off).")
        return result
    job.set_step("Switching Nova's boot files")
    snapshot = _switch_boot(plan, job)
    result["activated"] = True
    expected = Path(plan["boot"]["model"]).name
    if restart is None:
        _remember_pending(plan, snapshot)
        result["pending"] = "Takes effect the next time Nova's model starts; replaced files move to trash after that."
        job.set_step(result["pending"])
        return result
    job.set_step("Restarting the model server")
    try:
        outcome = restart() or {}
    except Exception as error:  # a crashing restart must not leave the new boot files in place
        _restore_boot(snapshot)
        raise InstallError(f"Restart raised {type(error).__name__}: {error}; the previous boot files are "
                           "restored. Start the model again to load the previous model.") from None
    if outcome.get("ok") is False:
        if outcome.get("chat_only"):
            _remember_pending(plan, snapshot)
            result["pending"] = "Nova is in chat-only mode; the new model loads at her next full start."
            job.set_step(result["pending"])
            return result
        _restore_boot(snapshot)
        raise InstallError(f"Restart failed ({outcome.get('error') or outcome}); the previous model is restored.")
    job.set_step(f"Waiting for {expected} to load")
    try:
        ok, seen = wait_until_loaded(expected, load_timeout, poll=poll, probe=probe, job=job)
    except jobs.Cancelled:
        job.set_step("Cancelled while the new model was loading; restoring the previous one")
        _restore_boot(snapshot)
        _restart_quietly(restart, job)
        raise
    if not ok:
        job.set_step("New model did not load; restoring the previous one")
        _restore_boot(snapshot)
        back = _restart_quietly(restart, job)
        raise InstallError(f"llama-server did not load {expected} (it reports {seen or 'nothing'}). "
                           "The previous boot files are restored and the new files stay installed. "
                           + ("The previous model is restarting." if back else
                              "Restarting the previous model FAILED; start it from Services."))
    result["verified"] = True
    job.set_step(f"Loaded: {seen}")
    if plan.get("replace"):
        job.set_step("Moving replaced files to trash quarantine")
        result["quarantine"] = quarantine(plan["replace"], "model_update", plan.get("id", ""))
    return result


def _restart_quietly(restart, job: jobs.Job) -> bool:
    """Restart during a rollback; report rather than raise, the rollback itself already happened."""
    try:
        outcome = restart() or {}
    except Exception as error:
        job.say(f"Restart during rollback raised {type(error).__name__}: {error}")
        return False
    if outcome.get("ok") is False:
        job.say(f"Restart during rollback failed: {outcome.get('error') or outcome}")
        return False
    return True


def _remember_pending(plan: dict, snapshot: dict) -> None:
    def keep(data):
        data["pending"] = {"plan": plan["id"], "expected": Path(plan["boot"]["model"]).name,
                           "replace": plan.get("replace") or [], "snapshot": snapshot, "at": store.now_iso()}
    store.mutate(keep)


def pending() -> dict | None:
    return store.load().get("pending")


def finish_pending(probe=loaded_model) -> dict:
    """After the next model start: confirm the new model is the one loaded, then quarantine."""
    todo = pending()
    if not todo:
        return {"state": "nothing-pending"}
    seen = probe()
    if not seen:
        return {"state": "waiting", "message": "The model server is not answering yet."}
    if seen.lower() != todo["expected"].lower():
        return {"state": "mismatch", "message": f"Nova loaded {seen}, not {todo['expected']}. Nothing was moved."}
    moved = quarantine(todo["replace"], "model_update", todo["plan"]) if todo.get("replace") else None

    def clear(data):
        data.pop("pending", None)
    store.mutate(clear)
    return {"state": "finished", "loaded": seen, "quarantine": moved}


def rollback_pending() -> dict:
    """Undo a switch that has not been verified yet."""
    todo = pending()
    if not todo:
        return {"state": "nothing-pending"}
    _restore_boot(todo["snapshot"])

    def clear(data):
        data.pop("pending", None)
    store.mutate(clear)
    return {"state": "restored", "message": "Boot files restored; restart Nova's model to load the previous one."}


def start(plan_id: str, confirm: bool, restart=None, after=None, **execute_options):
    """Start an install job for a stored plan. `after(job, result)` can chain training."""
    from . import plan as planner
    if confirm is not True:
        raise InstallError("Installing downloads tens of gigabytes; confirm it explicitly.")
    the_plan = planner.load(plan_id)

    def work(job):
        result = execute(the_plan, job, restart=restart, **execute_options)
        if after:
            # Training is a separate outcome: its failure or cancellation must not mark a verified
            # model install as failed (the RunPod runner has already stopped the pod by now).
            try:
                result["after"] = after(job, the_plan, result)
            except jobs.Cancelled:
                result["after"] = {"cancelled": True}
                job.say("Training cancelled; the model install itself is complete.")
            except Exception as error:
                result["after"] = {"error": f"{error}" or type(error).__name__}
                job.say(f"Training failed: {error}. The model install itself is complete.")
        return result
    return jobs.JOBS.start("install", f"Install {the_plan['model_id']} ({the_plan['quant']})", work)
