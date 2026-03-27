# Last updated: 2026-03-25
import re
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.insert(0, str(Path(__file__).parent.parent))

# Dynamic — watcher.py is at workspace/tools/nova_sync/watcher.py
# workspace/ is three levels up, and the watch root is its parent.
# This means the watcher follows the folder wherever it moves.
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
WATCH_DIR     = WORKSPACE_DIR.parent   # parent of workspace (Project_Nova or .openclaw)
SYNC_DIR      = WORKSPACE_DIR / "tools" / "nova_sync"
INDEX_PATH    = SYNC_DIR / "FILE_INDEX.md"
LINK_PATH     = SYNC_DIR / "FILE_INDEX_LINK.md"
DEBOUNCE_SECONDS = 10

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".clawhub", "screenshots",
}
EXCLUDE_SUBPATHS = {
    "logs/screenshots", "tools/backups", "agents/main/sessions",
}
INCLUDE_EXTENSIONS = {
    ".py", ".md", ".json", ".jsonl", ".txt", ".cmd", ".ps1", ".html"
}
EXCLUDE_FROM_TIMESTAMPS = {
    "FILE_INDEX.md", "FILE_INDEX_LINK.md", "session_start.json",
    "interrupt_inbox.json", "HEARTBEAT.md", ".drive_sync_cache.json",
}
EXCLUDE_FROM_INDEX = {
    ".drive_sync_cache.json",
}
WORKSPACE_ROOT_FILES = {
    "AGENTS.md", "BOOTSTRAP.md", "HEARTBEAT.md", "IDENTITY.md",
    "README.md", "SOUL.md", "TOOLS.md", "USER.md",
}


def update_timestamp_in_file(path: Path):
    if path.name in EXCLUDE_FROM_TIMESTAMPS:
        return
    suffix = path.suffix.lower()
    if suffix not in (".py", ".md"):
        return
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if suffix == ".py":
        pattern = r"^# Last updated: .+$"
        new_line = f"# Last updated: {timestamp}"
        if re.search(pattern, content, re.MULTILINE):
            updated = re.sub(pattern, new_line, content, flags=re.MULTILINE)
        else:
            lines = content.split("\n")
            insert_at = 0
            for i, line in enumerate(lines):
                if line.startswith("#!/"):
                    insert_at = i + 1
                    break
            lines.insert(insert_at, new_line)
            updated = "\n".join(lines)
    elif suffix == ".md":
        pattern = r"^_Last updated: .+_$"
        new_line = f"_Last updated: {timestamp}_"
        if re.search(pattern, content, re.MULTILINE):
            updated = re.sub(pattern, new_line, content, flags=re.MULTILINE)
        else:
            lines = content.split("\n")
            insert_at = 1 if lines and lines[0].startswith("#") else 0
            lines.insert(insert_at, new_line)
            updated = "\n".join(lines)
    else:
        return
    if updated != content:
        try:
            path.write_text(updated, encoding="utf-8")
            print(f"[watcher] Timestamp updated: {path.name}")
        except Exception as e:
            print(f"[watcher] Could not update timestamp in {path.name}: {e}")


