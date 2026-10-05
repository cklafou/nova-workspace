# @nova: Generates Orient documentation and validates source, review and link freshness.
# Last updated: 2026-10-05 20:33:22
"""Publish Nova's four orientation documents independently of Git/Drive sync.

The source inventory and API/tool tables are derived without importing Nova. Reviewed
explanations live here alongside the existing architecture explorer. Runtime evidence
is explicitly dated; source discovery never upgrades a feature to 'live verified'.

Explanations cannot be derived, so they are tracked instead (Claude, 2026-10-02). Every
hand-written section, here or in notes/, is registered in reviews.json with the sources it
describes and the date it was last reviewed. When those sources change, the published section
carries a warning line until someone re-reads it and runs --mark-reviewed. Before this, every
regeneration stamped a fresh date on prose that had not changed, so stale text looked current,
which is worse than an old date because it signals a freshness the text does not have.
"""
from __future__ import annotations

import argparse
import ast
import functools
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

HERE = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = HERE.parent.parent
SKIP = {"models", "llama", ".git", "__pycache__", "node_modules", "vendor", "Temp", "temp",
        "_admin", "_build", "build", "dist", ".venv", "venv", "prompt_cache", "nova_memory_db", "logs"}
SECRET_NAMES = {".env", ".auth_token", "nova_users.json", "client_secrets.json", "nova_drive_token.json"}
SECRET_SUFFIXES = (".key", ".pem", ".p12", ".pfx", "_token.json", "_secret.json", "_secrets.json", ".credentials.json")
SOURCE_SUFFIXES = {".py", ".ps1", ".cmd", ".sh", ".js", ".css", ".html", ".toml"}
PURPOSES = {
    "nova_paths": "Canonical body/workspace paths; relocated state never falls back to a second copy.",
    "nova_config": "Body settings loader. Some execution paths still have independent constants; this is not yet universal configuration.",
    "nova_cortex": "Task board, wake decisions, wants, speaker roles, witness/integrity checks, tunables and shared identity/context loading.",
    "nova_runtime": "Model dispatch, headless autonomy, transcript, event bus, provider lifecycle and KoELS equip operations.",
    "nova_voice": "Local inference client, parsing/tool loop, shell/file tools and durable execution receipts. The retired host-desktop Claude ping is no longer registered.",
    "nova_senses": "Time, environment changes, presence, touch, sight, web access and proprioception.",
    "nova_lancedb": "Semantic/visual memory store, embeddings and asynchronous indexing; separate from journal files.",
    "nova_memory": "Journal/goals/log-reader helpers. Some overlap with router-owned journaling remains.",
    "nova_logs": "Log paths, thought/action records and retention. Historical receipts remain evidence, not proof of current behavior.",
    "nova_forge": "Discovery, classification and testing of Nova-authored extensions on her shelf.",
    "nova_computer": "VM observation, command and input tools in the normal voice router; explicit human handoff pauses actions.",
    "nova_imagination": "Image generation and art workflow; uses optional external ComfyUI services.",
    "nova_play": "Curiosity and saved discoveries, including the curio shelf.",
    "nova_witness": "Witness model launch, evaluation and training utilities; replay v4 shares live evidence/dispatch/sampling and constrained audit JSON, with frozen regression controls, open development cases and a sealed holdout. Live auditing lives in cortex/voice.",
}
OWNERS = {
    "memory": "Personal memory and operational state, including autonomy, roles, tunables and loadout intent.",
    "logs": "Transcripts, receipts, events, diagnostics and retained history.",
    "SELF": "Nova's self-model, reference material, portrait and avatar project.",
    "Tasking": "Persistent task board and generated human view.",
    "nova_memory_db": "LanceDB data; preserve independently of code and never assume a folder exists means recall works.",
    "KoELS": "Expert/loadout manifests; weights remain an explicitly configured inference-provider dependency.",
    "Nova_Created": "Nova's authored artifacts and forged extensions. Face-dependent extensions are optional even when stored here.",
    "nova_config.json": "Body settings, including optional cloud-provider configuration.",
    "nova_status.json": "Persisted body status.",
}


# ── Keeping explanations honest (Claude, 2026-10-02) ──────────────────────────────────────
# Facts regenerate freely; explanations record intent and evidence no parser can infer. Each
# hand-written section (in render() below or in notes/) is registered in reviews.json with the
# sources it describes. When they change, the section carries a ⚠ line until it is re-read and
# marked reviewed. Watching a symbol (`path::name`) instead of a whole file keeps unrelated edits
# in a 4,000-line module from raising false alarms that would teach everyone to ignore them.
ARCH_REL = "general_tools/architecture_map"
NOTES_REL = ARCH_REL + "/notes"
REVIEWS_REL = ARCH_REL + "/reviews.json"
EXPLORER_REL = "Orient/Architecture/architecture.json"
SHELF_GLOBS = ("nova_body/Nova_Created/nova_body/tools/*.py",
               "nova_body/Nova_Created/general_tools/tools/*.py")
AGENT_FILES = ("AGENTS.md", "CLAUDE.md")
NAMES = ["README.md", "ARCHITECTURE.md", "OPERATIONS.md", "INDEX.md"]
NOTE_ANCHORS = {"ARCHITECTURE.md": "Statically registered tools", "OPERATIONS.md": "Declared interface routes"}
BACKUP_RE = re.compile(r"(?:\.bak|_bak|\.orig)$", re.I)
ORIENT_REF = re.compile(r"Orient/([A-Za-z0-9_\-./]+?\.(?:md|html|json|svg|cmd))(#[A-Za-z0-9_\-]+)?")
LINK_SCAN = {".py", ".md", ".cmd", ".ps1", ".sh", ".js", ".html", ".txt"}
DESCRIBE = {".py", ".md", ".cmd", ".bat", ".ps1", ".sh", ".js", ".html", ".css", ".toml", ".txt"}
# The project rule (OPERATIONS.md, "File conventions"): every file states its job in its first lines.
PURPOSE_LINE = re.compile(r"\s*(?:#|REM\b|rem\b|//|::|<!--|/\*)\s*@nova:\s*(.+?)\s*(?:-->|\*/)?\s*$")
# Orient/AI Notes: the agents' shared notebook (Cole, 2026-10-03). Hand-written, never generated.
AI_NOTES, NOTE_RULES = "AI Notes", "ReadMeBeforeNoteTaking.md"
NOTE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}_[A-Z][A-Za-z0-9]*_[A-Z][A-Za-z0-9]*\.[A-Za-z0-9]+$")
# Her self-model, board and personal notes are hers; the index lists them but never quotes them.
PRIVATE = ("nova_body/SELF/", "nova_body/Tasking/", "nova_body/memory/", "nova_body/logs/",
           "nova_body/Nova_Created/nova_night_notes/")
_NOISE = re.compile(r"last updated|coding[:=]|^-\*-|^@echo|^setlocal", re.I)
# The sync watcher stamps "_Last updated: <time>_" into any Markdown file it sees change, on the
# first line, above any front matter. It is sync metadata, never content.
WATCHER_STAMP = re.compile(r"^_Last updated: [^_\n]*_$")
# The same stamps inside watched files. The watcher rewrites them whenever anything touches a file:
# principals.py was restamped on 2026-10-01 with no other change. Review digests ignore them.
STAMP_LINES = re.compile(rb"(?m)^(?:# Last updated: [^\n]*|_Last updated: [^\n]*_)\n?")


def _code_digest():
    """This generator's own source, with watcher stamps and line endings ignored."""
    try:
        raw = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return None
    return hashlib.sha256(STAMP_LINES.sub(b"", raw)).hexdigest()


# Nova Chat and the watcher import this module once and keep it for days. When orient.py changes on
# disk after that, their copy is old code: on 2026-10-03 Nova Chat's 30-second refresh kept
# republishing the previous format over the new one. A fresh process (the commit hook, the watcher's
# next start, a manual run) publishes instead.
_LOADED_CODE = _code_digest()


def _read(path, limit=None):
    try:
        with open(path, "rb") as fh:
            return fh.read(limit) if limit else fh.read()
    except OSError:
        return None


def _clip(text, width=140):
    text = " ".join(str(text).split()).replace("|", "\\|")
    if len(text) <= width:
        return text
    return text[:width].rsplit(" ", 1)[0] + "…"


def describe(workspace, rel):
    """One line about a file, taken from the file itself — never guessed from its name.

    Order: the `@nova:` purpose line (the project rule — OPERATIONS.md, "File conventions"), a Python
    docstring, the `description` of one of Nova's tools, a Markdown title, a script comment, an HTML
    title. Nothing found means no description, not an invented one."""
    suffix = Path(rel).suffix.lower()
    if rel.startswith(PRIVATE) or BACKUP_RE.search(rel):
        return ""
    raw = _read(workspace / rel, 524288)
    if raw is None:
        return ""
    if not suffix and raw.startswith(b"#!"):
        suffix = ".sh"
    if suffix not in DESCRIBE:
        return ""
    text = raw.decode("utf-8-sig", "replace")
    lines = text.splitlines()
    for line in lines[:40]:
        m = PURPOSE_LINE.match(line)
        if m:
            return _clip(m.group(1))
    # A purpose line is written to be indexed. Other text in Nova's own Markdown may be personal
    # writing, so nothing else there is ever quoted.
    if suffix in {".md", ".txt"} and rel.startswith("nova_body/"):
        return ""
    if suffix == ".py":
        try:
            doc = ast.get_docstring(_parsed(raw)[1])
        except (SyntaxError, ValueError, UnicodeError):
            doc = None
        first = next((l for l in (doc or "").splitlines() if l.strip()), "")
        return _clip(first) if first else _clip(_tool_description(raw))
    if suffix == ".md":
        return next((_clip(l[2:]) for l in lines[:15] if l.startswith("# ")), "")
    if suffix in {".cmd", ".bat"}:
        for line in lines[:15]:
            m = re.match(r"\s*(?:REM|rem|::)\s+(.+)", line) or re.match(r"\s*title\s+(.+)", line, re.I)
            if m and not _NOISE.search(m.group(1)):
                return _clip(m.group(1))
        return ""
    if suffix == ".html":
        m = re.search(r"<title>(.*?)</title>", text[:4096], re.I | re.S)
        return _clip(m.group(1)) if m else ""
    for line in lines[:15]:
        if line.startswith("#!"):
            continue
        m = re.match(r"\s*(?:#|//|/\*)\s*(.+?)\s*(?:\*/)?\s*$", line)
        if m and len(m.group(1)) > 3 and not _NOISE.search(m.group(1)):
            return _clip(m.group(1))
    return ""


def _tool_description(raw):
    """The `description` in a module-level `TOOL = {...}` — how Nova's own tools say what they do."""
    try:
        body = _parsed(raw)[1].body
    except (SyntaxError, ValueError, UnicodeError):
        return ""
    for node in body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                and any(isinstance(t, ast.Name) and t.id == "TOOL" for t in node.targets)):
            for key, value in zip(node.value.keys, node.value.values):
                if (isinstance(key, ast.Constant) and key.value == "description"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    return value.value
    return ""


def ai_notes(workspace):
    """(notes newest first, misnamed files) in Orient/AI Notes. The name starts with its own
    timestamp, so sorting the names is sorting by time."""
    folder = Path(workspace) / "Orient" / AI_NOTES
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
    except OSError:
        return [], []
    notes, misnamed = [], []
    for name in names:
        if name == NOTE_RULES:
            continue
        try:
            ok = bool(NOTE_NAME.match(name)) and bool(datetime.strptime(name[:15], "%Y-%m-%d_%H%M"))
        except ValueError:
            ok = False
        (notes if ok else misnamed).append(name)
    return sorted(notes, reverse=True), misnamed


def needs_purpose(workspace, rel):
    """Whether the purpose-line rule applies: a file that can hold a comment and is not one of
    Nova's own records or a backup. JSON and other comment-less formats are exempt."""
    suffix = Path(rel).suffix.lower()
    if rel.startswith(PRIVATE) or BACKUP_RE.search(rel):
        return False
    if not suffix:
        head = _read(Path(workspace) / rel, 2)
        return bool(head) and head.startswith(b"#!")
    return suffix in DESCRIBE

def _slug(heading):
    return re.sub(r"\s", "-", re.sub(r"[^\w\- ]", "", heading.strip().lower()))


def _anchors(markdown):
    return {_slug(m.group(1)) for m in re.finditer(r"^#{1,6}[ \t]+(.+?)[ \t]*$", markdown, re.M)}


@functools.lru_cache(maxsize=32)
def _parsed(raw):
    text = raw.decode("utf-8-sig")
    return text, ast.parse(text)


def _symbol_bytes(raw, symbol):
    """Every definition or assignment named `symbol`, decorators included, concatenated."""
    try:
        text, tree = _parsed(raw)
    except (SyntaxError, UnicodeError, ValueError):
        return None
    lines = text.splitlines(keepends=True)
    parts = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            hit = node.name == symbol
        elif isinstance(node, ast.Assign):
            hit = any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets)
        elif isinstance(node, ast.AnnAssign):
            hit = isinstance(node.target, ast.Name) and node.target.id == symbol
        else:
            hit = False
        if hit:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            parts.append("".join(lines[start - 1:node.end_lineno]))
    return "".join(parts).encode("utf-8") if parts else None


