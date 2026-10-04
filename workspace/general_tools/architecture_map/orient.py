# @nova: Generates Orient documentation and validates source, review and link freshness.
# Last updated: 2026-10-03 09:57:32
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
    "nova_witness": "Witness model launch, evaluation and training utilities; the live auditing faculty is in cortex/voice.",
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
The retired host-desktop Claude ping and its aliases return an unknown-tool failure rather than
launching PowerShell. Active instructions no longer advertise it. The private Collaboration room
remains separate from Nova; asking Cole uses the ordinary conversation.

Tool starts and outcomes also enter Pipeline, correlated with the canonical receipt's operation
and run IDs. Human-facing final prose may remain buffered while actions are visible. The inline
witness uses Nova's main local model endpoint in a separate context; the separately launched 8081
server is not automatically the inline auditor. It checks the assembled delivered candidate,
including earlier tool-loop commentary, and receives available screenshot pixels with their
observation context. An explicit approval is distinct from a concern, an incomplete check or an
execution error. Incomplete/error checks remain visible and do not certify the draft. A concern
returns to Nova to revise in her own words; the auditor does not silently replace her voice.

Guest Bash (`computer_exec`), screenshots and hands target Nova's authenticated :1 display.
Host `run_command` is Windows PowerShell. WSLg :0 is another Linux graphical session, not the
native Windows desktop. Authorized host reach remains available; tool choice identifies the
destination. `computer_action` launch/browser helpers retain diagnostics and report the limited
postcondition they observed; a process or window alone does not prove a page loaded or a video played.
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
Unit/fixture passes do not certify every optional application, native window interaction or adapter swap.
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
turn on Nova when a message arrives. **Start Nova** in Conversation explicitly enables the full
stack; **Stop Nova** drains work, saves the active session and returns to chat-only. The launcher
stops its guardian/watcher before replacing workers and refuses a worker teardown without a
successful quiesce acknowledgment. New body input and updater mutations are blocked while a switch
is pending. Failed startup attempts return to a usable chat-only controller when recovery succeeds.
The main window and console stay open; the page reconnects and restores its unsent composer draft.
The launcher uses `start_llama_qwen36.cmd`, so its model selection matches the updater's boot files.
A launcher predating this feature needs one full app restart; refreshing the page alone cannot
upgrade that process. Start/Stop remains unavailable when lifecycle support cannot be reached. It
refuses to attach to an already-running full server as though that server were dormant. The
Collaboration room also works during a normal launch without being fed to Nova's conversation.
Both modes start the updater catalog check after a cancellable delay; this does not start the model
or enumerate installed weights. The controller status bar distinguishes Chat only from Nova running.

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
sources against startup, ignoring watcher header timestamps and line endings. This detects even
same-size edits with unchanged timestamps; it is not a census of every imported module.
New structured receipts distinguish success, failure, refusal,
timeout, cancellation and unknown. Guest receipts include their shell/display context. Pipeline
shows tool start and terminal outcomes rather than only witness work; its operation IDs link to
the tool ledger. Witness incomplete/error statuses are unverified, never approval. Historical
Pipeline rows whose recorded approval contains a tool request are shown as incomplete by the
controller without rewriting the original log. Historical receipts retain their original values; older
`ok: true` entries can mislabel nonzero exits. Validate their artifacts independently. A running
port does not prove successful inference. The Control widget exposes task scheduling, verification,
stop/resume, memory ingestion health and VM handoff through `/api/runtime/state` and related routes.

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

## Files and recovery

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
