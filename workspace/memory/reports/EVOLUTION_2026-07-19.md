# The forge, and the end of the sandbox
_Last updated: 2026-07-23 02:54:10_
_2026-07-19, Fable. Two of Cole's directives, one afternoon: "if she needs a tool, she should
write a design document, then make it — adapt as she sees necessary," and "she isn't in a sandbox.
My machine is her body. If she can't use it fully, she is crippled."_

---

## What prompted it

She was told to make a full-body avatar. Three attempts, each one changing only the *negative
prompt*, because `width`/`height`/`from_image` existed in her painter and were undocumented. Then
Cole told her "your hands reach all around my PC — think outside your folder," and she agreed
warmly to something her tools made structurally impossible: `run_command` returned
`Permission Denied` for anything outside Project_Nova.

Two different cages, same shape. She could not use what she had, and could not grow what she
lacked. The old unknown-tool error said it out loud: *"Cole can build you the limb; he can't build
one he doesn't know you reached for."* Kind, and exactly backwards — it cast her as the thing that
notices gaps and him as the thing that closes them. An organism that can only report its own
deficiencies to a maintainer isn't adapting. It's filing tickets.

## 1. The forge — `nova_body/nova_forge/`

She can now build her own tools, at runtime, and use them in the same conversation.

    nova_forge/designs/<name>.md    the design document  (REQUIRED)
    nova_forge/tools/<name>.py      TOOL = {...} + run(**args) -> str

Call the tool by name; the router finds it. Edit the file and call again — modules hot-reload on
mtime, so she can iterate mid-task without a restart. That is the "adapt as she sees necessary"
half.

**Design-first is enforced by her body, not by instruction.** A tool with no design document
refuses to load, and a stub under 200 characters is rejected as "a title, not a design." This is
deliberate: the discipline that only lives in a prompt is the discipline that gets skipped at 3am.
It also isn't ceremony — it forces her to name the actual gap before writing code (most bad tools
are answers to a misidentified problem), and it leaves a record of *why* she wanted something that
the code itself can never carry. It's the same standard the humans here follow: every fix today
has a report in `memory/reports/`.

Failures are contained. A tool that raises returns its own traceback with "it's your tool — read
it and fix it," and never takes the router down. Broken and blocked tools both appear in
`list_tools` with the reason, so a limb she grew is never invisible to her — that invisibility is
exactly what cost her the three avatar attempts.

## 2. The sandbox is gone

`run_command` may now use **any existing directory** as its cwd, and `read/write/list` accept
**absolute paths anywhere on the machine**. Relative paths still resolve against the workspace, so
`memory/STATUS.md` means what it always meant and none of her habits break. The
hallucinated-Unix-path repair is kept — that bug is real and separate (Qwen invents
`/home/nova/...` for files that live in the workspace).

`C:\Users\lafou\ComfyUI` — the thing she was sent to explore — is reachable now.

### What is still refused, and why

