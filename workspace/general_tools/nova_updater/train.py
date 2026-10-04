# Last updated: 2026-10-04 14:28:11
# @nova: LoRA training for new or installed models: job specs with Nova's proven defaults, verified training bundles, and RunPod or export runners.
"""Train a LoRA for a model Nova has (or is about to have).

Two ways in:
  * the update dialog's "LoRA training data" option (e.g. retrain the personality LoRA for
    Qwen3.8-27B with the v7 corpus), chained after the model install;
  * the widget's "Train a LoRA" tab for an installed model, no download (e.g. KoELS specialists).

A job is a bundle: the data files (checksummed, row-counted), job.json, the generic pod scripts
(template_gen.py proves the loss mask before training, train_lora.py, run_on_pod.sh). Runners:
  * export  - zip the bundle with instructions; you run it on any GPU box (no spend from here)
  * runpod  - start, upload, train, download, stop; delete the pod only after verified local installation
Paid runs need explicit consent. RunPod prepaid credit is the funding limit; Nova never recharges it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
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
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", family) or ".." in family:
        raise TrainError("base_family must be one plain folder name, like qwen3.8.")
    stamp = datetime.now().strftime("%Y%m%d")
    default_name = f"{'nova_core' if preset['role'] == 'personality' else 'koels'}_{family.replace('.', '')}_{stamp}"
    # ASCII only: the adapter's path ends up in a boot file the launcher reads in the console code page.
    output = "".join(ch for ch in (spec.get("output_name") or "") if ch.isascii() and (ch.isalnum() or ch in "_-"))
    output = (output or default_name)[:64]
    output_directory = _output_directory(dict(spec, base_family=family))
    training_directory = paths.training_model_dir(base) / output
    rows = sum(d["rows"] for d in data)
    hours = OVERHEAD_HOURS + rows * params["epochs"] * SECONDS_PER_ROW_EPOCH / 3600
    runner = spec.get("runner") or "export"
    if runner not in ("export", "runpod"):
        raise TrainError("runner must be export or runpod")
    data_center_ids = spec.get("data_center_ids", ["AP-JP-1"])
    if not isinstance(data_center_ids, list) or not data_center_ids or not all(
            isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+){2,}", value.strip())
            for value in data_center_ids):
        raise TrainError("Choose at least one datacenter ID, for example AP-JP-1 for Japan.")
    data_center_ids = list(dict.fromkeys(value.strip().upper() for value in data_center_ids))
    return {"preset": preset_name, "role": preset["role"], "base_model_id": base, "base_family": family,
            "output_name": output, "base_model_name": paths.training_model_name(base),
            "training_directory": paths.display(training_directory),
            "output_directory": paths.display(output_directory), "output_pattern": output + "_epoch<number>.gguf",
            "data": data, "rows": rows, "params": params, "runner": runner,
            "gpu": spec.get("gpu") or "NVIDIA H100 80GB HBM3", "estimate_hours": round(hours, 2),
            "data_center_ids": data_center_ids,
            "activate": bool(spec.get("activate", False)),  # A/B the epochs first (v6/v7 discipline)
            "scale": float(spec.get("scale", 1.0)),
            "replace": [str(p).replace("\\", "/") for p in spec.get("replace") or []]}


def _output_directory(spec: dict) -> Path:
    """Finished GGUF adapters stay beside their selected base model, never in Training Files."""
    selected = spec.get("output_directory")
    if not selected and spec.get("base_model_path"):
        selected = str(Path(str(spec["base_model_path"]).replace("\\", "/")).parent)
    target = Path(str(selected)) if selected else paths.models_root() / spec["base_family"]
    if not target.is_absolute():
        target = paths.workspace() / target
    target = target.resolve()
    if not target.is_relative_to(paths.models_root().resolve()) or target.is_relative_to(paths.training_root().resolve()):
        raise TrainError("Finished adapters must be beside their base model inside models, outside Training Files.")
    problem = paths.launcher_problem(paths.display(target))
    if problem:
        raise TrainError(problem)
    return target


def _atomic_text(path: Path, text: str) -> None:
    """Publish complete text only; the project watcher must never see partial inputs."""
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_copy(source: Path, destination: Path, overwrite: bool = True) -> None:
    temporary = destination.with_name("." + destination.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        shutil.copy2(source, temporary)
        if overwrite:
            os.replace(temporary, destination)
        else:
            # A same-directory hard link publishes all bytes atomically and refuses a
            # racing importer that created the destination after our collision check.
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _recipe(spec: dict) -> dict:
    return {"base_model_id": spec["base_model_id"], "output_name": spec["output_name"], "output_dir": "lora_out",
            "template_file": "chat_template.gen.jinja", "params": spec["params"],
            "data": [{"name": d["name"], "rows": d["rows"], "sha256": d["sha256"]} for d in spec["data"]],
            "preset": spec["preset"], "output_directory": paths.display(_output_directory(spec))}


def _bundle_readme(spec: dict) -> str:
    data = "\n".join(f"- `{item['name']}`: {item['rows']} training rows." for item in spec["data"])
    return f"""<!-- @nova: Explain this frozen LoRA training input package and how to use its dataset, recipe and scripts. -->
