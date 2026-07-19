# Last updated: 2026-07-19 12:35:24
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
s.add_text("I'm proud of the memory fix, it feels good", author="Nova", source="test")
s.add_text("I feel good about the memory fix, genuinely proud of it", author="Nova", source="test")
r = s.search_text("memory fix proud", top_k=5)
print(f"Entries after 2 near-duplicates: {len(r)} (expect 1)")
for h in r: print(f"  ts={h['timestamp']:.0f} content={h['content'][:80]}")
s.add_text("Completely unrelated thought about coffee", author="Nova", source="test")
r2 = s.search_text("coffee", top_k=3)
print(f"Coffee entries: {len(r2)} (expect 1)")
