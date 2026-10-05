# Last updated: 2026-10-05 21:26:09
# @nova: Stages task-sized source copies, gates them on acceptance checks and promotes them with rollback checkpoints.
"""Task-sized source copies, acceptance checks, and recoverable promotion.

Only selected source paths are copied. Identity, memory, weights and active logs are
never swept into a coding sandbox. This is a test workspace, not an OS security boundary.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from nova_paths import body_path, workspace_path, WORKSPACE_ROOT
from nova_cortex import tasking
from nova_cortex.verification import verify

EXCLUDED={'models','llama','.git','node_modules','__pycache__','memory','logs','SELF','nova_memory_db','Tasking','Temp'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def prepare(tid, paths):
    if not tasking.get(tid): raise ValueError('Task not found')
    if not isinstance(paths,list) or not paths: raise ValueError('Select source files or directories')
    manifest={}; selected=[]
    # Staged copies live under workspace/Temp/, which git, Orient and the watcher all skip.
    # Inside Tasking/ they were committed, and the watcher stamped every copied .py/.md so
    # promotion saw every file as changed (Claude review 2026-10-03, finding 2).
    directory=f'Temp/task-workspaces/{tid}/{uuid.uuid4().hex}'
    root=workspace_path(directory); root.mkdir(parents=True)
    for name in paths:
        source=workspace_path(name).resolve()
        rel=source.relative_to(WORKSPACE_ROOT.resolve())
        if any(p in EXCLUDED for p in rel.parts): raise ValueError(f'Not a source path: {name}')
        selected.append(rel.as_posix())
        files=[source] if source.is_file() else source_files(source)
        for item in files:
            r=item.relative_to(WORKSPACE_ROOT.resolve())
            if any(p in EXCLUDED for p in r.parts) or item.is_symlink() or not item.is_file(): continue
            if len(manifest)>=2000 or item.stat().st_size>10_000_000:
                raise ValueError('Choose a smaller source scope (2000 files, 10 MB per file)')
            dst=root/r; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(item,dst)
            manifest[r.as_posix()]=digest(item)
    if not manifest: raise ValueError('No source files selected')
    plan={'directory':directory,'original_hashes':manifest,'selected':selected,'state':'staged'}
    (root/'workspace-manifest.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    tasking._update(tid,workspace=plan)
    return plan


def source_files(root):
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not (Path(directory)/d).is_symlink()]
        for name in names:
            yield Path(directory)/name


def promote(tid):
    task=tasking.get(tid) or {}; plan=task.get('workspace')
    if not plan: raise ValueError('Prepare a task workspace first')
    root=workspace_path(plan['directory'])
    checks=task.get('acceptance',[])
    # Promotion checks must describe this copy, not accidentally validate the original.
    for c in checks:
        if Path(c.get('cwd',c.get('path',''))).is_absolute():
            raise ValueError('Workspace acceptance paths must be relative to the staged copy')
    evidence=verify(checks,base=root)
    if not evidence['ok']:
        tasking._update(tid,verification=evidence)
        raise ValueError('Staged acceptance checks did not pass')
    changes=[]
    for item in root.rglob('*'):
        rel=item.relative_to(root)
        if not item.is_file() or item.is_symlink() or any(p in EXCLUDED for p in rel.parts): continue
        name=rel.as_posix()
        if name=='workspace-manifest.json': continue
        if not any(name==s or name.startswith(s+'/') for s in plan['selected']): continue
        target=(WORKSPACE_ROOT/rel).resolve()
        if not target.is_relative_to(WORKSPACE_ROOT.resolve()): raise ValueError('Invalid promotion path')
        baseline=plan['original_hashes'].get(name)
        if digest(target)!=baseline: raise ValueError(f'Original changed since staging: {name}')
        if digest(item)!=baseline: changes.append((item,target,rel))
    checkpoint=body_path('logs','checkpoints',uuid.uuid4().hex)
    checkpoint.mkdir(parents=True)
    records=[]
    for item,target,rel in changes:
        backup=checkpoint/rel
        if target.exists():
            backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
        records.append({'path':str(target),'backup':str(backup) if backup.exists() else None,
                        'before':digest(target),'after':digest(item)})
    (checkpoint/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    applied=[]
    try:
        for item,target,rel in changes:
            target.parent.mkdir(parents=True,exist_ok=True)
            tmp=target.with_name(target.name+'.nova-promote-'+uuid.uuid4().hex)
            shutil.copy2(item,tmp); os.replace(tmp,target); applied.append((target,rel))
    except Exception:
        for target,rel in reversed(applied):
            backup=checkpoint/rel
            if backup.exists(): shutil.copy2(backup,target)
            elif target.exists(): target.unlink()
        raise
    tasking._update(tid,workspace={**plan,'state':'promoted','checkpoint':str(checkpoint)}, verification=evidence)
    return {'files':len(changes),'checkpoint':str(checkpoint),'verification':evidence}