# {spec['output_name']} - training inputs

Base model: `{spec['base_model_id']}`. Preset: **{spec['preset']}**.
Finished adapters belong in `{paths.display(_output_directory(spec))}` beside that base model.
This folder contains inputs; creating or exporting it does not train or activate an adapter.

{data}
- `job.json`: model, dataset checksums, output names and training parameters.
- `run_on_pod.sh`: runs checksum verification, the template gate, training and GGUF conversion.
- `train_lora.py`: training implementation; saves every epoch for comparison.
- `template_gen.py`: generates and verifies the assistant-only loss-mask template from the base tokenizer.
- `inputs.sha256`: checksums of the frozen dataset, recipe, scripts and this README.
- `outputs.json`, when present: verified adapter filenames/checksums and their final locations.
- `Run Details/`, when present: checksummed model revision, generated template, tokenization report and exact runtime dependencies from the GPU run.

To train, copy this folder to a CUDA PyTorch GPU machine and run `bash run_on_pod.sh`.
The script prepares an isolated environment and fetches its pinned llama.cpp converter into
`/workspace/nova-llama-converter-<revision>`. Allow network access to the named base model,
Python dependencies and converter repository; set `HF_TOKEN` only if the base model is gated. The scripts generate the template from that repository
at execution time. The run records its exact model revision and dependency versions in Run Details; the large remote base weights are not copied into this input package.
Download `gguf_out/`, then use Nova Chat's **Install trained LoRA** to verify and copy its GGUFs.
Compare the epochs before choosing a separate activation action. Managed runs stop the GPU first, then
delete the pod after verified local installation and provenance preservation; failed jobs retain recovery storage.
"""


def build_bundle(spec: dict, out_dir: Path) -> dict:
    """Write complete reproducibility inputs and checksums; no training or adapter activation."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in POD_FILES:
        _atomic_copy(POD_DIR / name, out_dir / name)
    for item in spec["data"]:
        source = Path(item["path"]) if Path(item["path"]).is_absolute() else paths.workspace() / item["path"]
        if _sha(source) != item["sha256"]:
            raise TrainError(f"{item['path']} changed after it was reviewed; review the job again.")
        _atomic_copy(source, out_dir / item["name"])
        if _sha(out_dir / item["name"]) != item["sha256"]:
            raise TrainError(f"{item['path']} changed while its training package was being copied.")
    job = dict(_recipe(spec), created=store.now_iso())
    _atomic_text(out_dir / "job.json", json.dumps(job, indent=2) + "\n")
    _atomic_text(out_dir / "README.md", _bundle_readme(spec))
    names = sorted([*POD_FILES, "job.json", "README.md", *[d["name"] for d in spec["data"]]])
    lines = [f"{_sha(out_dir / name)}  {name}" for name in names]
    _atomic_text(out_dir / "inputs.sha256", "\n".join(lines) + "\n")
    return {"dir": paths.display(out_dir), "files": sorted(p.name for p in out_dir.iterdir())}