def build_file_index(commit_ref=None):
    current_key = 0
    if INDEX_PATH.exists():
        try:
            existing = INDEX_PATH.read_text(encoding="utf-8")
            import re as _re
            match = _re.search(r"_cache_key: (\d+)_", existing)
            if match:
                val = int(match.group(1))
                if val <= 9999999:
                    current_key = val
        except Exception:
            pass
    cache_key = str(current_key + 1).zfill(7)

    if commit_ref is None:
        try:
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=WATCH_DIR, capture_output=True, text=True
            )
            commit_ref = hash_result.stdout.strip()
        except Exception:
            commit_ref = "main"

    github_base = f"https://raw.githubusercontent.com/cklafou/nova-workspace/{commit_ref}"
    lines = []
    lines.append("# FILE_INDEX.md -- Nova Workspace Raw File Index")
    lines.append("_Auto-generated on boot by nova_sync/watcher.py. Do not edit manually._")
    lines.append(f"_Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append(f"_cache_key: {cache_key}_")
    lines.append("")
    lines.append("Claude: all URLs below use a commit hash -- they are cache-proof.")
    lines.append("Fetch any URL directly. No ?t= needed.")
    lines.append(f"Example: {github_base}/workspace/tools/nova_sync/watcher.py")
    lines.append("")

    sections = {}
    excluded_dir_seen = set()
    excluded_subpath_seen = set()

    for path in sorted(WORKSPACE_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.name in EXCLUDE_FROM_INDEX:
            continue
        try:
            rel_display = str(path.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            parts_rel = path.relative_to(WORKSPACE_DIR).parts
        except ValueError:
            continue

        section = parts_rel[0] if len(parts_rel) > 1 else "root"

        excluded_dir = next((e for e in EXCLUDE_DIRS if e in path.parts), None)
        if excluded_dir:
            try:
                excl_parts = list(path.relative_to(WORKSPACE_DIR).parts)
                excl_idx = excl_parts.index(excluded_dir)
                excl_rel = "/".join(excl_parts[:excl_idx + 1])
            except (ValueError, IndexError):
                excl_rel = excluded_dir
            if excl_rel not in excluded_dir_seen:
                excluded_dir_seen.add(excl_rel)
                excl_section = excl_parts[0] if excl_idx > 0 else "root"
                if excl_section not in sections:
                    sections[excl_section] = []
                sections[excl_section].append((f"{excl_rel}/ (excluded)", None))
            continue

        matched_subpath = next(
            (sub for sub in EXCLUDE_SUBPATHS if rel_display.startswith(sub)), None
        )
        if matched_subpath:
            if matched_subpath not in excluded_subpath_seen:
                excluded_subpath_seen.add(matched_subpath)
                subpath_section = matched_subpath.split("/")[0]
                if subpath_section not in sections:
                    sections[subpath_section] = []
                sections[subpath_section].append((f"{matched_subpath}/ (excluded)", None))
            continue

        rel_display_encoded = rel_display.replace(" ", "%20")
        linkable = (
            path.suffix.lower() in INCLUDE_EXTENSIONS
            and path.name != "FILE_INDEX.md"
        )

        if linkable:
            try:
                rel = path.relative_to(WATCH_DIR)
                github_path = str(rel).replace("\\", "/").replace(" ", "%20")
                entry = (rel_display_encoded, f"{github_base}/{github_path}")
            except ValueError:
                entry = (rel_display_encoded, None)
        else:
            entry = (rel_display_encoded, None)

        if section not in sections:
            sections[section] = []
        sections[section].append(entry)

    if "root" in sections:
        lines.append("## Root")
        for rel_path, url in sections["root"]:
            lines.append(f"- [{rel_path}]({url})" if url else f"- {rel_path}")
        lines.append("")

    for section in sorted(k for k in sections if k != "root"):
        lines.append(f"## {section}/")
        for rel_path, url in sections[section]:
            lines.append(f"- [{rel_path}]({url})" if url else f"- {rel_path}")
        lines.append("")

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[watcher] FILE_INDEX.md updated ({len(sections)} sections, "
          f"{sum(len(v) for v in sections.values())} files, cache_key={cache_key})")

    if commit_ref and commit_ref != "main":
        link_url = (
            f"https://raw.githubusercontent.com/cklafou/nova-workspace/"
            f"{commit_ref}/workspace/tools/nova_sync/FILE_INDEX.md"
        )
        LINK_PATH.write_text(link_url + "\n", encoding="utf-8")
        print(f"[watcher] FILE_INDEX_LINK.md updated -> {commit_ref[:8]}")


GATEWAY_REAL = WORKSPACE_DIR / "nova_gateway.json"
GATEWAY_COPY = WORKSPACE_DIR / "nova_gateway - Copy.json"
GATEWAY_TOKEN_PLACEHOLDER = "[place token here]"


def sync_gateway_copy():
    """
    Keep 'nova_gateway - Copy.json' in sync with nova_gateway.json,
    substituting the real discord token with a placeholder so the copy
    is safe to commit to git.
    """
    if not GATEWAY_REAL.exists():
        return
    try:
        import json as _json
        content = _json.loads(GATEWAY_REAL.read_text(encoding="utf-8"))

        # Replace only the discord token; leave everything else identical.
        if "discord" in content and "token" in content["discord"]:
            content["discord"]["token"] = GATEWAY_TOKEN_PLACEHOLDER

        new_text = _json.dumps(content, indent=2) + "\n"

        # Only write if something (other than the token) actually changed.
        old_text = GATEWAY_COPY.read_text(encoding="utf-8") if GATEWAY_COPY.exists() else ""
        if new_text != old_text:
            GATEWAY_COPY.write_text(new_text, encoding="utf-8")
            print(f"[watcher] nova_gateway - Copy.json synced")
    except Exception as e:
        print(f"[watcher] Warning: could not sync gateway copy: {e}")


def git_push(watch_dir):
    try:
        subprocess.run(["git", "add", "."], cwd=watch_dir, check=True,
                       capture_output=True, text=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=watch_dir
        )
        if result.returncode == 1:
            subprocess.run(
                ["git", "commit", "-m", f"auto-commit {time.strftime('%Y-%m-%d %H:%M:%S')}"],
                cwd=watch_dir, check=True, capture_output=True, text=True
            )
            # Push with explicit upstream so it works even on a fresh branch.
            push_result = subprocess.run(
                ["git", "push", "--set-upstream", "origin", "HEAD"],
                cwd=watch_dir, capture_output=True, text=True
            )
            if push_result.returncode != 0:
                print(f"[{time.strftime('%H:%M:%S')}] Git push failed:")
                if push_result.stdout.strip():
                    print(f"  stdout: {push_result.stdout.strip()}")
                if push_result.stderr.strip():
                    print(f"  stderr: {push_result.stderr.strip()}")
                return None
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=watch_dir, capture_output=True, text=True
            )
            commit_hash = hash_result.stdout.strip()
            print(f"[{time.strftime('%H:%M:%S')}] Pushed (commit: {commit_hash[:8]})")
            return commit_hash
        else:
            print(f"[{time.strftime('%H:%M:%S')}] No changes to push")
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=watch_dir, capture_output=True, text=True
            )
            return hash_result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[{time.strftime('%H:%M:%S')}] Git error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"  stderr: {e.stderr.strip()}")
        return None


