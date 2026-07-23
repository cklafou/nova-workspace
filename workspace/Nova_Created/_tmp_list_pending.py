# Last updated: 2026-07-23 16:54:17
import json
q = json.load(open('memory/audit_queue.json'))
pending = [i for i in q['items'] if i['status'] == 'pending']
from collections import Counter
types = Counter(i['event_type'] for i in pending)
print(f"By type: {dict(types)}")
for i in pending:
    path = i.get('old_path') or i.get('new_path', '?')
    print(f"{i['event_type']:5s} {path}")