def preserve_inputs(spec: dict) -> dict:
    """Keep one immutable input package per run name; reuse exact reviewed inputs, never replace another run."""
    target = paths.training_model_dir(spec["base_model_id"]) / spec["output_name"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", spec["output_name"]):
        raise TrainError("The training run name must use plain letters, digits, - or _.")
    reviewed = spec.get("training_directory")
    if reviewed and paths.display(target) != reviewed:
        raise TrainError("The training-input destination changed after review; preview the job again.")
    if target.exists():
        try:
            old = json.loads((target / "job.json").read_text(encoding="utf-8"))
            old.pop("created", None)
            if old != _recipe(spec):
                raise ValueError("different recipe")
            required = {*POD_FILES, "job.json", "README.md", *[item["name"] for item in spec["data"]]}
            listed = set()
            for line in (target / "inputs.sha256").read_text(encoding="utf-8").splitlines():
                digest, name = line.split(None, 1)
                if name not in required or name in listed or _sha(target / name) != digest:
                    raise ValueError("changed package")
                listed.add(name)
            if listed != required or any(_sha(target / item["name"]) != item["sha256"] for item in spec["data"]):
                raise ValueError("incomplete or changed package")
        except (OSError, ValueError, TypeError) as error:
            raise TrainError(f"{paths.display(target)} already contains different or changed inputs; choose a new output name.") from error
        return {"dir": paths.display(target), "files": sorted(p.name for p in target.iterdir())}
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="." + spec["output_name"] + "-", dir=parent))
    try:
        build_bundle(spec, stage)
        if target.exists():
            raise TrainError(f"{paths.display(target)} was created by another request; retry with a new output name.")
        os.rename(stage, target)
    finally:
        if stage.exists() and stage.resolve().parent == parent.resolve():
            shutil.rmtree(stage)
    readme = parent / "README.md"
    if not readme.exists():
        _atomic_text(readme, f"""<!-- @nova: Describe the saved training-input packages for {paths.training_model_name(spec['base_model_id'])}. -->
# {paths.training_model_name(spec['base_model_id'])} - Training Files

Each subfolder is one LoRA training input package: dataset, recipe, scripts and checksums.
Read its README before using it. Merely saving or exporting a package does not run training.
Finished GGUF adapters live beside their base model, outside this Training Files folder.
Temporary downloads and logs stay in `Temp/updater`; paid training requires its own confirmation.
""")
    return {"dir": paths.display(target), "files": sorted(p.name for p in target.iterdir())}


def export(spec: dict) -> dict:
    """Preserve the inputs and create a downloadable zip without spending or training."""
    bundle = preserve_inputs(spec)
    folder = Path(bundle["dir"])
    if not folder.is_absolute():
        folder = paths.workspace() / folder
    downloads = paths.work_dir() / "exports"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / f"{spec['output_name']}_{uuid.uuid4().hex[:10]}_bundle.zip"
    temporary = archive.with_name("." + archive.name + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.name != "outputs.json":
                    zf.write(path, f"{spec['output_name']}/{path.name}")
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    return {"bundle": bundle, "zip": paths.display(archive), "folder": paths.display(folder),
            "training_directory": paths.display(folder), "output_directory": paths.display(_output_directory(spec)),
            "readme": paths.display(folder / "README.md")}


def _verified_output_hashes(folder: Path) -> dict:
    """Return verified output paths and their expected transfer digests."""
    folder = Path(folder)
    sums = folder / "SHA256SUMS.txt"
    if not sums.is_file():
        raise TrainError(f"{paths.display(folder)} has no SHA256SUMS.txt; refusing to install unverified adapters.")
    verified, seen = {}, set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split(None, 1)
        except ValueError as error:
            raise TrainError("SHA256SUMS.txt has a malformed entry") from error
        name = name.strip().lstrip("*")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest) or not name.lower().endswith(".gguf") \
                or any(character in name for character in ("/", "\\", ":")) or name in seen:
            raise TrainError("SHA256SUMS.txt must list unique GGUF filenames in this output folder.")
        path = folder / name
        if path.is_symlink() or path.resolve().parent != folder.resolve():
            raise TrainError("Adapter output must be a regular file in the selected output folder.")
        if not path.is_file() or _sha(path) != digest.lower():
            raise TrainError(f"{name} is missing or does not match SHA256SUMS.txt")
        seen.add(name)
        verified[path] = digest.lower()
    if not verified:
        raise TrainError("SHA256SUMS.txt lists no files")
    return verified