def copy_to_clipboard(text):
    try:
        subprocess.run(["clip"], input=text.encode("utf-8"), check=True, shell=True)
        print("[watcher] Session URL copied to clipboard.")
    except Exception as e:
        print(f"[watcher] Could not copy to clipboard: {e}")


def print_session_urls(commit_hash, copy_url=False):
    session_url = None
    print("")
    print("=" * 60)
    print("CLAUDE SESSION URL -- paste this to start a Claude session:")
    if commit_hash:
        session_url = (
            f"https://raw.githubusercontent.com/cklafou/nova-workspace/"
            f"{commit_hash}/workspace/tools/nova_sync/FILE_INDEX.md"
        )
        print(session_url)
    else:
        print("(push failed -- check git status)")
    print("=" * 60)
    print("")
    print("GEMINI DRIVE URL -- give this to Gemini once, forever:")
    print("https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya?usp=sharing")
    print("")
    print("CLAUDE BOOTSTRAP (permanent):")
    print("https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md")
    print("")
    if copy_url and session_url:
        copy_to_clipboard(session_url)


def run_push_cycle():
    # Sync the gateway config copy (real token → placeholder) before committing
    sync_gateway_copy()
    # Pass 1: push with a placeholder index (no commit hash yet)
    build_file_index()
    commit_hash = git_push(WATCH_DIR)
    if commit_hash:
        # Pass 2: rebuild index with the real commit hash so all raw URLs are
        # cache-proof, then push that updated index file.
        build_file_index(commit_ref=commit_hash)
        final_hash = git_push(WATCH_DIR)
        if final_hash:
            return final_hash
    return commit_hash


def run_sync_and_backup():
    try:
        from nova_sync.drive import sync_to_drive
        sync_to_drive()
    except Exception as e:
        print(f"[drive] Sync error: {e}")
    try:
        from nova_sync.backup import run_backup
        run_backup()
    except Exception as e:
        import traceback
        print(f"[backup] Backup error: {e}")
        traceback.print_exc()


def _extract_identifiers(path: Path) -> set:
    try:
        content = path.read_text(encoding="utf-8")
        classes = set(re.findall(r"^class\s+(\w+)", content, re.MULTILINE))
        funcs   = set(re.findall(r"^def\s+(\w+)",   content, re.MULTILINE))
        return classes | funcs
    except Exception:
        return set()


def _similarity(staged: Path, target: Path) -> float:
    if staged.suffix.lower() != ".py":
        return 1.0
    staged_ids = _extract_identifiers(staged)
    target_ids = _extract_identifiers(target)
    if not staged_ids and not target_ids:
        return 1.0
    if not staged_ids or not target_ids:
        return 0.0
    overlap = len(staged_ids & target_ids)
    union   = len(staged_ids | target_ids)
    return overlap / union if union > 0 else 0.0


