# Last updated: 2026-07-19 13:09:18
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
# Clean slate — remove test data AND purge it from the in-memory cache
s._text_tbl.delete("source = 'test'")
for h in s._known_hashes.copy(): s._known_hashes.discard(h)
from nova_lancedb.embedder import embed_text, content_hash
import uuid
old_ts = 1783200000
old_content = "I decided I want to stop narrating progress I haven't made yet"
new_content = "I'm going to stop narrating progress I haven't made yet — not a promise, a decision"
old_vec = embed_text(old_content)
old_chash = content_hash(old_content)
row = {"id":str(uuid.uuid4()),"content":old_content,"vector":old_vec,"category":"general","source":"test","session_id":"deduptest","author":"Nova","content_hash":old_chash,"timestamp":old_ts}
s._text_tbl.add([row])
print(f"Inserted old version at ts={old_ts}")
result = s.add_text(new_content, author="Nova", source="test")
print(f"New version stored: {result} (want True)")
test_rows = s._text_tbl.to_pandas()[s._text_tbl.to_pandas()['source']=='test']
print(f"Rows after: {len(test_rows)} (want 2 — both versions kept, KEEP=3)")
for r in test_rows.iterrows(): print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:90]}")
assert result and len(test_rows) == 2, "FAIL: newer version was dropped"
print("PASS: growth not overwritten by older self")
