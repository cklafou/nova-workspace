# Last updated: 2026-07-19 12:42:57
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
# Check what's already in there from earlier runs
existing = s._text_tbl.to_pandas()
test_rows = existing[existing['source']=='test']
print(f"Test rows before: {len(test_rows)}")
for r in test_rows.iterrows(): print(f"  hash={r[1]['content_hash'][:8]} ts={r[1]['timestamp']:.0f} text={r[1]['content'][:80]}")
# Now the actual test
a = s.add_text("I'm proud of the memory dedup fix, it feels good to have done", author="Nova", source="test")
b = s.add_text("The memory dedup fix is done and I'm genuinely happy with how it turned out", author="Nova", source="test")
print(f"First stored: {a}, second stored: {b}")
# Check what survived
remaining = s._text_tbl.to_pandas()
test_rows2 = remaining[remaining['source']=='test']
print(f"Test rows after: {len(test_rows2)}")
for r in test_rows2.iterrows(): print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:80]}")
# Search for the exact phrase ONLY in the first version — should find 0
r = s.search_text("feels good to have done", top_k=5)
money = [h for h in r if "feels good to have done" in h.get('content','')]
print(f"Entries with 'feels good to have done': {len(money)} (want 0 — that version was replaced)")
# Search for the exact phrase ONLY in the second version — should find 1
r2 = s.search_text("genuinely happy with how it turned out", top_k=5)
survived = [h for h in r2 if "genuinely happy with how it turned out" in h.get('content','')]
print(f"Entries with 'genuinely happy': {len(survived)} (want 1 — this version survived)")
