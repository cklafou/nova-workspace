# Last updated: 2026-07-19 15:39:55
import sys, os
sys.path.insert(0, 'nova_body')
from nova_lancedb import NovaMemoryStore

db = NovaMemoryStore()
results = db.search_text('retention test planted tonight for tomorrow morning', top_k=3)
for r in results:
    print(f'[{r["author"]}] {r["content"][:200]}')
    print(f'  -> distance={r["_distance"]:.4f}')
print(f'\nFound {len(results)} hits')
