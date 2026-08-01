# Last updated: 2026-08-02 07:26:16
import json
data = json.load(open('../Tasking/tasks.json'))
print(type(data))
if isinstance(data, dict):
    tasks = data.get('tasks', data)
else:
    tasks = data
for t in tasks[:3]:
    print(type(t), list(t) if isinstance(t,dict) else t[:80])