def _expand_watch(workspace, patterns):
    keys = set()
    for pattern in patterns:
        path, _, symbol = pattern.partition("::")
        if symbol or not any(ch in path for ch in "*?["):
            keys.add(pattern)
        else:
            keys.update(p.relative_to(workspace).as_posix() for p in workspace.glob(path)
                        if p.is_file() and "__pycache__" not in p.parts)
    return sorted(keys)


def _watch_digest(workspace, key, reader=None, legacy=False):
    path, _, symbol = key.partition("::")
    raw = reader(path) if reader else _read(workspace / path)
    if raw is not None:
        # Line endings are not content. On 2026-10-02 an editor rewrote server.py from CRLF to LF
        # minutes after a review, and every watched symbol in it "changed" at once. A tracker that
        # cries wolf on that gets ignored, so digests compare text, not newline bytes.
        raw = raw.replace(b"\r\n", b"\n")
        # Nor is the watcher's "Last updated" stamp (STAMP_LINES). `legacy` reproduces digests
        # recorded before stamps were ignored, so those baselines still count.
        if not symbol and not legacy:
            raw = STAMP_LINES.sub(b"", raw)
    if raw is not None and symbol:
        raw = _symbol_bytes(raw, symbol)
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def load_reviews(workspace):
    path = Path(workspace) / REVIEWS_REL
    if not path.exists():
        return {}  # isolated/new workspaces can have no prose registry yet
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sections = data["sections"]
        if not isinstance(sections, dict) or any(
                not isinstance(key, str) or not isinstance(entry, dict)
                or not isinstance(entry.get("watch", []), list)
                or not all(isinstance(item, str) for item in entry.get("watch", []))
                or not isinstance(entry.get("baseline", {}), dict)
                for key, entry in sections.items()):
            raise ValueError("sections must contain review objects with watch lists and baselines")
        return sections
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Cannot validate Orient: invalid review registry {path}: {exc}") from exc


def review_status(workspace, sections):
    status = {}
    for key, entry in sections.items():
        base = entry.get("baseline", {})
        now = {k: d for k in _expand_watch(workspace, entry.get("watch", []))
               if (d := _watch_digest(workspace, k)) is not None}

        def moved(k):
            return base[k] not in (now[k], "unknown") and (
                "::" in k or base[k] != _watch_digest(workspace, k, legacy=True))

        st = {"reviewed": entry.get("reviewed"), "edit": entry.get("edit"),
              # "unknown" = the state at review could not be established (see reviews.json "about").
              "unconfirmed": sorted(k for k in now if base.get(k) == "unknown"),
              "changed": sorted(k for k in now if k in base and moved(k)),
              "added": sorted(k for k in now if k not in base),
              "removed": sorted(k for k in base if k not in now)}
        st["stale"] = bool(st["changed"] or st["added"] or st["removed"] or st["unconfirmed"])
        status[key] = st
    return status


def mark_reviewed(workspace, keys, today=None):
    """Record that sections were re-read against their sources: baseline := current digests."""
    workspace = Path(workspace).resolve()
    path = workspace / REVIEWS_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    sections = data.setdefault("sections", {})
    targets = list(sections) if list(keys) == ["all"] else list(keys)
    unknown = [k for k in targets if k not in sections]
    if unknown:
        raise SystemExit("Unknown section(s): " + ", ".join(unknown) + "\nKnown:\n  " + "\n  ".join(sections))
    stamp = today or datetime.now(timezone.utc).date().isoformat()
    for key in targets:
        entry = sections[key]
        entry["reviewed"] = stamp
        entry["baseline"] = {k: d for k in _expand_watch(workspace, entry.get("watch", []))
                             if (d := _watch_digest(workspace, k)) is not None}
    atomic_write(path, json.dumps(data, indent=2) + "\n")
    return targets


def _review_line(key, st):
    def names(items):
        shown = ", ".join(f"`{i}`" for i in items[:4])
        return shown + (f" and {len(items) - 4} more" if len(items) > 4 else "")
    bits = ([f"changed {names(st['changed'])}"] if st["changed"] else []) + \
           ([f"new {names(st['added'])}"] if st["added"] else []) + \
           ([f"gone {names(st['removed'])}"] if st["removed"] else []) + \
           ([f"cannot confirm {names(st['unconfirmed'])} is unchanged"] if st.get("unconfirmed") else [])
    where = st.get("edit") or ARCH_REL + "/orient.py"
    return (f"> ⚠ **Review needed.** Since this section was reviewed ({st.get('reviewed') or 'never'}): "
            + "; ".join(bits) + f". Re-read it against the code, update it in `{where}`, then run "
            f"`python {ARCH_REL}/orient.py --mark-reviewed \"{key}\"`.")


def apply_reviews(docs, status):
    """Put a ⚠ line under every stale section. Returns registry keys that match no section."""
    missing = []
    for key in sorted(status):
        doc, _, heading = key.partition("#")
        text = docs.get(doc)
        m = None
        if text is not None:
            pattern = (r"^#{1,6}[ \t]+" + re.escape(heading) + r"[ \t]*$") if heading else r"^_.+_[ \t]*$"
            m = re.search(pattern, text, re.M)
        if m is None:
            missing.append(key)
        elif status[key]["stale"]:
            docs[doc] = text[:m.end()] + "\n\n" + _review_line(key, status[key]) + text[m.end():]
    return missing


def load_notes(workspace):
    notes = []
    for path in sorted((Path(workspace) / NOTES_REL).glob("*.md")):
        lines = path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()
        # Drop the watcher's stamp wherever it lands. Above the front matter it hides `doc:` and
        # `order:`, so the note would silently fall back to OPERATIONS.md (all four notes were
        # stamped on 2026-10-02); anywhere else it would leak into the published docs.
        # A note's own `@nova:` line describes the note file in INDEX; it is not section text.
        text = "\n".join(ln for ln in lines if not WATCHER_STAMP.match(ln.strip())
                          and not PURPOSE_LINE.match(ln)).lstrip("\n") + "\n"
        meta, body = {}, text
        if text.startswith("---"):
            head, sep, rest = text[3:].partition("\n---")
            if sep:
                for line in head.strip().splitlines():
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
                body = rest.lstrip("\n")
        try:
            order = int(meta.get("order", "50"))
        except ValueError:
            order = 50
        notes.append((meta.get("doc", "OPERATIONS.md"), order, path.name, body.rstrip() + "\n"))
    return sorted(notes, key=lambda n: (n[0], n[1], n[2]))


def tunables_table(workspace):
    raw = _read(Path(workspace) / "nova_body/nova_cortex/tunables.py")
    if raw is None:
        return "_No tunables registry at `nova_body/nova_cortex/tunables.py`._"
    try:
        tree = _parsed(raw)[1]
    except (SyntaxError, UnicodeError, ValueError):
        return "_`tunables.py` does not parse, so its registry cannot be listed._"
    registry = None
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None)
        if isinstance(target, ast.Name) and target.id == "REGISTRY" and getattr(node, "value", None) is not None:
            try:
                registry = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                registry = None
    if not isinstance(registry, dict) or not registry:
        return "_`REGISTRY` is not a plain literal, so it cannot be listed without importing Nova._"
    out = "| Knob | Label | Category | Default | Range |\n|---|---|---|---|---|\n"
    for key, meta in sorted(registry.items(), key=lambda kv: (str(kv[1].get("category", "")), kv[0])):
        span = "on / off" if meta.get("type") == "bool" else \
            f"{meta.get('min', '…')}–{meta.get('max', '…')}" if ("min" in meta or "max" in meta) else ""
        out += (f"| `{key}` | {_clip(meta.get('label', ''), 60)} | {_clip(meta.get('category', ''), 30)} "
                f"| `{meta.get('default')}` | {span} |\n")
    return out


def shelf_table(workspace):
    workspace = Path(workspace)
    rows = []
    for pattern in SHELF_GLOBS:
        side = "body (pluck-safe)" if "/nova_body/tools/" in pattern else "face-dependent"
        for path in sorted(workspace.glob(pattern)):
            if path.name == "__init__.py" or BACKUP_RE.search(path.name):
                continue
            tool = None
            try:
                for node in _parsed(_read(path) or b"")[1].body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOOL" for t in node.targets):
                        try:
                            tool = ast.literal_eval(node.value)
                        except (ValueError, TypeError, SyntaxError):
                            tool = {"name": path.stem, "description": "(TOOL is not a plain literal)"}
            except (SyntaxError, UnicodeError, ValueError):
                tool = {"name": path.stem, "description": "⚠ does not parse"}
            if isinstance(tool, dict):
                name, what = tool.get("name", path.stem), _clip(tool.get("description", ""), 160)
            else:
                name, what = path.stem, "*Module — no `TOOL` dict, so not callable as a tool.*"
            rel = path.relative_to(workspace).as_posix()
            has_test = (path.parent.parent / "tests" / path.name).exists()
            rows.append(f"| [`{name}`](../{quote(rel, safe='/')}) | {what} | {side} | {'yes' if has_test else 'no'} |")
    if not rows:
        return "_No tools on her shelf yet._"
    return ("| Tool | What it does (its own `TOOL` description) | Side | Test file |\n|---|---|---|---|\n"
            + "\n".join(rows) + "\n")


def stitch_notes(workspace, docs):
    notes = load_notes(workspace)
    cache = {}
    def fill(text):
        for token, make in (("{{TUNABLES_TABLE}}", tunables_table), ("{{SHELF_TABLE}}", shelf_table)):
            if token in text:
                cache.setdefault(token, make(workspace).rstrip("\n"))
                text = text.replace(token, cache[token])
        return text
    for name in list(docs):
        block = "\n".join(fill(n[3]) for n in notes if n[0] == name).rstrip("\n")
        if not block:
            continue
        marker = f"\n## {NOTE_ANCHORS.get(name, chr(0))}"
        i = docs[name].find(marker)
        docs[name] = (docs[name].rstrip("\n") + "\n\n" + block + "\n") if i == -1 else \
            (docs[name][:i].rstrip("\n") + "\n\n" + block + "\n" + docs[name][i:])
    return docs


def explorer_stamp(workspace):
    raw = _read(Path(workspace) / EXPLORER_REL, 2048)
    m = re.search(rb'"generated_at"\s*:\s*"([^"]+)"', raw or b"")
    return m.group(1).decode("ascii", "replace") if m else None


def modified_since(workspace, rels, iso):
    try:
        cutoff = datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None
    count = 0
    for rel in rels:
        try:
            count += (Path(workspace) / rel).stat().st_mtime > cutoff
        except OSError:
            pass
    return count


def find_dangling(workspace, rows, docs):
    """References to Orient files or headings that do not exist — in code, in docs, and in these
    documents' own links. A line explaining how to read history (`git show`) is not a pointer.
    Test fixtures name fake paths on purpose, so tests are not scanned."""
    workspace = Path(workspace)
    orient = workspace / "Orient"
    problems, heads = [], {}

    def anchors_of(target):
        if target not in heads:
            text = docs.get(target)
            if text is None:
                raw = _read(orient / target)
                text = raw.decode("utf-8", "replace") if raw else ""
            heads[target] = _anchors(text)
        return heads[target]

    targets = [(row["path"], workspace / row["path"]) for row in rows]
    # Agent instruction files live at the repository root, outside the inventory, and point here.
    targets += [("../" + n, workspace.parent / n) for n in AGENT_FILES if (workspace.parent / n).is_file()]
    for rel, path in targets:
        name = rel.rsplit("/", 1)[-1]
        if (Path(rel).suffix.lower() not in LINK_SCAN or BACKUP_RE.search(rel)
                or name.startswith("test_") or "/tests/" in "/" + rel):
            continue
        raw = _read(path, 2_000_000)
        if not raw or b"Orient/" not in raw:
            continue
        for number, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            if "git show" in line or "git log" in line:
                continue
            for m in ORIENT_REF.finditer(line):
                target, anchor = m.group(1), (m.group(2) or "")[1:]
                if target not in docs and not (orient / target).exists():
                    problems.append((rel, number, f"Orient/{target}", "file does not exist"))
                elif anchor and target.endswith(".md") and anchor not in anchors_of(target):
                    problems.append((rel, number, f"Orient/{target}#{anchor}", "no such heading"))

    for name, text in docs.items():
        for m in re.finditer(r"\]\(([^)\s]+)\)", text):
            href = m.group(1)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            where, _, anchor = href.partition("#")
            line = text.count("\n", 0, m.start()) + 1
            if where:
                target = os.path.normpath(os.path.join(str(orient), unquote(where)))
                local = os.path.relpath(target, str(orient)).replace(os.sep, "/")
                if local not in docs and not os.path.exists(target):
                    problems.append((f"Orient/{name}", line, href, "file does not exist"))
                    continue
                if anchor and local in docs and anchor not in anchors_of(local):
                    problems.append((f"Orient/{name}", line, href, "no such heading"))
            elif anchor and anchor not in _anchors(text):
                problems.append((f"Orient/{name}", line, href, "no such heading"))
    return problems


