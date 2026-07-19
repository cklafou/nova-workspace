# Last updated: 2026-07-19 12:36:02
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
a = s.add_text("I'm proud of the memory fix, it feels good", author="Nova", source="test")
b = s.add_text("I feel good about the memory fix, genuinely proud of it", author="Nova", source="test")
print(f"First stored: {a}, second stored: {b} (want False)")
r = s.search_text("memory fix proud", top_k=2)
for h in r: print(f"  dist={h.get('_distance','?'):.4f} ts={h['timestamp']:.0f}")
