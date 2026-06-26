# Last updated: 2026-06-27 02:45:45
import re
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

_ws = Path(__file__).parent.parent.parent
for _p in [str(_ws / "nova_body"), str(_ws / "general_tools")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Dynamic — watcher.py is at workspace/general_tools/nova_sync/watcher.py
# workspace/ is three levels up, and the watch root is its parent.
# This means the watcher follows the folder wherever it moves.
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
WATCH_DIR     = WORKSPACE_DIR.parent   # parent of workspace/ (e.g. Project_Nova/)
SYNC_DIR      = WORKSPACE_DIR / "general_tools" / "nova_sync"
INDEX_PATH    = SYNC_DIR / "FILE_INDEX.md"
LINK_PATH     = SYNC_DIR / "FILE_INDEX_LINK.md"
DEBOUNCE_SECONDS = 10

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", "screenshots",
}
EXCLUDE_SUBPATHS = set([
    "logs", "nova_body/backups", "general_tools/backups",
    "agents/main/sessions",
])

# Read .aignore dynamically and append to EXCLUDE_SUBPATHS
try:
    _aignore_file = WATCH_DIR / ".aignore"
    if _aignore_file.exists():
        for _line in _aignore_file.read_text("utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#"):
                # Remove trailing slash
                if _line.endswith("/"): _line = _line[:-1]
                # If the line starts with workspace/, strip it since EXCLUDE_SUBPATHS
                # are evaluated relative to WORKSPACE_DIR
                if _line.startswith("workspace/"):
                    EXCLUDE_SUBPATHS.add(_line[10:])
                else:
                    # Generic dir ignore
                    EXCLUDE_DIRS.add(_line)
except Exception as e:
    print(f"[watcher] Failed to load .aignore: {e}")

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
    "AGENTS.md", "BOOTSTRAP.md", "HEARTBEAT.md", "NOVA.md",
    "README.md", "TOOLS.md", "COLE.md",
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
    # Strip a leading BOM before doing anything. Python rejects a U+FEFF that is
    # not the very first bytes of a file, and prepending a "# Last updated" line
    # above a BOM relocates it mid-file → fatal SyntaxError (this exact bug crashed
    # server.py). Dropping it means we can never re-position a BOM, and we quietly
    # clean any file we stamp.
    if content and content[0] == "\ufeff":
        content = content.lstrip("\ufeff")
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
    lines.append(f"Example: {github_base}/workspace/general_tools/nova_sync/watcher.py")
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

        # Skip the Nova app's per-pid Chrome profile (.nova_app_profile_<pid>): it's
        # thousands of locked/binary files, never useful in the index, and git ignores it.
        if any(p.startswith(".nova_app_profile") for p in parts_rel):
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
            f"{commit_ref}/workspace/general_tools/nova_sync/FILE_INDEX.md"
        )
        LINK_PATH.write_text(link_url + "\n", encoding="utf-8")
        print(f"[watcher] FILE_INDEX_LINK.md updated -> {commit_ref[:8]}")





