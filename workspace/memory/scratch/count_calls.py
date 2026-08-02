# Last updated: 2026-08-02 23:08:32
import json
lines = [l for l in open('logs/tool_calls.jsonl') if '10:' in l]
times = [json.loads(l)['ts'] for l in lines]
print(f'{len(lines)} calls, {times[0]} to {times[-1]}')
