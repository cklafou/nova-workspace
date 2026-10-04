# Last updated: 2026-10-04 14:28:11
"""Read bounded, first-parent source history. No checkout, hooks or Nova imports.

Daily net changes suppress auto-save noise without pretending that Git records intent.
Reviewed development notes supply the separate, explicitly attributed decision layer.
"""
from __future__ import annotations

import ast
import os
import copy
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = 3
EXTENSIONS = {'.py', '.sh', '.cmd', '.ps1', '.toml', '.yaml', '.yml'}
BOUNDARIES = {'nova_start.py', 'NovaStart.cmd', 'StopNova.cmd', 'start_llama_qwen36.cmd',
              'general_tools/NovaLauncher.py', 'general_tools/nova_chat/server.py',
              'general_tools/nova_chat/runtime_host.py', 'general_tools/nova_chat/workspace_context.py',
              'general_tools/nova_chat/transcript.py', 'general_tools/nova_chat/session_manager.py',
              'general_tools/nova_chat/nova_bridge.py'}
SKIP = {'tests', 'reports', 'Temp', '__pycache__', '.git'}
SKIP.update({"SELF", "Nova_Created", "memory", "logs", "Tasking", "KoELS", "nova_memory_db", "models", "vendor", "node_modules"})
_BLOBS = {}


def run_git(workspace, *args, binary=False, input=None, timeout=90):
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    result = subprocess.run(['git', '-C', str(workspace), '-c', 'core.quotepath=false', *args],
                            input=input, capture_output=True, timeout=timeout, creationflags=flags)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace')[:500].strip())
    return result.stdout if binary else result.stdout.decode('utf-8', 'replace')


def head_revision(workspace):
    try:
        return run_git(workspace, 'rev-parse', '--verify', 'HEAD', timeout=5).strip()
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return 'unavailable'


def in_scope(path):
    p = Path(path)
    return path in BOUNDARIES or (path.startswith('nova_body/') and p.suffix in EXTENSIONS
                                  and not set(p.parts) & SKIP)


def normalize(source):
    # Only timestamp-only comment/header lines; do not discard arbitrary comments or strings.
    return '\n'.join(line for line in source.replace('\r\n', '\n').splitlines()
                     if not re.match(r'^\s*(?:#\s*|_\s*)Last updated\s*:', line, re.I)).rstrip('\n')


