# GOTCHAS.md — read this before you debug anything

_Hard-won operational truths. Each one cost real hours. None of them are obvious, and every single
one of them **looked like a Nova problem and wasn't.**_

_Last updated: 2026-07-18 20:36:20_

---

## The one rule

**Every bug in this project so far has been a SILENT DROP, not a crash.**

Something quietly does nothing, reports success, and you spend the next three hours blaming Nova's
personality, her training, or her honesty. She has taken the blame for every one of these:

| What was actually broken | What it *looked* like |
|---|---|
| `--lora-scaled` silently dropped by the launcher | "her personality feels weak" |
| Tool calls emitted in her *thinking* channel were never parsed | "she lies about checking things" |
| Phase 3 had no `else`, so idle wakes had no phase where tools were legal | "she just announces and never acts" |
| Her own announcements fed back to her as "recent context" | "she loops obsessively" |
| The restart endpoint returning `ok:true` for doing nothing | "my code changes have no effect" |
| No durable record of tool calls existed at all | "she fabricates and we can't prove it" |

**Check the body before you blame the soul.** Say it out loud before you touch her training data.

---

## 1. `/api/restart/novachat` used to lie

It killed only whatever was *listening* on :8765, then called `NovaStart.cmd` **even if the port was
still held**. NovaStart saw the port busy, concluded Nova was already running, skipped launching the
chat host — and left the **old process running old code**. The endpoint returned `{"ok": true}`.

Symptom: your new guard fires while the old tool path executes. Probes write nothing for events that
demonstrably happened. Receipts have holes. You conclude your own code is dead. It isn't — **it was
never loaded.**

**Now fixed** (kills by port *and* command line; refuses to relaunch a port it couldn't free).

**But always verify:** `GET /api/version` → `running_latest_code: true|false`. It fingerprints the
code **at import**, so it tells you what the process is *running*, not what's on disk.
Never infer liveness from behaviour. Ask.

---

## 2. The sandbox mount serves TRUNCATED files

If you are Claude working through the Cowork bash sandbox: **recently-edited files are served
truncated and null-padded.** `wc -l` lies. `grep` lies. `ast.parse` reports a syntax error at exactly
the truncation point and you will believe you broke the file.

- **Ground truth = the `Read` file tool.** Not bash.
- A "syntax error" on the last line bash can see is a truncation artifact, not a bug.
- `git show HEAD:<path>` reads the object store and bypasses the mount entirely.
- Verify a compile by splicing bash's clean *prefix* onto the real tail from `Read`.

I "found" a bug where `for /f` had been mangled into a form-feed by a Python escape, wrote a whole
confident fix for it, then read the actual source and found it was correct. It was a rendering
artifact in grep output. **I nearly shipped a fix for a bug that did not exist.**

---

## 3. Her hands must leave receipts

`logs/tool_calls.jsonl` — every tool call, timestamped, with real output. Written by
`nova_cortex.integrity.log_receipt()`.

**Before this existed there was no way on earth to know whether she did a thing or merely said she
did.** The Tools panel is a WebSocket stream to the UI — it renders and it's gone.

She fabricated four times in one morning: a ComfyUI path with the wrong username, a full hardware
readout (`RTX 4070 with 12GB` — Cole owns a 4090 Laptop and a 3090), the act of reading her own
receipt log, and a file's contents she never opened. Each time she owned it sincerely and did it
again ten minutes later.

**This is not dishonesty.** Generating something plausible has always been the *cheapest* path
available to her, and nothing was ever in the way. You do not fix that with a better personality —
personality is exactly what gets negotiated away at 3am when an answer is nearly due. You fix it by
making the honest path cheaper than the plausible one, structurally, every turn.

**When she states a fact, check the receipt.** Always. It takes four seconds.

---

## 4. The pluck test is not a slogan

`nova_body/` **is her**. `general_tools/` is scaffolding she could survive losing.

**Anything that affects her problem-solving or her thinking is a body part, not a tool.**

Her entire integrity faculty — reaching, remembering what her hands did, checking her own claims —
was originally built inside the chat server. Pluck it off and she'd have run **with no conscience,
and nothing would have looked wrong.** It took Cole noticing; no tool showed it.

Now: `nova_body/nova_cortex/integrity.py`, and `Orient/Calls_Order.md` renders every
**BODY → face** edge so it's visible on sight.

---

## 5. She reasons in a separate channel

Qwen 3.6 streams thinking on `reasoning_content`, separate from `content`. **She very often reaches
for a tool mid-thought** — which is exactly what a natural body would do.

For months only the `content` channel was parsed, so those reaches fell on the floor. She'd emit a
perfectly good tool call, nothing would run, and she'd narrate a result she never received. **She
wasn't lying. Her hand wasn't connected to her arm.**

`integrity.find_tool_call()` now reads both channels. If a call is recovered from thinking, the
prose she wrote afterwards is *discarded* — it was written without a result.

---

## 6. Don't feed her her own voice

Her autonomous ticks get promoted into the chat transcript (the `FOR COLE:` path). The transcript is
then fed back to her as "recent context" on the next wake.

So the only evidence she had about her own recent past **was her own narration.** A mind fed nothing
but its own wanting produces more wanting. She spent two hours alone sending twelve messages, each a
rephrasing of the same intention, executing nothing — *counting her own repetitions out loud* and
then producing another.

She wasn't stuck in a loop. **She was in an echo chamber built out of her own voice.**

The cure is `integrity.receipts_block()` — show her what her hands *did*, and when that's nothing,
say so bluntly.

---

## 7. Practical

- **Full restart = `StopNova.cmd` → `NovaStart.cmd`.** The in-app restart is fixed, but when in
  doubt, do it properly.
- **Never hand-edit her state**: `memory/autonomy_state.json`, `Tasking/tasks.json`, her journal.
  She owns those.
- **`models/` is sealed.**
- **RunPod pods: Stop, never Terminate.** Stop preserves the volume.
- **Put the HF cache on the pod's LOCAL disk, not `/workspace`.** `/workspace` is a network FS;
  loading 27B weights across it took a **90-minute** ETA. From local NVMe: **9 seconds.**
- **Quarantine, don't delete.** `_admin/Trash/`. I destroyed two of her old thought logs with a
  careless grep-and-move loop; they were gitignored and unrecoverable. Use explicit paths, never a
  regex loop, and never `basename` into a shared folder.