def verify_outputs(folder: Path) -> list:
    """Check gguf_out/SHA256SUMS.txt against the downloaded files."""
    return list(_verified_output_hashes(folder))


def install_outputs(spec: dict, folder: Path) -> dict:
    """Copy verified GGUFs beside their base model, preserving inputs separately and never overwriting adapters."""
    verified = _verified_output_hashes(folder)
    target = _output_directory(spec)
    for source in verified:
        if (target / source.name).exists():
            raise TrainError(f"{paths.display(target / source.name)} already exists; rename the output and install again.")
    bundle = preserve_inputs(spec)
    target.mkdir(parents=True, exist_ok=True)
    placed, records = [], []
    for source in verified:
        destination = target / source.name
        _atomic_copy(source, destination, overwrite=False)
        installed_hash = _sha(destination)
        if installed_hash != verified[source]:
            raise TrainError(f"Installed {source.name} does not match its verified download; remote recovery data must be retained.")
        placed.append(paths.display(destination))
        records.append({"path": paths.display(destination), "source_name": source.name, "sha256": installed_hash})
    package = Path(bundle["dir"])
    if not package.is_absolute():
        package = paths.workspace() / package
    receipt = package / "outputs.json"
    _atomic_text(receipt, json.dumps({"base_model_id": spec["base_model_id"], "base_family": spec["base_family"],
                                    "verified_at": store.now_iso(), "outputs": records,
                                    "note": "Transfer checksums verified; the supplied training recipe is retained, not proof of training execution."}, indent=2) + "\n")
    return {"installed": placed, "pick": placed[-1] if placed else None,
            "output_directory": paths.display(target), "training_directory": paths.display(package),
            "readme": paths.display(package / "README.md"), "receipt": paths.display(receipt)}


def activate_lora(rel_path: str, scale: float = 1.0) -> str:
    from .install import write_boot
    problem = paths.launcher_problem(rel_path)
    if not problem and ("," in rel_path or ":" in rel_path):
        # llama-server reads --lora-scaled as FNAME:SCALE,... (llama-common, build b9491)
        problem = f"{rel_path} contains ':' or ',', which llama-server reads as separators"
    if problem:
        raise TrainError(problem + "; use a workspace-relative path without command or adapter separators.")
    windows_path = rel_path.replace("/", "\\")
    line = f'--lora-scaled "{windows_path}:{scale:g}"'
    write_boot("active_lora.txt", line)
    return line


