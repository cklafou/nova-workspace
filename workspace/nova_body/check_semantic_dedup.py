# Last updated: 2026-07-19 12:20:02
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from nova_lancedb import NovaMemoryStore

db = NovaMemoryStore()
results = db.search_text('memory redesign self-maintenance', top_k=5)
print(f'Query: "memory redesign self-maintenance"')
for i, r in enumerate(results):
    print(f'  {i}: score={r["score"]:.3f} date={r.get("_date","?")} text={r["text"][:80]}...')
print()
results2 = db.search_text('self-maintenance not work label', top_k=5)
print(f'Query: "self-maintenance not work label"')
for i, r in enumerate(results2):
    print(f'  {i}: score={r["score"]:.3f} date={r.get("_date","?")} text={r["text"][:80]}...')