def _detect_and_queue_changes(watch_dir: Path, commit_hash: str) -> None:
    """
    Run after a successful commit to detect renamed, deleted, and new files.
    Writes events to memory/audit_queue.json for later review.

    Strategy:
      1. git diff --name-status -M  → authoritative rename detection (with similarity %)
      2. For deletes with no git-detected rename partner, cross-reference against
         new files using _similarity() as a fallback for low-similarity renames
         that git missed.
    """
    try:
        import sys as _sys
        _ws = Path(__file__).resolve().parent.parent.parent
        for _p in [str(_ws / "general_tools")]:
            if _p not in _sys.path:
                _sys.path.insert(0, _p)
        from audit_queue import add_item

        # git diff --name-status -M80 HEAD~1 HEAD
        # -M80 = detect renames at ≥80% similarity (slightly above git's 70% default)
        diff = subprocess.run(
            ["git", "diff", "--name-status", "-M80", "HEAD~1", "HEAD"],
            cwd=str(watch_dir), capture_output=True, text=True
        )
        if diff.returncode != 0:
            return

        short_hash  = commit_hash[:8]
        renames     = {}   # old_path → (new_path, confidence)
        deletions   = []   # old_path (no rename partner found yet)
        additions   = []   # new_path (no rename source found yet)

        for line in diff.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status = parts[0]

            if status.startswith("R"):
                # R097  old/path.py  new/path.py
                try:
                    pct  = int(status[1:]) / 100.0
                except ValueError:
                    pct  = 1.0
                old  = parts[1] if len(parts) > 1 else None
                new  = parts[2] if len(parts) > 2 else None
                # Strip leading "workspace/" if present (repo root may differ)
                if old:
                    old = old.removeprefix("workspace/")
                if new:
                    new = new.removeprefix("workspace/")
                if old and new:
                    renames[old] = (new, pct)
                    add_item(
                        event_type="rename",
                        commit=short_hash,
                        confidence=pct,
                        old_path=old,
                        new_path=new,
                    )
                    print(f"[watcher] queued rename: {old} → {new} ({pct:.0%})")

            elif status == "D":
                old = parts[1] if len(parts) > 1 else None
                if old:
                    old = old.removeprefix("workspace/")
                    if old not in renames:
                        deletions.append(old)

            elif status == "A":
                new = parts[1] if len(parts) > 1 else None
                if new:
                    new = new.removeprefix("workspace/")
                    additions.append(new)

        # ── Fallback: cross-reference unmatched deletes against new files ──────
        # Only .py files — non-code files don't have meaningful function signatures
        SIMILARITY_THRESHOLD = 0.20   # lower than pup's 0.25 — we just want a flag
        matched_adds = set()

        for old_rel in deletions:
            if not old_rel.endswith(".py"):
                add_item(
                    event_type="delete",
                    commit=short_hash,
                    confidence=1.0,
                    old_path=old_rel,
                )
                print(f"[watcher] queued delete: {old_rel}")
                continue

            old_abs = watch_dir / old_rel
            # File is deleted — reconstruct from git show HEAD~1:<path>
            try:
                show = subprocess.run(
                    ["git", "show", f"HEAD~1:{old_rel}"],
                    cwd=str(watch_dir), capture_output=True, text=True
                )
                if show.returncode == 0:
                    # Write to a temp path so _similarity() can read it
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".py", delete=False, encoding="utf-8"
                    ) as tf:
                        tf.write(show.stdout)
                        tmp_path = Path(tf.name)
                    old_abs = tmp_path
                else:
                    old_abs = None
            except Exception:
                old_abs = None

            best_score  = 0.0
            best_add    = None
            for new_rel in additions:
                if new_rel in matched_adds or not new_rel.endswith(".py"):
                    continue
                new_abs = watch_dir / new_rel
                if not new_abs.exists():
                    continue
                score = _similarity(old_abs, new_abs) if old_abs else 0.0
                if score > best_score:
                    best_score = score
                    best_add   = new_rel

            # Clean up temp file
            if old_abs and str(old_abs).startswith(tempfile.gettempdir()):
                try:
                    os.unlink(old_abs)
                except Exception:
                    pass

            if best_add and best_score >= SIMILARITY_THRESHOLD:
                matched_adds.add(best_add)
                add_item(
                    event_type="possible_rename",
                    commit=short_hash,
                    confidence=best_score,
                    old_path=old_rel,
                    new_path=best_add,
                    notes=f"git missed rename; _similarity()={best_score:.0%}",
                )
                print(f"[watcher] queued possible_rename: {old_rel} → {best_add} ({best_score:.0%})")
            else:
                add_item(
                    event_type="delete",
                    commit=short_hash,
                    confidence=1.0,
                    old_path=old_rel,
                )
                print(f"[watcher] queued delete: {old_rel}")

        # ── Unmatched additions ────────────────────────────────────────────────
        for new_rel in additions:
            if new_rel not in matched_adds:
                add_item(
                    event_type="new",
                    commit=short_hash,
                    confidence=1.0,
                    new_path=new_rel,
                )
                print(f"[watcher] queued new file: {new_rel}")

    except Exception as e:
        print(f"[watcher] audit_queue error (non-fatal): {e}")


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
            # Detect file changes and populate the audit queue
            _detect_and_queue_changes(Path(watch_dir), commit_hash)
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
            f"{commit_hash}/workspace/general_tools/nova_sync/FILE_INDEX.md"
        )
        print(session_url)
    else:
        print("(push failed -- check git status)")
    print("=" * 60)
    print("")
    print("CLAUDE BOOTSTRAP (permanent):")
    print("https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/general_tools/nova_sync/FILE_INDEX_LINK.md")
    print("")
    if copy_url and session_url:
        copy_to_clipboard(session_url)


