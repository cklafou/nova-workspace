# PROPOSED CHANGE — executive.py "continue, don't restart" fix
_Last updated: 2026-05-31 18:19:02_
_Drafted 2026-05-31 by Opus 4.8. **Proposed, not applied.** Apply + verify when the stack is live._
_Targets: `nova_body/nova_cortex/executive.py`, `general_tools/nova_chat/tool_router.py`._

---

## The problem (root cause of the 372 KB review doc)

`Nova_Architecture_Review.md` grew to 6,155 lines because the autonomy loop re-emitted the whole
review each wake and **appended** it instead of continuing the existing file (`## 4. Executive Faculty
& Tasking` appeared 16×; a second full `# Nova Architecture Review` restarted mid-file).

The mechanism, from the code:
- `executive.build_execution()` (line ~391) tells her to "do the NEXT concrete step … read, then write,"
  but **never tells her to read the current state of the task's output file first**, and never says
  "continue it — don't re-emit sections that already exist."
- The stall check inside `build_execution` (line ~411, `loop_n >= 3`) and `_progress_loop_count`
  (line ~210) only compare the **wording of her progress notes** via Jaccard similarity. She dodged it
  every wake by writing differently-worded notes ("wrote sections 1-9", "documented the body manifest")
  while actually re-appending the same content.

So the loop counter watched the wrong thing. The file itself was never consulted.

---

## Fix 1 — read-before-write on a task's output artifact (highest leverage)

In `build_execution(task, recent)`, detect an output-file path in the task title/notes and, if found,
(a) pre-inject its current section headers + tail, and (b) instruct continue-not-restart.

```python
import re
def _artifact_path(task) -> str | None:
    blob = f"{task.get('title','')} {task.get('notes','')}"
    m = re.search(r'([A-Za-z0-9_./\\-]+\.(?:md|py|json|txt))', blob)
    return m.group(1) if m else None
```

In `build_execution`, after the progress block:

```python
art = _artifact_path(task)
if art and os.path.exists(art):
    existing = open(art, encoding="utf-8").read()
    heads = "\n".join(re.findall(r'^#{1,3} .*$', existing, re.M)[-25:])
    L += ["",
          f"OUTPUT FILE [{art}] ALREADY EXISTS ({len(existing.splitlines())} lines). Its current "
          f"section headers:\n{heads}",
          "CONTINUE this file — do NOT re-emit sections it already has. read_file it first, find the "
          "FIRST gap or stub, and fill ONLY that with replace_file_content or a targeted append. "
          "If every planned section already has real content, the task is DONE — say so; do not "
          "rewrite what's there."]
```

This alone would have prevented the entire blowup.

## Fix 2 — idempotency guard in the file tools (belt-and-suspenders)

In `tool_router.py`, the `append_file` / `write_file` handlers: before appending markdown to an
existing file, refuse (return a warning result) if the appended content's top header already exists.

```python
def _dup_header_guard(path, new_content):
    if not os.path.exists(path): return None
    new_heads = re.findall(r'^#{1,3} (.+)$', new_content, re.M)
    if not new_heads: return None
    existing = open(path, encoding="utf-8").read()
    have = set(re.findall(r'^#{1,3} (.+)$', existing, re.M))
    dupes = [h for h in new_heads if h in have]
    if dupes:
        return (f"REFUSED: '{path}' already contains section(s): {dupes}. "
                "Edit the existing section with replace_file_content instead of appending a duplicate.")
    return None
```

Catches the failure even if the prompt guidance is ignored, and teaches her to edit-in-place.

## Fix 3 — make the stall check watch the artifact, not just note wording (optional, phase 2)

Augment `_progress_loop_count` (or add a sibling): if her last N progress notes claim writing to an
output file but that file's **header set / line count didn't materially change**, flag it as a stall —
the real signal. The current Jaccard-on-notes check is necessary but not sufficient.

---

## Apply + test plan (live only)

1. Apply Fix 1 + Fix 2 (Fix 3 optional). Full Restart.
2. Re-create a doc-writing task pointed at a fresh file. Force-wake 3-4×.
3. **Pass criteria:** she `read_file`s the doc before writing; section count grows monotonically; no
   duplicate `##` headers appear; when sections are all filled she emits `DONE:` instead of re-writing.
4. Watch the Tools pane for `read_file` preceding each write, and diff the doc between wakes.

**Risk:** low and contained to the execute-phase prompt + two tool handlers; no state-file or schema
changes. **Rollback:** revert the two files. Do not apply blind — verify against a running stack
(your own verify-don't-trust rule).
