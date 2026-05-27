# Last updated: 2026-05-27 14:11:37
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
        else:
            return f"ERROR: Unrecognized tool {tool_name}"
    except Exception as e:
        return f"ERROR executing {tool_name}: {str(e)}"