def parsed(source):
    tree = ast.parse(source)
    names = []
    def visit(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            child_prefix = prefix
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                child_prefix = f'{prefix}.{child.name}'.strip('.')
                names.append(child_prefix)
            visit(child, child_prefix)
    visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return ast.dump(tree, include_attributes=False), set(names)


def classify(path, before, after):
    if before is None:
        return {'kind': 'added', 'summary': 'File enters the retained history; it may have existed earlier.'}
    if after is None:
        return {'kind': 'removed', 'summary': 'File leaves this path. A rename may appear as an add/remove pair.'}
    housekeeping = path.endswith('.py') and normalize(before) == normalize(after)
    if housekeeping and path.endswith('.py'):
        try:
            housekeeping = ast.dump(ast.parse(before), include_attributes=False) == ast.dump(ast.parse(after), include_attributes=False)
        except (SyntaxError, ValueError):
            housekeeping = False
    if housekeeping:
        return {'kind': 'housekeeping', 'summary': 'Only timestamp headers or line endings changed.'}
    if path.endswith('.py'):
        try:
            old_ast, old_names = parsed(before)
            new_ast, new_names = parsed(after)
            if old_ast == new_ast:
                return {'kind': 'notes', 'summary': 'Comments, docstrings or formatting changed; executable statements have the same AST. Docstrings can still affect code that reads them.'}
            return {'kind': 'code', 'summary': 'Python structure changed; inspect the diff to understand the behavior.',
                    'added_symbols': sorted(new_names-old_names), 'removed_symbols': sorted(old_names-new_names)}
        except (SyntaxError, ValueError, RecursionError):
            return {'kind': 'unparsed', 'summary': 'Text changed, but a before/after snapshot cannot be parsed. Review the diff; no behavioral claim is made.'}
    return {'kind': 'definition', 'summary': 'A launch or provisioning definition changed.'}


def read_blobs(workspace, ids):
    missing = sorted({oid for oid in ids if oid and set(oid) != {'0'} and (str(workspace), oid) not in _BLOBS})
    # Bounded batches avoid one enormous cat-file output on a long-lived repository.
    for offset in range(0, len(missing), 80):
        batch = missing[offset:offset+80]
        output = run_git(workspace, 'cat-file', '--batch', binary=True,
                         input=('\n'.join(batch)+'\n').encode())
        cursor = 0
        for oid in batch:
            end = output.index(b'\n', cursor)
            header = output[cursor:end].split()
            if len(header) != 3 or header[1] != b'blob':
                raise RuntimeError('History blob is unavailable; no diff classification was invented')
            size = int(header[2]); start = end+1
            if size > 4_000_000:
                raise RuntimeError('Source history contains an unexpectedly large blob')
            _BLOBS[str(workspace), oid] = output[start:start+size].decode('utf-8-sig', 'replace')
            cursor = start+size+1
    return {oid: None if not oid or set(oid)=={'0'} else _BLOBS[str(workspace), oid] for oid in ids}


def git_scope(workspace):
    top = Path(run_git(workspace, 'rev-parse', '--show-toplevel').strip()).resolve()
    prefix = Path(workspace).resolve().relative_to(top).as_posix()
    prefix = '' if prefix == '.' else prefix+'/'
    return top, prefix, [prefix+'nova_body']+[prefix+p for p in sorted(BOUNDARIES)]


def scan_history(workspace, head):
    top, prefix, paths = git_scope(workspace)
    raw = run_git(top, 'log', '--first-parent', '--no-renames', '--no-decorate', '--no-show-signature',
                  '--format=%x1e%H%x1f%cI%x1f%s', '--raw', '--no-abbrev', head, '--', *paths)
    commits = []
    for record in raw.split('\x1e'):
        lines = record.strip().splitlines()
        if not lines or '\x1f' not in lines[0]:
            continue
        sha, when, title = lines[0].split('\x1f', 2)
        changes = []
        for line in lines[1:]:
            if not line.startswith(':') or '\t' not in line:
                continue
            meta, file = line.split('\t', 1)
            fields = meta.split()
            rel = file.removeprefix(prefix)
            if in_scope(rel) and len(fields) == 5:
                changes.append({'file': rel, 'before': fields[2], 'after': fields[3]})
        if changes:
            commits.append({'id': sha, 'when': when, 'title': title, 'changes': changes})
    days = {}
    for commit in reversed(commits):
        day = commit['when'][:10]
        entry = days.setdefault(day, {'date': day, 'commits': [], 'changes': {}})
        entry['commits'].append({k:v for k,v in commit.items() if k!='changes'})
        for change in commit['changes']:
            file = change['file']
            previous = entry['changes'].get(file)
            entry['changes'][file] = {**change, 'before': previous['before'] if previous else change['before']}
    all_ids = {oid for d in days.values() for c in d['changes'].values() for oid in [c['before'],c['after']]}
    blobs = read_blobs(top, all_ids)
    daily = []
    for day, entry in sorted(days.items(), reverse=True):
        changes = []
        for change in entry['changes'].values():
            if change['before'] == change['after']:
                continue  # Reverted within the day; raw commits remain in the day record.
            changes.append(change | classify(change['file'], blobs[change['before']], blobs[change['after']]))
        count = sum(c['kind']!='housekeeping' for c in changes)
        daily.append({'id': day, 'date': day, 'commits': list(reversed(entry['commits'])),
                      'files': changes, 'meaningful_files': count,
                      'housekeeping_files': len(changes)-count})
    tree = run_git(top, 'ls-tree', '-r', head, '--', *paths)
    head_files = {}
    for line in tree.splitlines():
        if '\t' not in line:
            continue
        meta, file = line.split('\t', 1); fields=meta.split(); rel=file.removeprefix(prefix)
        if in_scope(rel) and fields[1]=='blob':
            head_files[rel]=fields[2]
    return {'version':VERSION, 'head':head, 'daily':daily, 'head_files':head_files,
            'coverage': {'scoped_commits':len(commits), 'oldest':commits[-1]['when'] if commits else None,
                         'newest':commits[0]['when'] if commits else None,
                         'shallow':run_git(top,'rev-parse','--is-shallow-repository').strip()=='true',
                         'method':'First-parent history, grouped by the committer date and offset recorded by Git. File changes are net before/after changes for each day; edits reverted that day may not appear in the net diff.'}}


def document_refs(workspace, items):
    output=[]
    for original in items:
        item=copy.deepcopy(original); item['evidence']=[]; problems=[]
        for ref in item.get('refs',[]):
            p=(workspace/ref['file']).resolve()
            if not p.is_relative_to(workspace) or not p.is_file():
                problems.append('Missing development note: '+ref['file']);continue
            text=p.read_text(encoding='utf-8-sig',errors='replace')
            needle=ref.get('contains','')
            if not needle or needle not in text:
                problems.append('The referenced passage changed: '+ref['file'])
            if ref.get('review_hash') and ref['review_hash'] != hashlib.sha256(text.encode()).hexdigest():
                problems.append('Development note changed since this summary was reviewed: '+ref['file'])
            line=text[:text.find(needle)].count('\n')+1 if needle and needle in text else 1
            if '\0' in text: problems.append('Source contains damaged/null-padded text; only surviving passages can support this entry.')
            item['evidence'].append({'file':ref['file'],'line':line,'text':needle,'historical':True})
        item['problems']=problems; item.pop('refs',None); output.append(item)
    return output


def build_history(workspace, config_path):
    workspace=Path(workspace).resolve(); config_path=Path(config_path)
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    head=head_revision(workspace)
    result={'head':head,'daily':[],'working':[],'error':None,
            'milestones':document_refs(workspace,config.get('milestones',[])),
            'origin':config.get('origin','Earlier history may not be retained in this repository.'),
            'coverage':{},'decision_template':config.get('decision_template',{})}
    if head=='unavailable':
        result['error']='Git history unavailable. Documented milestones and the source map still work.'
        return result
    try:
        cache_path=config_path.parent/'Temp'/'history-cache.json'
        cached={}
        if cache_path.exists():
            try:cached=json.loads(cache_path.read_text(encoding='utf-8'))
            except (ValueError,OSError):pass
        if cached.get('head')!=head or cached.get('version')!=VERSION or cached.get('workspace')!=str(workspace):
            cached=scan_history(workspace,head);cached['workspace']=str(workspace)
            cache_path.parent.mkdir(parents=True,exist_ok=True)
            temp=cache_path.with_suffix('.tmp');temp.write_text(json.dumps(cached),encoding='utf-8');temp.replace(cache_path)
        result.update({k:cached[k] for k in ['daily','coverage']})
        top,_,_=git_scope(workspace)
        blobs=read_blobs(top,set(cached['head_files'].values()))
        paths=set(cached['head_files'])
        paths.update(p.relative_to(workspace).as_posix() for p in source_tree(workspace/'nova_body') if p.is_file() and in_scope(p.relative_to(workspace).as_posix()))
        paths.update(p for p in BOUNDARIES if (workspace/p).is_file())
        for file in sorted(paths):
            p=workspace/file;oid=cached['head_files'].get(file)
            before=blobs.get(oid);after=p.read_bytes().decode('utf-8-sig','replace') if p.is_file() else None
            if before==after or (before is None and after is None):continue
            # A Windows checkout can apply CRLF without an uncommitted source edit.
            if before is not None and after is not None and before.replace('\r\n','\n')==after.replace('\r\n','\n'):continue
            change=classify(file,before,after)
            if change['kind']=='housekeeping':continue
            result['working'].append({'file':file,**change})
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as exc:
        result['error']='History extraction unavailable: '+str(exc)[:500]
    return result


def history_diff(workspace, history, day, file):
    event=next((d for d in history.get('daily',[]) if d['id']==day),None)
    change=next((c for c in event['files'] if c['file']==file),None) if event else None
    if not change or not in_scope(file):raise PermissionError('Not a mapped history change')
    ids=[change['before'],change['after']]
    if not all(re.fullmatch(r'[a-f0-9]{40,64}',s) for s in ids):raise ValueError('Invalid history object')
    top,_,_=git_scope(workspace);blobs=read_blobs(top,ids)
    import difflib
    diff=''.join(difflib.unified_diff((blobs[ids[0]] or '').splitlines(True),(blobs[ids[1]] or '').splitlines(True),
                                    fromfile='before/'+file,tofile='after/'+file,n=3))
    return {'file':file,'date':day,'text':diff[:100_000],'truncated':len(diff)>100_000,
            'note':'Net source diff for this Git day, not a runtime trace or a record of intent.'}


def source_tree(root):
    """Walk source with excluded directory names pruned before descent."""
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if n not in SKIP and not n.startswith('.')
                   and not (Path(current) / n).is_symlink()]
        for name in files:
            yield Path(current) / name
