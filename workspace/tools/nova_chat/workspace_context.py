"""
nova_chat/workspace_context.py -- Workspace File Access for Nova Group Chat
============================================================================
Gives all chat AIs live, direct access to Cole's workspace files.

DESIGN PRINCIPLE:
  AIs inside nova_chat CANNOT fetch GitHub URLs. They can only see what is
  injected into their system prompt. This module reads files directly from
  disk and injects their contents as plain text -- no external links needed.

Always in context (every turn):
  - Live workspace manifest (clean tree, no URLs, generated fresh from disk)
  - All memory/ files (STATUS, JOURNAL, COLE, etc.)

Auto-injected when mentioned by name or context:
  - Any file: mention "server.py" or "nova_chat/server.py" -> contents injected
  - Any directory: mention "nova_chat" or "nova_memory" -> listing + all file
    contents injected recursively (up to per-dir file limit)
  - Fuzzy: "the tools directory", "look at nova_chat", "check autonomy" all work
"""

import os
import re
from pathlib import Path
from typing import Optional

# When running as a PyInstaller bundle, __file__ resolves inside _internal/.
# NovaLauncher.py sets NOVA_WORKSPACE to the real workspace root before starting
# the servers, so we use that when available.
WORKSPACE_DIR = Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ \
                else Path(__file__).parent.parent.parent
TOOLS_DIR     = WORKSPACE_DIR / "tools"

# ── Limits ────────────────────────────────────────────────────────────────────
TEXT_EXTENSIONS   = {".py", ".md", ".json", ".txt", ".jsonl", ".ps1", ".cmd",
                     ".yaml", ".yml", ".toml", ".ini", ".env"}
SKIP_DIRS         = {"__pycache__", ".git", "node_modules", ".clawhub",
                     "backups", "sessions", "static", "_admin"}
SKIP_FILES        = {"FILE_INDEX.md", "FILE_INDEX_LINK.md", ".drive_sync_cache.json",
                     "sessions_index.json"}

MANIFEST_MAX       = 25000  # flat file listing — needs room for full workspace
MEMORY_FILE_MAX    = 20000  # per memory/ file (STATUS.md can be detailed)
ONDEMAND_FILE_MAX  = 50000  # per on-demand file -- server.py is ~23k, no file should hit this
DIR_INJECT_MAX     = 200000 # total chars for directory injection -- nova_chat is ~100k
TOTAL_MAX          = 300000 # Sonnet 4.6=200k tokens, Gemini 2.5Pro=1M tokens -- use the room


# ── Workspace manifest ────────────────────────────────────────────────────────

