# @nova: Load and equip KoELS specialist adapters through the body runtime's model controller.
#        The equip mechanism handles the physical act of wearing a specialist loadout:
#        reading which adapters are loaded, the free in-set scale-swap, and
#        the heavy self-restart that rotates which adapters are loaded at boot. Bytes→GPU is a
#        bodily act, so it lives in HER runtime, never in a pluckable chat tool — and delegating
#        it here is how KoELS passes the pluck test (spec §3). Composes LlamaControl (the model
#        server) and reads the cognition loadout faculty's decisions; it only ACTS.
#
#        The launcher consumes koels_lora_args.txt; disposable launcher/parser tests prove
#        argument serialization. Actual adapter loading, application alongside Nova-core, and
#        per-adapter VRAM behavior remain unverified with real adapters on her installed build.
"""
nova_runtime/koels_equip.py — the equip mechanism (skeleton).

Two speeds, per the verified llama.cpp finding:
  • instant — equip/unequip/blend WITHIN the loaded set: POST /lora-adapters scales. No reload.
  • heavy   — rotate WHICH adapters are loaded: self-restart llama with a new boot --lora set
              (~30-60s dark). Deliberate, guarded (never mid-reply), Nova-aware.

All HTTP is injectable so the logic is testable with no model server; the real ops are the
defaults. Pairs with nova_cortex.loadout (the pure decision faculty that says WHICH loadout).
"""

from nova_paths import body_path

import json
import urllib.request
from pathlib import Path


