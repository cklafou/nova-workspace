# Last updated: 2026-10-01 06:38:29
import json
lines = [l for l in open('logs/tool_calls.jsonl') if '10:' in l]
times = [json.loads(l)['ts'] for l in lines]
print(f'{len(lines)} calls, {times[0]} to {times[-1]}')