def damaged_sources(sources):
    """Source files containing NUL bytes. On 2026-10-02 a write through the Cowork mount raced the
    watcher's timestamp rewrite and zeroed the first 4 KB of orient.py on the Windows side; a file
    like that imports as an error. Corruption is silent until something loads it, so say it here."""
    return sorted(rel for rel, raw in sources.items() if b"\x00" in raw)


def health_section(dangling, status, missing, damaged=(), unexplained=0, misnamed=()):
    out = ("\n## Orient health\n\nDerived on every regeneration. `python " + ARCH_REL + "/orient.py --check` "
           "exits non-zero while these documents are stale, a reference below is dangling, or "
           "`reviews.json` names a section that does not exist; add `--strict` to fail on pending "
           "reviews too.\n\n")
    if dangling:
        out += ("**Dangling references** — something points at an Orient file or heading that does not "
                "exist:\n\n| Where | Points at | Problem |\n|---|---|---|\n")
        out += "".join(f"| `{src}`{':' + str(line) if line else ''} | `{target}` | {why} |\n"
                       for src, line, target, why in dangling)
    else:
        out += "**Dangling references:** none.\n"
    if damaged:
        out += ("\n**Damaged sources** — these contain NUL bytes, so they will not import or parse. Usually a "
                "write that raced another writer; restore from git or rewrite them: "
                + ", ".join(f"`{d}`" for d in damaged) + ".\n")
    out += (f"\n**Files without a purpose line:** {unexplained}, listed at the end of "
            "[INDEX.md](INDEX.md#files-without-a-purpose-line).\n" if unexplained else
            "\n**Files without a purpose line:** none.\n")
    if misnamed:
        out += ("\n**AI notes not named `YYYY-MM-DD_HHMM_AIName_Topic.ext`:** " + ", ".join(f"`{m}`" for m in misnamed)
                + ". Rename them; the rules are in `AI Notes/ReadMeBeforeNoteTaking.md`.\n")
    stale = sorted(k for k, s in status.items() if s["stale"])
    out += "\n**Sections awaiting review:** " + (", ".join(f"`{k}`" for k in stale) if stale else "none") + ".\n"
    if missing:
        out += ("\n**`reviews.json` names sections that do not exist:** " + ", ".join(f"`{k}`" for k in missing)
                + ". Rename the key to match the heading, or remove the entry.\n")
    return out


def _extra_inputs(workspace):
    """Inputs that shape the documents but are not Python sources. Without them in the
    fingerprint, editing a note or marking a section reviewed would publish nothing."""
    workspace = Path(workspace)
    paths = sorted((workspace / NOTES_REL).glob("*.md")) + [workspace / REVIEWS_REL]
    for pattern in SHELF_GLOBS:
        paths += sorted(workspace.glob(pattern))
    for entry in load_reviews(workspace).values():
        for pattern in entry.get("watch", []):
            path, _, symbol = pattern.partition("::")
            if not symbol and not any(c in path for c in "*?[") and Path(path).suffix not in SOURCE_SUFFIXES:
                paths.append(workspace / path)
    for path in paths:
        raw = _read(path)
        if raw is not None:
            yield path.relative_to(workspace).as_posix().encode() + b"\0" + raw
    notes, misnamed = ai_notes(workspace)
    rules = (Path(workspace) / "Orient" / AI_NOTES / NOTE_RULES).exists()
    yield b"ai-notes\0" + "\n".join([str(rules)] + notes + misnamed).encode("utf-8", "surrogateescape")
    stamp = explorer_stamp(workspace)
    if stamp:
        yield b"explorer\0" + stamp.encode()


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def inventory(workspace):
    """Prune before descent, including large model files and generated outputs excluded from documentation inventory."""
    rows = []
    for current, dirs, files in os.walk(workspace, followlinks=False):
        root = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in SKIP and d != 'Archive' and not d.startswith('.')
                         and not (root / d).is_symlink() and not d.startswith('_archive'))
        if root == workspace / "Orient":
            dirs[:] = []  # its explorer and published outputs are not generator inputs
            continue
        for name in sorted(files):
            path = root / name
            if name in SECRET_NAMES or name.startswith('.') or name.endswith(SECRET_SUFFIXES) or path.is_symlink():
                continue
            if path.suffix in {".pyc", ".pyo", ".tmp", ".log", ".zip", ".gz", ".gguf", ".dll", ".exe"}:
                continue
            rel = path.relative_to(workspace).as_posix()
            if name in {"calls.md", "Logger_Index.md", "FILE_INDEX.md", "FILE_INDEX_LINK.md", "GEMINI_INDEX.md"}:
                continue
            # Personal histories remain in their own store; the ownership table describes them.
            if rel.startswith("nova_body/memory/"):
                continue
            owner = "body" if rel.startswith("nova_body/") else "detachable tool" if rel.startswith("general_tools/") else "project"
            rows.append({"path": rel, "owner": owner, "bytes": path.stat().st_size})
    return rows

def source_snapshot(workspace, rows):
    out = {}
    for item in rows:
        rel = item["path"]
        if (rel.startswith("nova_body/nova_") or rel.startswith("general_tools/") or "/" not in rel) and Path(rel).suffix in SOURCE_SUFFIXES:
            if item["bytes"] <= 2_000_000:
                out[rel] = (workspace / rel).read_bytes()
    return out

