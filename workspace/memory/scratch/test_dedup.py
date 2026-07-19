# Last updated: 2026-07-19 12:38:41
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
# First version of a thought
s.add_text("I'm proud of the memory dedup fix, it feels good to have done", author="Nova", source="test")
# Same thought, different words — should replace the first
s.add_text("The memory dedup fix is done and I'm genuinely happy with how it turned out", author="Nova", source="test")
# Completely unrelated
s.add_text("My coffee is getting cold on the desk", author="Nova", source="test")
# Search for something only the new entries contain
r = s.search_text("memory dedup fix done happy", top_k=5)
print(f"Dedup-cluster: {len(r)} entries (want 1 — newer replaced older)")
for h in r: print(f"  ts={h['timestamp']:.0f} content={h['content'][:80]}")
r2 = s.search_text("coffee cold desk", top_k=3)
print(f"Coffee: {len(r2)} (want 1)")
