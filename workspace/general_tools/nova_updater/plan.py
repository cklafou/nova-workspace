# @nova: Turns a chosen model, files and replacements into a checked install plan: sizes, disk space, compatibility, invalidated LoRAs and training.
"""Install plans (a dry run the user confirms).

`build(request)` does every check that does not change anything and returns a plan with an id.
`install.execute(plan_id)` later does exactly what the plan says. Nothing here downloads,
moves or deletes.

request = {
  "source": "huggingface",                 # where the GGUF files come from
  "model_id": "Qwen/Qwen3.8-27B",          # the base model (for naming, compatibility, training)
  "gguf_repo": "unsloth/Qwen3.8-27B-GGUF", # optional; picked automatically if omitted
  "quant": "UD-Q6_K_XL",                   # optional; defaults to what Nova runs today
  "mmproj": true,                          # include the vision projector (default: if Nova uses one)
  "activate": true,                        # switch Nova to it after download (else download only)
  "replace": ["models/qwen3.6/..."],       # files to move to trash quarantine after success
  "lora": {"mode": "none"|"keep"|"train", "train": {...}}  # personality LoRA handling
}
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import catalog, current, inventory, naming, net, paths, store

PUBLISHER_ORDER = ("unsloth", "ggml-org", "Qwen", "bartowski", "lmstudio-community")
MARGIN_BYTES = 5 * 1024 ** 3
PLAN_TTL_HOURS = 24


class PlanError(ValueError):
    pass


def _build_name(repo_id: str) -> str:
    """'bartowski/Qwen_Qwen3.8-27B-GGUF' -> 'qwen3.8-27b' (publisher prefixes and -GGUF removed)."""
    name = repo_id.split("/")[-1].lower()
    if name.endswith("-gguf"):
        name = name[:-5]
    owner_prefix = repo_id.split("/")[0].lower() + "_"
    for prefix in ("qwen_", owner_prefix):
        if name.startswith(prefix) and name[len(prefix):].startswith("qwen"):
            name = name[len(prefix):]
    return name


def gguf_sources(model_id: str, src, prefer: str | None = None, limit: int = 40) -> list:
    """GGUF builds of exactly `model_id` on `src` (no fine-tunes), best publisher first."""
    label = model_id.split("/")[-1]
    hits = src.search(q=label, gguf=True, limit=limit, sort="downloads")
    builds = [h for h in hits if _build_name(h.id) == label.lower()
              and ("gguf" in h.formats or h.id.lower().endswith("-gguf"))]
    order = ([prefer] if prefer else []) + [p for p in PUBLISHER_ORDER if p != prefer]

    def rank(hit):
        owner = hit.id.split("/")[0]
        pos = order.index(owner) if owner in order else len(order)
        return (pos, -(hit.downloads or 0))
    return sorted(builds, key=rank)


def gguf_options(files) -> dict:
    """Group GGUF files into quant choices (split parts together) and projectors."""
    quants, projectors = {}, []
    for f in files:
        if not f.path.lower().endswith(".gguf"):
            continue
        info = naming.parse_gguf_filename(f.path)
        if info["mmproj"]:
            projectors.append(f)
            continue
        label = info["quant"] or info["stem"]
        bucket = quants.setdefault(label, {"label": label, "files": [], "size": 0})
        bucket["files"].append(f)
        bucket["size"] += f.size or 0
    for bucket in quants.values():
        bucket["files"].sort(key=lambda f: f.path)
    return {"quants": quants, "projectors": projectors}


def pick_projector(projectors, preferred: str | None = None):
    """The vision projector to pair with the model: the same file name as today, else F16 > BF16 > Q8_0."""
    if not projectors:
        return None
    names = {p.path.split("/")[-1].lower(): p for p in projectors}
    if preferred and preferred.lower() in names:
        return names[preferred.lower()]
    for ending in ("-f16.gguf", "-bf16.gguf", "-q8_0.gguf"):
        for name, proj in sorted(names.items()):
            if name.endswith(ending):
                return proj
    return max(projectors, key=lambda p: p.size or 0)


def describe_candidate(source: str, model_id: str, gguf_repo: str | None = None) -> dict:
    """Everything the dialog needs to offer choices for one model."""
    src = catalog.source(source)
    if not getattr(src, "installable", False):
        raise PlanError(f"{src.title} models cannot be installed from here.")
    running = current.active_model()
    builds = []
    if gguf_repo:
        builds = [gguf_repo]
    else:
        own = src.files(model_id)
        if any(f.path.lower().endswith(".gguf") for f in own):
            builds = [model_id]
        builds += [h.id for h in gguf_sources(model_id, src, running.get("publisher_hint"))]
    seen, options = set(), []
    for repo in builds:
        if repo in seen:
            continue
        seen.add(repo)
        try:
            grouped = gguf_options(src.files(repo))
        except net.NetError as error:
            options.append({"repo": repo, "error": str(error)})
            continue
        options.append({"repo": repo,
                        "quants": [{"label": q["label"], "size": q["size"],
                                    "files": [f.to_dict() for f in q["files"]]} for q in grouped["quants"].values()],
                        "projectors": [p.to_dict() for p in grouped["projectors"]]})
        if len(options) >= 6:
            break
    return {"source": source, "model_id": model_id, "current": running, "builds": options,
            "suggested": _suggest(options, running)}


def _suggest(options, running) -> dict | None:
    """Like-for-like: same quant and projector style as today, from the first build that has them."""
    for option in options:
        quants = {q["label"].lower(): q for q in option.get("quants", [])}
        want = (running.get("quant") or "").lower()
        if want and want in quants:
            proj = pick_projector([catalog.FileInfo(**p) for p in option["projectors"]],
                                  Path(running.get("mmproj_path") or "").name or None)
            return {"gguf_repo": option["repo"], "quant": quants[want]["label"],
                    "mmproj": proj.path if proj else None}
    for option in options:
        for label in ("Q6_K", "Q5_K_M", "Q4_K_M"):
            for q in option.get("quants", []):
                if q["label"].lower().endswith(label.lower()):
                    proj = pick_projector([catalog.FileInfo(**p) for p in option["projectors"]])
                    return {"gguf_repo": option["repo"], "quant": q["label"], "mmproj": proj.path if proj else None}
    return None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build(request: dict, src=None, inv: dict | None = None, disk_usage=shutil.disk_usage) -> dict:
    source = request.get("source") or "huggingface"
    src = src or catalog.source(source)
    model_id = (request.get("model_id") or "").strip()
    parsed = naming.parse(model_id)
    if not parsed:
        raise PlanError("Choose a model whose name includes its size, like Qwen/Qwen3.8-27B.")
    running = current.active_model()
    gguf_repo = request.get("gguf_repo") or None
    quant = request.get("quant") or running.get("quant")
    if not gguf_repo:
        found = gguf_sources(model_id, src, running.get("publisher_hint"))
        if not found:
            raise PlanError(f"No GGUF build of {parsed.label} was found on {src.title}.")
        gguf_repo = found[0].id
    grouped = gguf_options(src.files(gguf_repo))
    if not grouped["quants"]:
        raise PlanError(f"{gguf_repo} has no GGUF model files.")
    choice = None
    for label, bucket in grouped["quants"].items():
        if quant and label.lower() == quant.lower():
            choice = bucket
    if choice is None:
        raise PlanError(f"{gguf_repo} has no {quant} build. Available: {', '.join(sorted(grouped['quants']))}")
    want_proj = request.get("mmproj")
    if want_proj is None:
        want_proj = bool(running.get("mmproj_path"))
    projector = None
    if want_proj:
        preferred = want_proj if isinstance(want_proj, str) else Path(running.get("mmproj_path") or "").name or None
        projector = pick_projector(grouped["projectors"], preferred)
    models_root = paths.models_root()
    target_dir = models_root / (request.get("folder") or parsed.slug)
    if not _inside(target_dir, models_root):
        raise PlanError("The install folder must be inside the models folder.")
    downloads = []
    for f in choice["files"] + ([projector] if projector else []):
        name = f.path.split("/")[-1]
        dest = target_dir / name
        present = dest.is_file() and f.size is not None and dest.stat().st_size == f.size
        downloads.append({"path": f.path, "name": name, "size": f.size, "sha256": f.sha256,
                          "url": src.download_url(gguf_repo, f.path), "dest": paths.display(dest),
                          "present": present})
    need = sum((d["size"] or 0) for d in downloads if not d["present"])
    free = disk_usage(models_root if models_root.exists() else models_root.parent).free
    blocking, warnings = [], []
    if need + MARGIN_BYTES > free:
        blocking.append(f"Needs {need / 1024**3:.1f} GiB plus a 5 GiB margin; only {free / 1024**3:.1f} GiB free.")
    if any(d["sha256"] is None for d in downloads):
        warnings.append("Some files have no published sha256; they will be size-checked only.")
    inv = inv if inv is not None else inventory.scan()
    replace = []
    for item in request.get("replace") or []:
        rel = str(item).replace("\\", "/")
        full = (paths.workspace() / rel) if not Path(rel).is_absolute() else Path(rel)
        if not _inside(full, models_root):
            raise PlanError(f"{rel} is outside the models folder; only installed models and LoRAs can be replaced.")
        if not full.exists():
            raise PlanError(f"{rel} does not exist.")
        if any(paths.display(full) == d["dest"] for d in downloads):
            raise PlanError(f"{rel} is one of the files being installed.")
        replace.append(paths.display(full))
    invalid = inventory.invalidated_by(parsed.slug, inv)
    activate = bool(request.get("activate", True))
    lora = request.get("lora") or {"mode": "none"}
    if lora.get("mode") not in ("none", "keep", "train"):
        raise PlanError("lora.mode must be none, keep or train")
    if activate and lora["mode"] == "keep":
        stale = [l for l in invalid if l["active"] and l["kind"] == "lora"]
        if stale:
            warnings.append("The active personality LoRA was trained for another base model; keeping it "
                            "would load without error and behave wrongly. Choose 'train' or 'none'.")
    training = None
    if lora["mode"] == "train":
        from . import train
        spec = dict(lora.get("train") or {})
        spec.setdefault("base_model_id", train.training_base_for(model_id, src))
        spec["base_family"] = parsed.slug
        training = train.prepare_spec(spec)
    compat = _compatibility(src, model_id, running, request.get("check_config", True))
    if compat.get("warning"):
        warnings.append(compat["warning"])
    plan = {"id": "", "created": store.now_iso(), "source": source, "model_id": model_id,
            "family": parsed.slug, "gguf_repo": gguf_repo, "quant": choice["label"],
            "target_dir": paths.display(target_dir), "downloads": downloads, "download_bytes": need,
            "free_bytes": free, "activate": activate,
            "boot": {"model": next(d["dest"] for d in downloads if not naming.parse_gguf_filename(d["name"])["mmproj"]),
                     "mmproj": next((d["dest"] for d in downloads if naming.parse_gguf_filename(d["name"])["mmproj"]), None)},
            "replace": replace, "invalidated": invalid, "lora": {"mode": lora["mode"]}, "training": training,
            "compatibility": compat, "warnings": warnings, "blocking": blocking, "current": running}
    plan["id"] = hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def keep(data):
        plans = data.setdefault("plans", {})
        cutoff = datetime.now(timezone.utc) - timedelta(hours=PLAN_TTL_HOURS)
        for key in [k for k, v in plans.items() if v.get("created", "") < cutoff.isoformat()]:
            plans.pop(key, None)
        plans[plan["id"]] = plan
    store.mutate(keep)
    return plan


def load(plan_id: str) -> dict:
    plan = (store.load().get("plans") or {}).get(plan_id)
    if not plan:
        raise PlanError("That plan expired or does not exist; review the choices again.")
    return plan


def _compatibility(src, model_id: str, running: dict, check: bool) -> dict:
    """Same architecture as today's model means the current llama.cpp build will load it."""
    if not check or not running.get("label"):
        return {"checked": False}
    try:
        new = src.config(model_id)
        old_id = f"{(naming.parse(model_id).org or 'Qwen')}/{running['label']}"
        old = src.config(old_id)
    except (net.NetError, ValueError, KeyError) as error:
        return {"checked": False, "warning": f"Could not compare architectures ({error})."}
    keys = ("architectures", "model_type")
    same = all(new.get(k) == old.get(k) for k in keys)
    text_new, text_old = new.get("text_config") or {}, old.get("text_config") or {}
    shape_same = all(text_new.get(k, new.get(k)) == text_old.get(k, old.get(k))
                     for k in ("num_hidden_layers", "hidden_size"))
    out = {"checked": True, "same_architecture": same, "same_shape": shape_same,
           "new": {k: new.get(k) for k in keys}, "old": {k: old.get(k) for k in keys}}
    if not same:
        out["warning"] = ("Different architecture from today's model: the current llama.cpp build may not "
                          "load it. The install verifies the model actually loads and rolls back if not.")
    return out