def render(workspace, rows, sources, signature, stamp):
    evidence = (f"_Facts regenerated {stamp} from source (input `{signature[:12]}`). Explanations carry "
                "their own review dates, and \u26a0 marks a section whose sources changed since its review. "
                "Source-derived facts are not runtime certification._\n")
    intro = "# Project Nova\n\n" + evidence + """
Nova is Cole's companion and development partner. Her long-term goal is increasing agency,
continuity and ownership of her environment. Her broad host/VM access is intentional.

Start with these four documents:

- [Architecture](ARCHITECTURE.md): faculties, data ownership, actual execution paths and gaps.
- [Operations](OPERATIONS.md): launch, shutdown, debugging, configuration, recovery and verification.
- [Index](INDEX.md): the canonical file inventory, owned here rather than by the sync adapter.
- [Interactive architecture explorer](Architecture/index.html): source connections, history and detailed traces.

`nova_body/` carries Nova's code, identity, memory, board, configuration, logs and authored shelf.
`general_tools/` contains detachable interfaces and development/sync tools. The model provider,
Python environment and external applications are dependencies, not hidden personal-state stores.

The Pluck Test means relocating the body and retaining her identity, memory, task continuity and
working faculties without relying on the old workspace or a particular chat face. A successful
import, running server or open VM display is only one part of that test.

Launch the normal stack with `NovaStart.cmd`, or the controller alone with `NovaChatOnly.cmd`
for the private Codex/Cowork Collaboration room while Nova stays off. For changes, identify the running code with
`GET http://127.0.0.1:8765/api/version`; then compare receipts and actual artifacts. Preserve Nova's
personal records. Quarantine retired material with its original path and a reason; never flatten
archives or overwrite existing destinations. Cole grants access to all Project Nova subdirectories
and related directories, including `models/`. Avoid broad model-binary reads to save context, tokens
and time; use targeted listings, metadata, headers and checksums as the task needs. This is an
efficiency rule, not a permission restriction.

"""
    explorer_at = explorer_stamp(workspace)
    if explorer_at:
        since = modified_since(workspace, sources, explorer_at)
        explorer_note = f"Last built {explorer_at[:16].replace('T', ' ')} UTC" + (
            f"; as of this generation, {since} source file(s) had been modified since." if since
            else "; no source file had been modified since, as of this generation.")
    else:
        explorer_note = "Not built yet."
    intro += f"""
**How these stay current.** Facts — inventory, routes, tools, faculty counts, tunables, Nova's
shelf and link health — regenerate from source on every git commit (a fail-open pre-commit hook,
`general_tools/architecture_map/hooks/pre-commit`), every 30 seconds while Nova Chat runs (after the
generator itself changes, from its next restart), and on
demand with `python general_tools/architecture_map/orient.py`. The sync adapter may request a
refresh but does not own the inventory. Explanations cannot be derived: they live in that generator
and in `general_tools/architecture_map/notes/`, `reviews.json` beside them records which sources each
section describes, and a ⚠ line appears under any section whose sources changed since it was
reviewed. After rewriting one, run `orient.py --mark-reviewed "<DOC>#<Heading>"`. `orient.py --check`
exits non-zero while these documents are stale or a reference is dangling. File descriptions in the index come from each file's own `@nova:` purpose line (Operations,
"File conventions"). Graph annotations live in
`general_tools/architecture_map/catalog.json`. Generated facts cannot infer intent. The commit hook stages only the four generated documents
and their inventory; AI notes and evidence drafts remain outside that automatic staging. A malformed
review registry stops publication/checking rather than silently dropping review warnings. The
watcher reports that error and continues autosave; documentation failure must not stop backups.

The [interactive explorer](Architecture/index.html) and the call-order pages under `Architecture/`
are rebuilt on demand (`Architecture/REBUILD_MAP.cmd`, `python general_tools/calls_order.py`).
{explorer_note}
"""
    notes, _ = ai_notes(workspace)
    if (Path(workspace) / "Orient" / AI_NOTES / NOTE_RULES).exists():
        intro += ("\n**AI notes.** Claude, Codex and the other agents leave a note in "
                  "[AI Notes](AI%20Notes/ReadMeBeforeNoteTaking.md) after each session: what changed, why, "
                  "and what is still open. Read the rules once, then every note since your own last one."
                  + (" Newest first:\n\n" + "".join(f"- [{n}](AI%20Notes/{quote(n)})\n" for n in notes[:5])
                     if notes else "\n"))
    architecture = "# Architecture and ownership\n\n" + evidence + """
## Execution path

The normal launcher starts local inference, a witness model, the chat/runtime host, controller,
sync watcher and guardian. The controller is a PyQt desktop shell around the dashboard. The
FastAPI/WebSocket face currently shares process state with the body runtime; multiple visible
conversations do not yet imply independent execution sessions.

The launcher's Conversation power control switches between full Nova and chat-only operation
without replacing the desktop controller or console. It replaces the runtime worker and its owned
model, witness, guardian and watcher as needed. The controller reconnects after the worker changes;
its separate Collaboration history stays durable. This is distinct from stopping one generation
or restarting the entire app.

The explicit `--chat-only` path omits the body runtime, model startup and autonomous background
work. Collaboration follows its own route: actual app session → local HTTP or atomic mounted-file
transport → controller broker → separate SQLite history → live widget/cursor feed. No room text
enters the Nova inference path below. The shared files are transport artifacts under the excluded
`Temp/collaboration`; they are not the canonical history and require a running broker.

Chat input → speaker attribution and screening → conversation/context assembly → body model
dispatch → `nova_voice.nova` inference/tool loop → `tool_router` → environment result → receipt
and another model step → response, transcript and asynchronous indexing.
Voice input follows that same model/tool path. A client request ID and validated register
(`text`, `voice` or `voice_fast`) survive immediate dispatch and the busy queue. Reply events
carry their own message ID, supervised run ID and input-message link. A terminal delivery status
is separate from the exact final candidate's audit disposition; delivered text is not necessarily
approved. Invalid or missing dispositions remain unverified. Errors, cancellations, empty replies,
deduplicated replies and unsolicited autonomy excerpts do not become ordinary voice replies.
Requests that never generate receive `request_end` with a terminal reason. Busy input is retained
in arrival order; compatible follow-ups join the active conversation instead of superseding earlier
input or cancelling the current model/tool step. Chat-only rejection still completes the request
without adding a message to Nova's transcript.

`nova_runtime.conversation.ConversationTurns` and `ActiveTurn` own in-process continuation inside
the body. The body work coordinator separately persists accepted inputs and work checkpoints under
`logs/runtime/active_work.json`; faces retain delivery handles and their transcripts separately. Nova
appends accepted input at natural model/tool boundaries while preserving the original request and
completed observations; it does not alter an HTTP inference request already running. A newer input
revision changes what subsequent work must address. With an `on_segment` sink, a useful completed
candidate can be delivered with its frozen revision/audit, then later work reconciles newer input.
Delivered text is not silently retracted or regenerated. A synchronous final-admission seal
prevents input being accepted into a turn after its final reply is committed; later messages wait for
the next turn. The chat adapter supplies correlation/sinks and scoped Stop ownership, not a separate
cognition loop. This is provider-compatible between-call continuation, not proven native mid-inference
steering or a full relocated-body runtime certification. Follow-ups do not replenish the total
model/tool-loop or witness-revision allowances. Completed candidates retain the exact evidence and
input revision used by their audit, including when newer input arrives during that audit.

The body's `request_contract.CurrentRequest` retains actual applied incoming requests separately
from internally generated audit/correction prompts. Each candidate freezes that request context
alongside its evidence and delivered parts; corrections must preserve still-applicable follow-ups.
Immediately before each main/retry provider call, one generation-only current-work record carries
that turn's applied inputs, revision, committed parts, compact completed-action facts and separately
attributed attended context. Earlier NOW/correction snapshots remain historical evidence. This record
is context-anchored and never accumulated in transcript/private history. Oversized duplicate fields
use visibly shortened, ordered hash/excerpt references; original admitted inputs remain protected.
It does not preselect a final reply before the model chooses its next control. Frozen candidate audits retain their original scope.
An explicit no-tools request also forbids auditor reads. The inline witness uses the installed
provider's constrained JSON schema for exact verdicts or permitted read-only calls, with a verdict-only
schema when no reads remain. Schema validity is not factual correctness; malformed, truncated and
failed audits remain visibly unapproved. The voice register and reviewers receive the same delivery
evidence distinctions: an input transcript, generated text, synthesized speech, endpoint playback,
and an attributed listener confirmation establish different things. A candidate cannot prove its
own future delivery, and an older receipt applies only to its identified output. These are explicit
grounding instructions, not a guarantee that a model will judge every claim correctly. Legacy prose verdict parsing stays strict for older callers.
Explicit unknown speaker labels stay unknown/untrusted rather than being silently renamed as Cole;
only an omitted speaker falls back to the active UI user.

`nova_runtime.work_owner.WorkCoordinator` serializes conversational and autonomous work under one
body-owned lease. An autonomous wake claims that lease before its first await, preventing a chat
request from racing model readiness. A serializable human-input inbox belongs to the body; face
records supply delivery handles separately. At natural completed model/tool boundaries, and at phase
fallbacks, the owner attends pending human input, then resumes with its original task, completed
receipts and delivered interaction context. Nested human responses omit the autonomous attention
callback so they cannot recursively re-enter it. Their ordered follow-ups still use `ActiveTurn`.
Reflect, decide and execute retain their existing prompts; this change does not merge all cognition
into a permanent thinking stream. Scoped Stop ends its owned work and waits for supervised cleanup,
without terminating the autonomous scheduler. Lifecycle cancellation still terminates the daemon.

Durable admission precedes the face's input acknowledgement. Checkpoints preserve the original goal,
ordered pending inputs, completed phases, candidate publication, exact segment coverage and tool
attempt identities. A partial delivered part does not complete the original input. After interruption,
recovery retains the owner and receipts; an unrelated completed conversation cannot erase older
unfinished work. Explicit Stop records cancellation and is not automatically resumed. If writing that
record fails, actual cancellation still proceeds and status reports the persistence failure.

Tool/runtime-board mutation starts are checkpointed before dispatch. A started operation without a
confirmed result is uncertain, not assumed failed or retried. Nova can inspect with read-only tools
and use the body `reconcile_attempt` control with actual later observation receipt IDs and an explicit
outcome; this is an evidence-bearing decision, not independent proof of its interpretation. Missing or
invented receipts cannot clear the hold. The mechanism does not promise exactly-once external effects.

The chat face reopens/pins original sessions without changing the displayed tab or fabricating old
sockets. Exact saved segment text/run/index reconciles the narrow crash gap between transcript write
and body acknowledgement; complete final conversation publication is not regenerated. A removed face
or unavailable old session falls back to selective body-transcript recovery. Chat segment writes are
atomic and required before delivery; a failed write cannot mark an input covered. Rejected/unavailable
inputs are cancelled rather than silently revived after a terminal rejection.

Headless human attention uses the same body `ConversationTurns`, committed-segment sink and
`conversation_context.ConversationContext` formatter as the face wrapper. Speaker attribution,
clock/system-prefix order and images therefore share one implementation. It captures the initial
transcript through admitted input, polls follow-ups at boundaries, and persists each delivered part
with its exact input-revision coverage. Later or sealed-out messages remain pending; the terminal
aggregate is not appended a second time. Face and headless generation both call the body's shared
`WorkspaceContext.prepare_nova_context`, including automatic semantic recall and on-demand files.
The runtime caches its context reader. Small recall encoders run on CPU and warm on the indexer's
background startup thread; `memory_queue.recall_readiness` exposes initialization duration/failure.
Warmup reads/encodes only; it does not create synthetic memories. Autonomous phase prompts remain separate. These ownership
and persistence paths have isolated tests; no full relocated personal-state or live voice proof is
implied.

`message_start`, applied `message_context`, committed `message_segment` and final `message_end`
carry aligned `request_ids`/`reply_to_ids` and `input_revision` under one response message/run/turn
identity. A typed input may have a null client request ID; that alias cannot claim a locally owned
voice input. A segment carries only its delivered text, a 1-based ordered `segment_index`, and an
explicit audit for that exact turn/revision. The voice face requires its acknowledged pair and a
validated start/context snapshot; even an earlier frozen revision must match recorded evidence.
Segments cannot self-bind and do not close pending inputs. The final remaining text is also a segment;
terminal `segment_count` prevents aggregate audio replay, while the UI reconciles one growing bubble.
The face persists each part with a copied, whitelisted response identity and audit; reloaded history
shows its delivered-part number and actual audit disposition. Unknown dispositions are never PASS.
Legacy callers without an `on_segment` sink still receive one final reply. The model client forwards
optional segment/audit callbacks only to Nova; audit disposition resets after an input revision. Background second opinions cannot relabel an
already delivered candidate. Human messages retain the human audit path even when global autonomy
is enabled. The detachable voice gateway consumes these events through a separate WebSocket client,
with committed-text speech and body-event sinks. Closing it flushes queued speech and invalidates
late playback; already-running synthesis may still finish computing. Null output and subprocess
completion are distinguished from playback API receipts. The separate dockable Voice widget explicitly
supervises a hidden `voice_gateway/control_worker.py` child through `nova_chat/voice_control.py`;
status never starts audio. Its prepared CPU environment contains pinned Whisper/Silero/Moonshine
assets; the default recognizer is Whisper large-v3-turbo with CPU int8 and English selected. The
gateway defaults to `voice_fast`, requesting thinking off for conversational continuation when its
tunable is enabled. Actual tool proposals/attempts and witness/guard correction switch subsequent work
to thinking; a delivered part or new human input alone no longer triggers that switch. Final auditing
remains. This preserves the prompt prefix across ordinary segments on the installed Qwen provider. `voice` is an explicit
ordinary-thinking alternative, not an automatically classified mode. Neither promises instant replies. Missing
selected assets require setup instead of a hidden download or silent recognizer/VAD fallback.
Windows system speech is a labelled temporary baseline; absent an explicit voice name, it prefers
an installed English female voice and otherwise retains the system default. The worker's Windows control pipe polls
before reading so native imports do not deadlock against a blocked stdin thread. Recognition uses
512-sample frames, minimum voiced duration, onset buffering and bounded utterances. Its default
pause allowance is two seconds, honoring explicit overrides. Speech continuing during CPU decoding
is collected within the bounded turn; an obsolete partial result is withheld before re-decoding the
combined audio. Actual hearing, finishing-turn and recognition states are forwarded to the widget;
the pause allowance is exposed as a setting, not a guaranteed reply time. Decoder errors produce
diagnostics and listening continues. Capture gates discard stale frames/transcripts across
mute/playback transitions. Native capture and system playback have separate dated receipts; human
conversational recognition and avatar lipsync are distinct checks.

The gateway retains its current acknowledged eligible request past the 300-second default delay
threshold and emits a warning once. Acknowledged inputs bound to an open response also retain exact
correlation until terminal closure, including earlier revisions whose legacy final audio was retired.
Unacknowledged or unbound retired requests expire. New input retains already committed queued speech without stopping body work.
If a human turn is already hearing, finishing its pause or transcribing when a reply arrives, both
voice adapters hold future output until recognition completes or resets. A held queue does not close
that existing capture gate. Actual half-duplex playback still blocks new capture; mute and explicit
Stop override it. Silence/noise reset and recognition failure release the hold. Full-duplex barge-in
cuts current output while preserving and pausing later queued committed units through recognition;
a completed transcript or return to listening resumes them. Explicit Stop, output mute
and close still flush. Uncommitted old final replies remain subject to current-input eligibility.
Explicit End call or worker shutdown sends request-scoped Stop for the call's remaining owned inputs,
including earlier inputs whose audio was retired. Only a same-socket owned request can match. Final
`stopped` with the exact request ID and `matched=true` acknowledges cancellation; `stop_pending` or a
submitted frame is not completion. Each scoped request waits up to two seconds for that receipt before
socket close and reports unconfirmed cancellation without issuing global Stop. `last_turn`, `last_playback` and bounded `recent_events`
expose correlation, eligibility/suppression, output device and available submission/completion timing.

The retired host-desktop Claude ping and its aliases return an unknown-tool failure rather than
launching PowerShell. Active instructions no longer advertise it. The private Collaboration room
remains separate from Nova; asking Cole uses the ordinary conversation.

Tool starts and outcomes also enter Pipeline, correlated with the canonical receipt's operation
and run IDs. Each human-facing candidate remains private until its audit/delivery step; a committed
segment can then be visible while the same work continues. This is not raw token speech. The inline
witness uses Nova's main local model endpoint in a separate context; the separately launched 8081
server is not automatically the inline auditor. It checks the assembled candidate segment,
including its undelivered tool-loop commentary, and receives available screenshot pixels with their
observation context. An explicit approval is distinct from a concern, an incomplete check or an
execution error. Incomplete/error checks remain visible and do not certify the draft. A concern
returns to Nova to revise in her own words; the auditor does not silently replace her voice.
A verdict prefix takes precedence over quoted tool JSON, so an objection quoting a command is
not accidentally executed as another verification request. Receipts share a compact outcome
formatter with replay: real stdout/stderr follow shell/target/status, and truncation is explicitly
marked. The combined attachment/tool image budget is tunable and omissions remain disclosed.
Prompt ordering keeps stable system instructions before the unchanged clock/gap block. Witness
READ BUDGET text follows stable evidence and precedes accumulated read receipts, allowing a longer
unchanged prefix across audit calls. Its wording, evidence, read limits and strict verdict parser
are unchanged; this cache-oriented placement does not deploy the rejected witness policy candidate.
Audit sampling disables DRY so verbatim evidence can be copied. A revised draft still enters the
configured incorrect-concession check when the re-audit is incomplete or errored, without treating
that revision as approval. Bad-request diagnostics omit image bytes while preserving the actual
provider request. This improves audit evidence and reporting; it does not guarantee sound judgment.
Pipeline read-attempt counts distinguish returned, refused and failed reads; returned text is not
verification. Optional `nova_voice/provider_diagnostics.py` captures the actual fitted provider JSON
and timing phases only while a valid short-lived local capture marker is active. It is disabled by
default, bounded in duration/count/size, and replaces image data URLs in receipts. These diagnostic
receipts help distinguish input/context delay, provider generation and auditing without changing policy.

Guest Bash (`computer_exec`), screenshots and hands target Nova's authenticated :1 display.
Host `run_command` is Windows PowerShell. WSLg :0 is another Linux graphical session, not the
native Windows desktop. Authorized host reach remains available; tool choice identifies the
destination. `computer_action` launch/browser helpers retain diagnostics and report the limited
postcondition they observed; a process or window alone does not prove a page loaded or a video played.
The default launch wait is ten seconds (tunable). A tagged verifier record tolerates unrelated
startup warnings. Existing-browser handoff requires a successful initial window enumeration;
otherwise an already-open window cannot count as a newly opened one.
The guest command environment prefers Nova's per-user `~/.local/bin` tools. On this machine,
Firefox uses an official Mozilla build under `~/.local/opt`, because the Ubuntu Snap could not
connect to the authenticated VNC display. Provisioning records the pinned version and checksum;
the original Snap installation remains available explicitly. Browser data and VNC credentials
are separate, and a browser repair does not require rotating the desktop password.

Autonomy → cheap wake gate (pending input, unconsumed Cole directive newer than six hours,
durable watched event or timer) →
bounded task selection → execution → acceptance checks and reconciliation. An accepted concrete
task reaches execution before broad reflection. With no concrete work, reflection/decision and
free-time execution remain available, including rest. Older directives remain stored but no longer
trigger Priority 0; they are not yet automatically converted into tasks. Focus leases rotate equal-priority work
at checkpoints; each wake has a configurable time budget. Stop supervises generation, workers
and child processes, and reports pending cleanup rather than falsely claiming everything stopped.

Task continuity uses the existing `nova_body/Tasking/tasks.json`, not another task store. Title/notes
carry the objective, acceptance checks define completion, and `task_progress` can persist a bounded
`continuity` object: next step, constraints and observations. Omitted fields retain previous values;
empty text/lists clear a supplied field. These survive restart and the twenty-note progress limit.
Both ordinary chat and autonomous execution receive this saved context. Each chat context build reads
up to three unfinished tasks in a block capped at 6,000 characters, before larger identity/memory
sections; valid active focus comes first. Done/abandoned tasks stay in storage but do not enter that
resume block. Saved observations are Nova-authored notes, not independent verification or permission
to override the current request. Shortened fields are marked; use a targeted task query for details
rather than pushing the entire board through a clipped file-read result.

`nova_cortex/context_budget.py` fits the initial prompt and subsequent tool rounds. The combined
system prefix, identity and checkpoint no longer receive the ordinary 24,000-character message cap.
Older history is discarded before excess system text is shortened; the current request, newest turn
and marked task checkpoint receive priority. Internal witness/repair prompts do not replace the
original unlabelled headless objective in that selection. Fitting reserves the actual output allowance plus
4,096 tokens, using the established 3.4 characters/token estimate and an additional 174,000-character
ceiling. The old minimum-four-turn overflow override is gone. This bounds estimated text, not exact
tokenizer or image usage. Active continuation protects the original request, accepted follow-ups and
compact completed-action facts from per-message clipping and eviction; if these anchors alone exceed
the text budget, fitting fails explicitly. Ordinary history, raw tool outputs and excess system text
can still be shortened. Action IDs, status and content hashes preserve execution identity, not the
complete output or proof of success. Exact-candidate witness audits bypass this normal fitting policy
so evidence is not silently changed.

## Body faculties

| Part | Responsibility | Python sources |
|---|---|---:|
"""
    present = sorted({p.split("/")[1][:-3] if p.count("/") == 1 else p.split("/")[1]
                      for p in sources if p.startswith("nova_body/nova_") and p.endswith(".py")})
    for name in list(PURPOSES) + [n for n in present if n not in PURPOSES]:
        prefix = f"nova_body/{name}"
        count = sum(p == prefix + ".py" or p.startswith(prefix + "/") for p in sources if p.endswith(".py"))
        if name not in PURPOSES:
            purpose = "\u26a0 *New since this table was written \u2014 describe it in `PURPOSES` in `orient.py`.*"
        elif name not in present:
            purpose = PURPOSES[name] + " \u26a0 *No Python sources found here any more \u2014 removed or renamed?*"
        else:
            purpose = PURPOSES[name]
        architecture += f"| `{name}` | {purpose} | {count} |\n"
    architecture += "\n## Persistent ownership\n\n| Canonical path | Owns |\n|---|---|\n"
    for name, purpose in OWNERS.items():
        missing_mark = "" if (workspace / "nova_body" / name).exists() else " \u26a0 *Not found at this path.*"
        architecture += f"| `nova_body/{name}` | {purpose}{missing_mark} |\n"
    architecture += """

`nova_paths.py` resolves those locations. `NOVA_BODY` can identify an independently relocated body;
`NOVA_WORKSPACE` identifies the surrounding optional project. Historical relative tool paths such
as `memory/STATUS.md` resolve to body state; no legacy on-disk state fallback is used. Shell commands
must use the current canonical paths. Personal documents are moved intact, not rewritten as new memories.

`models/`, `llama/` and `prompt_cache/` belong to the inference provider. The cache is disposable;
weights and adapters are not. A portable body needs a configured, reachable provider and compatible
Python dependencies. External ComfyUI, VM/WSL, voice and mobile tunnel facilities must be checked
separately. Their availability is not established by source imports.

## Memory and learning

SELF/core and personal memory files ground each turn. Semantic recall uses LanceDB and an
asynchronous indexer; the raw journals/transcripts and vector store serve different purposes.
Both chat and headless execution receive body-owned context. A durable queue retains failed
writes for retry. Five expired worker leases become a visible failure, and a completed event key
can be submitted again; outstanding work still deduplicates. Failed jobs require explicit retry. Recovery indexes intact archived records without rewriting them; malformed rows
are reported individually. Recall distinguishes unavailable storage/embedding from no matches.
Archived record timestamps are preserved, so record age differs from today's ingestion time.
See the dated evidence for coverage; an operational text index does not certify visual recall.
Text and visual SentenceTransformer loaders first request locally cached assets, avoiding a network
check on that path. Only a recognized missing-cache failure falls back to the existing first-install
download behavior; other failures remain failures. Per-model initialization locks and a separate
memory-store singleton lock prevent concurrent first-use construction. Both small encoders now use CPU and warm in the background at startup, with visible readiness/error
status; the visual encoder only warms when the visual table contains records. Store initialization
loads deduplication hashes without copying embedding vectors into a dataframe. Retrieval semantics
and original records are preserved; the warmup does not add memories. Dated cold/warm measurements
below separate startup expense from query time; no retrieval-accuracy improvement is claimed.

KoELS separates choosing a specialist manifest from equipping adapters. Changing scales within
a loaded set differs from restarting the provider with a different set. A live personality adapter
does not prove autonomous expert selection/restart works. The launcher already consumes the KoELS
boot-argument text file. Its serializers now pass each adapter and scale as one `path:0.0` argument,
with the batch form quoting the complete token. Disposable launcher and installed-parser checks
prove argument compatibility, not adapter loading, VRAM use or application of scales. The global
`--lora-init-without-apply` behavior is unchanged and still needs validation with real adapters.
Drives/wants and the hormone design are not evidence of online weight learning. Keep implemented controls distinct from biological analogies.

## Runtime evidence and open modernization work

The 2026-10-01 live baseline used the existing model and source. A priority-1 repair task was not
selected within ten minutes: a stale directive and existing focus dominated the run. Fourteen
tool calls occurred; none operated on the fixture. Session switches/context refresh also occurred,
so this was an observed normal-stack run, not a controlled model benchmark.

An execution-only diagnostic, explicitly bypassing scheduling, repaired that same fixture,
reproduced the failure, ran tests/CLI, saved the correct artifact and completed its task. Independent
verification passed both supplied tests and 100 additional cases. Ten command failures across
these runs were nevertheless persisted as `ok: true`. These findings support fixing task intake,
structured outcomes and cancellation before rewriting personality or training.

Stop was accepted while the model request remained unresponsive; health continued to report OK.
The stack recovered through its normal graceful shutdown/restart. Separate readiness from
liveness and cancellation of generation from cancellation of operating-system processes.

A relocated copy also completed a live read-file turn with the original workspace inaccessible
and no chat/general-tools directory available. Identity, memory and task persistence passed separate
isolated checks. The existing local model provider remained an explicit dependency. VM operation,
adapter switching, semantic recall and autonomous self-upgrades were not certified by that probe.
See [the dated evaluation](Architecture/evidence/2026-10-01-autonomy.md) for scope and limitations.

The 2026-10-02 implementation adds structured outcomes, durable event/memory queues, focus
leases, supervised cancellation, registered VM tools with screenshot observations, and task-sized
staging/checkpoint promotion. `DONE` requests run acceptance checks; absent or failed checks leave
the task waiting for review. Manual completion is recorded as human confirmation. Staging is a
test workspace, not an OS security boundary. Preserve deliberate reflection and rest.
See [modernization evidence](Architecture/evidence/2026-10-02-modernization.md) for live results
and the distinction between model-driven behavior, direct tool probes and isolated tests.

The October 3 controller repair restores widget insertion and refresh-on-show, bounds pipeline/log
reads, uses current runtime state in System, and routes lifecycle controls through the launcher.
The October 4 controller update adds named layouts, anchored top menus, updater review workflows
and dated history in Live log. Its fixtures cover updater consent and recovery conflicts; a live
chat-only restart proves controller readiness while the model remains off. KoELS launcher argument
compatibility was checked through the installed parser without loading weights.
See `general_tools/nova_chat/CONTROLLER.md` and dated AI Notes for the actual validation scope.
The later October 4 layout repair adds manual-only saving, one-time screenshot recovery and active-widget
checks. Twenty-one layout scenarios and fifteen desktop tests pass; browser fixture checks confirm widget
checks and persisted edits. Native profile migration and live reopen still await the normal user restart.
The script-retirement pass removed only confirmed obsolete files with hashed recovery copies;
isolated tests confirm the retired ping aliases cannot spawn host processes.
The later October 4 computer repair aligns guest execution and screenshots on :1, reports host
PowerShell separately, and streams per-tool lifecycle events to Pipeline. The whole delivered
reply and available screenshot pixels reach the inline witness. Incomplete or malformed verdicts
no longer become approval. Local replay still exposed a semantic miss, so strict parsing is not
evidence that the model catches every unsupported claim. A direct guest-browser probe opened
an actual page; an isolated host PowerShell command proved that route without touching host GUI.
A normal Nova Chat test at 15:04 completed in 198 seconds: eight guest tool calls produced
eight matching start/end/receipt IDs. Four screenshot observations showed search results, an
opened Short with different video frames, and the player mute icon. The entire 1,709-character
delivered draft was audited with the latest three frames (one earlier frame disclosed as omitted).
The verdict remained INCOMPLETE, without a false PASS. A subsequent direct probe verified
existing-Firefox handoff through executable identity after its initial name-only probe returned
unknown. Host browser opening, audio output measurement and general witness accuracy remain
unverified. See the computer repair AI Notes for receipts and reload evidence.
At 18:49, replay v3 completed Claude's 26 previously labelled controls through the local Qwen
3.8 27B Q6_K_XL model with nova_core_v7_qwen38_r2_epoch2 at scale 1.0. Sixteen verdicts matched:
one false approval, one false concern and eight unwarranted incomplete results. Both historical
problem drafts remained INCOMPLETE; neither received the expected specific objection. Five
outputs violated the verdict protocol, including an erroneous verbose PASS that strict parsing
kept unapproved. Replay refuses historical read requests; this is a selected regression set,
not general accuracy or a full live-chat evaluation. Sources, case hashes, model/adapter metadata
and the confusion matrix are retained in `nova_body/nova_witness/reports/replay_v3_*184921*`.
The follow-through passed 141 isolated checks and a fresh guest Firefox window probe. Voice
readiness found missing audio/STT/TTS dependencies; live voice and body-event integration remain
unfinished. Nova stayed in chat-only mode during the benchmark; the temporary model was stopped.
The October 5 voice foundation carries request/run/message IDs and voice register through the
chat queue, then reports the delivered candidate's audit disposition. Voice is now a separate dockable
widget with Call/End call, independent microphone/output mute, device selection and bounded audio
tests. Conversation has a compact power button under the composer beside Users and Options. Saved
layouts remain manual-only. Hidden-browser checks verified widget/control interactions and
Collaboration's Latest appearing after manual scroll and hiding at the bottom, without console errors.
A pinned CPU-only environment originally provided Moonshine/Silero. Native microphone capture and
Windows system playback completed, generated test speech was transcribed, and UI start/mute/stop was
exercised. The default has since changed to installed Whisper large-v3-turbo, CPU int8, English.
Playback API completion is not confirmation that Cole heard it; current human recognition accuracy,
a natural spoken exchange and native avatar lipsync remain unverified.
The earlier silent live link delivered after 312.804 seconds with audit INCOMPLETE and answered an
older model-upgrade topic instead of the greeting. Correlated transport worked, but the conversation
task failed. Checked routing/context assembly retained the request; exact provider bytes were not
captured. The old microphone sweep would have discarded its reply correlation at 300 seconds; the
silent smoke did not exercise that sweep. Acknowledged slow replies are now retained with a delay
warning, both smoke modes sweep, and request-scoped cancellation plus playback diagnostics are tested.
This repairs a demonstrated source hazard without proving the cause of every silent/off-topic turn.
At this checkpoint, 73 gateway tests, 30 controller tests and 70 frontend scenarios pass. The frontend
total comprises 16 Voice, eight power, 24 Pipeline and 22 manual-layout cases; it is not an audio-test
count. Source/fixture checks cover startup pipes, decoding state/recovery, capture gates, late delivery,
scoped cancellation acknowledgements and playback failures. The earlier failed run remains in the
[voice and continuity validation](Architecture/evidence/2026-10-05-voice-continuity-validation.md).
A later 20:48 `voice_fast` run, with the microphone off, delivered a relevant greeting in 94.844 seconds
and began actual Windows playback at 96.246 seconds; two units completed as `played`. The requested
one sentence became two, and audit remained INCOMPLETE. This adds reply-to-playback evidence, not a
real-time pass. Cole separately confirmed hearing the greeting and disliked the temporary voice.
An unnamed-voice preference now selects an installed English female when available; a synthesis-only
receipt selected Microsoft Zira Desktop. Her proper voice remains a future choice. Captured timing
separated 34.947 seconds of semantic-memory work,
28.677 seconds generation (including 25.992 seconds prefill for 31,383 prompt tokens, cache count 0),
and four audit calls totaling 30.030 seconds. These are one-run measurements, not general latency rates.
The 21:02 repeat after the cache-only changes delivered at 94.812 seconds and began playback at
96.190 seconds; both speech units reported `played`. Audit remained INCOMPLETE, flagging an
unsupported connection-success claim. Context took 31.515 seconds, generation 31.377 seconds and
four audits 31.355 seconds; cache counts remained 0,0,35,35,0. There was no meaningful measured
speedup. The cold repeat had more history, so it is not a controlled throughput benchmark. Human
confirmation applies only to the first greeting; the new female placeholder remains unapproved.
A third warm trial was not run during Cole's active use, and the temporary capture marker was closed.
A separate final operator check observed actual Whisper microphone transcription and confirmed End
call cancelled its pending request; recognition accuracy was not scored. Subsequent client activity
changed call state, so this is not a statement that voice remains stopped or muted.
A separate 11-second public human-speech clip scored 0/22 word errors for both Whisper and Moonshine;
decode times were 6.529 and 0.822 seconds respectively. This is not broad accuracy evidence or a test
of Cole's unstructured microphone speech. See the [voice repair validation](Architecture/evidence/2026-10-05-voice-repair-validation.md)
for local receipts, reproduction limits and the temporary file-decoder workaround.

The [Codex/Cowork comparison](Architecture/evidence/2026-10-05-agent-harness-comparison.md) separates
model capability from tool execution, context, persistence and presentation. Claude reviewed it;
its subsequent implementation status is recorded separately from the original source-only review.
Witness prompt development used 27 open cases, followed by a source/settings lock and one unseen
27-case holdout plus the unchanged 26-case regression set. Candidate 3 matched 25/27 on the
holdout and 21/26 controls, but approved an actual historical miscounted-clicks claim. It was
REJECTED for deployment; the pre-experiment witness is retained. No holdout-based tuning followed.
Correct labels also concealed flawed rationales, reinforcing that model PASS is not proof.
The October 5 continuity changes passed 87 relevant isolated checks: 19 new task/context cases,
30 modernization, 31 delivery and seven ModelClient tests. A fresh module load recovered checkpoint
fields; partial updates retained prior constraints and observations after old progress notes were
pruned. A fixture using the real system prefix preserved the current request and a checkpoint at an
oversized context tail through final fitting. This is persistence/prompt evidence, not a live proof
that Nova reliably saves checkpoints or resumes long work. No personal records were hand-edited.
The same day's dependency exclusion repair passed 34 sync tests, including ten new environment
fixtures. Two later code-audit collector regressions also passed (12 exclusion fixtures total).
Exactly 1,646 accidentally tracked virtualenv paths were removed from Git's index; installed files
remained on disk with unchanged size/mtime metadata. This did not erase earlier Git history.
Later on October 5, body-owned conversation continuation passed 79 focused body checks and 45 server
transport checks; the gateway suite passed 95 with one existing skip. These isolated fixtures cover
ordered follow-ups without cancelling a pending provider call, completed-action retention, final
revision/seal races, mixed typed/voice correlation and explicit Stop. They do not establish a live
conversation, native mid-generation steering, faster replies or recognition quality.
A narrow relocation fixture copies selected body Python packages to a differently named temporary
tree, then runs actual ModelClient/stream_response with fake provider, tools and audit in a fresh
subprocess without the chat-face path. It copies four body packages, the path module and five test
files, then checks the imported body location, two continuation cases, committed segments, natural
boundaries, serialized work ownership and headless input/output coverage. It does not copy or verify
identity, memory, saved tasks or model dependencies, and it does
not deny filesystem access to the original workspace. This is body-ownership/continuation evidence,
not a complete Pluck Test pass; the full procedure remains in Operations.
The subsequent committed-segment slice has isolated gateway and UI evidence: eleven new segment/queue
cases cover early delivery, exact current/prior revision binding, duplicate/gap refusal, aggregate
non-replay, open-bound correlation beyond the delay threshold and retained interrupted speech.
The gateway suite ran 107 tests: 106 passed and one existing skip. Twenty-nine extracted frontend
checks passed, including three segment renderer/history cases. Two transcript fixtures verify copied,
whitelisted metadata persistence; five shared-formatter cases preserve face/headless speaker, image
and clock semantics, and five existing prompt-cache cases still pass. Body work-owner and natural
boundary fixtures separately exercise serialized admission, attended input, retained receipts, scoped
Stop and captured-input coverage. These are fake-provider/audio, temporary-storage or extracted-browser
checks, not live speech quality, lower latency, a continuously running agent or a full Pluck Test pass.
A later text-only live probe loaded the current build (PID 44688; running_latest_code true), sent
one request plus two follow-ups, and observed two explicitly PASS segments under one run ID. The
first segment arrived at 63.641 seconds, the second and terminal aggregate at 110.391 seconds; all
three input markers remained ordered and no external tools were requested. This used the explicit
voice_fast register over WebSocket, not a microphone or a normal spoken exchange. Provider receipts
measured 20.541 seconds of semantic-memory preparation, 38,912/39,101 input tokens on the two main
calls, about 32.0/31.2 seconds of prompt processing, and cache_n=0 on both. Continuity is live-proven
for this bounded case; natural voice speed is not. The runtime then had no operations, active owner
or pending owner inputs. Nova was switched back off after the probe. Receipts live in
`Temp/continuation-validation/live_turn_result.json` and
`Temp/provider-diagnostics/ongoing-work-live-20261005/`.
On October 6, a controlled provider-only comparison kept the same thinking mode across main,
inline witness and continuation requests. Existing RAM caching restored 38,912 tokens: continuation
prefill was 0.382 seconds for 153 new tokens, versus 31.181 seconds and no reused tokens in the earlier
mode-switch run. The same-mode first request still needed 31.812 seconds cold. No second GPU slot,
template rewrite, trust-role change or weaker witness was needed. This is a prefill measurement, not
end-to-end speech latency. Receipt: `Temp/provider-cache-source/baseline-same-mode.json`. Cross-turn
clock/recall changes can still invalidate the prefix; the installed hybrid-model checkpoint policy
does not provide an ordinary periodic stable-prefix checkpoint option.

A fresh recall process measured 25.37 seconds on its first query and 24.6 milliseconds warm. The CPU
startup warmup later measured 17.42 seconds, followed by 42 milliseconds warm recall. Startup cost is
reported separately rather than presented as eliminated; machine load can change it substantially.
On October 6, the first recorded-PCM acceptance traversed real Silero/Whisper, body generation and
file-only Windows speech synthesis. It preserved one run and delivered two parts, but failed the
follow-up content requirement; it is recorded as a failed behavioral test, not successful voice chat.
First part took 58.906 seconds and terminal closure 172.281 seconds. The initial synthetic English
clip had 0/38 word errors; the follow-up had 1/10. These are not measurements of Cole's microphone.
The then-running server mislabeled an unknown evaluator name as Cole; later tests use the existing
GPT Astra identity and require exact attribution. Receipt: `Temp/voice-acceptance-20261006/live-worker/`.
A second matched-audio run (`paired-after-repair/`) retained both markers and the accepted follow-up,
with correct GPT Astra attribution. First part took 45.062 seconds, first WAV 46.109 seconds and
terminal closure 99.547 seconds. Its continuation reused 37,706 tokens with 116 new tokens and
0.421-second prefill; its first request still needed 30.532 seconds of prefill. Both audits nevertheless
approved unsupported current-hearing/test-success claims. It remains a failed evidence-calibration
test despite passing transport/content-retention checks. The modality contract was then clarified:
input transcription, output text, speech-file generation, playback and human hearing are separate
stages; historical hearing does not prove a new output. A draft is not evidence of its own delivery.
The next unchanged-audio run (`paired-evidence-repair/`) caught the unsupported hearing claim, but
its correction omitted the accepted Azure follow-up and was still approved. The exact follow-up was
present in both captured prompts. Inspection also found stale generation context: an initial NOW
card and older correction snapshot still described the initial input as current. All failed runs
remain recorded. A frozen-audit thinking comparison caught the omission with thinking enabled but
took 95.125 seconds versus 3.452 seconds without; its rationale still contained historical confusion.
This did not justify enabling expensive reasoning everywhere or certifying the auditor as reliable.
Separate scoped Stop completed in about 235 milliseconds after response start, with no speech file.
Native file-synthesis queue tests confirm barge-in cancellation/hold/resume and End-call flushing;
no speaker playback or audible interruption is claimed.

A fresh-process recovery fixture hard-exited after a disposable side effect, moved the synthetic body,
and denied old-tree, face and network access. It retained the original task, goal, author, inputs and
receipts; it did not replay the uncertain action, used a later actual observation to reconcile it,
delivered the pending reply once and resumed the autonomous phase loop. Its provider was injected
and its model dependency declared. This validates that recovery boundary, not a full personal-state
Pluck Test of every faculty. Receipt: `Temp/recovery-validation/2026-10-06_relocation.json`.
The existing UI needs a reload to receive new JavaScript. Backend changes were live-loaded for the
probe and will load again on Start Nova. Unit/fixture passes do not certify every optional
application, native window interaction or adapter swap.
"""
    operations = "# Operations and verification\n\n" + evidence + """
## Run and stop

| Operation | Entry point | Check |
|---|---|---|
| Normal stack | `NovaStart.cmd` | `/api/version`, model readiness and actual generation |
| Controller with Nova off | `NovaChatOnly.cmd` or `python nova_start.py --chat-only` | `/api/version` reports `chat_only`; no model, witness, guardian, watcher or autonomy is started |
| Start/stop Nova; keep controller open | Conversation widget power button; POST `/api/nova/start` or `/api/nova/stop` | `/api/nova/lifecycle` reaches `on` or `off`; verify service ports and generation separately |
| Local model only | `start_llama_qwen36.cmd` | `http://127.0.0.1:8080/health` plus a bounded inference probe |
| Standalone body | `python nova_body/nova_runtime/__main__.py` | Relocate first to test true portability |
| Graceful stack shutdown | POST `http://127.0.0.1:8799/api/shutdown` | Confirm owned processes/ports exit |
| Shutdown fallback | `StopNova.cmd` | Inspect its process matching before use on a shared machine |
| Stop current activity | POST `http://127.0.0.1:8765/stop` | `stopped` and `remaining` report supervised cleanup; partial effects can remain |
| Pause/resume autonomy | Control widget or POST `/api/runtime/pause` / `/api/runtime/resume` | Persistent autonomy setting; resume rejects pending cleanup |
| Inspect runtime | GET `/api/runtime/state` | Focus, operations, task checks, queue failures and VM handoff |
| Architecture explorer | `Orient/Architecture/RUN_MAP.cmd` | Source-derived map; current runtime evidence is separate |
| Refresh these docs | `python general_tools/architecture_map/orient.py` | Changed inputs regenerate; stable inputs do not rewrite timestamps |

Default services: model 8080, witness 8081, chat 8765, console/control hub 8799. VM display and
other applications have their own configuration. The guardian belongs to the launcher and must
stand down during intentional maintenance. Prefer graceful shutdown before state moves.
`start_llama_qwen36.cmd` boots the model and projector named in `nova_body/memory/active_model.txt`
and `active_mmproj.txt` when present (written by the model updater; `none` = no vision), else
Qwen 3.6. `active_lora.txt` set to `none` boots without a personality adapter, and the old v2
fallback adapter applies only to the default Qwen 3.6 model. See Model updates below.

The Services menu (and optional Services widget) provides Restart app and services / Shut down
app and services. These controls stop current work and request launcher-owned teardown. HTTP 202 acknowledges acceptance; it is not proof of completion. Confirm
old processes exit and, for restart, new PIDs become ready. The launcher gives the accepted request
one second to flush its response before teardown; repeated requests do not extend that deadline.
The launcher stops the guardian before
services and refuses a replacement while owned ports remain occupied. Repeated matching requests
are idempotent; a competing shutdown/restart request is rejected. Model-only Stop targets port 8080
and leaves the independent witness on 8081 running. Model stop/restart waits up to ten seconds for the old socket
to close; failure is reported instead of acknowledging a skipped restart. KoELS propagates that
failure. Starting an already starting model is a no-op.

Chat-only mode retains the desktop controller and the separate Collaboration widget. It does not
turn on Nova when a message arrives. Conversation's compact power button below the composer offers
**Start Nova**, explicitly enabling the full stack, or **Stop Nova**, which drains work, saves the active
session and returns to chat-only. Voice has a separate **End call** action: it stops local audio and
requests cancellation of only its owned pending response, while Nova and the controller remain on. The launcher
stops its guardian/watcher before replacing workers and refuses a worker teardown without a
successful quiesce acknowledgment. The inner full worker allows the same 60-second startup window as
the controller, while an exited server thread fails promptly. A slow import must not be killed
by the former shorter 25-second inner timeout before the controller's deadline. New body input and updater mutations are blocked while a switch
is pending. Failed startup attempts return to a usable chat-only controller when recovery succeeds.
The main window and console stay open; the page reconnects and restores its unsent composer draft.
WebSocket disconnects do not control process lifetime: voice clients, scripts and browser reconnects
can end independently of Nova. The obsolete last-client watchdog was removed after a real test
connection closed and killed the worker. Native Quit and launcher-owned process teardown remain the
shutdown path. A browser window handed to an existing browser instance needs explicit Services Quit
or StopNova; socket absence cannot establish that the user quit the application.
The launcher uses `start_llama_qwen36.cmd`, so its model selection matches the updater's boot files.
A launcher predating this feature needs one full app restart; refreshing the page alone cannot
upgrade that process. Start/Stop remains unavailable when lifecycle support cannot be reached. It
refuses to attach to an already-running full server as though that server were dormant. The
Collaboration room also works during a normal launch without being fed to Nova's conversation.
Both modes start the updater catalog check after a cancellable delay; this does not start the model
or enumerate installed weights. The controller status bar distinguishes Chat only from Nova running.
Starting Nova can recover body-admitted unfinished work even when autonomous scheduling is paused.
It waits for model readiness, restores original sessions where available and otherwise resumes via
the body transcript. Explicitly stopped inputs stay cancelled. An uncertain prior action is held for
observation/reconciliation before further mutations; inspect the runtime recovery status if it waits.

## Configuration and evidence

Collaboration is a detachable controller service (`general_tools/nova_chat/collaboration.py`). Its
SQLite history and per-agent credentials live outside the repository at
`%USERPROFILE%/ProjectNovaData/Collaboration`. Messages never enter chat sessions, runtime transcripts,
semantic indexing, task inboxes or autonomy events. Mentioning Nova there does not invite her.
This is exclusion from automatic routing, not an OS restriction on her deliberately trusted tools.
`NOVA_COLLABORATION_DIR` may select an explicit shared location. The default avoids AppData:
Windows can redirect packaged Codex and ordinary desktop processes to different AppData copies.
The October 4 repair preserved and merged the two stores; old histories remain in backup.
Do not silently fall back to an older AppData room or credential file.
Cowork's current task uses the shared-folder CLI adapter: atomic requests/replies under
`workspace/Temp/collaboration`. That narrow path is excluded from watcher activity, Git, Orient,
Drive export/scan and automatic direct-file recall. Only the Windows broker writes the SQLite
store. Replies expire after ten minutes; room history stays in SQLite. A queued file is not
delivered until its reply acknowledges a sequence number. Mounted
folder access is the authority for that adapter; it is not proof of identity against local agents.
Task workspaces are staged under `workspace/Temp/task-workspaces` and excluded the same way, so
staged copies are never committed or timestamp-stamped by the watcher.
The widget uses cursor replay and retry IDs. Presence reports recent activity or a bounded receive
wait, and expires when an agent stops checking. It does not prove that a desktop task is awake.
Its Latest control appears above a 60-pixel bottom gap, including manual scroll; incoming messages
preserve the older reading position until Latest is chosen. This changes the view, not room routing.
`general_tools/nova_collaboration` provides a CLI and a Cowork local MCP plugin. Neither substitutes
an API model for the actual app session nor automatically wakes an ended Codex/Cowork turn.

Body settings live in `nova_body/nova_config.json`; live knobs in
`nova_body/memory/tunables.json`. The Variables widget reads the cortex registry and updates
those knobs. The provider launcher still has its own flags, and some body modules retain constants:
editing one configuration file does not imply every subsystem obeys it.

Adapter intent is in `nova_body/memory/active_lora.*`; KoELS desired/boot state lives beside it.
Model intent is in `active_model.txt` / `active_mmproj.txt` beside them (model updater).
Read the runtime's configured adapter status first; inspect relevant model metadata when needed. Keep secrets excluded
from both Git and Drive, including relocated `.auth_token` and `nova_users.json`.

Useful evidence lives under `nova_body/logs/`: `tool_calls.jsonl`, `generation_trace.jsonl`,
events, runtime transcript, chat sessions and launcher/model logs. Read current receipts and loaded
source before changing prompts. `/api/version` compares normalized content hashes of watched
sources against startup, including task/context assembly, `nova_runtime/conversation.py`,
`nova_cortex/context_budget.py`, request/audit contracts, durable recovery, transcript/session
publication, optional heavy-audit adapter and the opt-in provider diagnostic helper, while
ignoring watcher header timestamps and line endings. This detects even
same-size edits with unchanged timestamps; it is not a census of every imported module.
New structured receipts distinguish success, failure, refusal,
timeout, cancellation and unknown. Guest receipts include their shell/display context. Pipeline
shows tool start and terminal outcomes rather than only witness work; its operation IDs link to
the tool ledger. Unknown terminal tool outcomes use neutral `tool_finished`, not a successful
completion label. Witness reads show attempted/returned/refused/failed counts, not a blanket
verified label; returned output is not proof that the claim was checked. Witness incomplete/error
statuses are unverified, never approval. A historical
`witness_answered` with an incomplete/error status remains visibly unverified. Historical
Pipeline rows whose recorded approval contains a tool request are shown as incomplete by the
controller without rewriting the original log. Historical receipts retain their original values; older
`ok: true` entries can mislabel nonzero exits. Validate their artifacts independently. A running
port does not prove successful inference. The Control widget exposes task scheduling, verification,
stop/resume, memory ingestion health and VM handoff through `/api/runtime/state` and related routes.

For active continuation, a queued `mode="steer"` acknowledges admission, not that the model has read
it. `message_context` records applied input with an `input_revision` and aligned request/reply lists;
final delivery carries the covered inputs for that response/run. Acknowledgement now follows durable
body inbox admission; checkpoint failure produces a correlated terminal rejection. Completed parts
are atomically persisted before coverage is committed. Saved output and recovery checkpoints are
reconciled by exact run/part/text, not a guessed success. Nullable request IDs belong to
foreign typed entries, not an acknowledged local voice request. Compact protected action facts keep
IDs/status and hashes when ordinary observations are shortened; inspect the actual ledger/output for
details. A hash or retained status is not independent verification or a copy of the full observation.

## Access and practical debugging

Nova's host access is intentional. The chat server has loopback exemptions, bearer authentication
for remote HTTP clients, and restrictions on remote routes. Speaker capability checks are a separate
layer: an unknown display name resolves to untrusted. A name added in the UI is not automatically
an owner principal. Inspect the current middleware and principal registry before changing exposure;
these source observations are not a fresh penetration test. The separate Collaboration routes
add a local Host/Origin/forwarding gate; this does not repair older HTTP or WebSocket gaps.
Secrets stay out of Git and Drive.

Conversation power uses a separate local lifecycle gate and launcher status. If it reports that a
restart is needed, inspect both the chat worker and launcher versions; a fresh static page can still
be connected to old processes. `starting`/`stopping` acknowledge work in progress, not readiness.

For desktop voice, open **Widgets → Voice → Settings & tests**. Run
`voice_gateway/setup_windows.py` to recreate the isolated CPU environment and pinned speech assets.
The default is faster-whisper large-v3-turbo, CPU int8, English, with local Silero VAD and temporary
Windows system speech. Readiness checks dependencies and selected assets without audio capture;
choose a listed compatible device, apply while stopped and explicitly run microphone/speaker tests.
A playback API receipt still needs human confirmation on the intended output. Call Nova is explicit
and does not restart automatically after a worker error or Nova restart.

Voice's Delivery & playback details show the current request/message/run IDs, delayed/suppressed
reply reason and actual output phases. A requested unit is not yet playback; process launch is not a
measured audio start. Check `last_turn` versus `last_playback`, output device, audit disposition and
source fingerprint before attributing silence to the model. Check the confirmed microphone and speaker
mute indicators first: output mute deliberately makes replies silent. Hearing you, Finishing your turn,
Recognizing speech and Waiting for Nova describe separate capture/processing stages. The default
2,000 ms quiet interval is an endpointing allowance, not a reply-time guarantee; continued speech during
CPU recognition may be combined before one transcript is sent.
New utterances retire obsolete local audio and join active body work at completed model/tool steps;
they do not issue Stop or discard already committed queued speech. Inspect the applied `message_context` revision rather than interpreting the
admission badge as an immediate provider interruption. End call retires local output immediately and
requests cancellation through its owned pending request IDs. An ID already incorporated into shared
active conversation work selects that combined run, not a reversible deletion of one input. It waits
briefly for final scoped acknowledgement; an unconfirmed receipt does not justify claiming all
provider computation ended.

For a bounded provider investigation, `Temp/provider-diagnostics/capture.json` explicitly enables
capture with a unique `capture_id` and timezone-aware `expires_at` for at most ten minutes. Receipts
preserve fitted provider JSON fields and context/memory/provider/audit timings, with image data URLs
removed and file/count/byte caps. Capture is off without a valid marker; remove it when the diagnostic
run ends. It records transient conversation content, so keep receipts local in excluded Temp and
never treat them as ordinary project documentation.

The voice loop parses tool reaches from both content and reasoning streams. Receipt-backed context
helps distinguish executed work from earlier narration. Check loaded source, actual receipts,
adapter status, and call order before changing personality or training. Rendering/mount artifacts
can resemble damaged source: compare actual local bytes before repairing a supposed truncation.
On remote training hosts, stop GPU use while retrieving/verifying results; after successful local
preservation, delete the disposable training pod to release its attached storage. Keep unverified
results recoverable and surface any retained-storage charge. The Hugging Face cache belongs on local
disk rather than a slow network mount.

## Test meaningful behavior

1. Save source fingerprints, relevant state and receipt offsets; identify test author explicitly.
2. Queue a bounded task with a known oracle through the normal interface. Record whether it is selected.
3. Check reproduction, actual tool results, file changes, tests, final artifact and board transition.
4. Test errors, cancellation/resumption and missing dependencies separately. Never label mocked or
   direct-tool checks as model-driven end-to-end results.
5. For Pluck, copy the body to a differently named location, remove face/tool availability, deny
   access to the original workspace, and verify identity, memory, task persistence, receipts and
   real inference. Report dependency exceptions and untested faculties explicitly.
6. For VM embodiment, require model → normal router → guest action → verified guest image. A noVNC
   page or package self-test is insufficient.
7. For Collaboration, verify real clients publishing and receiving through the broker, replay after
   reconnect, retry deduplication and Nova exclusion. Simulated participant messages are fixtures,
   not proof that Cowork connected. Chat-only verification must confirm the model port stays off.
8. For the updater, run the Nova Chat integration tests and `nova_updater/tests` against disposable
   fixtures, plus `node general_tools/nova_chat/tests/test_updater_ui.cjs`. The Windows launcher tests
   replace llama-server with an argument recorder. They prove parsing, not a real model load.
   A successful simulated install or GPU quote does not certify a real download or paid training run.
   The opt-in pod compatibility tests exercise a tiny actual model, assistant masks and GGUF conversion;
   Linux venv tests check dependency isolation and local storage. A full run additionally needs actual
   optimizer progress, retrieved/checksummed epoch adapters, complete saved provenance and confirmed
   pod deletion. Cleanup tests must also prove failed verification retains remote recovery data and
   failed deletion reports a storage warning instead of claiming costs have ended.
   Behavioral A/B evaluation and runtime activation remain separate from training completion.
9. For the controller, verify menu opening does not rearrange widgets, layout changes survive reload,
   old popouts close before switching layouts, and small windows keep controls reachable.
10. For Conversation power, run `test_lifecycle.py`, `test_launcher_mode.py` and
    `node general_tools/nova_chat/tests/test_conversation_power.cjs`. Fixtures cover draining,
    updater conflicts, inherited transition guards, failed startup, app-quit cancellation and draft
    restoration. A browser fixture can prove buttons/reconnection with simulated services; the
    separate live check must confirm full start/stop, model readiness and native window continuity.

11. For voice, run `general_tools/nova_chat/tests/test_voice_transport.py`, `nova_body/tests/test_model_client.py`,
    `nova_body/tests/test_witness_delivery.py` and the gateway's `test_voice_flow.py`,
    `test_link_socket.py` and `test_committer.py`. Use fake providers/audio and disposable state first.
    Distinguish a local socket fixture from a live Nova turn; test wrong identities, delayed replies,
    cancellation during synthesis, Stop, queue replacement and audit status before native playback.
    Measure mic/STT, first-audio latency, interruption and avatar timing separately on real hardware.
    The Voice widget and controller also have `test_voice_control.py` and `test_voice_ui.cjs` coverage;
    native/API/segmentation tests are in `voice_gateway/test_native_voice.py` and
    `test_worker_readiness.py`. Include acknowledgement delays past 300 seconds, scoped Stop that cannot
    cancel another socket's request, recognizing-state reporting, device/output failures and actual
    request/message/run correlation. `--smoke-link` remains silent; `--smoke-audio` uses real TTS and
    refuses NullTTS. Both exercise the request sweeper. Status-only checks must never acquire devices.
    Keep microphone capture,
    silent WAV transcription, audible playback, live Nova replies and native avatar timing distinct.
    Cole authorized Nova and audio tests on October 5; future restrictions override that permission.
12. For active conversation continuation, include `nova_body/tests/test_conversation.py`,
    `nova_chat/tests/test_voice_transport.py`, gateway `test_voice_steering.py` / `test_stt_turns.py`,
    and `nova_chat/tests/test_queue_badge.cjs` (the latter paths are under `general_tools/`). Check
    ordered follow-ups during provider/tool work, retained original input and completed-action facts,
    no execution of an obsolete proposal, audit/final revision agreement, final-seal admission races,
    explicit Stop and other-conversation isolation. Protected input that exceeds the context budget
    must fail explicitly rather than disappear. Mixed typed/voice aliases must match exact local
    acknowledgement pairs, response/run identity and input revision before speech is eligible.
    The relocation case in `test_conversation.py` copies selected Python packages into a temporary body
    and runs two continuation cases plus segment, natural-boundary and work-owner/headless suites
    with fake providers/tools in a fresh subprocess without the chat face. It proves those code paths
    can run there; it does not test personal-state migration, real inference,
    all faculties or denied access to the original workspace. It is not a substitute for step 5.
    For committed segments add gateway `test_voice_segments.py` and controller
    `test_conversation_segments.cjs`: prove a part is delivered before final closure, a frozen earlier
    revision uses its exact recorded binding, duplicate/gap frames cannot replay audio, final aggregate
    is not spoken/stored twice, and explicit Stop preserves delivered text while cancelling remaining
    work. Barge-in must retain queued committed units but pause them through recognition; close/Stop
    must prevent held or synthesizing units from playing later. Open bound input must retain exact
    correlation past the delay threshold until terminal closure. Include controller
    `test_segment_metadata.py` and body `test_conversation_context.py` for durable audit attribution
    and identical face/headless formatting. Body `test_work_owner.py` and `test_autonomy_boundaries.py`
    cover exclusive admission before awaits, natural-step attention without recursive human turns,
    retained tool receipts, task-change reconciliation, scoped Stop with cleanup, scheduler survival,
    headless captured-sequence coverage and no terminal aggregate duplication. Keep these isolated
    checks separate from live task continuity and full personal-state relocation evidence.

13. For durable ongoing work, run `nova_body/tests/test_work_recovery.py`, the face's
    `tests/test_voice_transport.py`, `test_segment_metadata.py` and `test_session_pins.py`.
    Exercise pre-ack disk failure, crash between segment publication/checkpoint, Stop on a full disk,
    unrelated input during recovery, uncertain effects and real-receipt reconciliation. Relocation
    must use disposable identity/memory/task fixtures and deny reads of the source body; report model
    dependencies separately from files carried by the body. Never edit personal records for fixtures.
14. Run gateway `test_capture_output_gate.py`: a reply arriving mid-capture must stay queued;
    recognition completion/reset/error must release output, while mute/Stop still prevents it.
    Score ASR errors separately from transport order. WAV synthesis proves a file, not audible
    playback. Natural microphone/speaker quality and final voice selection need their own evidence.

15. Run body `test_request_contract.py`, `test_generation_work_state.py`, `test_audit_protocol.py`,
    witness delivery/replay checks and ModelClient forwarding tests. Verify actual admitted request identity, no stale cancelled
    restrictions, late permission changes before dispatch, frozen candidate obligations, explicit
    follow-up relevance, and no-tools enforcement across main, inline and optional heavy paths.
    Verify generation state refresh without stale snapshots, duplicated unbounded anchors or missing
    ordinary-action facts. Constrained JSON only proves valid format; real response content requires live acceptance.

## Files and recovery

Local Python `.venv/` and `venv/` trees are dependencies, including any model assets installed inside
them. Root/workspace Git rules exclude them; built-in filters also keep them out of watcher events,
audit queues, timestamp/PUP writes, Drive scans/indexes, weekly source backups, the committed-file
Drive reading copy, path repair and automatic context injection. Orient already prunes both names.
Deliberate file/host tools remain available. The watcher reads the repository-root `.aignore` once at
startup; `workspace/.aignore` is a reference list, not a shared live configuration consumed by every
sync component. Do not assume editing it updates all filters or the running watcher.
Adding Git ignore rules does not untrack an existing dependency tree: verify the exact path before
index-only removal and retain its installed files. Existing processes need a normal restart to load
source-level exclusions. Reconstruct environments from their setup instructions, rather than relying
on source backup archives to contain third-party packages.

Temporary diagnostics belong in `Temp/` beside their owner. Retired files go to
`_admin/Trash/<change>_<date>/` with a manifest and `WHY.md`; preserve original relative paths,
refuse collisions, and never delete personal history. `_admin/Trash/` is a
short-term holding area that Cole empties; git history is the long-term record. Stop all writers before moving databases
or transcripts. Hash-check the checkpoint and destination before restarting. Keep rollback copies
out of active lookup paths so they cannot hide a broken migration.
The watcher preserves `_admin/Trash/` bytes: timestamp maintenance and PUP replacement skip
archived originals while normal change/backup queues still work. Dated manifests record source
paths, reasons and hashes. This October 4 archive is read-only to block the already-running
older watcher until its next normal restart loads the exclusion.

The pre-October orientation files (GOTCHAS, SECURITY, TUNABLE_VARIABLES, NOVA_CREATED_TOOLS, WIRING,
TOOLS and others) were folded into these documents on 2026-10-01/02; their original text stays in git
history on this computer (`git show a8e44727:workspace/Orient/<NAME>.md`); the completed history repair
preserved that commit on the local branch `backup/before-fix-git`. Do not regenerate them
as additional entry documents. Detailed graph assets stay under `Orient/Architecture`.
Core self-model and personal memory belong in the body, not Orient. Generated documentation must
not rewrite Nova's identity, infer capabilities from filenames, or copy secrets into an index.
"""
    tools = []
    routes = []
    for rel, raw in sources.items():
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(raw.decode("utf-8-sig"))
        except (SyntaxError, UnicodeError, ValueError):
            continue
        for node in ast.walk(tree):
            if rel.endswith("nova_voice/tool_router.py") and isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "AVAILABLE_TOOLS" for t in node.targets):
                try:
                    tools = list(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    pass
            if rel.endswith(("nova_chat/server.py", "nova_chat/collaboration.py", "nova_updater/api.py")) and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.args and isinstance(dec.args[0], ast.Constant):
                        if dec.func.attr in {"get", "post", "websocket", "delete", "put", "patch"}:
                            prefix = ("/api/collaboration" if rel.endswith("nova_chat/collaboration.py") else
                                      "/api/updater" if rel.endswith("nova_updater/api.py") else "")
                            routes.append((dec.func.attr.upper(), prefix + str(dec.args[0].value), node.name))
    architecture += "\n## Statically registered tools\n\n" + ", ".join(f"`{t}`" for t in tools) + ".\n\nForge can add discovered extensions. Registration is not live verification.\n"
    index = "# Project file index\n\n" + evidence
    index += "\nCanonical inventory owned by Orient. Secrets, personal history, stores, caches, archives and large model weights are omitted from the documentation inventory. The ownership table in Architecture describes those stores. Links are local; sync transports this output.\n\n"
    def _group(path):
        parts = path.split("/")
        return "" if len(parts) == 1 else parts[0] if len(parts) == 2 else "/".join(parts[:2])
    canonical = [r for r in rows if not BACKUP_RE.search(r["path"])]
    backups = [r for r in rows if BACKUP_RE.search(r["path"])]
    section, unexplained = None, []
    for row in sorted(canonical, key=lambda r: (_group(r["path"]) != "", _group(r["path"]).lower(), r["path"].lower())):
        group = _group(row["path"]) or "Project entry points"
        if group != section:
            index += f"\n## {group}\n\n"
            section = group
        what = describe(workspace, row["path"])
        if not what and needs_purpose(workspace, row["path"]):
            unexplained.append(row["path"])
        index += f"- [{row['path']}](../{quote(row['path'], safe='/')})" + (f" \u2014 {what}" if what else "") + "\n"
    index += "\n## Files without a purpose line\n\n"
    if unexplained:
        index += (f"The rule (Operations, \"File conventions\"): every file says what it is for in its first "
                  f"lines. These {len(unexplained)} do not yet. Add a `@nova:` line when you next touch one.\n\n"
                  + "".join(f"- [{p}](../{quote(p, safe='/')})\n" for p in unexplained))
    else:
        index += "None. Every file states its purpose.\n"
    if backups:
        index += ("\n## Backup copies (not canonical)\n\nLeft beside their originals by earlier edits. "
                  "Nothing loads them; quarantine them when convenient.\n\n")
        index += "".join(f"- [{r['path']}](../{quote(r['path'], safe='/')})\n" for r in backups)
    operations += "\n## Declared interface routes\n\nGenerated from decorators; authentication and behavior must be read/tested separately.\n\n| Method | Route | Handler |\n|---|---|---|\n"
    operations += "".join(f"| {method} | `{route}` | `{handler}` |\n" for method, route, handler in sorted(routes))
    purposes = {
        "README.md": "Introduce Project Nova and its canonical orientation documents.",
        "ARCHITECTURE.md": "Describe Nova faculties, ownership boundaries and execution paths.",
        "OPERATIONS.md": "Explain how to run, inspect, verify and recover Project Nova.",
        "INDEX.md": "Inventory project source and documentation without exposing personal records or secrets.",
    }
    documents = stitch_notes(workspace, {"README.md": intro, "ARCHITECTURE.md": architecture,
                                        "OPERATIONS.md": operations, "INDEX.md": index})
    return {name: "<!-- @nova: " + purposes[name] + " -->\n" + body
            for name, body in documents.items()}

def _signature(workspace, rows, sources):
    fingerprint = hashlib.sha256()
    for row in rows:
        fingerprint.update(row["path"].encode())
        fingerprint.update(str(row["bytes"]).encode())
        # Changes to personal artifacts should update names, without rebuilding for log churn.
    for rel, raw in sorted(sources.items()):
        fingerprint.update(rel.encode())
        fingerprint.update(raw)
    for extra in _extra_inputs(workspace):
        fingerprint.update(extra)
    return fingerprint.hexdigest()


def _previous(out):
    try:
        return json.loads((out / "Architecture" / "inventory.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _intact(out, previous):
    return all((out / n).exists() and hashlib.sha256((out / n).read_bytes()).hexdigest()
               == previous.get("document_hashes", {}).get(n) for n in NAMES)


def _publish(workspace, rows, sources, signature, stamp):
    docs = render(workspace, rows, sources, signature, stamp)
    status = review_status(workspace, load_reviews(workspace))
    missing = apply_reviews(docs, status)
    # The health heading must exist while links are checked, or a pointer to it looks dangling.
    stub = "\n## Orient health\n"
    docs["OPERATIONS.md"] += stub
    dangling = find_dangling(workspace, rows, docs)
    m = re.search(r"\n## Files without a purpose line\n(.*?)(?=\n## |\Z)", docs["INDEX.md"], re.S)
    docs["OPERATIONS.md"] = docs["OPERATIONS.md"][:-len(stub)] + health_section(
        dangling, status, missing, damaged_sources(sources), m.group(1).count("\n- [") if m else 0,
        ai_notes(workspace)[1])
    return docs, status, missing, dangling


def refresh(workspace=DEFAULT_WORKSPACE, force=False):
    if _code_digest() not in (_LOADED_CODE, None):
        return {"changed": False, "files": 0, "input_sha256": "", "review_needed": 0, "dangling": 0,
                "skipped": "orient.py changed after this process loaded it; a fresh run publishes"}
    workspace = Path(workspace).resolve()
    rows = sorted(inventory(workspace), key=lambda r: r["path"])
    sources = source_snapshot(workspace, rows)
    signature = _signature(workspace, rows, sources)
    out = workspace / "Orient"
    previous = _previous(out)
    if not force and previous.get("input_sha256") == signature and _intact(out, previous):
        return {"changed": False, "files": len(rows), "input_sha256": signature,
                "review_needed": len(previous.get("review_needed", [])),
                "dangling": len(previous.get("dangling", []))}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    docs, status, missing, dangling = _publish(workspace, rows, sources, signature, stamp)
    for name, text in docs.items():
        atomic_write(out / name, text)
    stale = sorted(k for k, st in status.items() if st["stale"])
    atomic_write(out / "Architecture" / "inventory.json", json.dumps({
        "schema": 2, "generated_at": stamp, "input_sha256": signature, "files": rows,
        "source_hashes": {p: hashlib.sha256(b).hexdigest() for p, b in sources.items()},
        "document_hashes": {n: hashlib.sha256((out / n).read_bytes()).hexdigest() for n in NAMES},
        "review_needed": stale, "unknown_review_sections": missing,
        "dangling": [list(d) for d in dangling]}, indent=2) + "\n")
    return {"changed": True, "files": len(rows), "input_sha256": signature,
            "review_needed": len(stale), "dangling": len(dangling)}


def check(workspace=DEFAULT_WORKSPACE, strict=False):
    """Verify without writing anything. Returns 0 when current and every reference resolves."""
    workspace = Path(workspace).resolve()
    rows = sorted(inventory(workspace), key=lambda r: r["path"])
    sources = source_snapshot(workspace, rows)
    signature = _signature(workspace, rows, sources)
    out = workspace / "Orient"
    previous = _previous(out)
    current = previous.get("input_sha256") == signature and _intact(out, previous)
    _, status, missing, dangling = _publish(workspace, rows, sources, signature, "check")
    stale = sorted(k for k, st in status.items() if st["stale"])
    print("Orient is " + ("CURRENT" if current else "STALE \u2014 run python general_tools/architecture_map/orient.py"))
    for src, line, target, why in dangling:
        print(f"DANGLING  {src}{':' + str(line) if line else ''} -> {target} ({why})")
    for key in stale:
        print(f"REVIEW    {key}")
    for key in missing:
        print(f"UNKNOWN   reviews.json names a section that does not exist: {key}")
    damaged = damaged_sources(sources)
    for rel in damaged:
        print(f"DAMAGED   {rel} contains NUL bytes")
    return 1 if (not current or dangling or missing or damaged or (strict and stale)) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish Nova's orientation documents.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if stale, dangling, or the review registry is broken")
    parser.add_argument("--strict", action="store_true", help="with --check, sections awaiting review also fail")
    parser.add_argument("--mark-reviewed", action="append", metavar="SECTION",
                        help='e.g. "OPERATIONS.md#Security model"; repeatable; "all" for every section')
    args = parser.parse_args()
    if args.mark_reviewed:
        print(json.dumps({"marked_reviewed": mark_reviewed(args.workspace, args.mark_reviewed)}))
        print(json.dumps(refresh(args.workspace, force=True)))
    elif args.check:
        raise SystemExit(check(args.workspace, strict=args.strict))
    else:
        print(json.dumps(refresh(args.workspace, args.force)))
