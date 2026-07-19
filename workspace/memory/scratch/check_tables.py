# Last updated: 2026-07-19 14:14:26
import sys, os, json
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_store
store = get_store()
s = store.get_stats()
print('get_stats keys:', list(s.keys()))
for k, v in s.items():
    print(f'  {k}: {v}')
