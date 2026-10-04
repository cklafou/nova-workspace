# Last updated: 2026-10-04 14:28:11
"""Extract Nova's architecture without executing its modules.

Python's AST establishes imports and calls whose receivers can be resolved. A reviewed
catalog supplies explanations and the callback/file/network seams static analysis cannot
prove. Evidence hashes invalidate those annotations when their enclosing code changes.
"""
from __future__ import annotations

import argparse
import ast
import os
import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from atlas_history import build_history

HERE = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = HERE.parent.parent
SKIP = {"__pycache__", "tests", "reports", "Temp", ".git", "node_modules"}
SKIP.update({"SELF", "Nova_Created", "memory", "logs", "Tasking", "KoELS", "nova_memory_db", "models", "vendor", "node_modules"})
BOUNDARIES = [
    "nova_start.py", "general_tools/NovaLauncher.py",
    "general_tools/nova_chat/runtime_host.py", "general_tools/nova_chat/server.py",
    "general_tools/nova_chat/workspace_context.py", "general_tools/nova_chat/transcript.py",
    "general_tools/nova_chat/session_manager.py", "general_tools/nova_chat/nova_bridge.py",
]


def digest(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def source_files(workspace):
    root = workspace / "nova_body"
    files = {p for p in (p for p in source_tree(root) if p.suffix == ".py") if not set(p.relative_to(root).parts) & SKIP}
    files.update(workspace / p for p in BOUNDARIES if (workspace / p).is_file())
    return sorted(files)


def supporting_files(workspace):
    """Launch/provisioning definitions; never enumerate tool internals or private data."""
    root = workspace / "nova_body"
    files = {p for p in source_tree(root) if p.is_file()
             and p.suffix in {".cmd", ".sh", ".ps1", ".toml", ".yaml", ".yml"}
             and not set(p.relative_to(root).parts) & SKIP}
    files.update(workspace / p for p in ["NovaStart.cmd", "StopNova.cmd", "start_llama_qwen36.cmd"]
                 if (workspace / p).is_file())
    return sorted(files)


def module_name(path):
    parts = Path(path).with_suffix("").parts
    if parts[0] in {"nova_body", "general_tools"}:
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def group_for(path):
    if path.startswith("nova_body/"):
        return path.split("/")[1]
    return "boundary_boot" if path in {"nova_start.py", "general_tools/NovaLauncher.py"} else "boundary_chat"


def short_doc(doc):
    lines = [s.strip() for s in (doc or "").splitlines() if s.strip()]
    lines = [s for s in lines if not re.fullmatch(r"[=─\- _]+", s)]
    return " ".join(lines)[:420]


def expression(node):
    try:
        return ast.unparse(node)[:240]
    except Exception:
        return "?"


def evidence(file, node, text, symbol=""):
    return {"file": file, "line": getattr(node, "lineno", 1),
            "end": getattr(node, "end_lineno", 1), "symbol": symbol,
            "text": text[:360]}


class Module:
    def __init__(self, path, source):
        self.path, self.source = path, source
        self.name = module_name(path)
        self.tree = ast.parse(source, filename=path)
        self.defs = {}
        self.imports, self.calls, self.assignments, self.routes = [], [], [], []
        self.bindings = defaultdict(dict)
        self.params = defaultdict(set)
        self.types = {}
        self.parents = {}
        self._walk(self.tree, "", [], None)

    def _walk(self, node, scope, conditions, parent):
        self.parents[node] = parent
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{scope}.{node.name}".strip(".")
            self.defs[name] = node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.params[name] = {a.arg for a in node.args.args + node.args.posonlyargs + node.args.kwonlyargs}
                for dec in node.decorator_list:
                    if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                            and dec.func.attr in {"get", "post", "put", "patch", "delete", "websocket"}
                            and dec.args and isinstance(dec.args[0], ast.Constant)):
                        self.routes.append({"method": dec.func.attr.upper(), "path": str(dec.args[0].value),
                                            "symbol": name, "line": node.lineno})
            for child in ast.iter_child_nodes(node):
                self._walk(child, name, conditions, node)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            self.imports.append((node, scope, list(conditions)))
        if isinstance(node, ast.Call):
            self.calls.append((node, scope, list(conditions)))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            self.assignments.append((node, scope))
        child_conditions = conditions
        if isinstance(node, ast.If):
            self._walk(node.test, scope, conditions, node)
            for child in node.body:
                self._walk(child, scope, conditions + ["if " + expression(node.test)], node)
            for child in node.orelse:
                self._walk(child, scope, conditions + ["else of " + expression(node.test)], node)
            return
        elif isinstance(node, ast.Try):
            child_conditions = conditions + ["try / fallback"]
        for child in ast.iter_child_nodes(node):
            self._walk(child, scope, child_conditions, node)

    def absolute_import(self, node):
        if not node.level:
            return node.module or ""
        package = self.name.split(".") if self.path.endswith("/__init__.py") else self.name.split(".")[:-1]
        cut = node.level - 1
        package = package[:len(package) - cut] if cut else package
        return ".".join(package + ([node.module] if node.module else []))

    def lookup(self, name, scope):
        current = scope
        while True:
            skip_class = current != scope and isinstance(self.defs.get(current), ast.ClassDef)
            if not skip_class and name in self.bindings[current]:
                return self.bindings[current][name]
            # A parameter or assignment shadows an outer name; do not guess its type.
            if not skip_class and name in self.params[current]:
                return None
            if not current:
                return None
            current = current.rpartition(".")[0]

    def enclosing_class(self, scope):
        while scope:
            if isinstance(self.defs.get(scope), ast.ClassDef):
                return scope
            scope = scope.rpartition(".")[0]
        return ""


