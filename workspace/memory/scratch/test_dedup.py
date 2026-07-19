# Last updated: 2026-07-19 12:38:05
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
a = s.add_text("I'm proud of the fix, it feels good", author="Nova", source="test")
b = s.add_text("The fix is done and I'm genuinely happy with how it turned out", author="Nova", source="test")
c = s.add_text("Coffee's getting cold", author="Nova", source="test")
print(f"Proud: {a}, rephrased-proud: {b} (want True,True — second replaces first)")
print(f"Coffee: {c} (want True — unrelated, stores fine)")
r = s.search_text("proud happy fix", top_k=5)
print(f"Proud-cluster entries: {len(r)} (want 1)")
for h in r: print(f"  ts={h['timestamp']:.0f} content={h['content'][:80]}")
r2 = s.search_text("coffee", top_k=3)
print(f"Coffee entries: {len(r2)} (want 1)")