def _build_manifest() -> str:
    """
    Generate a compact, URL-free flat file listing directly from disk.
    Format: one relative path per line, sorted.  No GitHub URLs needed.
    AIs use this to know what files exist and their exact relative paths.
    """
    paths = []
    for p in sorted(WORKSPACE_DIR.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
            # Skip noisy dirs
            if any(skip in p.parts for skip in SKIP_DIRS):
                continue
            if p.name in SKIP_FILES:
                continue
            rel = str(p.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            paths.append(rel)

    header = (
        "# Nova Workspace — All Files (relative paths from workspace root)\n"
        "# To read any file: it will be auto-injected when you mention its name.\n"
        f"# Total readable files: {len(paths)}\n"
    )
    listing = "\n".join(paths)
    result = header + listing
    if len(result) > MANIFEST_MAX:
        # Should not happen at 25000, but truncate gracefully if it does
        result = result[:MANIFEST_MAX] + "\n... (listing truncated — workspace very large)"
    return result


def _get_always_load() -> list:
    """Return relative paths for always-loaded memory files."""
    paths = []
    memory_dir = WORKSPACE_DIR / "memory"
    if memory_dir.exists():
        for f in sorted(memory_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in {".md", ".json"}:
                if f.name not in SKIP_FILES:
                    paths.append(f"memory/{f.name}")
    return paths


# ── WorkspaceContext ──────────────────────────────────────────────────────────

class WorkspaceContext:
    """
    Manages workspace file + directory context for a nova_chat session.
    Reads everything from local disk -- no GitHub URLs required.
    """

    def __init__(self):
        self._manifest: str = ""          # live tree, regenerated each session
        self._always: dict = {}           # path -> content (memory/ files)
        self._on_demand: dict = {}        # path/dir -> content, per message turn
        self._known_files: dict = {}      # lowercase name -> full relative path
        self._known_dirs: dict = {}       # lowercase dirname -> Path object

        self._refresh()

    def _refresh(self):
        """Rebuild manifest, index, and always-loaded files from disk."""
        self._manifest = _build_manifest()
        self._always.clear()
        self._known_files.clear()
        self._known_dirs.clear()

        # Load memory/ files
        for rel in _get_always_load():
            parts = rel.replace("\\", "/").split("/")
            p = WORKSPACE_DIR.joinpath(*parts)
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    self._always[rel] = content[:MEMORY_FILE_MAX]
                except Exception as e:
                    self._always[rel] = f"[read error: {e}]"

        # Index ALL files in workspace for name->path lookup
        self._index_workspace()

    def _index_workspace(self):
        """Walk disk and index every text file and every directory."""
        for p in WORKSPACE_DIR.rglob("*"):
            if any(skip in p.parts for skip in SKIP_DIRS):
                continue
            rel = str(p.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
                name = p.name.lower()
                # Store shortest-path candidate (prefer specific over generic)
                if name not in self._known_files or len(rel) < len(self._known_files[name]):
                    self._known_files[name] = rel
                # Also index partial paths: nova_chat/server.py
                parts = rel.split("/")
                for i in range(len(parts)):
                    partial = "/".join(parts[i:]).lower()
                    if partial not in self._known_files:
                        self._known_files[partial] = rel
            elif p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith("."):
                name = p.name.lower()
                if name not in self._known_dirs:
                    self._known_dirs[name] = p

    # ── Per-message update ────────────────────────────────────────────────────

    def update_for_message(self, message: str):
        """
        Scan message for file and directory references and inject their contents.
        Works on natural language -- no special syntax required.
        Clears previous on-demand cache each turn (stays fresh).

        Detection layers:
          1. @file:path  -- explicit syntax
          2. file.py     -- filename with extension
          3. mentor      -- bare stem word (finds mentor.py automatically)
          4. nova_chat   -- directory/package name
          5. tools/path  -- path-style reference
        """
        self._on_demand.clear()
        msg_lower = message.lower()

        # 1. Explicit @file: syntax
        for m in re.finditer(r"@file:([\w/\\.\-]+)", message):
            self._inject_file(m.group(1).replace("\\", "/"))

        # 2. Filenames with extensions: mentor.py, nova_chat/server.py
        for candidate in re.findall(
            r"[\w][\w/\\.\-]*\.(?:py|md|json|jsonl|txt|ps1|yaml|yml|toml|cmd)",
            message, re.IGNORECASE
        ):
            norm     = candidate.lower().replace("\\", "/")
            basename = norm.split("/")[-1]
            if norm in self._known_files:
                self._inject_file(self._known_files[norm])
            elif basename in self._known_files:
                self._inject_file(self._known_files[basename])

        # 3. Bare stem words: "mentor" -> mentor.py, "brain" -> brain.py
        # Only fires when the stem unambiguously maps to one file
        for word in re.findall(r"\b([a-z][a-z0-9_]{2,})\b", msg_lower):
            candidates = []
            for ext in (".py", ".md"):
                key = word + ext
                if key in self._known_files:
                    candidates.append(self._known_files[key])
            # Also check partial paths ending in stem.py
            for name, path in self._known_files.items():
                if name.endswith("/" + word + ".py") and path not in candidates:
                    candidates.append(path)
            # Deduplicate preserving order
            seen, unique = set(), []
            for p in candidates:
                if p not in seen:
                    seen.add(p); unique.append(p)
            if len(unique) == 1:
                self._inject_file(unique[0])

        # 4. Directory/package names: "nova_chat", "nova_advisor"
        for dir_name, dir_path in self._known_dirs.items():
            if re.search(r"\b" + re.escape(dir_name) + r"\b", msg_lower):
                self._inject_directory(dir_path)

        # 5. Path-style refs: "tools/nova_chat", "nova_advisor/"
        for ref in re.findall(r"[\w]+(?:/[\w]+)+/?", message):
            ref_norm = ref.strip("/").lower()
            if ref_norm in self._known_dirs:
                self._inject_directory(self._known_dirs[ref_norm])
            elif ref_norm in self._known_files:
                self._inject_file(self._known_files[ref_norm])


    def _inject_file(self, rel_path: str):
        """Read a single file from disk into on-demand context."""
        norm = rel_path.replace("\\", "/").lower()
        if any(norm.endswith("/" + k) or norm == k
               for k in self._on_demand):
            return  # already have it

        # Resolve to actual Path
        candidates = []
        parts = rel_path.replace("\\", "/").split("/")
        candidates.append(WORKSPACE_DIR.joinpath(*parts))
        # Try case-insensitive lookup via index
        if norm in self._known_files:
            real_rel = self._known_files[norm]
            candidates.insert(0, WORKSPACE_DIR.joinpath(*real_rel.split("/")))

        for p in candidates:
            if p.exists() and p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    key = str(p.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                    self._on_demand[key] = content[:ONDEMAND_FILE_MAX]
                    return
                except Exception as e:
                    rel_str = str(parts)
                    self._on_demand[rel_str] = f"[read error: {e}]"
                    return

        # Last resort: rglob by filename
        filename = parts[-1]
        for match in WORKSPACE_DIR.rglob(filename):
            if any(skip in match.parts for skip in SKIP_DIRS):
                continue
            if match.suffix.lower() in TEXT_EXTENSIONS:
                try:
                    content = match.read_text(encoding="utf-8", errors="replace")
                    key = str(match.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                    self._on_demand[key] = content[:ONDEMAND_FILE_MAX]
                    return
                except Exception:
                    pass

        self._on_demand[rel_path] = "[file not found on disk]"

    def _inject_directory(self, dir_path: Path):
        """
        Inject a directory listing + all readable file contents recursively.
        Respects DIR_INJECT_MAX total chars to avoid blowing context.
        """
        dir_key = str(dir_path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
        if dir_key in self._on_demand:
            return  # already injected this dir this turn

        total = 0
        injected = []

        # Build listing header
        listing_lines = [f"Directory: {dir_key}/", ""]
        for p in sorted(dir_path.rglob("*")):
            if any(skip in p.parts for skip in SKIP_DIRS):
                continue
            rel = str(p.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            if p.is_dir() and p.name not in SKIP_DIRS:
                listing_lines.append(f"  📁 {rel}/")
            elif p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
                listing_lines.append(f"  📄 {rel}")

        listing = "\n".join(listing_lines)
        injected.append(("__listing__/" + dir_key, listing))
        total += len(listing)

        # Inject each file's contents
        for p in sorted(dir_path.rglob("*")):
            if any(skip in p.parts for skip in SKIP_DIRS):
                continue
            if not p.is_file() or p.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if p.name in SKIP_FILES:
                continue
            if total >= DIR_INJECT_MAX:
                injected.append(("__truncated__/" + dir_key,
                                 "[directory injection truncated -- too many files]"))
                break
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                key = str(p.relative_to(WORKSPACE_DIR)).replace("\\", "/")
                chunk = content[:ONDEMAND_FILE_MAX]
                injected.append((key, chunk))
                total += len(chunk)
            except Exception:
                pass

        for key, content in injected:
            self._on_demand[key] = content

    def pin_file(self, rel_path: str) -> tuple:
        """Pin a file into always-loaded context (persists across turns)."""
        self._inject_file(rel_path)
        norm = rel_path.replace("\\", "/")
        # Find the actual key used
        for key, content in list(self._on_demand.items()):
            if key.endswith(norm.split("/")[-1]) or key == norm:
                if content and not content.startswith("["):
                    self._always[f"[pinned] {key}"] = content
                    del self._on_demand[key]
                    return True, content
                break
        return False, "[file not found]"

    # ── Context building ──────────────────────────────────────────────────────

    def build_context_block(self) -> str:
        """
        Assemble the full context string injected into AI system prompts.
        Contains: workspace manifest, memory files, on-demand files/dirs.
        All content is the actual file text -- no GitHub links.
        """
        parts = []
        total = 0

        parts.append("=" * 70)
        parts.append("NOVA WORKSPACE — LIVE CONTEXT")
        parts.append("All file contents below are read directly from disk.")
        parts.append("Do NOT reference external URLs to look up file contents --")
        parts.append("everything you need is already inline below.")
        parts.append("=" * 70)
        parts.append("")

        # Workspace tree (compact, no URLs)
        parts.append("--- WORKSPACE TREE ---")
        parts.append(self._manifest)
        parts.append("")
        total += len(self._manifest)

        # Always-loaded memory files
        for rel, content in self._always.items():
            if not content or content.startswith("[file not found]"):
                continue
            header = f"--- {rel} ---"
            chunk = f"{header}\n{content}\n"
            if total + len(chunk) > TOTAL_MAX:
                parts.append(f"{header}\n[omitted -- context budget reached]\n")
                break
            parts.append(chunk)
            total += len(chunk)

        # On-demand: directories first (listings), then files
        listings  = {k: v for k, v in self._on_demand.items() if k.startswith("__listing__/")}
        filedata  = {k: v for k, v in self._on_demand.items() if not k.startswith("__")}
        truncated = {k: v for k, v in self._on_demand.items() if k.startswith("__truncated__/")}

        if listings or filedata:
            parts.append("--- AUTO-INJECTED (mentioned in message) ---")

        for key, listing in listings.items():
            dir_name = key.replace("__listing__/", "")
            header = f"--- DIRECTORY: {dir_name}/ ---"
            chunk = f"{header}\n{listing}\n"
            if total + len(chunk) <= TOTAL_MAX:
                parts.append(chunk)
                total += len(chunk)

        for key, content in filedata.items():
            header = f"--- FILE: {key} ---"
            chunk = f"{header}\n{content}\n"
            if total + len(chunk) > TOTAL_MAX:
                parts.append(f"{header}\n[omitted -- context budget reached]\n")
                break
            parts.append(chunk)
            total += len(chunk)

        for key, msg in truncated.items():
            parts.append(f"[{key.replace('__truncated__/', '')}: {msg}]")

        parts.append("")
        parts.append("=" * 70)
        parts.append("END WORKSPACE CONTEXT")
        parts.append("=" * 70)

        return "\n".join(parts)

    def get_file_list_summary(self) -> str:
        always_count = len(self._always)
        on_demand_count = len([k for k in self._on_demand if not k.startswith("__")])
        return f"{always_count} memory files + live manifest" + (
            f" + {on_demand_count} on-demand" if on_demand_count else ""
        )

    def reload(self):
        """Reload everything from disk (called on new session or session switch)."""
        self._refresh()

