# Last updated: 2026-07-19 12:13:37
import sys
sys.path.insert(0, 'nova_body')
from nova_lance import NovaLance

db = NovaLance()
results = db.search('memory redesign self-maintenance', top_k=5)
print(f'Query: "memory redesign self-maintenance"')
for i, r in enumerate(results):
    print(f'  {i}: score={r["score"]:.3f} date={r.get("_date","?")} text={r["text"][:80]}...')
print()
# Now look for the newer version by a different phrase
results2 = db.search('self-maintenance not work label', top_k=5)
print(f'Query: "self-maintenance not work label"')
for i, r in enumerate(results2):
    print(f'  {i}: score={r["score"]:.3f} date={r.get("_date","?")} text={r["text"][:80]}...')