def loaded_loras(port: int = 8080, timeout: float = 3.0):
    """Adapter file names llama-server reports at GET /lora-adapters, or None if it is not answering."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/lora-adapters", timeout=timeout) as response:
            data = json.loads(response.read(1 << 20).decode("utf-8"))
    except Exception:
        return None
    return [Path(str(a.get("path", "")).replace("\\", "/")).name for a in data if isinstance(a, dict) and a.get("path")]


def activate(rel_path: str, scale: float = 1.0, restart=None, probe=loaded_loras, timeout: float = 600.0,
             poll: float = 3.0, sleep=None) -> dict:
    """Equip an adapter and prove it loaded (v6 lesson: the equip can 'succeed' while llama-server
    runs bare; trust /lora-adapters, not the launcher log). On any failure the previous boot line is
    restored and the previous setup restarted, and the result says what happened (ok: False)."""
    import time
    from . import current
    from .install import write_boot
    sleep = sleep or time.sleep
    if not (paths.workspace() / rel_path).is_file():
        raise TrainError(f"{rel_path} does not exist")
    before = current.snapshot_boot_files().get("active_lora.txt")
    line = activate_lora(rel_path, scale)
    if restart is None:
        return {"ok": True, "boot_line": line, "verified": False, "message": "Takes effect at the next model start."}

    def undo(reason: str, outcome) -> dict:
        write_boot("active_lora.txt", before)
        try:
            again = restart() or {}
        except Exception as error:
            again = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        restarted = again.get("ok") is not False
        return {"ok": False, "error": reason + (" The previous adapter setting is restored and the model is restarting."
                                                if restarted else " The previous adapter setting is restored, but "
                                                "restarting FAILED: start the model from Services."),
                "restart": outcome, "restored_previous": True, "previous_restart": "ok" if restarted else "failed"}

    try:
        outcome = restart() or {}
    except Exception as error:
        outcome = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    if outcome.get("ok") is False:
        if outcome.get("chat_only"):
            return {"ok": True, "boot_line": line, "verified": False,
                    "message": "Nova is in chat-only mode; the adapter loads at her next full start."}
        return undo(f"Restart failed ({outcome.get('error') or outcome}).", outcome)
    name = Path(rel_path).name
    deadline = time.monotonic() + timeout
    seen = None
    while time.monotonic() < deadline:
        seen = probe()
        if seen is not None and name in seen:
            return {"ok": True, "boot_line": line, "restart": outcome, "verified": True, "loaded": seen}
        sleep(max(0.0, min(poll, deadline - time.monotonic())))
    return undo(f"llama-server is running without {name} (it reports {seen if seen is not None else 'nothing'}).",
                outcome)


def preserve_run_details(spec: dict, output_folder: Path, job_id: str, *, require_complete=False) -> str | None:
    """Keep small, checksummed runtime inputs alongside the frozen training recipe."""
    source = Path(output_folder) / "training_details"
    if not source.is_dir():
        if require_complete:
            raise TrainError("Managed training is missing its reproducibility details; the pod must be retained.")
        return None  # Imported older adapters may have only a GGUF checksum manifest.
    manifest = source / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise TrainError("Training details have no checksum manifest")
    allowed = {"environment.txt", "base_source.json", "tokenization_report.json",
               "chat_template.gen.jinja", "base_config/config.json", "README.md"}
    checked = []
    seen = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        path = source / name
        if name not in allowed or name in seen or path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise TrainError("Unexpected training details file")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest) or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024 or _sha(path) != digest.lower():
            raise TrainError("Training details checksum or size mismatch")
        seen.add(name)
        checked.append((path, name, digest.lower()))
    if not checked:
        raise TrainError("Training details manifest is empty")
    if require_complete and seen != allowed:
        raise TrainError("Managed training has incomplete reproducibility details; the pod must be retained.")
    target = paths.training_model_dir(spec["base_model_id"]) / spec["output_name"] / "Run Details" / job_id
    target.mkdir(parents=True, exist_ok=False)
    for path, name, digest in checked:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        _atomic_copy(path, destination, overwrite=False)
        if _sha(destination) != digest:
            raise TrainError("Preserved training details do not match their verified checksums; the pod must be retained.")
    _atomic_copy(manifest, target / "SHA256SUMS.txt", overwrite=False)
    return paths.display(target)


def run(spec: dict, job: jobs.Job, runner=None) -> dict:
    """Bundle, run remotely, verify, install. Activation is the caller's decision (A/B first)."""
    folder = paths.work_dir() / "jobs" / f"{spec['output_name']}_{job.id}"
    job.set_step("Building the training bundle")
    bundle = preserve_inputs(spec)
    bundle_path = Path(bundle["dir"])
    if not bundle_path.is_absolute():
        bundle_path = paths.workspace() / bundle_path
    if runner is None:
        raise TrainError("No GPU runner configured; use the export runner or set up RunPod.")
    finalize = getattr(runner, "finalize_success", None)
    try:
        outputs = runner.run(bundle_path, folder / "gguf_out", job)
        job.check_cancel()
        job.set_step("Verifying downloaded adapters against SHA256SUMS.txt")
        if callable(finalize):
            verified = verify_outputs(Path(outputs))
            # prepare_spec normalizes epochs to an integer; save_strategy='epoch' retains each.
            expected = {f"{spec['output_name']}_epoch{epoch}.gguf"
                        for epoch in range(1, int(spec["params"]["epochs"]) + 1)}
            if {path.name for path in verified} != expected:
                raise TrainError("Downloaded adapters do not include exactly every requested epoch; the pod must be retained.")
        details = preserve_run_details(spec, Path(outputs), job.id, require_complete=callable(finalize))
        placed = install_outputs(spec, Path(outputs))
        job.check_cancel()
        if callable(finalize):
            finalize(job)
    except Exception:
        retain = getattr(runner, "retain_unverified", None)
        if callable(retain):
            retain(job)
        raise
    return {"bundle": bundle, **placed, "run_details": details,
            "runpod_cost": getattr(runner, "cost_summary", None)}


