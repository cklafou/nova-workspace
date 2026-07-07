# Runtime Verification — 2026-06-10 (Fable session, with Cole)
_Last updated: 2026-07-08 08:44:42_

All three §4 checks from `PASSOVER_2026-06-04_opus-to-fable.md` are **live-verified on Cole's box**.
This supersedes the passover's §3 state table: every row is now ✓ in the LIVE column.

## Results

**1. Normal restart (6b loop + KoELS wiring) — PASS.** Boot 08:25 KST: wake → reflect → act,
generations flowing, tools executing, transcript + SESSION LOG rendering, zero console errors,
zero today-dated tracebacks. Manifest sense live (caught a new file appearing in real time).
The relocated cognition loop runs from the body; KoELS faculties instantiated clean.

**2. The pluck (`python -m nova_runtime`) — PASS, after one fix.** Run 1 hit `boot — headless`
and `faces=0 (0 = headless, healthy)` but couldn't think: `nova_lancedb` and `nova_chat.clients`
weren't importable because `__main__.py` only put `nova_body` on sys.path. **Fixed:** it now adds
workspace root + `general_tools` + `nova_body`, matching the default boot's import surface.
Run 2: llama **spawn** path exercised (`started: True`), indexer thread up, model client
registered, and real headless generations — wake 08:51:47 → reflect 08:52:06 (19s = a real
model call), repeating on schedule, no server attached. **The pluck milestone is proven.**
`RUN_PLUCK.cmd` (workspace root) re-runs the whole test one-click; output tees to
`logs\pluck_<date>.log` (line-buffered UTF-8, append-and-close per line — mount-readable).

**3. Step-2 kill-by-name via model-server restart — PASS.** `POST /api/restart/server` →
`_rt_llama.restart()`: llama-server PID 34308 killed, fresh PID 41204 spawned, model reloaded,
`/api/llama/status` → running, UI reconnected. Verified via tasklist PID capture before/after.
Caveat: triggered via the API (same handler as the Services-menu item); the menu *click* itself
wasn't exercised — the UI renderer was wedged at that moment (see gotchas).

## Fixes landed this session (all Read-verified; running live since the 08:57 boot)
- `nova_body/nova_runtime/__main__.py` — full import surface for headless boot (the pluck fix).
- `nova_body/nova_runtime/runtime.py` (nvidia-smi) and `nova_body/nova_runtime/llama_control.py`
  (powershell kill) — `encoding="utf-8", errors="replace"`, matching `tool_executor.py`'s existing
  hardening. Cause: run 2 showed two `UnicodeDecodeError` crashes in subprocess reader threads
  (CP949 console bytes vs UTF-8 decode) — silent VRAM-metric loss at minimum. No more bare
  `text=True` captures remain in `nova_body`.
- `RUN_PLUCK.cmd` — new, described for the manifest (`@nova:` header).

## Open items / next
- **Step 7 cleanup is now unblocked** (the §4 gate this verification existed for): delete
  vestigial server-side dupes, move `run_ai_response` generation+persistence fully into the body.
- **KoELS:** gates are unchanged — trained gaming GGUF adapter → `-fa`/VRAM live check → one-line
  launcher flip → chess plumbing test.
- **t43 is stalled** (130+ wakes, no progress/close): she's asked Cole twice what the testing
  session needs from her / what to do with the architecture-review doc. Needs Cole's answer or
  a board decision — hers to manage, his to answer.
- Temp evidence files left in `logs/`: `pluck_2026-06-10.log`, `pycheck.txt`, `llama_*.txt` —
  delete freely.

## Gotchas confirmed for the next session (passover §5 still accurate)
- The sandbox mount **lags/tears on appends** to files held open (events jsonl, launcher log,
  transcript) — the **Read tool is ground truth**, bash tail/grep of hot logs is not. New files
  sync fine, so write evidence to fresh files (the `RUN_PLUCK` tee pattern works).
- Her UI froze once under automation (CDP click timeout → minutes-long reload). Recovered by
  itself after the llama restart; cause unestablished. If her renderer wedges, drive the API
  endpoints directly from a fresh tab instead of clicking the menus.
- Explorer-address-bar `cmd /c ... > file` is a workable way to run/read one-shot Windows
  commands when no terminal access exists (console windows are click-tier + masked).