def run_drive_sync():
    """Mirror the workspace to Google Drive so Gemini sees an up-to-date copy.
    Diff-based (only changed files upload). Non-fatal: a Drive hiccup or missing
    Google credentials must never block the git push or crash the watch loop.
    Restored 2026-05-26 — Gemini can't reliably read raw GitHub URLs, so Drive is
    the channel that keeps it able to see Project Nova."""
    try:
        from nova_sync import drive
        drive.sync_to_drive()
    except Exception as e:
        print(f"[drive] sync skipped (non-fatal): {e}")


def run_push_cycle():
    # Pass 1: push with a placeholder index (no commit hash yet)
    build_file_index()
    commit_hash = git_push(WATCH_DIR)
    result = commit_hash
    if commit_hash:
        # Pass 2: rebuild index with the real commit hash so all raw URLs are
        # cache-proof, then push that updated index file.
        build_file_index(commit_ref=commit_hash)
        final_hash = git_push(WATCH_DIR)
        if final_hash:
            result = final_hash
    # Drive rides along with every GitHub push so Gemini's mirror updates at the
    # same moment Claude's GitHub index does — both at once (Cole's call 2026-05-26).
    run_drive_sync()
    return result


def run_sync_and_backup():
    # Drive sync now rides inside run_push_cycle() (fires with every GitHub push),
    # so this only handles local session/weekly backups. Git remains the history /
    # source of truth; Drive is Gemini's readable mirror.
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


# The watcher calls run_manifest_pass after EVERY debounced batch of file changes, and Nova's
# autonomy writes state files constantly — so without throttling this regenerated + emitted a
# "manifest refreshed" Live Log line every ~13s (the spam Cole saw) AND its writes fed her
# change-wake loop. Cap real regens to once / interval, and only EMIT when the manifest actually
# changed (part count / flags differ) so the Live Logs feed stays quiet when nothing moved.
_MANIFEST_MIN_INTERVAL_S = 300
_last_manifest = {"sig": None, "ts": 0.0}


