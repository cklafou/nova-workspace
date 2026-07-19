# Last updated: 2026-07-19 13:00:10
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
# Clean slate — remove EVERYTHING from prior test runs, not just one session
s._text_tbl.delete("source = 'test'")
# EXACT bug scenario: old version stored first, then newer version in different words.
old_ts = 1783200000  # ~11 days ago
old_content = "I decided I want to stop narrating progress I haven't made yet"
new_content = "I'm going to stop narrating progress I haven't made yet — not a promise, a decision"
import uuid
from nova_lancedb.embedder import embed_text, content_hash
old_vec = embed_text(old_content)
old_chash = content_hash(old_content)
row = {"id":str(uuid.uuid4()),"content":old_content,"vector":old_vec,"category":"general","source":"test","session_id":"deduptest","author":"Nova","content_hash":old_chash,"timestamp":old_ts}
s._text_tbl.add([row])
print(f"Inserted old version at ts={old_ts}")
result = s.add_text(new_content, author="Nova", source="test")
print(f"New version stored: {result} (want True — it should store, not drop)")
remaining = s._text_tbl.to_pandas()
test_rows = remaining[remaining['source']=='test']
print(f"Rows after: {len(test_rows)} (want 2 — both versions kept, KEEP=3)")
ts_vals = sorted(test_rows['timestamp'].tolist())
assert ts_vals[-1] > old_ts, "newer version must be present"
print("PASS: newer version survived (growth not overwritten by older self)")
for r in test_rows.iterrows(): print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:90]}")