# Last updated: 2026-07-19 12:25:39
import sys, os
sys.path.insert(0, 'nova_body')
from nova_lancedb import NovaMemoryStore

db = NovaMemoryStore()

q1 = db.search_text('memory redesign self-maintenance', top_k=5)
print(f'Query: "memory redesign self-maintenance" — {len(q1)} results\n')
for i, r in enumerate(q1):
    print(f'  {i}: d={r["_distance"]:.3f} cat={r["category"]}: {r["content"][:90]}...')

print()
q2 = db.search_text('self-maintenance not work label', top_k=5)
print(f'Query: "self-maintenance not work label" — {len(q2)} results\n')
for i, r in enumerate(q2):
    print(f'  {i}: d={r["_distance"]:.3f} cat={r["category"]}: {r["content"][:90]}...')

print()
# Now check: are the two queries returning the SAME entries? (dedup check)
s1 = set(r['id'] for r in q1)
s2 = set(r['id'] for r in q2)
overlap = s1 & s2
print(f'Overlap between the two queries: {len(overlap)} out of {len(s1)} + {len(s2)} entries')
if overlap:
    print('SAME entries surfacing for different queries — that is semantic, not a hash collision.')
else:
    print('No overlap — each query found genuinely different memories. Good: the vector space has structure.')
