import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
from nova_lancedb.embedder import embed_text, content_hash
import uuid, time
s = NovaMemoryStore()
s._text_tbl.delete("source = 'debug'")
old_ts = 1783200000
old_content = "I decided I want to stop narrating progress I haven't made yet"
new_content = "I'm going to stop narrating progress I haven't made yet — not a promise, a decision"
old_vec = embed_text(old_content)
old_chash = content_hash(old_content)
new_chash = content_hash(new_content)
print(f"old hash: {old_chash}")
print(f"new hash: {new_chash}")
print(f"hashes match: {old_chash == new_chash}")
row = {"id":str(uuid.uuid4()),"content":old_content,"vector":old_vec,"category":"general","source":"debug","session_id":"deduptest","author":"Nova","content_hash":old_chash,"timestamp":old_ts}
s._text_tbl.add([row])
print(f"Known hashes before add_text: {s._known_hashes}")
result = s.add_text(new_content, author="Nova", source="debug")
print(f"add_text returned: {result}")
all_rows = s._text_tbl.to_pandas()
for r in all_rows.itertuples():
    print(f"  ts={r.timestamp:.0f} hash={r.content_hash[:12]} content={r.content[:60]}")
