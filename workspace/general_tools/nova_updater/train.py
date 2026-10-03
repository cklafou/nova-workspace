# @nova: LoRA training for new or installed models: job specs with Nova's proven defaults, verified training bundles, and RunPod or export runners.
"""Train a LoRA for a model Nova has (or is about to have).

Two ways in:
  * the update dialog's "LoRA training data" option (e.g. retrain the personality LoRA for
    Qwen3.8-27B with the v7 corpus), chained after the model install;
  * the widget's "Train a LoRA" tab for an installed model, no download (e.g. KoELS specialists).

A job is a bundle: the data files (checksummed, row-counted), job.json, the generic pod scripts
(template_gen.py proves the loss mask before training, train_lora.py, run_on_pod.sh). Runners:
  * export  - zip the bundle with instructions; you run it on any GPU box (no spend from here)
  * runpod  - start your pod, upload, run, download, verify, ALWAYS stop the pod (never terminate)
Paid runs need an explicit confirm that carries the cost estimate the user saw.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from . import catalog, jobs, naming, net, paths, store

POD_FILES = ("run_on_pod.sh", "train_lora.py", "template_gen.py")
POD_DIR = Path(__file__).resolve().parent / "pod"
V7 = {"r": 16, "alpha": 32, "dropout": 0.05, "epochs": 2, "lr": 1e-4, "batch": 1, "grad_accum": 8,
      "max_length": 4096, "scheduler": "cosine", "warmup_ratio": 0.03, "seed": 42,
      "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]}
PRESETS = {
    "personality": {"title": "Personality (Nova-core v7 recipe)", "role": "personality", "params": dict(V7)},
    "specialist": {"title": "Specialist / KoELS (same recipe, separate adapter)", "role": "koels", "params": dict(V7)},
}
LIMITS = {"r": (4, 128), "alpha": (4, 256), "epochs": (1, 10), "lr": (1e-6, 1e-3), "batch": (1, 8),
          "grad_accum": (1, 64), "max_length": (512, 32768), "dropout": (0.0, 0.5), "warmup_ratio": (0.0, 0.3)}
SECONDS_PER_ROW_EPOCH = 1.9      # v6 actual: ~24 min for 361 rows x 2 epochs on one H100 SXM, incl. load
OVERHEAD_HOURS = 0.35            # boot, deps, model download to local disk, conversion


class TrainError(ValueError):
    pass


def training_base_for(model_id: str, src=None) -> str:
    """Prefer the bf16 'unsloth/<name>' mirror v6/v7 trained on; fall back to the model itself."""
    label = model_id.split("/")[-1]
    mirror = f"unsloth/{label}"
    if mirror == model_id:
        return model_id
    try:
        files = (src or catalog.source("huggingface")).files(mirror)
        if any(f.path.endswith(".safetensors") for f in files):
            return mirror
    except (net.NetError, ValueError):
        pass
    return model_id


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_data(rel: str) -> dict:
    """A training file must be JSONL rows with a 'messages' list containing an assistant turn."""
    path = Path(rel) if Path(rel).is_absolute() else paths.workspace() / rel
    if not path.is_file():
        raise TrainError(f"{rel} does not exist")
    if path.suffix.lower() != ".jsonl":
        raise TrainError(f"{rel}: training data must be a .jsonl file of chat rows")
    rows, problems = 0, []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            rows += 1
            try:
                row = json.loads(line)
                messages = row["messages"]
                if not any(m.get("role") == "assistant" for m in messages):
                    problems.append(f"line {number}: no assistant turn")
            except (ValueError, KeyError, TypeError, AttributeError):
                problems.append(f"line {number}: not a {{'messages': [...]}} row")
            if len(problems) >= 5:
                break
    if problems:
        raise TrainError(f"{rel}: " + "; ".join(problems))
    if rows == 0:
        raise TrainError(f"{rel} has no rows")
    return {"path": paths.display(path), "name": path.name, "rows": rows, "sha256": _sha(path),
            "bytes": path.stat().st_size}


def prepare_spec(spec: dict) -> dict:
    """Validate and complete a training request. Pure checks; nothing is written."""
    preset_name = spec.get("preset") or "personality"
    if preset_name not in PRESETS:
        raise TrainError(f"Unknown preset '{preset_name}'. Choose: {', '.join(PRESETS)}")
    preset = PRESETS[preset_name]
    params = dict(preset["params"])
    for key, value in (spec.get("params") or {}).items():
        if key == "target_modules":
            if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
                raise TrainError("target_modules must be a list of module names")
            params[key] = value
            continue
        if key not in LIMITS:
            raise TrainError(f"Unknown training option '{key}'")
        low, high = LIMITS[key]
        number = float(value)
        if not low <= number <= high:
            raise TrainError(f"{key} must be between {low} and {high}")
        params[key] = int(number) if isinstance(V7.get(key), int) else number
    base = (spec.get("base_model_id") or "").strip()
    parsed = naming.parse(base)
    if not parsed:
        raise TrainError("Choose the base model to train on (a repo id like unsloth/Qwen3.8-27B).")
    files = spec.get("data_files") or []
    if not files:
        raise TrainError("Choose at least one .jsonl training file.")
    data = [inspect_data(f) for f in files]
    if len({d["name"] for d in data}) != len(data):
        raise TrainError("Two training files share a name; rename one.")
    family = spec.get("base_family") or parsed.slug
    stamp = datetime.now().strftime("%Y%m%d")
    default_name = f"{'nova_core' if preset['role'] == 'personality' else 'koels'}_{family.replace('.', '')}_{stamp}"
    output = "".join(ch for ch in (spec.get("output_name") or default_name) if ch.isalnum() or ch in "_-")[:64]
    rows = sum(d["rows"] for d in data)
    hours = OVERHEAD_HOURS + rows * params["epochs"] * SECONDS_PER_ROW_EPOCH / 3600
    runner = spec.get("runner") or "export"
    if runner not in ("export", "runpod"):
        raise TrainError("runner must be export or runpod")
    return {"preset": preset_name, "role": preset["role"], "base_model_id": base, "base_family": family,
            "output_name": output, "data": data, "rows": rows, "params": params, "runner": runner,
            "gpu": spec.get("gpu") or "NVIDIA H100 80GB HBM3", "estimate_hours": round(hours, 2),
            "activate": bool(spec.get("activate", False)),  # A/B the epochs first (v6/v7 discipline)
            "scale": float(spec.get("scale", 1.0)),
            "replace": [str(p).replace("\\", "/") for p in spec.get("replace") or []]}


def build_bundle(spec: dict, out_dir: Path) -> dict:
    """Write everything the pod needs into out_dir and checksum it."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in POD_FILES:
        shutil.copy2(POD_DIR / name, out_dir / name)
    for item in spec["data"]:
        source = paths.workspace() / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
        if _sha(source) != item["sha256"]:
            raise TrainError(f"{item['path']} changed after it was reviewed; review the job again.")
        shutil.copy2(source, out_dir / item["name"])
    job = {"base_model_id": spec["base_model_id"], "output_name": spec["output_name"], "output_dir": "lora_out",
           "template_file": "chat_template.gen.jinja", "params": spec["params"],
           "data": [{"name": d["name"], "rows": d["rows"], "sha256": d["sha256"]} for d in spec["data"]],
           "created": store.now_iso(), "preset": spec["preset"]}
    (out_dir / "job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    lines = [f"{_sha(out_dir / n)}  {n}" for n in sorted([*POD_FILES, "job.json", *[d["name"] for d in spec["data"]]])]
    (out_dir / "inputs.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"dir": paths.display(out_dir), "files": sorted(p.name for p in out_dir.iterdir())}


EXPORT_README = """Nova LoRA training bundle ({output})
Base model: {base}   Rows: {rows}   Preset: {preset}   Estimated GPU time: {hours} h on one H100

On a GPU machine with ~80 GB VRAM (e.g. your RunPod pod):
  1. Copy this folder to the machine (e.g. /workspace/nova_jobs/{output}).
  2. Make sure llama.cpp is at /workspace/llama.cpp (or `export LLAMA_CPP=...`; the script
     clones it if missing) and the Hugging Face base is reachable (`export HF_TOKEN=...` if gated).
  3. bash run_on_pod.sh
  4. Download gguf_out/ back to this folder; then in Nova Chat choose "Install trained LoRA".
     The updater checks SHA256SUMS.txt before installing.
  5. STOP the pod (never Terminate).
"""


def export(spec: dict) -> dict:
    """The no-spend runner: a zip you can run anywhere."""
    folder = paths.work_dir() / "jobs" / f"{spec['output_name']}_{datetime.now().strftime('%H%M%S')}"
    bundle = build_bundle(spec, folder / "bundle")
    (folder / "bundle" / "README.txt").write_text(EXPORT_README.format(
        output=spec["output_name"], base=spec["base_model_id"], rows=spec["rows"], preset=spec["preset"],
        hours=spec["estimate_hours"]), encoding="utf-8")
    archive = folder / f"{spec['output_name']}_bundle.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((folder / "bundle").iterdir()):
            zf.write(path, f"{spec['output_name']}/{path.name}")
    return {"bundle": bundle, "zip": paths.display(archive), "folder": paths.display(folder)}


def verify_outputs(folder: Path) -> list:
    """Check gguf_out/SHA256SUMS.txt against the downloaded files. Returns verified file paths."""
    folder = Path(folder)
    sums = folder / "SHA256SUMS.txt"
    if not sums.is_file():
        raise TrainError(f"{paths.display(folder)} has no SHA256SUMS.txt; refusing to install unverified adapters.")
    verified = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        path = folder / name
        if not path.is_file() or _sha(path) != digest.lower():
            raise TrainError(f"{name} is missing or does not match SHA256SUMS.txt")
        verified.append(path)
    if not verified:
        raise TrainError("SHA256SUMS.txt lists no files")
    return verified


def install_outputs(spec: dict, folder: Path) -> dict:
    """Copy verified adapters into models/<family>/ (never overwriting)."""
    target = paths.models_root() / spec["base_family"]
    target.mkdir(parents=True, exist_ok=True)
    placed = []
    for path in verify_outputs(folder):
        dest = target / path.name
        if dest.exists():
            raise TrainError(f"{paths.display(dest)} already exists; rename the output and install again.")
        shutil.copy2(path, dest)
        placed.append(paths.display(dest))
    return {"installed": placed, "pick": placed[-1] if placed else None}


def activate_lora(rel_path: str, scale: float = 1.0) -> str:
    from .install import launcher_path, write_boot
    line = f"--lora-scaled {launcher_path(rel_path)}:{scale:g}"
    write_boot("active_lora.txt", line)
    return line


def run(spec: dict, job: jobs.Job, runner=None) -> dict:
    """Bundle, run remotely, verify, install. Activation is the caller's decision (A/B first)."""
    folder = paths.work_dir() / "jobs" / f"{spec['output_name']}_{job.id}"
    job.set_step("Building the training bundle")
    bundle = build_bundle(spec, folder / "bundle")
    if runner is None:
        raise TrainError("No GPU runner configured; use the export runner or set up RunPod.")
    outputs = runner.run(folder / "bundle", folder / "gguf_out", job)
    job.set_step("Verifying downloaded adapters against SHA256SUMS.txt")
    placed = install_outputs(spec, Path(outputs))
    return {"bundle": bundle, **placed}


def start(spec_request: dict, confirm=None, runner_factory=None):
    """Start a training job. RunPod needs confirm={'max_cost_usd': <the estimate shown>}."""
    spec = prepare_spec(spec_request)
    if spec["runner"] == "export":
        return jobs.JOBS.start("train-export", f"Export training bundle {spec['output_name']}",
                               lambda job: export(spec), exclusive=False)
    from . import runpod
    runner = (runner_factory or runpod.RunPodRunner.from_credentials)(spec)
    estimate = runner.estimate(spec)
    if not isinstance(confirm, dict) or float(confirm.get("max_cost_usd", -1)) < estimate["cost_usd"]:
        raise TrainError(f"This run is estimated at ${estimate['cost_usd']:.2f} "
                         f"({spec['estimate_hours']} h at ${estimate['per_hour']:.2f}/h). "
                         "Confirm with max_cost_usd at least that amount.")
    runner.max_cost_usd = float(confirm["max_cost_usd"])
    return jobs.JOBS.start("train", f"Train {spec['output_name']} on RunPod", lambda job: run(spec, job, runner))