def run_pup_cycle():
    SIMILARITY_THRESHOLD = 0.25

    staged = [
        p for p in sorted(WORKSPACE_DIR.iterdir())
        if p.is_file()
        and p.name not in WORKSPACE_ROOT_FILES
        and p.suffix.lower() in (".py", ".md", ".json", ".jsonl", ".txt", ".html")
    ]

    if not staged:
        print("[pup] No staged files found in workspace root.")
        print(f"[pup] Drop files to patch into: {WORKSPACE_DIR}")
        return None

    print(f"[pup] Found {len(staged)} staged file(s): {[f.name for f in staged]}")
    print("")

    patched = 0
    skipped = 0

    for staged_file in staged:
        name = staged_file.name
        print(f"[pup] Processing: {name}")

        candidates = [
            p for p in WORKSPACE_DIR.rglob(name)
            if p != staged_file
            and p.is_file()
            and len(p.relative_to(WORKSPACE_DIR).parts) > 1
        ]

        if not candidates:
            print(f"[pup]   SKIP: no matching file found in any subdirectory.")
            skipped += 1
            continue

        scored = []
        for c in candidates:
            score = _similarity(staged_file, c)
            rel = str(c.relative_to(WORKSPACE_DIR)).replace("\\", "/")
            scored.append((score, c, rel))
            print(f"[pup]   Candidate: {rel}  (similarity: {score:.0%})")

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_match, best_rel = scored[0]

        if best_score < SIMILARITY_THRESHOLD:
            print(f"[pup]   SKIP: best match '{best_rel}' only {best_score:.0%} similar.")
            skipped += 1
            continue

        top_scorers = [s for s in scored if s[0] == best_score]
        if len(top_scorers) > 1 and best_score < 0.8:
            print(f"[pup]   SKIP: {len(top_scorers)} equally-scored candidates at {best_score:.0%}:")
            for _, _, rel in top_scorers:
                print(f"[pup]     - {rel}")
            skipped += 1
            continue

        content = staged_file.read_text(encoding="utf-8")
        best_match.write_text(content, encoding="utf-8")
        staged_file.unlink()
        print(f"[pup]   PATCHED: {name} -> {best_rel}")
        patched += 1

    print("")
    print(f"[pup] Patch complete: {patched} patched, {skipped} skipped.")

    if patched == 0:
        print("[pup] Nothing patched -- skipping push.")
        return None

    print("[pup] Pushing to GitHub...")
    commit_hash = run_push_cycle()
    run_sync_and_backup()
    print_session_urls(commit_hash, copy_url=True)
    print("[pup] --pup complete. Exiting.")
    return commit_hash


class GitAutoCommit(FileSystemEventHandler):
    def __init__(self):
        self.last_event_time = 0
        self.changed_files = set()

    def on_modified(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle(event.src_path)

    def _handle(self, src_path: str):
        if ".git" in src_path or "__pycache__" in src_path:
            return
        if src_path.endswith(".pyc") or "FILE_INDEX.md" in src_path:
            return
        path = Path(src_path)
        if any(excl in path.parts for excl in EXCLUDE_DIRS):
            return
        if path.suffix.lower() in (".py", ".md"):
            update_timestamp_in_file(path)
        self.changed_files.add(src_path)
        self.last_event_time = time.time()


if __name__ == "__main__":
    PUSH_ONLY = "--push" in sys.argv
    PUP_MODE  = "--pup"  in sys.argv
    FULL_MODE = "--full" in sys.argv

    if PUP_MODE:
        print("[watcher] --pup mode: patch workspace root files, push, exit.")
        run_pup_cycle()
        sys.exit(0)

    if FULL_MODE:
        print("[watcher] --full mode: import audit first, then push.")
        print("")
        print("[watcher] Running interactive import audit (dir_patch)...")
        try:
            from nova_sync.dir_patch import run_audit
            run_audit(interactive=True, auto=False, report_only=False)
        except Exception as e:
            print(f"[dir_patch] Audit error: {e}")
        print("")
        print("[watcher] Audit complete. Proceeding with push...")
        commit_hash = run_push_cycle()
        run_sync_and_backup()
        print_session_urls(commit_hash, copy_url=True)
        print("[watcher] --full complete. Exiting.")
        sys.exit(0)

    if PUSH_ONLY:
        print("[watcher] --push mode: one-shot push then exit.")
        commit_hash = run_push_cycle()
        run_sync_and_backup()
        print_session_urls(commit_hash, copy_url=True)
        print("[watcher] --push complete. Exiting.")
        sys.exit(0)

    # Normal watch mode
    print(f"[watcher] Starting. Watching {WATCH_DIR}")
    print("[watcher] Building initial FILE_INDEX.md...")
    commit_hash = run_push_cycle()
    run_sync_and_backup()
    print_session_urls(commit_hash, copy_url=False)

    handler = GitAutoCommit()
    observer = Observer()
    observer.schedule(handler, str(WATCH_DIR), recursive=True)
    observer.start()
    print(f"[watcher] Watching for changes -- push after {DEBOUNCE_SECONDS}s of inactivity")

    try:
        while True:
            time.sleep(1)
            if handler.last_event_time and (
                time.time() - handler.last_event_time >= DEBOUNCE_SECONDS
            ):
                handler.last_event_time = 0
                handler.changed_files.clear()
                loop_hash = run_push_cycle()
                if loop_hash:
                    print(
                        f"CLAUDE SESSION URL: https://raw.githubusercontent.com/"
                        f"cklafou/nova-workspace/{loop_hash}/workspace/tools/nova_sync/FILE_INDEX.md"
                    )
                try:
                    from nova_sync.drive import sync_to_drive
                    sync_to_drive()
                except Exception as e:
                    print(f"[drive] Sync error: {e}")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
