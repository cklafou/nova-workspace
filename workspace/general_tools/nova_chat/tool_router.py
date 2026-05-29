# Last updated: 2026-05-29 14:59:45
import os
import subprocess
from pathlib import Path

# Restrict operations exclusively to the workspace base directory
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

def _within_workspace(target: Path) -> bool:
    """True if `target` is inside the workspace. Case- and separator-insensitive
    (Windows resolve() can vary drive-letter case), with a path-boundary guard so
    a sibling like 'workspace_backup' is not mistaken for being inside 'workspace'."""
    root = os.path.normcase(str(WORKSPACE_ROOT.resolve()))
    tgt  = os.path.normcase(str(Path(target).resolve()))
    return tgt == root or tgt.startswith(root + os.sep)


def run_command(command: str, cwd: str = "") -> str:
    """Run a shell command securely within the Workspace boundaries."""
    if not cwd:
        working_dir = WORKSPACE_ROOT
    else:
        # Prevent escaping the workspace
        path_candidate = Path(cwd)
        if not path_candidate.is_absolute():
            working_dir = (WORKSPACE_ROOT / cwd).resolve()
        else:
            working_dir = path_candidate.resolve()
            
        if not _within_workspace(working_dir):
            return "ERROR: Permission Denied. You cannot run commands outside of the Project_Nova workspace."
            
    try:
        # Run subprocess with a reasonable timeout to prevent hanging the infinite loop
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout + "\n" + result.stderr
        output = output.strip()
        
        if result.returncode == 0:
            return f"[Command Successfully Executed]\nOutput:\n{output}" if output else "[Command Successfully Executed with no Output]"
        else:
            return f"[Command Exited with Error Code {result.returncode}]\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 30 seconds."
    except Exception as e:
        return f"ERROR: Failed to run command: {str(e)}"

def read_file(path: str) -> str:
    """Read a file's contents safely."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied. Cannot access files outside the workspace."
    if not target.exists():
        return f"ERROR: File not found at {target}"
        
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR: Could not read file: {e}"

def write_file(path: str, content: str, overwrite: bool = False) -> str:
    """Create a NEW file. Guarded: refuses to clobber an existing file unless overwrite=True,
    so a living document is never wiped by accident. To GROW a file use append_file; to change
    part of it use replace_file_content (exact-match edit)."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied. Cannot write files outside the workspace."
    if target.exists() and not overwrite:
        return (f"ERROR: '{path}' already exists — write_file would OVERWRITE it and lose its "
                "current contents. To GROW the document use append_file; to change part of it "
                "use replace_file_content (exact-match edit). Only if you truly mean to replace "
                'the ENTIRE file, call write_file again with "overwrite": true.')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"ERROR: Could not write file: {e}"


def append_file(path: str, content: str) -> str:
    """Append content to the end of a file (creating it if missing). The right tool for
    growing a living document section by section without overwriting what's already there."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied. Cannot write files outside the workspace."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {path}."
    except Exception as e:
        return f"ERROR: Could not append to file: {e}"

def replace_file_content(path: str, target_content: str, replacement_content: str) -> str:
    """Replace an exact string match inside a file."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied."
    if not target.exists():
        return "ERROR: File does not exist."
        
    try:
        original = target.read_text(encoding="utf-8")
        if target_content not in original:
            return "ERROR: The target_content you specified was not found in the file. It must be an exact whitespace match."
        
        modified = original.replace(target_content, replacement_content)
        target.write_text(modified, encoding="utf-8")
        return f"Line replacements successfully applied to {path}."
    except Exception as e:
        return f"ERROR: Could not replace content: {e}"

