# Last updated: 2026-10-04 14:28:11
"""Task acceptance checks are execution evidence, separate from a model's DONE text."""
import hashlib
from pathlib import Path
from nova_paths import workspace_path, WORKSPACE_ROOT
from nova_runtime.operations import run_process


def validate_checks(checks):
    if not isinstance(checks,list) or len(checks)>20:
        raise ValueError('acceptance must be a list of up to 20 checks')
    for check in checks:
        if not isinstance(check,dict) or check.get('kind') not in {'command','file'}:
            raise ValueError('each acceptance check needs kind command or file')
        if check['kind']=='command':
            argv=check.get('argv')
            if not isinstance(argv,list) or not argv or not all(isinstance(a,str) for a in argv):
                raise ValueError('command acceptance needs an argv list, not shell text')
        elif not isinstance(check.get('path'),str):
            raise ValueError('file acceptance needs a path')
    return checks


def verify(checks, base=None):
    validate_checks(checks)
    if not checks:
        return {'ok':False,'state':'needs_review','checks':[],
                'reason':'No acceptance checks were specified; completion needs human review.'}
    results=[]
    def resolve(path):
        p=Path(path)
        return (Path(base)/p).resolve() if base is not None and not p.is_absolute() else workspace_path(p)
    for check in checks:
        try:
            if check['kind']=='command':
                r=run_process(check['argv'],cwd=resolve(check.get('cwd','')),
                              timeout=min(120,max(1,float(check.get('timeout',30)))))
                ok=(r['status'] in {'succeeded','failed'} and r['exit_code']==check.get('expect_exit',0)
                    and check.get('stdout_contains','') in r['stdout'])
                results.append({'ok':ok,**r,'stdout':r['stdout'][:4000],'stderr':r['stderr'][:4000]})
            else:
                p=resolve(check['path']).resolve()
                sealed=(WORKSPACE_ROOT/'models').resolve()
                if p==sealed or sealed in p.parents: raise ValueError('models/ is sealed')
                data=p.read_bytes()
                ok=(len(data)>=int(check.get('min_bytes',1)))
                if 'sha256' in check: ok=ok and hashlib.sha256(data).hexdigest()==check['sha256']
                if 'contains' in check: ok=ok and check['contains'] in data.decode('utf-8')
                results.append({'ok':ok,'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        except Exception as e:
            results.append({'ok':False,'error':str(e)})
    ok=all(r['ok'] for r in results)
    return {'ok':ok,'state':'passed' if ok else 'failed','checks':results}
