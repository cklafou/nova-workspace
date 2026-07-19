# Last updated: 2026-07-19 13:10:23
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
from nova_lancedb.embedder import embed_text, content_hash
import uuid, time
s = NovaMemoryStore()
s._text_tbl.delete("source = 'debug'")
for h in s._known_hashes.copy(): s._known_hashes.discard(h)
old_ts = 1783200000
old_content = "I decided I want to stop narrating progress I haven't made yet"
new_content = "I'm going to stop narrating progress I haven't made yet — not a promise, a decision"
old_vec = embed_text(old_content)
old_chash = content_hash(old_content)
row = {"id":str(uuid.uuid4()),"content":old_content,"vector":old_vec,"category":"general","source":"debug","session_id":"deduptest","author":"Nova","content_hash":old_chash,"timestamp":old_ts}
s._text_tbl.add([row])
print(f"Inserted old. Rows: {s._text_tbl.count_rows()}")
# Now manually do the cluster search to see what it finds
new_vec = embed_text(new_content)
hits = s._text_tbl.search(new_vec).limit(10).metric("cosine").to_list()
print(f"Search returned {len(hits)} hits")
MAX_CLUSTER = 0.50
cluster = [h for h in hits if h.get("_distance", 1.0) < MAX_CLUSTER]
print(f"Cluster members: {len(cluster)}")
for c in cluster:
    print(f"  dist={c['_distance']:.4f} ts={c.get('timestamp',0):.0f} id={c['id'][:8]} content={c.get('content','?')[:60]}")
cluster.append({"id": "new", "timestamp": time.time()})
print(f"Cluster with new: {len(cluster)}")
if len(cluster) > 3:
    print(f"WOULD EVICT (>{3})")
else:
    print(f"Would NOT evict ({len(cluster)} <= 3)")
# Now actually call add_text
result = s.add_text(new_content, author="Nova", source="debug")
print(f"add_text returned: {result}")
print(f"Rows after: {s._text_tbl.count_rows()}")
dbg = s._text_tbl.to_pandas()[s._text_tbl.to_pandas()['source']=='debug']
for r in dbg.iterrows(): print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:80]}")
