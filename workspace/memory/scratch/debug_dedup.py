# Last updated: 2026-07-19 13:01:53
import sys; sys.path.insert(0, 'nova_body')
from nova_lancedb.hippocampus import NovaMemoryStore
s = NovaMemoryStore()
s._text_tbl.delete("source = 'test'")
import uuid
from nova_lancedb.embedder import embed_text, content_hash
old = "I decided I want to stop narrating progress I haven't made yet"
row = {'id':str(uuid.uuid4()),'content':old,'vector':embed_text(old),'category':'general',
       'source':'test','session_id':'t','author':'Nova','content_hash':content_hash(old),'timestamp':1783200000}
s._text_tbl.add([row])
new = "Going to stop narrating progress I haven't made yet"
result = s.add_text(new, author='Nova', source='test')
print('add_text returned:', result)
remaining = s._text_tbl.to_pandas()[s._text_tbl.to_pandas()['source']=='test']
print(f'rows: {len(remaining)}')
for r in remaining.iterrows():
    print(f"  ts={r[1]['timestamp']:.0f} text={r[1]['content'][:80]}")
