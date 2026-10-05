# Last updated: 2026-10-05 18:23:37
# @nova: Lightweight update check run at each Nova Chat start: one catalog query, cached, never blocking the app or raising.
"""Is there a newer dense model in Nova's size class?

Startup calls `start_background_check()`. It runs on a daemon thread, makes at most one catalog
request (cached for `ttl_hours`), and records the result for `GET /api/updater/status`.
A failure (offline, rate-limited) is recorded as a state, never raised into Nova Chat.

A candidate must be: the same family as the running model (Qwen), a higher version, dense
(no MoE, not a quantized or base-only variant), 27-32B by name, and permissively licensed
(Apache-2.0/MIT by default - Cole's licensing rule for Nova's weights).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading

from . import catalog, current, naming, net, store

DEFAULTS = {
    "enabled": True,
    "ttl_hours": 12,
    "min_b": 27,
    "max_b": 32,
    "licenses": list(catalog.PERMISSIVE),
    "source": "huggingface",
    "authors": ["Qwen"],
    "timeout": 6,
}
_session_declined: set = set()
_running = threading.Lock()


def settings() -> dict:
    saved = store.load().get("settings") or {}
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in saved.items() if k in DEFAULTS})
    return merged


def save_settings(changes: dict) -> dict:
    clean = {k: v for k, v in (changes or {}).items() if k in DEFAULTS}

    def apply(data):
        data.setdefault("settings", {}).update(clean)
        return dict(DEFAULTS, **data["settings"])

    return store.mutate(apply)


def evaluate(hits, running: naming.ModelName | None, decisions: dict, cfg: dict) -> list:
    """Pure: turn catalog hits into update candidates for the running model."""
    if running is None:
        return []
    pool = catalog.filter_hits(hits, min_b=cfg["min_b"], max_b=cfg["max_b"], dense_only=True,
                               licenses=cfg["licenses"] or None, include_quantized=False,
                               pipelines={"text-generation", "image-text-to-text", ""},
                               family=running.family, newer_than=running)
    out = []
    for hit in pool:
        parsed = naming.parse(hit.id)
        if not parsed or not parsed.dense_chat:
            continue
        if hit.params and not (cfg["min_b"] - 1.5 <= hit.params / 1e9 <= cfg["max_b"] + 2.0):
            continue  # name says 27-32B but the weights disagree; skip rather than guess
        decision = decisions.get(hit.id) or {}
        out.append({"id": hit.id, "source": hit.source, "version": parsed.version_text,
                    "size_b": parsed.size_b, "params_b": round(hit.params / 1e9, 2) if hit.params else None,
                    "created": hit.created, "license": hit.license, "gated": hit.gated, "url": hit.url,
                    "pipeline": hit.pipeline, "slug": parsed.slug,
                    "remembered": decision.get("decision") if decision.get("remember") else None})
    out.sort(key=lambda c: (naming._key(naming.parse(c["id"])), c["created"]), reverse=True)
    return out


def _fresh(entry: dict, ttl_hours: float, running_label) -> bool:
    try:
        when = datetime.fromisoformat(entry["checked_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return (entry.get("current_label") == running_label
            and datetime.now(timezone.utc) - when < timedelta(hours=float(ttl_hours)))


def _with_decisions(result: dict, decisions: dict) -> dict:
    for cand in result.get("candidates", []):
        decision = decisions.get(cand["id"]) or {}
        cand["remembered"] = decision.get("decision") if decision.get("remember") else None
    pending = [c for c in result.get("candidates", [])
               if not c.get("remembered") and c["id"] not in _session_declined]
    result["notify"] = bool(pending) and result.get("state") == "ok"
    result["pending"] = [c["id"] for c in pending]
    return result


def run_check(force: bool = False, src=None) -> dict:
    """Check now (or return the cached answer). Never raises."""
    cfg = settings()
    model = current.active_model()
    running = naming.parse(model["label"]) if model.get("label") else None
    data = store.load()
    decisions = data.get("decisions") or {}
    cached = data.get("check") or {}
    if not cfg.get("enabled", True):
        return {"state": "disabled", "current": model, "candidates": [], "notify": False, "pending": []}
    if not force and _fresh(cached, cfg["ttl_hours"], model.get("label")):
        return _with_decisions(dict(cached), decisions)
    if not _running.acquire(blocking=False):
        return _with_decisions(dict(cached, state="checking"), decisions)
    try:
        result = {"checked_at": store.now_iso(), "current": model, "current_label": model.get("label"),
                  "source": cfg["source"], "candidates": [], "state": "ok", "message": ""}
        if running is None:
            result.update(state="unknown-current",
                          message="Could not tell which model Nova runs, so there is nothing to compare.")
        else:
            try:
                source = src or catalog.source(cfg["source"])
                hits = []
                for author in cfg["authors"] or [running.org or running.family]:
                    hits += source.search(author=author, sort="createdAt", limit=100, timeout=cfg["timeout"])
                result["candidates"] = evaluate(hits, running, decisions, cfg)
                if not result["candidates"]:
                    result["message"] = f"{running.label} is the newest {cfg['min_b']}-{cfg['max_b']}B dense model found."
            except (net.NetError, ValueError) as error:
                previous = cached.get("candidates") or []
                result.update(state="offline", message=str(error), candidates=previous)
            except Exception as error:  # a check must never break Nova Chat
                result.update(state="error", message=f"{type(error).__name__}: {error}",
                              candidates=cached.get("candidates") or [])

        def write(state):
            state["check"] = result
        store.mutate(write)
        return _with_decisions(dict(result), decisions)
    finally:
        _running.release()


def start_background_check(delay: float = 3.0) -> threading.Thread:
    """Fire-and-forget for Nova Chat startup."""
    def work():
        import time
        time.sleep(max(0.0, delay))
        try:
            run_check()
        except Exception:
            pass
    thread = threading.Thread(target=work, name="nova-updater-check", daemon=True)
    thread.start()
    return thread


def status() -> dict:
    data = store.load()
    result = dict(data.get("check") or {"state": "never-checked", "candidates": []})
    checked_current = result.get("current")
    result["current"] = current.active_model()
    result["checked_current"] = checked_current
    result["catalog_stale"] = bool(checked_current and checked_current.get("label") != result["current"].get("label"))
    out = _with_decisions(result, data.get("decisions") or {})
    if out["catalog_stale"]:
        # A cached comparison is not evidence that the newly configured model needs updating.
        out["notify"], out["pending"] = False, []
    if store.problem():
        out["warning"] = store.problem()
    return out


def record_decision(ids, decision: str, remember: bool) -> dict:
    """Update / Decline from the notification. `remember` silences future prompts for these versions."""
    if decision not in ("update", "decline"):
        raise ValueError("decision must be 'update' or 'decline'")
    ids = [i for i in (ids or []) if isinstance(i, str) and i]
    if not ids:
        raise ValueError("choose at least one version")

    def apply(data):
        book = data.setdefault("decisions", {})
        for model_id in ids:
            if remember:
                book[model_id] = {"decision": decision, "remember": True, "at": store.now_iso()}
            else:
                book.pop(model_id, None)
        return book

    store.mutate(apply)
    if decision == "decline" and not remember:
        _session_declined.update(ids)
    return status()


def forget_decision(model_id: str) -> dict:
    def apply(data):
        (data.get("decisions") or {}).pop(model_id, None)
    store.mutate(apply)
    _session_declined.discard(model_id)
    return status()
