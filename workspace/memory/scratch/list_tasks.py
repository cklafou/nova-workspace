# Last updated: 2026-07-21 17:36:37
import json
with open('Tasking/tasks.json') as f:
    t = json.load(f)
for k, v in t['tasks'].items():
    title = v.get('title', '(untitled)')
    print(f'{k} [{v["status"]}] {title}')