class KoELSEquip:
    def __init__(self, workspace, llama, port: int = 8080, http_get=None, http_post=None):
        self.workspace = Path(workspace)
        self.llama = llama                      # LlamaControl — composition, not inheritance
        self.port = port
        self.state_path = body_path('memory', workspace=self.workspace) / "koels_loadout.json"   # desired set (persisted)
        self.args_path = body_path('memory', workspace=self.workspace) / "koels_lora_args.json"  # structured boot arguments; launcher reads the adjacent .txt
        self._http_get = http_get or self._default_get      # injectable for tests
        self._http_post = http_post or self._default_post

    # ── boot --lora args (pure) ─────────────────────────────────────────────────────
    @staticmethod
    def build_lora_args(adapter_paths) -> list:
        """Flags to PRELOAD a set of adapters INACTIVE at boot (per the finding):
            --lora-scaled <p>:0.0  (xN)  then  --lora-init-without-apply
        Equip then activates them at runtime via /lora-adapters. Pure → unit-testable; the
        launcher consumes these. Empty set → no flags (Nova-core only)."""
        args: list = []
        for p in adapter_paths or []:
            args += ["--lora-scaled", f"{p}:0.0"]
        if args:
            args.append("--lora-init-without-apply")
        return args

    @staticmethod
    def build_lora_args_line(adapter_paths) -> str:
        """Same preload flags as build_lora_args, but a batch-ready line quoting each path:scale token
        for a launcher to read via `set /p` (start_llama_qwen36.cmd). Empty string when no
        loadout (Nova-core only) → the launcher adds no --lora. The scale must be part of
        the same argument as its path; current llama-server rejects a separate scale token."""
        parts: list = []
        for p in adapter_paths or []:
            parts += ["--lora-scaled", f'"{p}:0.0"']
        if parts:
            parts.append("--lora-init-without-apply")
        return " ".join(parts)

    # ── desired-loadout persistence (survives the self-restart) ─────────────────────
    def save_desired_loadout(self, names) -> None:
        """Persist the specialist set she asked for, so after a self-restart she resumes with it
        (alongside autonomy_state.json). Body-owned state — survives the reload like autonomy on/off."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"desired": sorted(set(names or []))}, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[koels] could not persist desired loadout: {e}")

    def load_desired_loadout(self) -> list:
        try:
            if self.state_path.exists():
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                return list(data.get("desired", []))
        except Exception:
            pass
        return []

    # ── runtime status (which adapters are loaded NOW) ──────────────────────────────
    def read_loaded(self) -> list:
        """GET /lora-adapters → the adapter records loaded at boot. Best-effort; [] if the model
        is down (pluck-safe — never raises out)."""
        try:
            return self._http_get(f"http://127.0.0.1:{self.port}/lora-adapters") or []
        except Exception:
            return []

    def equip_instant(self, id_scales) -> dict:
        """The FREE swap: POST /lora-adapters [{"id":N,"scale":s}, …] to activate / deactivate /
        blend adapters ALREADY loaded. No reload. id_scales = [{"id":int,"scale":float}, …]."""
        try:
            self._http_post(f"http://127.0.0.1:{self.port}/lora-adapters", id_scales)
            return {"ok": True, "applied": id_scales}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def loaded_names(self, manifests) -> set:
        """Map the runtime's loaded adapters back to manifest names (match by adapter path /
        basename). Lets cognition's loadout_status label instant vs restart."""
        records = self.read_loaded()
        loaded_paths = {str(a.get("path", a)).lower() for a in records} if records else set()
        names = set()
        for name, man in (manifests or {}).items():
            ap = str(man.get("adapter", "")).lower()
            if not ap:
                continue
            if any(ap == lp or Path(ap).name == Path(lp).name for lp in loaded_paths):
                names.add(name)
        return names

    # ── the heavy rotate: self-restart with a new boot --lora set ───────────────────
    def self_restart_with_loadout(self, adapter_paths, desired_names=None) -> dict:
        """Rotate WHICH adapters are loaded — the ~30-60s-dark path. Persists the desired set,
        writes the boot --lora args, then cycles the model server (LlamaControl owns the physical
        down→up; KoELS owns the policy).

        start_llama_qwen36.cmd consumes koels_lora_args.txt at boot; the JSON file is a
        structured copy. Disposable tests prove the command reaches the installed parser.
        Real adapter loading, application alongside Nova-core and VRAM use still need a
        separate live check; accepting a restart does not establish those outcomes."""
        if desired_names is not None:
            self.save_desired_loadout(desired_names)
        args = self.build_lora_args(adapter_paths)
        try:
            self.args_path.parent.mkdir(parents=True, exist_ok=True)
            self.args_path.write_text(json.dumps({"args": args}, indent=2), encoding="utf-8")
            # batch-ready line the launcher (start_llama_qwen36.cmd) reads via `set /p`
            (body_path('memory', workspace=self.workspace) / "koels_lora_args.txt").write_text(
                self.build_lora_args_line(adapter_paths), encoding="utf-8")
        except Exception as e:
            print(f"[koels] could not write lora args: {e}")
        return self.llama.restart()             # guarded relaunch (KoELS self-restart's home)

    # ── orchestrator: instant if loaded, else guarded heavy ─────────────────────────
    def equip(self, loadout_name, manifests, *, allow_restart: bool = False) -> dict:
        """Equip a specialist. Already loaded → instant (caller scales it to 1.0 via equip_instant).
        Not loaded → needs the heavy self-restart, guarded behind allow_restart so she never goes
        dark without a deliberate yes / pre-authorization. Returns a plan/result dict."""
        man = (manifests or {}).get(loadout_name)
        if not man:
            return {"ok": False, "error": f"no manifest for '{loadout_name}'"}
        if loadout_name in self.loaded_names(manifests):
            return {"ok": True, "mode": "instant",
                    "note": "adapter already loaded — activate via equip_instant(scale=1.0)"}
        if not allow_restart:
            return {"ok": False, "mode": "restart_needed",
                    "note": (f"'{loadout_name}' not loaded; rotating it in needs a self-restart "
                             "(~30-60s dark). Call again with allow_restart=True — never mid-reply.")}
        result = self.self_restart_with_loadout([man.get("adapter")], desired_names=[loadout_name])
        return {"ok": bool(result.get("ok")) and result.get("started") is not False,
                "mode": "restart", "result": result}

    # ── default real HTTP (overridden in tests) ─────────────────────────────────────
    @staticmethod
    def _default_get(url):
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def _default_post(url, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
