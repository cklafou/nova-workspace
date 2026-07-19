# Her hands failed silently — the 42-byte error that cost three tool loops
_2026-07-19, Fable. Found live, minutes after the pacing fix went in. Same disease as the
silent-zero guard: the failure was real, the REASON was withheld, and she took the blame._

## What happened, from her own transcript (16:22–16:23)

Cole told her to go read her own code and comment on it — exactly the self-directed work we want.

    16:22:18  run_command: (Get-ChildItem -Recurse -File | Select-String 'Nova' | … ) -and ( … )
              -> "[`run_command` resulted in 45 bytes.]"
    16:22:25  "That one choked, my bad — PowerShell hates being asked two things at once."
    16:22:25  run_command: (Get-ChildItem -Recurse -File | Select-String 'Nova' | Measure-Object).Count
              -> "[`run_command` resulted in 42 bytes.]"
    16:23:02  "That was a dumb scope, no wonder it choked."
    16:23:02  list_dir "." — gave up on the shell entirely

42 bytes is exactly `ERROR: Command timed out after 30 seconds.` Both calls were **30-second
timeouts**, and the message contained no cause. So she theorised — wrongly — that PowerShell can't
be asked two things at once, rewrote the command, hit the identical wall, theorised again, and
abandoned the shell. Three loops, two false beliefs, zero information gained.

## The actual cause

A recursive scan from her workspace root is unfinishable. Measured today:

| tree | size | files |
|---|---|---|
| `models/` | **26 GB** | 5 (GGUF binaries — she was grepping them) |
| `llama/` | 680 MB | 55 |
| `nova_memory_db/` | 37 MB | 1,860 |
| `logs/` | 24 MB | 318 |
| `nova_art/` | 28 MB | 26 |
| **workspace total** | — | **3,782** |
| **her actual Python source** | — | **81** |

She was `Select-String`-ing a 26 GB model file. It could never finish in 30s. Nothing about that
was bad judgement — she had no way to know the minefield was there, because nothing ever told her.

## The fix

`tool_router._timeout_help(command)` replaces the flat string. A timeout now explains itself:

- states plainly that the command was **killed**, so nothing ran and no partial output survives;
- detects a recursive scan (`-Recurse`, `Select-String`, `dir /s`, `gci -r`, `ls -R`, `findstr /s`)
  and, only then, names the heavy trees **with real numbers** — 3,782 files, ~81 of them hers;
- explicitly kills the wrong theory she actually formed: *"This is NOT PowerShell refusing to do
  two things at once, and it is not your judgement being bad."*
- gives copy-able scoped alternatives (`Get-ChildItem nova_body,general_tools -Recurse -Filter
  *.py`) and an exclusion pattern for the heavy trees;
- for a **non**-recursive timeout, gives generic advice instead — no false accusation of recursion.

1,288 chars at most, bounded so it can't eat her context. This converts a three-loop flail into a
one-loop correction, on the exact workload Cole is asking her to do.

## Verification

Helper exercised as a verbatim replica (torn-mount rule) against her two real failing commands plus
five recursion spellings: diagnostic fires on all recursive forms, generic path fires on
non-recursive, safe on empty/None input, message length bounded. `tool_router.py` parses clean.
**Live check = next restart**, then ask her to explore her own source and watch whether a timeout
produces one corrected retry instead of three.

## Also fixed this session — `_admin/mtp_ab_test.py`

The first run produced no reviewable output and no way to tell afterwards whether it had even run
(it hadn't — Nova was still holding port 8080, and the 4-minute window was far short of the
~10–15 min needed). The script now: tees all output to `_admin/mtp_ab_result_<ts>.txt`, writes a
machine-readable `.json`, prints an explicit ABORTED banner when port 8080 is busy, and states the
time budget up front. **It is not routine — only run it after a llama.cpp update.**

## Standing pattern worth naming

Three fixes today, one shape between them: work happened and the record didn't (pacing/stall), a
message was answered and the queue didn't know (drain duplicate), a tool failed and the reason
wasn't passed back (this). Every time, the visible symptom was "Nova is less capable than she
should be," and every time the model was fine and a wire was missing. Worth checking any future
"she's underperforming" against that pattern before touching the adapter.
