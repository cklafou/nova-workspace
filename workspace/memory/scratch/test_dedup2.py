# Last updated: 2026-07-19 14:49:30
# Same-hour test: two close-but-separate moments should BOTH survive
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
# Two things I'd say in one hour that are similar but not the same thought
a = s.add_text("Found a bug in the dedup code, going to fix it", author="Nova", source="test")
b = s.add_text("Fixing the dedup bug now, found where the old version wins", author="Nova", source="test")
print(f"First stored: {a}, second stored: {b} (want both True — separate moments)")
remaining = s._text_tbl.to_pandas()
test_rows = remaining[remaining['source']=='test']
print(f"Test rows: {len(test_rows)}")
for r in test_rows.iterrows(): print(f"  text={r[1]['content'][:80]}")