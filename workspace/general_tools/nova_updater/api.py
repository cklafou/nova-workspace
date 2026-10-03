# @nova: Nova Chat's routes for the model updater (status, decisions, search, inventory, plans, installs, training), answering only this computer's own pages.
"""FastAPI router for the updater. Nova Chat includes it with one line:

    from nova_updater.api import create_router as create_updater_router
    app.include_router(create_updater_router(restart_model=_rt_llama.restart))

and calls `nova_updater.check.start_background_check()` at startup.

These routes can download tens of gigabytes and start paid GPU time, so every one is guarded:
the Host header must name this computer (stops DNS-rebinding pages), a browser Origin must be
local, and the caller must be on loopback. Paid or large actions also need explicit confirms.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from . import catalog, check, install, inventory, jobs, net, plan, runpod, train

LOCAL_NAMES = {"127.0.0.1", "localhost", "::1"}
LOOPBACK_CLIENTS = {"127.0.0.1", "::1"}
PROXY_HEADERS = ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip")


def make_guard(allowed_clients=LOOPBACK_CLIENTS):
    """Same rules as Nova Chat's collaboration routes (nova_chat/collaboration.py).

    Socket on loopback; Host names this computer with an explicit port; no proxy headers (a local
    tunnel would otherwise make remote callers look local); a browser Origin must be exactly this
    server (another local port is a different site); Fetch Metadata must say same-origin or none;
    and every POST must be JSON, so a plain HTML form cannot trigger a download or a paid run.
    """
    def guard(request: Request):
        client = request.client.host if request.client else ""
        if client not in allowed_clients:
            raise HTTPException(403, "The updater is available only on this computer.")
        host = request.headers.get("host", "")
        try:
            parsed = urlsplit("http://" + host)
            valid = parsed.hostname in LOCAL_NAMES and parsed.port is not None
        except ValueError:
            valid = False
        if not valid or any(name in request.headers for name in PROXY_HEADERS):
            raise HTTPException(403, "Direct loopback requests only.")
        origin = request.headers.get("origin")
        if origin and origin != "http://" + host:
            raise HTTPException(403, "The updater rejects cross-origin requests.")
        if request.headers.get("sec-fetch-site") not in (None, "none", "same-origin"):
            raise HTTPException(403, "The updater rejects cross-site requests.")
        if request.method == "POST" and request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise HTTPException(415, "Send application/json.")
    return guard


def _fail(error: Exception) -> JSONResponse:
    if isinstance(error, net.NetError):
        return JSONResponse({"ok": False, "error": str(error)}, status_code=502)
    if isinstance(error, RuntimeError) and "still running" in str(error):
        return JSONResponse({"ok": False, "error": str(error)}, status_code=409)
    return JSONResponse({"ok": False, "error": str(error)}, status_code=400)


EXPECTED = (ValueError, net.NetError, plan.PlanError, train.TrainError, install.InstallError,
            runpod.RunPodError, RuntimeError, FileNotFoundError)


def create_router(restart_model=None, allowed_clients=LOOPBACK_CLIENTS) -> APIRouter:
    """`restart_model()` restarts llama-server and returns {'ok': bool, ...}; None = apply at next start."""
    router = APIRouter(prefix="/api/updater", dependencies=[Depends(make_guard(allowed_clients))])

    async def call(fn, *args, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except EXPECTED as error:
            return _fail(error)

    @router.get("/status")
    async def status():
        def gather():
            out = check.status()
            todo = install.pending()
            out["pending_install"] = ({k: v for k, v in todo.items() if k != "snapshot"} if todo else None)
            out["busy"] = jobs.JOBS.busy()
            out["sources"] = catalog.describe_sources()
            out["settings"] = check.settings()
            out["credentials"] = runpod.credentials_view()
            return out
        return await call(gather)

    @router.post("/check")
    async def run_check(body: dict = Body(default={})):
        return await call(check.run_check, bool((body or {}).get("force", True)))

    @router.post("/decision")
    async def decision(body: dict = Body(...)):
        return await call(check.record_decision, body.get("ids") or [], body.get("decision"), bool(body.get("remember")))

    @router.post("/forget")
    async def forget(body: dict = Body(...)):
        return await call(check.forget_decision, str(body.get("id") or ""))

    @router.post("/settings")
    async def settings(body: dict = Body(...)):
        return await call(check.save_settings, body)

    @router.get("/sources")
    async def sources():
        return catalog.describe_sources()

    @router.get("/search")
    async def search(source: str = "huggingface", q: str = "", author: str = "", min_b: float | None = None,
                     max_b: float | None = None, dense: bool = False, license: str = "", format: str = "",
                     pipeline: str = "", include_quantized: bool = True, sort: str = "created",
                     limit: int = 50, newer: bool = False):
        def work():
            src = catalog.source(source)
            api_sort = {"created": "createdAt", "modified": "lastModified", "downloads": "downloads",
                        "likes": "likes"}.get(sort, "createdAt")
            hits = src.search(q=q, author=author or None, sort=api_sort, limit=max(limit, 50),
                              gguf=(format == "gguf"), pipeline=pipeline or None)
            from . import current
            running = current.current_name() if newer else None
            hits = catalog.filter_hits(hits, min_b=min_b, max_b=max_b, dense_only=dense,
                                       licenses=[x for x in license.split(",") if x] or None,
                                       include_quantized=include_quantized,
                                       formats=[format] if format else None,
                                       newer_than=running)
            ordered = catalog.sort_hits(hits, sort)[: max(1, min(limit, 200))]
            return {"source": source, "count": len(ordered), "results": [h.to_dict() for h in ordered]}
        return await call(work)

    @router.get("/candidate")
    async def candidate(id: str, source: str = "huggingface", gguf_repo: str = ""):
        return await call(plan.describe_candidate, source, id, gguf_repo or None)

    @router.get("/inventory")
    async def get_inventory():
        return await call(inventory.scan)

    @router.post("/plan")
    async def make_plan(body: dict = Body(...)):
        return await call(plan.build, body)

    @router.post("/install")
    async def start_install(body: dict = Body(...)):
        def work():
            the_plan = plan.load(str(body.get("plan_id") or ""))
            train_confirm = body.get("train_confirm")
            after = _training_chain(train_confirm) if the_plan.get("training") else None
            job = install.start(the_plan["id"], body.get("confirm") is True, restart=restart_model, after=after)
            return job.to_dict()
        return await call(work)

    @router.get("/jobs")
    async def list_jobs():
        return jobs.JOBS.recent()

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        found = jobs.JOBS.get(job_id)
        return found if found else JSONResponse({"ok": False, "error": "No such job"}, status_code=404)

    @router.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        return {"ok": jobs.JOBS.cancel(job_id)}

    @router.post("/finish")
    async def finish():
        return await call(install.finish_pending)

    @router.post("/rollback")
    async def rollback():
        return await call(install.rollback_pending)

    @router.post("/train/preview")
    async def train_preview(body: dict = Body(...)):
        def work():
            spec = train.prepare_spec(body.get("spec") or {})
            if spec["runner"] == "runpod":
                spec["cost"] = runpod.RunPodRunner.from_credentials(spec).estimate(spec)
            return spec
        return await call(work)

    @router.post("/train")
    async def start_training(body: dict = Body(...)):
        def work():
            return train.start(body.get("spec") or {}, body.get("confirm")).to_dict()
        return await call(work)

    @router.post("/train/install")
    async def install_trained(body: dict = Body(...)):
        def work():
            spec = train.prepare_spec(body.get("spec") or {})
            from pathlib import Path
            from . import paths
            folder = Path(str(body.get("folder") or ""))
            folder = folder if folder.is_absolute() else paths.workspace() / folder
            return train.install_outputs(spec, folder)
        return await call(work)

    @router.post("/lora/activate")
    async def activate(body: dict = Body(...)):
        def work():
            line = train.activate_lora(str(body.get("path") or ""), float(body.get("scale", 1.0)))
            restarted = restart_model() if (restart_model and body.get("restart")) else None
            return {"ok": True, "boot_line": line, "restart": restarted}
        return await call(work)

    @router.get("/credentials")
    async def get_credentials():
        return runpod.credentials_view()

    @router.post("/credentials")
    async def set_credentials(body: dict = Body(...)):
        return await call(runpod.save_credentials, body)

    return router


def _training_chain(confirm):
    """Train right after a verified model install, inside the same job (one job at a time)."""
    def after(job, the_plan, result):
        spec = the_plan["training"]
        if spec["runner"] == "export":
            return train.export(spec)
        if not result.get("installed"):
            return {"skipped": "model files were not installed"}
        runner = runpod.RunPodRunner.from_credentials(spec)
        estimate = runner.estimate(spec)
        if not isinstance(confirm, dict) or float(confirm.get("max_cost_usd", -1)) < estimate["cost_usd"]:
            return {"skipped": f"training needs a confirmed cost ceiling of at least ${estimate['cost_usd']:.2f}"}
        runner.max_cost_usd = float(confirm["max_cost_usd"])
        outcome = train.run(spec, job, runner)
        if spec.get("activate") and outcome.get("pick"):
            outcome["boot_line"] = train.activate_lora(outcome["pick"], spec.get("scale", 1.0))
        return outcome
    return after