REVIEW_TTL_HOURS = 24


def preview(spec_request: dict) -> dict:
    """Validate a request and remember exactly what the user reviewed, data checksums included.
    A run starts only from the returned review_id, so data edited after the preview is refused
    instead of silently trained."""
    spec = prepare_spec(spec_request)
    review_id = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def keep(data):
        reviews = data.setdefault("train_reviews", {})
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=REVIEW_TTL_HOURS)).isoformat(timespec="seconds")
        for key in [k for k, v in reviews.items() if v.get("created", "") < cutoff]:
            reviews.pop(key, None)
        reviews[review_id] = {"created": store.now_iso(), "spec": spec}
    store.mutate(keep)
    return dict(spec, review_id=review_id)


def reviewed(review_id) -> dict:
    """The spec behind a preview, provided every data file is still exactly what was reviewed."""
    entry = (store.load().get("train_reviews") or {}).get(str(review_id or ""))
    if not entry:
        raise TrainError("Preview the training first and send its review_id (previews last 24 hours).")
    spec = entry["spec"]
    for item in spec["data"]:
        try:
            now = inspect_data(item["path"])
        except TrainError as error:
            raise jobs.Conflict(f"{item['path']} changed after the preview ({error}); preview it again.") from None
        if (now["sha256"], now["rows"]) != (item["sha256"], item["rows"]):
            raise jobs.Conflict(f"{item['path']} changed after the preview; preview it again to review the new data.")
    return spec


def confirm_paid_training(confirm) -> None:
    """Consent to this reviewed paid run; no artificial per-run spending ceiling."""
    if not isinstance(confirm, dict) or confirm.get("paid") is not True:
        raise TrainError("Confirm this paid RunPod training run with paid: true. It uses existing wallet credit; Nova will not recharge it.")


def start(review_id, confirm=None, runner_factory=None):
    """Start a reviewed training run (see preview). RunPod needs confirm={'paid': True}; prepaid wallet credit funds the run."""
    spec = reviewed(review_id)
    if spec["runner"] == "export":
        return jobs.JOBS.start("train-export", f"Export training bundle {spec['output_name']}",
                               lambda job: export(spec), exclusive=False)
    confirm_paid_training(confirm)
    from . import runpod
    runner = (runner_factory or runpod.RunPodRunner.from_credentials)(spec)
    runner.estimate(spec)
    runner.paid_confirmed = True
    return jobs.JOBS.start("train", f"Train {spec['output_name']} on RunPod", lambda job: run(spec, job, runner))
