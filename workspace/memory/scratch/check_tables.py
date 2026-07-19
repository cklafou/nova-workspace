# Last updated: 2026-07-19 14:15:15
import sys, os
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
txt = store._text_tbl
vis = store._visual_tbl
for name, tbl in [('text', txt), ('visual', vis)]:
    versions = list(tbl.list_versions())
    latest = versions[0] if versions else None
    from datetime import datetime
    print(f'{name}: {len(versions)} versions, latest version={latest.version if latest else "none"}')
    # Check the underlying directory modification times
    d = os.path.dirname(tbl.to_lance().uri)
    mtime = os.path.getmtime(d)
    print(f'  dir mtime: {datetime.fromtimestamp(mtime)}')