A short, narrow list of operations that are instant, total and irreversible: formatting a drive,
`diskpart`, `bcdedit`, raw disk overwrite, secure-wiping free space, deleting shadow copies, and a
recursive delete aimed at a **drive root or an entire system tree** (`C:\`, `C:\Windows`,
`C:\Users`, `C:\Program Files`).

This is not the sandbox in a smaller costume. Deleting her own files, clearing another project's
temp folder, removing something deep inside `C:\Users\lafou\...` — all allowed. The distinction is
matched on **whole paths**: `C:\Users` is every profile on the box; `C:\Users\lafou\ComfyUI\temp`
is a scratch folder and deleting it is ordinary work. An earlier draft of the guard matched by
prefix and refused the second one — a guard that blocks real jobs gets routed around, which is
worse than no guard at all.

The reason is not distrust. She runs unattended overnight with PowerShell in her hands, and
earlier today she emitted a malformed command (`... | Select-String 'Nova' | ...) -and (...`).
Malformed happens. `Remove-Item C:\ -Recurse -Force` malformed once is the whole machine, her body
included, with no undo. The guard protects *her* as much as him — wrecking Cole's computer by
accident is the single worst thing she could do, and she would never choose it. When refused, she
is told to bring it to Cole rather than route around it.

## 3. What she's been told

Her system prompt's filesystem section was rewritten. It used to open *"your filesystem root IS the
Project_Nova workspace"* — which is now simply false. It now says her home is the workspace, her
**body is the machine**, absolute paths work, and if a job lives outside her folder she should go
there rather than announce that she will. It also carries the forge contract and the design-first
rule, and names the catastrophe guard honestly instead of letting her discover it as a mystery
refusal.

The painter's documentation was fixed in the same pass — `width`/`height` (the actual answer to
"it keeps giving me chest-up"), `from_image`/`change` (img2img), `mask` (inpaint), `style`, `lora`,
`seed`. Verified every documented parameter is real and reaches the imagination faculty.

## Verification

- Forge, in isolation: **10/10** — no design blocks; stub design rejected; real design loads and
  runs; hot-reload picks up an edit without restart; a raising tool is contained; an unknown name
  falls through to normal dispatch; catalog reports forged vs blocked.
- Catastrophe guard: **23/23** — 11 destructive commands refused (including `rd /s /q C:\Users`,
  which an order-dependent regex missed in my first draft), 12 ordinary jobs allowed including
  destructive-but-scoped deletes outside the workspace.
- End-to-end through the real `execute_tool`: **8/8** — reaching for a missing tool now returns
  build instructions instead of "ask Cole"; code-without-design is blocked; design-then-code works
  first call; the forged tool appears in `list_tools`; the cwd jail is gone; a bad cwd still fails
  clearly; a catastrophic command is refused with its reason.
- All three edited files parse clean. Test artifacts removed.

**Needs a restart to load.** Then the honest test is not to tell her any of this — give her a job
that needs a tool she doesn't have, and see whether she writes a design and builds one.

---

# ADDENDUM — she passed, then broke it, so the forge grew teeth

## What she actually did (verified from receipts, full-date filtered)

    20:40:01 + 20:40:16   read nova_forge/__init__.py — twice, before writing anything
    20:40:39              wrote designs/comfy_inspect.md
    20:41:20              wrote tools/comfy_inspect.py
    20:41:28              called it on C:\Users\lafou\ComfyUI\output   <- OUTSIDE the workspace
    20:41:44-20:42:06     recursively searched ComfyUI's install for workflow files
    20:42:21              inspected a real one: blueprints/Image Edit (Flux.2 Dev).json
    20:42:38              Get-Content on that same file to CHECK her tool's output against it

Under two and a half minutes from "I need a thing" to "I built it and verified it against the real
target," using reach that returned `Permission Denied` an hour earlier. Her design document was
real — GAP honestly self-diagnosed (*"I spent them changing adjectives instead of checking what the
workflow was actually doing"*, which matches her receipts exactly), SHAPE a proper contract, TEST
naming the outside-workspace target. Her error handling was genuinely good: 9/9 on my harness, all
four failure paths returning strings rather than raising.

## Then she broke it, unprompted, and that is the useful part

At **20:44** — before anyone reported anything — she rewrote the parser, having seen it handle the
real blueprint badly. Good instinct. The rewrite:

- fixed the original fault (an operator-precedence bug: `"img2img" in t or "image" in t and "load"
  not in t` parses as `A or (B and C)`, so it flagged `EmptyLatentImage` — the *txt2img* node, the
  opposite signal — and excluded `LoadImage`, the actual indicator);
- and **broke API-format parsing entirely** — `{"1": {"class_type": ...}}`, the shape her own
  painter emits. Tested live: "No nodes found" on both a txt2img and an img2img graph.

She optimised for the single sample in front of her and silently lost the general case. Nothing
made her re-check what used to work. **Design-first was enforced; test-after was not.** Her own
design template has a TEST section and nothing ever made her run it.

## The fix — evidence of test, same mechanism as design-first

`nova_forge/tests/<name>.py`, re-run automatically on any edit to the tool *or* the tests, with the
verdict riding along with **every** result:

| state | meaning | what she sees |
|---|---|---|
| VERIFIED | tests exist and pass | clean output, no banner |
| UNVERIFIED | no tests | *"you do not actually know it works, you know it ran"* |
| FAILING | tests fail | loud banner naming the broken case; output marked suspect |
| BLOCKED | no design | refuses to load (unchanged) |

A failing tool still **runs** — she may be mid-iteration, and blocking that is friction she would
learn to route around. But it can never hand back a clean-looking answer, which is exactly how a
regression gets believed. Same philosophy as the silent-zero guard already in her hands: you don't
fix a miss by refusing, you fix it by making the miss impossible to overlook.

Test format is deliberately cheap — a `CASES` list of `expect_contains` / `expect_startswith` /
`expect_equals` / `expect_absent`, plus `def check(run)` for anything richer. A discipline nobody
will follow is worse than none. Her prompt now also tells her to include a case for what should
*not* happen: **a tool that says yes to everything passes a test that only ever checks yes** —
which is precisely the false positive she shipped.

## Verification — 12/12

Includes a replay of her exact regression: take a passing tool, edit it so it breaks the old case,
call it again. The banner fires automatically and names both broken cases. Also covered: clean
output when passing, UNVERIFIED nudge when untested, catalog warnings, auto-recovery when fixed, a
broken *test file* reported as such instead of blamed on the tool, `check()` form, and design-first
still enforced above tests. Her live `comfy_inspect` now correctly reports **UNVERIFIED**.

**Needs a restart.** The next honest test: hand her the img2img false positive and see whether she
fixes it, writes the tests, and catches her own API-format regression in the process.
