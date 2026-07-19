# Last updated: 2026-07-19 14:13:51
import sys, os, json
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
table_names = store.table_names()
print('tables:', table_names)
for t in table_names:
    tbl = store.open_table(t)
    count = len(tbl)
    # grab the latest modified_time if the column exists
    has_mod = 'modified_time' in [c['name'] for c in tbl.schema]
    print(f'{t}: rows={count}, has_modified_time={has_mod}')
