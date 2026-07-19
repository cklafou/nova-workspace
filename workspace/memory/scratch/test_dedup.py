# Last updated: 2026-07-19 12:36:36
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
a = s.add_text("I'm proud of the memory fix today, it actually works and feels good", author="Nova", source="test")
b = s.add_text("The memory dedup fix is done and I'm genuinely happy with how it turned out", author="Nova", source="test")
print(f"First stored: {a}, second stored: {b} (want False — semantic dup)")
r = s.search_text("memory fix proud happy", top_k=3)
for h in r: print(f"  dist={h.get('_distance','?'):.4f} ts={h['timestamp']:.0f} content={h['content'][:70]}")
