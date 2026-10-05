# Last updated: 2026-10-05 18:23:37
"""Recover searchable coverage from intact local records; never rewrite originals."""
import gzip
import hashlib
import json
from datetime import datetime
from nova_paths import body_path
from nova_runtime.work_queue import WorkQueue


def enqueue_records(queue=None):
    queue=queue or WorkQueue('memory')
    count=0; errors=[]
    sessions=body_path('logs','chat_sessions')
    files=list(sessions.rglob('*_chat.jsonl'))+list(sessions.rglob('*_chat.jsonl.gz'))
    for p in files:
        try:
            opener=gzip.open if p.suffix=='.gz' else open
            with opener(p,'rt',encoding='utf-8') as f:
                for number,line in enumerate(f,1):
                    if not line.strip(): continue
                    try:
                        row=json.loads(line)
                        text=row.get('content','')
                        if not isinstance(text,str) or not text.strip(): continue
                        ts=row.get('timestamp')
                        stamp=datetime.fromisoformat(ts).timestamp() if isinstance(ts,str) else float(ts or p.stat().st_mtime)
                        payload={'type':'text','content':text,'author':row.get('author','recorded speaker'),
                                 'source':'archive:chat','session_id':p.name.split('_chat')[0], 'timestamp':stamp}
                    except (ValueError,TypeError,AttributeError) as e:
                        errors.append({'file':str(p),'line':number,'error':str(e)})
                        continue  # A damaged row must not hide the rest of the archive.
                    queue.put(payload,key='backfill:'+hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()); count+=1
        except Exception as e:
            errors.append({'file':str(p),'error':str(e)})
    journal=body_path('memory','JOURNAL.md')
    if journal.exists():
        text=journal.read_text(encoding='utf-8')
        for i in range(0,len(text),2000):
            chunk=text[i:i+2000]
            payload={'type':'text','content':'[Archived journal excerpt; file modification time is not the event date]\n'+chunk,
                     'author':'Nova (journal archive)','source':'archive:journal','session_id':'',
                     'timestamp':journal.stat().st_mtime}
            queue.put(payload,key='journal:'+hashlib.sha256(chunk.encode()).hexdigest()); count+=1
    return {'records_considered':count,'errors':errors,'queue':queue.snapshot()}


if __name__=='__main__':
    print(json.dumps(enqueue_records(),indent=2))
