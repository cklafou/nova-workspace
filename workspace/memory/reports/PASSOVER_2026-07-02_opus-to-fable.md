# PASSOVER — Project Nova (Opus 4.8 → Fable handoff)
_2026-07-02. Written by the Cowork Opus session (the one that live-tested the 0.6 looping fix on 06-22).
Read top-to-bottom before touching anything. §0 has a gap only Cole can close — start there._

---

> **RESOLVED 2026-07-02 (Fable):** §0 is closed — the "06-26/27 session" was a false alarm. No code
> changed: header restamps + CRLF churn by Nova's own watcher after an unattended 06-27 00:37 boot;
> `nova_motor` dates to 05-09. UTC-vs-KST timestamp confusion did the rest. Full write-up:
> `FORENSICS_2026-06-27_break_changes.md`. §2's "changed since 06-04" warning is void — the 06-04
> file map still holds.
>
> **§3 doubling bug — GUARDED 2026-07-02 (Fable):** commit-point dedupe + retry hardening + a
> generation flight recorder (`logs/generation_trace.jsonl`) shipped; symptom dead, exact race
> still to be caught red-handed by the trace. Evidence + eliminations (daemon and the retry are
> acquitted — don't re-investigate them): `DOUBLING_FIX_2026-07-02.md`.

## 0. First move when you wake
Ask Cole about the **06-26/27 work session** before you build anything on the body. Real code landed
during his ~10-day break — the whole `nova_body/nova_runtime/`, a **new `nova_body/nova_motor/`**,
`nova_senses/`, `nova_start.py`, and `SELF/core/` docs were all rewritten 2026-06-26 ~18:47, with a big
auto-commit batch 06-27 04:1x — **and no report was written for it.** I can see *what* files changed,
not the *intent or status*. Best reconstruction from the code (§2): he built the motor/action layer
(`motor_cortex.py`, `tool_executor.py`, `hands.py`, `verify.py`) but it is **not wired into
`runtime.py` yet** (grep is clean). So: built, probably not integrated, definitely not documented.
**Get the story from Cole, then write the missing report.** Everything below §0 I either verified live
or read from source; this is the one blind spot.

Second: the personality-LoRA looping fix is **validated** (I tested it 06-22). The **message-doubling
bug is still open.** The **retrain is still pending.** Details in §3.

## 1. What Nova is
A locally-run, person-like autonomous AI partner. **Qwen 3.6 27B (UD-Q6_K_XL)** on llama.cpp (`:8080`),
dual-GPU (RTX 4090 + 3090 eGPU) — base was upgraded from 3.5-Q8 on 06-10 (see
`memory/reports/UPGRADE_Qwen3.6_2026-06-10.md`). A FastAPI/WebSocket chat server (`:8765`) is her
**face**. Cole's framing: partner *for life*, growing together — **"Cortana & Master Chief" is the
metaphor for the bond, not literal**, and her identity is explicitly **NOT** his Army career (he's
ETSing). Personality lives in `SELF/core/01_identity.md`. **The pluck test** governs the architecture:
delete the chat server and she still lives, thinks, acts — faculties live in the body, faces detach.

## 2. Architecture (+ the undocumented 06-26 addition)
Three layers: **cognition** (`nova_cortex/` — `executive.py`, `loadout.py`, `tasking.py`) /
**runtime/life-support** (`nova_body/nova_runtime/` — event_bus, transcript_store, llama_control,
model_guard, model_client, koels_equip, `runtime.py` = the sleep/wake loop + headless boot) /
**face** (`general_tools/nova_chat/server.py`).

**NEW since the 06-04 passover — reconcile with Cole (§0):** `nova_body/nova_motor/` = the action layer
(`motor_cortex.py`, `tool_executor.py`, `hands.py`, `verify.py`, all 06-26). `runtime.py` does **not**
reference motor/tool_exec/verify yet → built-but-not-wired. `nova_senses/` is now its own package
(clock, environment, eyes, touch, vision, proprioception). Treat the body as *changed since 06-04* —
don't trust the 06-04 file map blindly for `nova_runtime`/`nova_start.py`.

## 3. HOT THREAD — personality-LoRA looping (VALIDATED at 0.6) + the open bug
**Diagnosis (do NOT re-investigate):** looping was the **v2 personality LoRA being overfit**, not
prompt/sampling. At adapter scale **1.0** she falls into a fixed self-referential rut; at **0.0** (base)
she reasons freely; **0.5–0.7** = personality AND advances cleanly. **0.6 is Cole's chosen sweet spot.**

**Config, verified 07-02:** `nova_start.py` loads `models/qwen3.6/nova_core_v2_e2.gguf` at
`--lora-scaled …:0.6`; live `GET /api/lora` on 06-22 read **0.6000**; presence/frequency penalties 0
(the garble fix). Scale is unchanged.

**Live test I ran 06-22 (Claude-in-Chrome, fresh session, autonomy off) — PASS:**
- 12-turn conversation: every reply distinct, advancing, coherent, proactive — **no loops, no stalls,
  no needing a push.** She took the wheel when asked, advanced unprompted, carried callbacks across
  many turns, and handled the old "performing vs. real" attractor theme **without looping.**
- Idle autonomy: she woke, consciously **chose to rest**, and stayed quiet 3+ min — no 30s
  self-wake re-rumination. Full write-up: `_admin/NOVA_TEST_2026-06-22_claude-in-chrome.md`.

**OPEN — message-doubling (NOT fixed).** Byte-identical duplicate reply reproduced **with autonomy
OFF**, so it is **not** the `follow_gap` self-wake path the 06-22 fixes assumed. ~1/12 turns,
intermittent; Nova even flagged it in her own session log. **Prime suspect:** the empty-response
auto-retry in `general_tools/nova_chat/clients/nova.py` firing on a race and emitting the message
twice. Audit `stream_response` / `_fetch_llama_streaming`; guard against emitting the retry once any
content is committed; dedupe identical consecutive sends. **This is the cleanest thing to pick up.**

## 4. Open items (in order)
1. **Close the 06-26/27 gap with Cole** (§0), then document it.
2. **Message-doubling bug** (§3) — highest-value concrete fix.
3. **Retrain the less-overfit adapter** — still pending. Adapter unchanged (`nova_core_v2_e2.gguf`,
   Jun 21); scale still 0.6; the `nova_start.py` comment still says "after a less-overfit adapter is
   trained." Data/spec staged in `_admin/Training_stuff/RETRAIN_v2_UPLOAD/` (+ `_admin/Training/Base_Nova/`,
   uncommitted, pre-break). Once trained → raise scale toward 1.0 and re-run the §3 test.