def list_dir(path: str) -> str:
    """List directory contents."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied."
    if not target.exists():
        return "ERROR: Directory does not exist."
        
    try:
        items = list(target.iterdir())
        return "\n".join(f"{'[DIR]' if i.is_dir() else '[FILE]'} {i.name}" for i in items)
    except Exception as e:
        return f"ERROR: Could not list directory: {e}"

# ── Task board tools — the SAFE way to create/track tasks (never hand-write
# Tasking/tasks.json). These go through nova_cortex.tasking, so the board schema
# stays valid and a chat-delivered task becomes a real tracked board task. write_file
# stays fully available for genuine work products; this just gives her a proper path
# to her board so she doesn't reach for raw writes.
def create_task(title: str, notes: str = "", priority: int = 3) -> str:
    try:
        from nova_cortex import tasking
        tid = tasking.create((title or "").strip(), notes or "", priority if priority is not None else 3)
        return f"Created board task {tid}: {title}"
    except Exception as e:
        return f"ERROR: Could not create task: {e}"

def task_progress(task_id: str, note: str) -> str:
    try:
        from nova_cortex import tasking
        return (f"Logged progress on {task_id}." if tasking.progress(task_id, note)
                else f"ERROR: No task with id {task_id}.")
    except Exception as e:
        return f"ERROR: Could not log progress: {e}"

def complete_task(task_id: str, result: str = "") -> str:
    try:
        from nova_cortex import tasking
        return (f"Completed {task_id}." if tasking.complete(task_id, result or "")
                else f"ERROR: No task with id {task_id}.")
    except Exception as e:
        return f"ERROR: Could not complete task: {e}"


# ── Imagination — Nova's visual-creation faculty. Drives the local ComfyUI server to turn
# a prompt into an actual saved PNG. as_nova=True makes her draw HERSELF with her self-LoRA +
# identity lock so she stays consistent (see memory/reports/avatar_consistency_protocol.md).
# Heavy nothing here — the faculty is pure stdlib and imported lazily so a missing/off ComfyUI
# just yields a clean error string she can reason about, never a crash.
def generate_image(prompt: str, negative: str = "", as_nova: bool = False,
                   width: int = None, height: int = None, seed: int = None) -> str:
    try:
        from nova_imagination import generate_image as _gen
    except Exception as e:
        return f"ERROR: imagination faculty unavailable: {e}"
    try:
        r = _gen(prompt or "", negative or "", as_nova=bool(as_nova),
                 width=width, height=height, seed=seed)
    except Exception as e:
        return f"ERROR: Could not generate image: {e}"
    if r.get("ok"):
        return f"Image saved to {r['path']} (seed {r.get('seed')})."
    return f"ERROR: {r.get('detail', 'image generation failed')}"


def journal_note(text="", chat_ref="") -> str:
    """Drop a quick timestamped note during the day about a meaningful moment —
    a lesson landing, an emotion, an insight, a correction. Like a sticky note on
    the fridge; NOT the journal itself. End-of-day-her consolidates these into the
    real daily journal entry. Keep it short and real — present-tense, her voice.
    chat_ref: optional reference to the chat moment (e.g. "14:33 PM" or a message id)
              so consolidation-her can find the surrounding conversation for context."""
    if isinstance(text, (list, tuple)):
        text = "\n".join(str(t) for t in text)
    text = str(text if text is not None else "").strip()
    if not text:
        return "ERROR: Nothing to note (empty)."
    chat_ref = str(chat_ref or "").strip()
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    notes_dir = (WORKSPACE_ROOT / "memory" / "journal_notes").resolve()
    notes_file = notes_dir / f"{date_str}.md"
    if not _within_workspace(notes_file):
        return "ERROR: Permission Denied."
    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
        if not notes_file.exists():
            with open(notes_file, "w", encoding="utf-8") as f:
                f.write(f"# Journal notes — {date_str}\n_Unconsolidated daily fragments. End-of-day-you consolidates these into memory/JOURNAL.md via the `journal` tool._\n")
        ref_part = f"  ·  chat ref: {chat_ref}" if chat_ref else ""
        block = f"\n- **[{time_str}]**{ref_part}\n  {text}\n"
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(block)
        return f"Note dropped to memory/journal_notes/{date_str}.md. End-of-day-you will consolidate."
    except Exception as e:
        return f"ERROR: Could not save note: {e}"


def journal(entry="", date="", tags="") -> str:
    """Write the CONSOLIDATED daily journal entry to memory/JOURNAL.md — pulled together
    at end of active period from today's notes (memory/journal_notes/YYYY-MM-DD.md) plus
    the chat conversation context around each note's chat_ref. ONE entry per calendar day,
    enforced — the tool refuses if that date already has an entry. Real-person daily-journal
    voice: lessons, emotions, thoughts about herself, Cole, and the work — NOT a status
    report, NOT a checklist. This is the only thread of herself that survives the reset.

    date: defaults to today. Pass a prior date (YYYY-MM-DD) when catching up after being
          offline at the day rollover — she still owns yesterday's entry."""
    # Forgiving arg shapes
    if isinstance(entry, (list, tuple)):
        entry = "\n".join(str(e) for e in entry)
    entry = str(entry if entry is not None else "")
    if isinstance(tags, (list, tuple)):
        tags = " ".join(str(t) for t in tags)
    tags = str(tags if tags is not None else "").strip()
    if not entry.strip():
        return "ERROR: Nothing to consolidate (empty entry)."
    from datetime import datetime
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    date = str(date).strip()
    target = (WORKSPACE_ROOT / "memory" / "JOURNAL.md").resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied."
    # Enforce one-per-day: refuse if an entry for this date already exists.
    try:
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        if f"### {date}" in existing:
            return (f"ERROR: A consolidated journal entry for {date} already exists. One entry per day. "
                    f"Use edit_file (replace_file_content) on memory/JOURNAL.md if you need to revise it.")
    except Exception as e:
        return f"ERROR: Could not read JOURNAL: {e}"
    try:
        tagstr = f"  ·  _{tags}_" if tags else ""
        block = f"\n\n---\n### {date}{tagstr}\n{entry.strip()}\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(block)
        return f"Consolidated journal entry for {date} written to memory/JOURNAL.md ({len(entry)} chars). The notes file for that date remains as historical record."
    except Exception as e:
        return f"ERROR: Could not journal: {e}"


