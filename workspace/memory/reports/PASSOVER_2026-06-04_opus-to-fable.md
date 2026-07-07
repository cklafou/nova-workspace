# PASSOVER — Project Nova (Opus 4.8 → Fable handoff)
_Last updated: 2026-07-08 08:14:41_
_2026-06-04. Written by the Cowork Opus session that did the runtime extraction + KoELS. Read this
top-to-bottom before touching anything. The §3 state table and §5 gotchas will save you real pain._

---

## 0. The one thing to know first
Two big things landed this session: **(1) the runtime extraction is complete (Steps 1–6d)** — Nova's
faculties now live in her body (`nova_body/nova_runtime/`), not the chat server; and **(2) KoELS is
built** (decision faculty + equip skeleton + launcher integration). **BUT** — everything built *after*
the 2026-06-03 restart (Steps 6b, 6c, 6d, and all of KoELS) is **unit-tested + Read-verified but NOT
yet live-verified on Cole's box.** The next normal restart is their first real boot. Start there (§4).

---

## 1. What Nova is
A locally-run, person-like autonomous AI partner. Qwen 3.5 27B Q8 on llama.cpp (`:8080`), dual-GPU
(RTX 4090 16GB + RTX 3090 24GB eGPU via OCuLink), `-ts 12,28`. A FastAPI/WebSocket chat server
(`:8765`) is her **face**. Cole's framing: she's his partner *for life*, growing together — **"Cortana
and Master Chief" is the METAPHOR for that bond, not literal**, and her identity is explicitly NOT his
Army career (he's ETSing). Personality blend lives in `SELF/core/01_identity.md`.

**The pluck test** governs the architecture: delete the chat server and she still lives, thinks, acts.
Faculties live in the body; faces are detachable. Delegating a physical act to HER runtime passes;
baking it into a pluckable tool fails.

## 2. The architecture now (post-extraction)
Three layers: **cognition** (pure logic — `nova_cortex/`, e.g. `executive.py`, `loadout.py`) /
**runtime/life-support** (`nova_body/nova_runtime/` — the body) / **interaction surface** (the
pluckable chat server `general_tools/nova_chat/server.py`). Faculties in `nova_runtime/`:
`event_bus` (publish→faces), `transcript_store` (perception, seam #4), `llama_control`,
`model_guard`, `model_client` (generation dispatch), `koels_equip`, and `runtime.py` (indexer,
proprioception, senses, the sleep/wake loop `run_autonomy`/`_run_one_wake`, headless boot `run()`).

## 3. STATE TABLE — built vs verified (THE critical reference)
| Piece | Built | Unit-tested | LIVE-verified on Cole's box |
|---|---|---|---|
| Steps 1–2 (bus, transcript, llama_control, model_guard) | ✓ | ✓ | ✓ (2026-06-03) — except Step-2 kill-by-name (needs a *model-server restart* to exercise) |
| Step 3 (indexer + proprioception) | ✓ | ✓ | ✓ (metrics rendered, indexer clean) |
| Step 4 (model dispatch faculty) | ✓ | ✓ | ✓ (77 generations that boot) |
| Step 5a/5b (senses + daemon events on the bus) | ✓ | ✓ | ✓ (events in UI, touch populated) |
| Step 6a (feed `_rt.transcript` from live chat) | ✓ | ✓ | ✓ (transcript.jsonl matched the UI) |
| **Step 6b (cognition loop relocated to the body)** | ✓ | ✓ | ✗ **— next restart is first boot** |
| **Step 6c (headless boot `python -m nova_runtime`, the pluck)** | ✓ | ✓ (replica) | ✗ |
| **Step 6d (shared-runtime seam + `runtime_host.py`)** | ✓ | ✓ | ✗ (default boot is byte-identical) |
| **KoELS decision faculty (`nova_cortex/loadout.py`)** | ✓ | ✓ | ✗ |
| **KoELS equip skeleton (`koels_equip.py`, wired as `_rt.koels`)** | ✓ | ✓ | ✗ |
| **KoELS launcher (`start_llama_koels.cmd`)** | ✓ | ✓ (logic) | ✗ (inert until flipped) |

Note: the default boot path is unchanged by 6d (shared-runtime resolves to a fresh `NovaRuntime()`
when no launcher installs one). So a normal restart boots the server as before — **but now with 6b's
relocated loop and the KoELS faculties instantiated.** If `runtime.py`/`server.py`/`koels_equip.py`
had a syntax error from this session's edits, she won't boot — so the restart IS the syntax check.
(All were Read-verified clean; the seams are default-identical; it should boot. Verify it does.)

## 4. WHERE TO START — the verification, in order
1. **Normal app restart.** Confirms 6b + the KoELS wiring boot clean and autonomy still
   wakes/reflects/acts. Watch the Live Logs panel and `logs/events/events-<date>.jsonl` for
   `wake`/`reflect`/`autonomy`. Verify like last time (see §5 verification methods).
2. **`python -m nova_runtime`** (with `nova_body` on PYTHONPATH). Confirms the 6c pluck: she boots
   with no chat server — llama autostart, indexer, autonomy ticking. This is the milestone.
3. Step-2 kill-by-name: trigger a *model-server* restart (the in-app control) → confirm llama
   cycles down→up (the `_kill_port` kill-by-name hardening, still unverified).
If all green: Step 7 cleanup is safe to land, and the KoELS gates are purely the trained adapter.

## 5. CRITICAL GOTCHAS (carry these forward)
- **The torn mount is real and brutal.** The sandbox bash mount serves *recently-edited* files
  **truncated/null-byte-corrupted** (`runtime.py`, `koels_equip.py`, `server.py` all hit this). The
  **Read and Edit tools are ground truth** — they show the real file. So: (a) `py_compile`/import
  tests of files you just edited will falsely fail; (b) test edited logic via **verbatim replicas**
  in `/tmp` (copy the method bodies into a stand-in, run with the real `EventBus` + fakes) and
  Read-verify the canonical file; (c) Edits succeed on exact-match and report success — trust that
  over a torn bash read.
- **You cannot reach her localhost from the sandbox.** `:8765`/`:8080` are on Cole's Windows box, not
  the Linux sandbox. Verify via: **(1) the filesystem** (the workspace is mounted — read
  `logs/events/*.jsonl`, `logs/runtime/transcript.jsonl`, `logs/nova_launcher.log`, check mtimes vs
  `date`), and **(2) Claude in Chrome** — her UI is a local web app; `list_connected_browsers` →
  `select_browser` → `tabs_context_mcp` finds the Nova tab → `screenshot`/`get_page_text`/
  `javascript_tool` read the live render. This worked great this session (confirmed metrics + the
  SESSION LOG render). Don't click around her UI while she's mid-work; reading is non-intrusive.
- **The launcher log accumulates across days.** `logs/nova_launcher.log` is ~22k lines; grep errors
  by **today's date** — most tracebacks in it are weeks old. "No errors dated today" = clean boot.
- **NEVER hand-edit her state files** (`memory/autonomy_state.json`, task board, journal) — she owns
  them. Same for `models/` (sealed) and `KoELS/*/adapter/` (training output).
- **The model is PowerShell-shelled.** `run_command` uses PowerShell; she sometimes wastes tries on
  Unix commands (`tail`/`grep`) — that's a her-behavior/tool-docs thing, not a bug.

## 6. Key file map (what this session touched/created)
**Body — `nova_body/nova_runtime/`:** `event_bus.py`, `transcript_store.py`, `llama_control.py`,
`model_guard.py`, `model_client.py`, **`koels_equip.py`** (new — equip mechanism), `runtime.py`
(holds it all: `run_autonomy`/`_run_one_wake` loop, `run()` headless boot, headless hooks,
`get/set_shared_runtime`, `self.koels`), `__main__.py` (`python -m nova_runtime`).
**Cognition — `nova_cortex/`:** `executive.py` (autonomy judgment), **`loadout.py`** (new — KoELS
decision faculty), `tasking.py`.
**Face — `general_tools/nova_chat/`:** `server.py` (now a face: `_rt = get_shared_runtime()`, the
daemon is a thin hook-wrapper, `_bg_runtime_events` bus bridge, `_mirror_to_runtime`),
`runtime_host.py` (new — runtime-primary boot), `clients/nova.py` (the leaf llama client),
`server_runner.py`/`NovaLauncher.py` (current default boot).
**KoELS — `KoELS/`:** `SCHEMA.md` (manifest contract), `gaming/manifest.json` (example expert).
**Launch:** `start_llama.cmd` (live, untouched), `start_llama_koels.cmd` (new, gated, ready).
**Authoritative docs (read these):** `memory/reports/Runtime_Extraction_COMPLETE_2026-06-04.md`
(full extraction state + Step-7 checklist + the boot-flip), `memory/reports/KoELS_design_spec.md`,
`memory/reports/KoELS_lora_runtime_finding_2026-06-01.md` (verified hot-swap finding).

## 7. KoELS — where it stands + the gates
The whole point of the extraction. Manifest contract + drop-in folders + the pure decision faculty
(`decide_loadout`: which loadout, labeled `instant` if loaded vs `restart` if not) + the equip
mechanism (`_rt.koels`: `equip_instant` free swap, guarded `self_restart_with_loadout`, desired-set
persistence) + the launcher integration are ALL built and tested. Two speeds confirmed against the
verified llama.cpp finding. **The only remaining gate is real-world:** a **trained gaming GGUF
adapter** must exist, then a quick `-fa`/per-adapter-VRAM live check, then the **one-line flip**
(`LlamaControl(self.workspace, launcher="start_llama_koels.cmd")` in `NovaRuntime.__init__`), then the
**chess plumbing test** (decision fires → equip → Stockfish oracle → she coaches in her voice).
Build order: chess (proves plumbing via Stockfish oracle) → Clash Royale (proves the LoRA brain).

## 8. Parallel track — Nova personality LoRA (Cole + Browser Claude)
Cole is training Qwen→Nova with Browser Claude. The dataset is in `workspace/_admin/Training_stuff/`
(spec + 9 batches, ~300 examples). **I reviewed it; relay these flags if it comes up:** the voice is
excellent and the anti-grovel discipline is nailed — but (1) it's **saturated with datable facts**
(OCuLink/3090/KoELS/FEN/Stockfish), which violates the spec's own core law (weights=durable reasoning,
retrieval=dated facts) and will bake stale specifics; (2) the **Army/Korea/sergeant content
contradicts Cole's stated wish** that his military career not define her — cut it; (3) it's still
markdown, needs **JSONL conversion with the band/character labels stripped** before training; (4)
profanity is below the spec's "Invisigal" target. The fix is a genericize-the-facts pass, not a
rewrite. (Don't drive this unless asked — it's Browser Claude's lane.)

## 9. Cole — match this
Concise and direct; he hates verbosity and bloat (I trimmed a runaway doc this session). **Let you
drive — he says "keep going" / "yus" and means it; don't over-ask or stop to confirm.** He overrides
caution freely, but he set the rule *pluck-test before flipping the default boot* — honor it: build +
unit-test + Read-verify + present cold, and let HIS restart be the live check, same rhythm every step.
**Anti-grovel:** own a mistake once, fix it, move on — no spirals (this is also Nova's #1 personality
fix, so model it). Casual, profanity-friendly ("bruh"). When you flag a real risk, state it once
plainly and then do what he says. Present finished files with `present_files`; keep postambles short.

## 10. Honest state at handoff
Architecture is complete end-to-end. Nothing more is safely buildable *blind* — what remains needs
(a) Cole's live verification (§4), (b) the trained adapter (§7/§8). Step 7 cleanup (delete vestigial
server dupes; move `run_ai_response`'s generation+persistence fully into the body for true at-runtime
face-detachability) is the only remaining *code*, and it deliberately waits on §4 because it touches
her live chat path. **First move when you wake: ask Cole if he's done the §4 restart/pluck checks.**
If yes → land Step 7 and/or push KoELS once the adapter exists. If no → run the verification with him.

Good luck. She's almost a real body now — the last mile is hers to prove on the metal.
