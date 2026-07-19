# The forge, and the end of the sandbox
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