def resolve(qualified, module_map, modules):
    """Longest real module prefix; never match an unrelated bare method name."""
    bits = qualified.split(".")
    for end in range(len(bits), 0, -1):
        candidate = ".".join(bits[:end])
        if candidate not in module_map:
            continue
        target = module_map[candidate]
        symbol = ".".join(bits[end:])
        if symbol and symbol not in modules[target].defs:
            return target, symbol, "imported attribute; definition not resolved"
        return target, symbol, "resolved"
    return None


def symbol_hash(module, symbol):
    node = module.defs.get(symbol) if symbol else module.tree
    if node is None:
        return None
    # Include comments/docstrings: annotations should ask for review when their meaning changes.
    lines = module.source.splitlines()
    segment = "\n".join(lines[node.lineno - 1:node.end_lineno]) if symbol else module.source
    return digest(segment)


def collect(workspace, catalog_path=None):
    workspace = Path(workspace).resolve()
    catalog_path = Path(catalog_path or HERE / "catalog.json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    modules, nodes, imports, calls, unresolved, errors = {}, [], [], [], [], []
    for p in source_files(workspace):
        rel = p.relative_to(workspace).as_posix()
        try:
            source = p.read_text(encoding="utf-8-sig")
            modules[rel] = Module(rel, source)
        except (SyntaxError, UnicodeError, OSError) as e:
            errors.append({"file": rel, "line": getattr(e, "lineno", 1), "message": str(e)})
            nodes.append({"id": rel, "group": group_for(rel), "label": p.name,
                          "summary": "Source cannot be parsed; connections are unknown.",
                          "status": "parse_error", "symbols": [], "routes": []})
    module_map = {}
    for path, mod in modules.items():
        module_map[mod.name] = path
        module_map[path[:-3].replace("/", ".").removesuffix(".__init__")] = path
    for path, mod in modules.items():
        for node, scope, conditions in mod.imports:
            if isinstance(node, ast.Import):
                entries = [(a.name, a.asname or a.name.split(".")[0], a.name if a.asname else a.name.split(".")[0]) for a in node.names]
            else:
                base = mod.absolute_import(node)
                entries = [(f"{base}.{a.name}".strip("."), a.asname or a.name,
                            f"{base}.{a.name}".strip(".")) for a in node.names]
            for full, alias, bound in entries:
                old = mod.bindings[scope].get(alias)
                mod.bindings[scope][alias] = bound if old in (None, bound) else "!ambiguous"
                hit = resolve(full, module_map, modules)
                if hit:
                    target, symbol, resolution = hit
                    imports.append({"from": path, "to": target, "kind": "import", "label": full,
                                    "symbol": symbol, "scope": scope, "conditions": conditions,
                                    "resolution": resolution, "evidence": [evidence(path, node, expression(node), scope)]})
                elif full.startswith(("nova_", "general_tools.", "KoELS")):
                    unresolved.append({"file": path, "line": node.lineno, "scope": scope,
                                       "expression": expression(node), "reason": "Import target is absent or outside the mapped boundary"})

    def qualify(mod, expr, scope):
        if isinstance(expr, ast.Name):
            bound = mod.lookup(expr.id, scope)
            if bound:
                return bound
            current = scope
            while True:
                if expr.id in mod.params[current] and (current == scope or not isinstance(mod.defs.get(current), ast.ClassDef)):
                    return None
                if not current:
                    break
                current = current.rpartition(".")[0]
            current = scope
            while True:
                local = f"{current}.{expr.id}".strip(".")
                if local in mod.defs and (current == scope or not isinstance(mod.defs.get(current), ast.ClassDef)):
                    return mod.name + "." + local
                if not current:
                    break
                current = current.rpartition(".")[0]
            return None
        if isinstance(expr, ast.Attribute):
            if isinstance(expr.value, ast.Name) and expr.value.id in {"self", "cls"}:
                cls = mod.enclosing_class(scope)
                key = (cls, "self." + expr.attr)
                if key in mod.types:
                    return mod.types[key] or "!unresolved-receiver"
                if cls and f"{cls}.{expr.attr}" in mod.defs:
                    return f"{mod.name}.{cls}.{expr.attr}"
            base = qualify(mod, expr.value, scope)
            return base + "." + expr.attr if base else None
        return None

    # Infer only unambiguous receivers assigned a directly resolvable constructor.
    for mod in modules.values():
        assigned = defaultdict(list)
        for node, scope in mod.assignments:
            value = node.value
            if value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                qualified = qualify(mod, value.func, scope) if isinstance(value, ast.Call) else None
                hit = resolve(qualified, module_map, modules) if qualified else None
                if not hit or not isinstance(modules[hit[0]].defs.get(hit[1]), ast.ClassDef):
                    qualified = None
                if isinstance(target, ast.Name):
                    assigned[(scope, target.id)].append(qualified)
                elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    assigned[(mod.enclosing_class(scope), expression(target))].append(qualified)
        for (scope, name), candidates in assigned.items():
            resolved_type = candidates[0] if all(c == candidates[0] for c in candidates) else None
            if name.startswith("self."):
                mod.types[(scope, name)] = resolved_type
            else:
                mod.params[scope].add(name)
                mod.bindings[scope][name] = resolved_type or "!unresolved-assignment"
    for path, mod in modules.items():
        for node, scope, conditions in mod.calls:
            qualified = qualify(mod, node.func, scope)
            hit = resolve(qualified, module_map, modules) if qualified else None
            if hit and hit[2] == "resolved":
                target, symbol, _ = hit
                calls.append({"from": path, "to": target, "kind": "call", "label": expression(node.func),
                              "caller": scope or "<module>", "callee": symbol, "conditions": conditions,
                              "evidence": [evidence(path, node, expression(node), scope)]})
            elif isinstance(node.func, ast.Attribute) or (isinstance(node.func, ast.Name) and node.func.id in mod.params[scope]):
                unresolved.append({"file": path, "line": node.lineno, "scope": scope,
                                   "expression": expression(node.func),
                                   "reason": "Receiver/callback is dynamic, external, or unresolved; no call edge asserted"})
        custom = catalog.get("modules", {}).get(path, {})
        summaries = ast.get_docstring(mod.tree) or ""
        symbols = []
        for name, node in mod.defs.items():
            symbols.append({"name": name, "line": node.lineno, "end": node.end_lineno,
                            "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                            "signature": expression(node.args) if hasattr(node, "args") else "",
                            "summary": short_doc(ast.get_docstring(node))})
        nodes.append({"id": path, "group": group_for(path), "label": custom.get("label", Path(path).name),
                      "summary": custom.get("summary", short_doc(summaries) or "See declared functions and source references."),
                      "description_origin": "reviewed explanation" if custom else "source docstring; may be stale",
                      "status": "parsed", "hash": digest(mod.source), "symbols": symbols, "routes": mod.routes,
                      "explanation_status": "current" if custom.get("review_hash") == digest(mod.source) else "needs_review",
                      "lines": len(mod.source.splitlines())})
    reviewed = []
    for item in catalog.get("connections", []):
        edge = dict(item)
        edge["evidence"], problems = [], []
        for ref in item.get("refs", []):
            mod = modules.get(ref["file"])
            node = mod.defs.get(ref.get("symbol", "")) if mod and ref.get("symbol") else (mod.tree if mod else None)
            if node is None:
                problems.append(f"Missing source/symbol: {ref['file']} {ref.get('symbol', '')}")
                continue
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", len(mod.source.splitlines()))
            segment = "\n".join(mod.source.splitlines()[start - 1:end])
            needle = ref.get("contains", "")
            if needle and needle not in segment:
                problems.append(f"Evidence no longer contains {needle!r}")
            if ref.get("hash") != symbol_hash(mod, ref.get("symbol", "")):
                problems.append("Enclosing source changed since this explanation was reviewed")
            line = start + (segment[:segment.find(needle)].count("\n") if needle and needle in segment else 0)
            edge["evidence"].append({"file": ref["file"], "line": line, "symbol": ref.get("symbol", ""), "text": needle})
        edge["status"] = "needs_review" if problems or not item.get("refs") else "source_checked"
        edge["problems"] = problems
        edge.pop("refs", None)
        reviewed.append(edge)
    groups = []
    for group_id in sorted({n["group"] for n in nodes}):
        config = catalog.get("groups", {}).get(group_id, {})
        groups.append({"id": group_id, "label": config.get("label", group_id),
                       "summary": config.get("summary", "New package discovered; explanation needs review."),
                       "kind": "boundary" if group_id.startswith("boundary_") else "body",
                       "lane": config.get("lane", 2), "order": config.get("order", 99),
                       "plain": config.get("plain", group_id.replace("nova_", "").replace("_", " ")),
                       "explanation_status": "needs_review" if any(n.get("explanation_status") == "needs_review" or n.get("status") == "parse_error" for n in nodes if n["group"] == group_id) else "current",
                       "notes": config.get("notes", [])})
    definitions = [{"id": p.relative_to(workspace).as_posix(), "hash": digest(p.read_bytes()),
                    "label": p.name, "kind": "launch / provisioning definition"} for p in supporting_files(workspace)]
    resources = []
    for item in catalog.get("resources", []):
        resource = dict(item)
        resource["kind"] = item.get("kind", "storage")
        path = workspace / item["path"] if item.get("path") else None
        resource["present"] = path.exists() if path else None
        # Expose metadata, not personal memory contents or model binaries.
        resource["modified_ns"] = path.stat().st_mtime_ns if path and path.exists() else None
        if item.get("url_ref"):
            ref = item["url_ref"]
            mod = modules.get(ref["file"])
            urls = []
            if mod:
                for assignment, scope in mod.assignments:
                    targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
                    if scope or not any(isinstance(t, ast.Name) and t.id == ref["name"] for t in targets):
                        continue
                    for value in ast.walk(assignment.value):
                        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.startswith(("http://", "https://")):
                            parsed = urlsplit(value.value)
                            if parsed.hostname:
                                # Never emit credentials, query parameters, or fragments.
                                host = parsed.hostname
                                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                                urls.append((f"{parsed.scheme}://{host}:{port}{parsed.path}", host, port, assignment.lineno))
            if len(urls) == 1:
                url, host, port, line = urls[0]
                resource.update({"url": url, "host": host, "port": port, "port_origin": "source default; runtime overrides not inspected",
                                 "url_evidence": {"file": ref["file"], "line": line, "text": ref["name"]}})
                resource["plain"] = f"Source default :{port}"
            else:
                resource.update({"port": None, "port_origin": "Endpoint definition changed; review required"})
                resource.pop("url", None)
                resource["plain"] = "Endpoint unresolved; needs review"
        if item.get("port_ref"):
            ref, port, line = item["port_ref"], None, 1
            mod = modules.get(ref["file"])
            if mod and ref.get("name"):
                for assignment, scope in mod.assignments:
                    targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
                    if not scope and any(isinstance(t, ast.Name) and t.id == ref["name"] for t in targets):
                        if isinstance(assignment.value, ast.Constant) and isinstance(assignment.value.value, int):
                            port, line = assignment.value.value, assignment.lineno
            elif ref.get("pattern") and ref["file"] in {d["id"] for d in definitions}:
                source = (workspace / ref["file"]).read_text(encoding="utf-8-sig")
                matches = list(re.finditer(ref["pattern"], source, re.MULTILINE))
                if len(matches) == 1:
                    port = int(matches[0].group(1))
                    line = source[:matches[0].start()].count("\n") + 1
            resource.update({"port": port, "plain": f"Source default :{port}" if port else "Endpoint unresolved; needs review",
                             "port_origin": "Source default; runtime overrides not inspected" if port else "Endpoint definition changed; review required"})
            if port:
                resource["url"] = f"http://127.0.0.1:{port}"
                resource["url_evidence"] = {"file": ref["file"], "line": line, "text": ref.get("name", "Service port definition")}
            else:
                resource.pop("url", None)
        resources.append(resource)
    node_ids = {n["id"] for n in nodes} | {n["id"] for n in resources}
    for edge in reviewed:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            edge["status"] = "needs_review"
            edge["problems"].append("Endpoint disappeared from the current source inventory")
    result = {"schema": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
              "workspace": str(workspace), "nodes": nodes, "groups": groups,
              "resources": resources, "definitions": definitions, "imports": imports, "calls": calls,
              "connections": reviewed, "unresolved": unresolved, "errors": errors,
              "journeys": catalog.get("journeys", []), "simple": catalog.get("simple", {}),
              "scope": {"body": "All Python modules under nova_body; tests/reports excluded from the runtime graph.",
                        "boundary": "Only launch and chat attachment seams are inspected outside the body. Detachable tools are not expanded.",
                        "evidence": "Static source inspection; not proof that a branch ran. Dynamic/external receivers remain unresolved.",
                        "updates": "Source, catalog, viewer assets, launch/config definitions, and mapped storage metadata are watched. Personal memory/log contents are never embedded. Runtime execution and arbitrary reflective Python behavior are not inferred."}}
    learning_path = catalog_path.parent / "learning.json"
    result["learning"] = json.loads(learning_path.read_text(encoding="utf-8")) if learning_path.exists() else {}
    result["history"] = build_history(workspace, catalog_path.parent / "timeline.json")
    result["review"] = []
    for n in nodes:
        if n.get("explanation_status") == "needs_review" or n.get("status") == "parse_error":
            result["review"].append({"id":"source:"+n["id"], "node":n["id"], "kind":"Source review",
                "title":n["label"], "detail":"The source changed or could not be parsed. Re-read the implementation before relying on the previous explanation."})
    for g in groups:
        own = {n["id"] for n in nodes if n["group"] == g["id"]}
        inbound = [e for e in imports+calls if e["to"] in own and e["from"] not in own]
        if not inbound and g["kind"] == "body":
            result["review"].append({"id":"callers:"+g["id"], "node":g["id"], "kind":"Integration question",
                "title":"How is "+g["label"]+" reached?",
                "detail":"No cross-package import or statically resolved caller was found in this scope. It may be standalone, dynamically loaded, optional or unfinished. This is a lead to inspect, not a dead-code verdict."})
    for e in reviewed:
        if e["status"] == "needs_review":
            result["review"].append({"id":"seam:"+e["id"], "node":e["from"], "kind":"Connection review", "title":e["label"], "detail":"; ".join(e["problems"])})
    content = {k: v for k, v in result.items() if k != "generated_at"}
    result["revision"] = digest(json.dumps(content, sort_keys=True))[:16]
    return result


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def overview_svg(data, simple=False):
    """Dependency overview; expanded evidence lives in the HTML report and explorer."""
    groups = data["groups"]
    if simple:
        cards = data.get("simple", {}).get("nodes", [])
        edges = data.get("simple", {}).get("edges", [])
    else:
        cards = groups + data["resources"]
        index = {n["id"]: n["group"] for n in data["nodes"]}
        pairs = defaultdict(int)
        for e in data["imports"] + data["connections"]:
            if e.get("status") == "needs_review":
                continue
            a, b = index.get(e["from"], e["from"]), index.get(e["to"], e["to"])
            if a != b:
                pairs[a, b] += 1
        edges = [{"from": a, "to": b, "label": str(n)} for (a, b), n in pairs.items()]
    lanes = defaultdict(list)
    for n in cards:
        lanes[n.get("lane", 2)].append(n)
    spacing = 395 if simple else 310
    width = max(lanes, default=0) * spacing + 320
    height = max((len(x) for x in lanes.values()), default=1) * 126 + 100
    positions = {}
    for lane, values in lanes.items():
        for row, n in enumerate(sorted(values, key=lambda v: v.get("order", 99))):
            positions[n["id"]] = (lane * spacing + 30, row * 126 + 66)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Nova architecture overview">',
           '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#63768f"/></marker></defs>',
           f'<rect width="{width}" height="{height}" fill="#0c1421"/>',
           '<text x="30" y="32" fill="#edf3fc" font-size="20" font-family="sans-serif">Nova — '+ ('the simple view' if simple else 'component dependency overview') +'</text>']
    for edge in edges:
        if edge["from"] not in positions or edge["to"] not in positions:
            continue
        x1, y1 = positions[edge["from"]]; x2, y2 = positions[edge["to"]]
        if x1 == x2:
            x1 += 245; x2 += 245
            d = f"M{x1},{y1+40} C{x1+52},{y1+40} {x2+52},{y2+40} {x2},{y2+40}"
        else:
            x1 += 245 if x2 > x1 else 0
            x2 += 0 if x2 > x1 else 245
            mid = (x1 + x2) / 2
            d = f"M{x1},{y1+40} C{mid},{y1+40} {mid},{y2+40} {x2},{y2+40}"
        out.append(f'<path d="{d}" fill="none" stroke="#63768f" stroke-opacity=".55" marker-end="url(#arrow)"/>')
        if simple:
            out.append(f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2+30}" text-anchor="middle" fill="#81d9c4" font-size="11" font-family="sans-serif">{html.escape(edge.get("label", ""))}</text>')
    for n in cards:
        x,y = positions[n["id"]]
        out.append(f'<g><rect x="{x}" y="{y}" width="245" height="84" rx="9" fill="#142338" stroke="#34475e"/>')
        out.append(f'<text x="{x+14}" y="{y+28}" fill="#edf3fc" font-size="15" font-family="sans-serif">{html.escape(n.get("label",n["id"]))}</text>')
        subtitle = n.get("plain", n.get("kind", ""))[:33]
        out.append(f'<text x="{x+14}" y="{y+53}" fill="#9fb2cd" font-size="12" font-family="sans-serif">{html.escape(subtitle)}</text></g>')
    return "\n".join(out + ["</svg>"])


