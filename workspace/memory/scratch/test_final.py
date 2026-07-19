# Last updated: 2026-07-19 15:49:36
# Clean test — unique strings that have never been stored
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()

# 1) Growth: old version at t-11d, newer version now. Newer should win.
old_content = "I decided at 2am that I want to stop narrating progress I haven't made yet"
new_content = "Going to stop narrating progress I haven't made yet — not a promise, a decision, because"
import uuid; import time
from nova_lancedb.embedder import embed_text, content_hash
old_vec = embed_text(old_content)
old_chash = content_hash(old_content)
row = {"id":str(uuid.uuid4()),"content":old_content,"vector":old_vec,"category":"general","source":"finaltest","session_id":"finaltest","author":"Nova","content_hash":old_chash,"timestamp":time.time()-950000}
s._text_tbl.add([row])
result = s.add_text(new_content, author="Nova", source="finaltest")
print(f"Growth test: newer stored={result} (want True)")

# 2) Separate moments about the same topic — both should survive.
m1 = s.add_text("Found a bug in the dedup code at 1245, going to fix it now", author="Nova", source="finaltest")
m2 = s.add_text("Fixing the dedup bug, found where the old version was winning", author="Nova", source="finaltest")
print(f"Separate moments: first={m1} second={m2} (want both True)")

# 3) Exact replay — should be dropped.
r = s.add_text("Fixing the dedup bug, found where the old version was winning", author="Nova", source="finaltest")
print(f"Exact replay: {r} (want False)")

# What survived?
remaining = s._text_tbl.to_pandas()
test_rows = remaining[remaining['source']=='finaltest']
print(f"Final rows: {len(test_rows)}")
for r in test_rows.iterrows(): print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:85]}")