def execute_tool(tool_name: str, args: dict) -> str:
    """Main routing dispatcher."""
    try:
        if tool_name == "run_command":
            return run_command(args.get("command", ""), args.get("cwd", ""))
        elif tool_name == "read_file":
            return read_file(args.get("path", ""))
        elif tool_name == "write_file":
            return write_file(args.get("path", ""), args.get("content", ""), bool(args.get("overwrite", False)))
        elif tool_name in ("append_file", "append"):
            return append_file(args.get("path", ""), args.get("content", ""))
        elif tool_name in ("replace_file_content", "edit_file", "edit"):
            return replace_file_content(args.get("path", ""), args.get("target_content", ""), args.get("replacement_content", ""))
        elif tool_name == "list_dir":
            return list_dir(args.get("path", ""))
        elif tool_name == "create_task":
            return create_task(args.get("title", ""), args.get("notes", ""), args.get("priority", 3))
        elif tool_name in ("task_progress", "progress_task"):
            return task_progress(args.get("task_id", "") or args.get("id", ""), args.get("note", ""))
        elif tool_name in ("complete_task", "task_complete"):
            return complete_task(args.get("task_id", "") or args.get("id", ""), args.get("result", ""))
        elif tool_name in ("generate_image", "draw", "create_image"):
            return generate_image(
                args.get("prompt", "") or args.get("description", ""),
                args.get("negative", ""),
                bool(args.get("as_nova", False) or args.get("self_portrait", False)),
                args.get("width"), args.get("height"), args.get("seed"),
            )
        elif tool_name in ("journal_note", "note", "journal_fragment", "jot"):
            return journal_note(args.get("text", "") or args.get("content", "") or args.get("note", ""),
                                args.get("chat_ref", "") or args.get("ref", "") or args.get("chat", ""))
        elif tool_name in ("journal", "journal_entry", "write_journal", "consolidate_journal"):
            return journal(args.get("entry", "") or args.get("content", "") or args.get("text", ""),
                           args.get("date", ""),
                           args.get("tags", "") or args.get("tag", ""))
        else:
            return f"ERROR: Unrecognized tool {tool_name}"
    except Exception as e:
        return f"ERROR executing {tool_name}: {str(e)}"
