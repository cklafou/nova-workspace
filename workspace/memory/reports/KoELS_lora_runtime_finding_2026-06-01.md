# KoELS — VERIFIED finding: llama.cpp runtime LoRA capability
_Last updated: 2026-07-08 08:14:41_
_Resolves §7 gate 2 + §10 item 2 of `KoELS_design_spec.md`. Cowork Opus, 2026-06-01._

## The question (spec §7)
Can the inference stack (llama.cpp as used) **hot-swap a LoRA adapter onto the already-running model**, or does a switch require a full model reload? The spec said: don't assume from memory — verify against the actual stack.

## What was checked
- **Her stack:** a ~2025-05-05 `llama.cpp` build (`llama/llama-server.exe` + CUDA dlls), launched by `start_llama.cmd` with `-fa on`, Q8 (`qwen-27b-q8.gguf`) + `--mmproj`, dual-GPU `-ts 12,28`, `-c 32768`. **No `--lora` flag wired today** — LoRA isn't used at all yet.
- **Current llama.cpp capability** (sources below).

## Answer: HOT-SWAP IS SUPPORTED — no base-model reload. KoELS lands in the "elegant" case.

Future equip-layer shape:
- **Preload** adapters at startup: `--lora-scaled <a.gguf> 0.0 … --lora-init-without-apply` (loaded but inactive).
- **Equip live:** `POST /lora-adapters [{"id":N,"scale":1.0}, …]` sets each adapter's scale at runtime — enable / disable / blend — no reload, near-instant.
- **Per-request** is cleaner still: a completion can carry its own `lora` field (PR #10994), so "equip for this turn" needs no global mutation — ideal for a body that decides per-task whether to wear a specialist.
- **Stacking works:** multiple adapters at scale > 0 at once → the future gaming+finance case is supported at the runtime layer.

## Constraints that shape the equip design
1. **GGUF only.** Train PEFT on cloud → convert (`convert_lora_to_gguf` / gguf-my-lora). The expert's `adapter/` folder holds the GGUF.
2. **Preloaded-only.** `/lora-adapters` switches among adapters loaded *at boot*; it does **not** load new files at runtime. So **adding a new specialist (drop-in `legal/` folder) costs one llama restart** to `--lora` it. The launcher should enumerate `KoELS/*/adapter/*.gguf` and load them all at startup; switching within that set is free. (Drop-in-folder vision intact — "new expert ⇒ one restart," not "live load.")
3. **VRAM bounds the preloaded roster.** Her 40 GB is near-full with Q8-27B + mmproj (~4.7 GB free on the 4090, ~2.6 GB on the 3090 per `start_llama.cmd`). LoRA adapters are small (tens–hundreds of MB), so a handful fit, but the simultaneously-loaded count is capped — preload the likely set, restart to rotate the full library.
4. **One LIVE check still owed (not assumed):** `-fa on` (flash attention) + runtime LoRA together on her exact build, and the real per-adapter VRAM cost on the split. Quick to confirm once any small GGUF adapter exists. Flagged, not assumed — the same verify-don't-trust rule that produced this finding.

## Net effect on the design
The spec's "if a reload is required, swap less eagerly" branch does **NOT** apply — swaps are cheap. The equip mechanism is now designable. It remains gated only on:
- **Gate 1:** the runtime-extraction landing (equip lives in the runtime body layer it creates), and
- the quick `-fa`/VRAM live check above.

## Design refinement — working-set + self-restart loadout (Cole, 2026-06-01)

Cole's fix for constraints #2/#3 (can't preload every possible specialist; unloaded ones need a restart): don't try to load them all — make the restart a **deliberate, Nova-aware action**, two-tier.

1. **Loadout visibility (cognition-side, pluck-safe).** Nova can see, at any moment, **which specialists are loaded now (instant-equip)** vs **which exist on disk but aren't loaded (would need a restart)**. This is runtime *status* her decision faculty reads — diff the live `/lora-adapters` set (loaded) against the `KoELS/*` manifests on disk (available). Pure perception; no GPU, no outward act.

2. **Self-restart to rotate the loaded set (runtime-side).** When a task needs a specialist that *isn't* loaded, Nova restarts her own runtime with that adapter added to the boot `--lora` set. A life-support act → lives in the runtime body layer the extraction creates, never in the chat server.

**The honest cost (don't gloss it):** swapping the loaded set is a **full base-model reload** (~30–60s, she goes briefly dark — the reload we watched during today's restarts), because adapters can only be added at boot. It is NOT the instant scale-swap. So the design is two speeds:
- **Instant** — equip/unequip/blend *within* the loaded set (`/lora-adapters` scale, or per-request `lora`).
- **Heavy (self-restart)** — rotate *which* specialists are loaded; deliberate, ~30–60s dark.

Her decision faculty weighs it: stay within the loaded working-set when possible; self-restart only on a clear, worth-it domain change to an unloaded specialist. This is the spec's "swap less eagerly when it's heavy" logic — scoped to the *load-rotation* tier only, while in-set swaps stay free.

**What this needs when we build it (after the runtime extraction):**
- A runtime **status surface** Nova reads: `loaded` (equippable now) vs `available` (on disk, needs restart) — `/lora-adapters` ∪ a `KoELS/*` manifest scan.
- A body-owned **desired-loadout set**, persisted across restart (alongside `autonomy_state.json`), so after a self-restart she comes back with the set she asked for and resumes her task — state survives the reload, like autonomy on/off does today.
- A **guarded self-restart** runtime action (relaunch llama with the new `--lora` set → re-health-gate → reattach the face). Guard it: never mid-reply to Cole; announce/confirm before going dark unless pre-authorized.

This doesn't move the equip mechanism's gates — it's a *switching-policy* refinement on top of the verified hot-swap finding, and still waits on gate 1 (the runtime extraction) for a home.

## Sources
- [llama.cpp server README — `/lora-adapters`, `--lora-scaled`, `--lora-init-without-apply`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [PR #10994 — per-request LoRA adapters](https://github.com/ggml-org/llama.cpp/pull/10994) (builds on PR #8332, the runtime hot-swap endpoint)
- [Discussion #8849 — swapping LoRA per request on llama-server](https://github.com/ggml-org/llama.cpp/discussions/8849)
