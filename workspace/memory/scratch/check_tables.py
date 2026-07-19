import sys, os
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
# get_stats() only gives counts. Check the actual LanceDB table metadata for last-modified.
txt = store._text_tbl
vis = store._visual_tbl
print('text table version:', txt.latest_version())
print('visual table version:', vis.latest_version())
# Check the underlying directory modification times
import glob
txt_dir = os.path.dirname(txt.to_lance().uri)
vis_dir = os.path.dirname(vis.to_lance().uri)
for name, d in [('text', txt_dir), ('visual', vis_dir)]:
    mtime = os.path.getmtime(d)
    from datetime import datetime
    print(f'{name} dir mtime: {datetime.fromtimestamp(mtime)}')