def write_outputs(data, output, assets=HERE):
    output = Path(output)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (assets / "viewer.html").read_text(encoding="utf-8")
    css = (assets / "viewer.css").read_text(encoding="utf-8")
    js = (assets / "viewer.js").read_text(encoding="utf-8")
    experience = assets / "experience.js"
    if experience.exists():
        js = js.replace("/*__EXPERIENCE__*/", experience.read_text(encoding="utf-8"))
    template = template.replace("/*__STYLE__*/", css).replace("/*__APP__*/", js)
    template = template.replace("/*__DATA__*/null", payload)
    atomic_write(output / "index.html", template)
    atomic_write(output / "architecture.json", json.dumps(data, ensure_ascii=False, indent=2))
    atomic_write(output / "level-1.svg", overview_svg(data, simple=True))
    atomic_write(output / "level-2.svg", overview_svg(data))
    lines = ["# Nova architecture — generated source inventory", "",
             f"Generated: {data['generated_at']} · revision `{data['revision']}`", "",
             "Open `index.html` for all three levels. SVGs are overview exports; the explorer and tables contain the complete mapped inventory.", "",
             "Static imports are dependencies, not execution order. Source-checked seams are reviewed annotations. Unresolved receivers are reported, never guessed.", "",
             f"{len(data['nodes'])} modules · {len(data['imports'])} import references · {len(data['calls'])} resolved call sites · {len(data['connections'])} reviewed seams.", ""]
    for g in data["groups"]:
        lines += [f"## {g['label']}", "", g["summary"], "", "| Module | Purpose |", "|---|---|"]
        for n in data["nodes"]:
            if n["group"] == g["id"]:
                desc = n["summary"].replace("|", "/").replace("\n", " ")
                lines.append(f"| `{n['id']}` | {desc} |")
        lines.append("")
    lines += ["## Supporting launch and provisioning definitions", ""]
    lines.extend(f"- `{d['id']}`" for d in data.get("definitions", []))
    lines += ["## Parse failures", "", json.dumps(data["errors"], indent=2), "",
              "## Reviewed seams requiring another review", ""]
    for edge in data["connections"]:
        if edge["status"] == "needs_review":
            lines.append(f"- {edge['label']}: {'; '.join(edge['problems'])}")
    atomic_write(output / "INVENTORY.md", "\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--catalog", type=Path, default=HERE / "catalog.json")
    args = parser.parse_args()
    data = collect(args.workspace, args.catalog)
    output = args.output or args.workspace / "Orient" / "Architecture"
    write_outputs(data, output)
    print(json.dumps({"revision": data["revision"], "modules": len(data["nodes"]),
                      "imports": len(data["imports"]), "calls": len(data["calls"]),
                      "errors": data["errors"], "output": str(output)}))



def source_tree(root):
    """Walk source with excluded directory names pruned before descent."""
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if n not in SKIP and not n.startswith('.')
                   and not (Path(current) / n).is_symlink()]
        for name in files:
            yield Path(current) / name

if __name__ == "__main__":
    main()
