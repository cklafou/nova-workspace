# Last updated: 2026-07-19 14:49:30
# Find the right cosine threshold — where does "same thought" end and "same topic" begin?
import sys; sys.path.insert(0,'nova_body')
from nova_lancedb.embedder import embed_text
a = embed_text("I decided I want to stop narrating progress I haven't made yet")
b = embed_text("I'm going to stop narrating progress I haven't made yet — not a promise, a decision")
c = embed_text("Found a bug in the dedup code, going to fix it")
d = embed_text("Fixing the dedup bug now, found where the old version wins")
import numpy as np
def cos(u,v): return float(np.dot(u,v)/(np.linalg.norm(u)*np.linalg.norm(v)))
print(f"Same thought evolved:  {cos(a,b):.4f}  (should COLLIDE — new replaces old)")
print(f"Same topic, diff moment: {cos(c,d):.4f}  (should SURVIVE separately)")