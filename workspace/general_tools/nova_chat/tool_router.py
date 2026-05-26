# Last updated: 2026-05-26 14:46:24
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

def write_file(path: str, content: str) -> str:
    """Create or overwrite a file."""
    target = (WORKSPACE_ROOT / path).resolve()
    if not _within_workspace(target):
        return "ERROR: Permission Denied. Cannot write files outside the workspace."
        
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"ERROR: Could not write file: {e}"

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

def execute_tool(tool_name: str, args: dict) -> str:
    """Main routing dispatcher."""
    try:
        if tool_name == "run_command":
            return run_command(args.get("command", ""), args.get("cwd", ""))
        elif tool_name == "read_file":
            return read_file(args.get("path", ""))
        elif tool_name == "write_file":
            return write_file(args.get("path", ""), args.get("content", ""))
        elif tool_name == "replace_file_content":
            return replace_file_content(args.get("path", ""), args.get("target_content", ""), args.get("replacement_content", ""))
        elif tool_name == "list_dir":
            return list_dir(args.get("path", ""))
        else:
            return f"ERROR: Unrecognized tool {tool_name}"
    except Exception as e:
        return f"ERROR executing {tool_name}: {str(e)}"