def run_manifest_pass():
    """Regenerate Nova's Body Manifest (SELF/) and log a drift summary so her
    self-model stays in sync with the code. Throttled + deduped (see note above)."""
    import json as _json, subprocess as _sp, time as _time
    from datetime import datetime as _dt
    if _time.time() - _last_manifest["ts"] < _MANIFEST_MIN_INTERVAL_S:
        return                                   # throttle: at most one regen per interval
    _last_manifest["ts"] = _time.time()
    bm = WORKSPACE_DIR / "general_tools" / "build_manifest.py"
    if not bm.exists():
        return
    try:
        _sp.run([sys.executable, str(bm)], cwd=str(WORKSPACE_DIR),
                capture_output=True, timeout=120)
    except Exception as e:
        print(f"[manifest] regen error: {e}")
        return
    try:
        mf = WORKSPACE_DIR / "SELF" / "reference" / "manifest.json"
        data = _json.loads(mf.read_text(encoding="utf-8"))
        fl = data.get("flags", {})
        und = fl.get("undescribed", [])
        dead = fl.get("dead_part_candidates", [])
        sig = (data.get("part_count"), tuple(sorted(und)), tuple(sorted(dead)))
        if sig == _last_manifest["sig"]:
            return                               # unchanged → don't spam the Live Logs feed
        _last_manifest["sig"] = sig
        text = (f"Body manifest refreshed: {data.get('part_count')} parts, "
                f"{len(und)} undescribed, {len(dead)} no-inbound-ref")
        print(f"[manifest] {text}")
        ev_dir = WORKSPACE_DIR / "logs" / "events"
        ev_dir.mkdir(parents=True, exist_ok=True)
        payload = {"type": "nova_event", "event": "manifest", "text": text,
                   "level": "info",
                   "ts": _dt.now().isoformat(),
                   "undescribed": und, "dead_part_candidates": dead}
        with open(ev_dir / f"events-{_dt.now().strftime('%Y-%m-%d')}.jsonl",
                  "a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[manifest] drift-log error: {e}")


def run_audit_pass():
    """Run the code-health audit once and log a one-line summary so broken calls,
    dead code, or unreferenced files (e.g. after moving docs into SELF/) are caught
    automatically on boot. Added 2026-05-24."""
    import subprocess as _sp, json as _aj
    from datetime import datetime as _dt
    ap = WORKSPACE_DIR / "general_tools" / "audit_scripts.py"
    if not ap.exists():
        return
    try:
        r = _sp.run([sys.executable, str(ap), "--summary"],
                    capture_output=True, text=True, timeout=180, cwd=str(WORKSPACE_DIR))
        summary = (r.stdout or "").strip() or "audit complete"
        print(f"[audit] {summary}")
        ev = WORKSPACE_DIR / "logs" / "events"
        ev.mkdir(parents=True, exist_ok=True)
        with open(ev / f"events-{_dt.now().strftime('%Y-%m-%d')}.jsonl", "a",
                  encoding="utf-8") as f:
            f.write(_aj.dumps({"type": "nova_event", "event": "audit",
                               "text": summary[:300],
                               "level": "warn" if r.returncode else "info",
                               "ts": _dt.now().isoformat()}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[audit] pass skipped: {e}")


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
        # The Nova app's per-pid Chrome profile (.nova_app_profile_<pid>) lives in the
        # workspace and churns constantly. Ignoring it here stops that churn from
        # triggering a push+Drive cycle — a Drive read of its locked files hung the
        # server (Cole, 2026-05-26). git already ignores it via .gitignore.
        if ".nova_app_profile" in src_path:
            return
        path = Path(src_path)
        # SELF/ is generated by run_manifest_pass(). Ignoring it here breaks the
        # watcher<->manifest feedback loop: a regen writes SELF/ files, which the
        # watcher would otherwise see as changes and regen again, forever (and it
        # would stamp timestamps into generated files). Generated output is still
        # committed on the next real source change.
        if "SELF" in path.parts:
            return
        # logs/ is pure runtime output: event feed (logs/events/*.jsonl), session
        # transcripts, and the manifest/audit drift lines that run_manifest_pass and
        # run_audit_pass APPEND to logs/events. Watching it creates a self-sustaining
        # loop — a regen writes a "manifest" line, the watcher sees the .jsonl change,
        # debounces, regenerates, writes another line, forever (~every debounce). That
        # loop floods Nova's Live Logs feed and spams git. Logs are data, never source.
        if "logs" in path.parts:
            return
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
    run_manifest_pass()
    run_audit_pass()

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
                run_manifest_pass()
                if loop_hash:
                    print(
                        f"CLAUDE SESSION URL: https://raw.githubusercontent.com/"
                        f"cklafou/nova-workspace/{loop_hash}/workspace/general_tools/nova_sync/FILE_INDEX.md"
                    )
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
