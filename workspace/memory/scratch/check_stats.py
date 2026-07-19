# Last updated: 2026-07-19 15:14:33
import sys, os, json
sys.path.insert(0, 'nova_body')
from nova_lancedb import get_stats
s = get_stats()
for k in ['text_last_write', 'visual_last_write']:
    v = s.get(k)
    print(f'{k}: {v}  (present={v is not None})')
print('all keys:', list(s.keys()))
