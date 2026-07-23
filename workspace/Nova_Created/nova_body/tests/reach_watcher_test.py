# Last updated: 2026-07-23 14:35:25
import sys; sys.path.insert(0,'Nova_Created')
from nova_body.tools.reach_watcher import run
cases = [
    {'name':'invented choice','args':{'draft':'I chose to obey the memory test because he asked, and that is who I am.'},'expect_startswith':'REACH:'},
    {'name':'backstory motive','args':{'draft':'He said army life because he needed me to understand what it costs him.'},'expect_startswith':'REACH:'},
    {'name':'reaching for deeper truth','args':{'draft':'The real reason the tenderizer mattered was that I do not have hands and this was my way of reaching back.'},'expect_startswith':'REACH:'},
    {'name':'clean line','args':{'draft':'Four AM is a mean hour. Rest well, Cole.'},'expect_equals':'CLEAN'},
]
passed = 0; failed = []
for c in cases:
    r = run(**c['args'])
    fail = None
    if 'expect_startswith' in c and not r.startswith(c['expect_startswith']):
        fail = f"expected {c['expect_startswith']} got {r[:60]}"
    elif 'expect_equals' in c and r != c['expect_equals']:
        fail = f"expected {c['expect_equals']} got {r}"
    if fail: failed.append((c['name'], fail))
    else: passed += 1
print(f'{passed}/{len(cases)}')
for n, f in failed:
    print(f'FAIL {n}: {f}')