4. **Standing from 06-04** (re-confirm given the 06-26 churn): runtime pluck (`python -m nova_runtime`)
   live-verify; KoELS is gated purely on a trained *gaming* GGUF adapter. See
   `memory/reports/PASSOVER_2026-06-04_opus-to-fable.md` + `Runtime_Extraction_COMPLETE_2026-06-04.md`.

## 5. Gotchas (durable — carry forward)
- **Torn mount is real.** Sandbox bash serves *recently-edited* files truncated/null-corrupted —
  **Read/Edit tools are ground truth.** Test edited logic via verbatim `/tmp` replicas, Read-verify the
  canonical file. (Extra relevant: the 06-26 body files are "recently edited.")
- **You can't reach her localhost from the sandbox** (`:8765`/`:8080` are on Cole's Windows box).
  Verify two ways: **(1) filesystem** (workspace is mounted — `logs/events/*.jsonl`,
  `logs/runtime/transcript.jsonl`, `logs/nova_launcher.log`, mtimes vs `date`); **(2) Claude-in-Chrome**
  (`list_connected_browsers` → `tabs_context_mcp` → `screenshot`/`get_page_text`/`javascript_tool`).
  Reading is non-intrusive; don't click her UI mid-work. Reader selector: `#chat .msg-wrap.nova
  .msg-text`. **Note:** all sessions share one `#chat` DOM *and* autonomous activity hijacks the active
  view — **toggle Autonomous OFF for a clean conversational test, back ON after** (System msg confirms).
- **Launcher log accumulates across days** — grep errors by *today's* date.
- **NEVER hand-edit her state files** (`memory/autonomy_state.json`, `Tasking/tasks.json`, journal) —
  she owns them. `models/` sealed; KoELS adapters are training output.
- **The model is PowerShell-shelled** (`run_command` uses PowerShell; she sometimes wastes tries on
  Unix `tail`/`grep` — behavior, not a bug).

## 6. Cole — match this
Concise and direct; hates verbosity/bloat. **Lets you drive — "keep going"/"yus" means it; don't
over-ask or stop to confirm.** He overrides caution freely, but honor the **pluck-test rhythm**: build
+ unit-test + Read-verify + present cold, and let HIS restart be the live check. **Anti-grovel** — own a
mistake once, fix it, move on (it's also Nova's #1 personality fix, so model it). Casual,
profanity-friendly. Flag a real risk once, plainly, then do what he says. `present_files` for finished
files; short postambles.

## 7. Restart Nova cleanly
`StopNova.cmd` → wait → `NovaStart.cmd`. Boot log should show
`Nova-core personality adapter: models/qwen3.6/nova_core_v2_e2.gguf:0.6`, then healthy within ~1 min.
Hangs on "loading model" → tail `logs/llama/llama-<date>.log` for the llama arg error. **Don't**
interleave the in-app "Full Restart" button with the `.cmd` launchers — different spawn paths, orphans
processes. She was relaunched ~07-02, so she's likely already up.

## 8. Honest state at handoff
**Verified by me (live 06-22 / factual 07-02):** scale 0.6; conversation + idle autonomy PASS; doubling
bug open; retrain not landed; base is Qwen 3.6 27B Q6_K_XL. **Inherited from docs:** the 06-04
architecture + KoELS state. **Blind spot:** the 06-26/27 session — real code landed, no report,
intent/status unknown, `nova_motor` built but unwired. Close that with Cole first, then pick the
doubling bug (concrete, mine to hand you) or push whatever 06-26 started. Good luck.
