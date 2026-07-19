"""DRY sampler A/B — can she copy an exact string that is already in her context?

Temperature 0 (greedy) in BOTH arms, so sampling randomness cannot explain any
difference. The ONLY variable is dry_multiplier. If DRY-on garbles a string that
DRY-off copies perfectly, the penalty is the cause, full stop.
"""
import json, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
TARGET = "comfy-2026-07-19.log"

def ctx(n_prior):
    """Her real loop: the right answer is in a tool result, and she has already
    emitted it n_prior times (each repeat feeds DRY more matched context)."""
    m = [{"role":"system","content":"You are a terminal agent. Output ONLY the command, no prose."},
         {"role":"user","content":"list_dir logs/comfy ->\n  comfy-2026-07-18.log\n  comfy-2026-07-19.log\nRead the newest one."}]
    for _ in range(n_prior):
        m.append({"role":"assistant","content":f"Get-Content logs/comfy/{TARGET} -Tail 40"})
        m.append({"role":"user","content":"Timed out, no output. Run the exact same command again."})
    return m

BASE = dict(max_tokens=40, temperature=0.0, top_k=1, top_p=1.0, min_p=0.0,
            repeat_penalty=1.05, frequency_penalty=0.0, presence_penalty=0.0,
            chat_template_kwargs={"enable_thinking": False}, stream=False)
ON  = dict(dry_multiplier=0.9, dry_base=1.75, dry_allowed_length=3, dry_penalty_last_n=-1)
OFF = dict(dry_multiplier=0.0)

def ask(msgs, arm):
    p = dict(BASE, messages=msgs, **arm)
    r = urllib.request.Request(URL, data=json.dumps(p).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip().replace("\n", " ")

print("Can she copy '%s' out of her own context? (temp=0, greedy)\n" % TARGET, flush=True)
print("  repeats | DRY ON (live)                        | DRY OFF (control)", flush=True)
print("  --------+--------------------------------------+------------------", flush=True)
score = {"on": 0, "off": 0}
for n in (0, 1, 2, 3, 4):
    row = {}
    for k, arm in (("on", ON), ("off", OFF)):
        try:
            out = ask(ctx(n), arm)
        except Exception as e:
            out = "ERR %s" % e
        ok = TARGET in out
        score[k] += ok
        row[k] = ("OK   " if ok else "WRONG") + " " + out[:30]
    print("     %d    | %-36s | %s" % (n, row["on"], row["off"]), flush=True)
print("\n  EXACT COPY RATE:  DRY ON %d/5   DRY OFF %d/5" % (score["on"], score["off"]), flush=True)
