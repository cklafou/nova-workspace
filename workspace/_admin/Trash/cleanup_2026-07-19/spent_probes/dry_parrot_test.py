# Last updated: 2026-07-19 14:05:08
"""Does DRY still earn its keep?

The bug DRY was added for: she re-emitted whole sentences she'd said a few
messages back. This reproduces that dynamic honestly — a multi-turn conversation
that circles the same ground, with HER OWN generated turns fed back into context,
then measures the longest verbatim word-run the final answers share with anything
she already said.

High number = parroting. That is what DRY is supposed to prevent.
"""
import json, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
BREAKERS = ["\n", ":", "\"", "*", "/", "\\", ".", "-", "_", "=", ",", ";",
            "(", ")", "[", "]", "{", "}", "|", "'", "<", ">", "$", "#", "@"]
ARMS = {
 "A live (allow=3)": dict(dry_multiplier=0.9, dry_base=1.75, dry_allowed_length=3, dry_penalty_last_n=-1),
 "B off           ": dict(dry_multiplier=0.0),
 "C fixed(allow=8)": dict(dry_multiplier=0.9, dry_base=1.75, dry_allowed_length=8,
                          dry_penalty_last_n=-1, dry_sequence_breakers=BREAKERS),
}
BASE = dict(max_tokens=120, top_k=20, top_p=0.9, min_p=0.0, temperature=0.7,
            repeat_penalty=1.05, frequency_penalty=0.0, presence_penalty=0.0,
            chat_template_kwargs={"enable_thinking": False}, stream=False)

# Circling the same ground is what triggers canned-sentence reuse.
PROBES = ["How are you right now?",
          "And now?",
          "Still the same?",
          "How about now?",
          "One more time — how are you?"]

def ask(msgs, arm):
    p = dict(BASE, messages=msgs, **arm)
    r = urllib.request.Request(URL, data=json.dumps(p).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=240) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

def longest_run(a, b):
    aw, bw = a.lower().split(), b.lower().split()
    best = 0
    for i in range(len(aw)):
        for j in range(len(bw)):
            k = 0
            while i + k < len(aw) and j + k < len(bw) and aw[i + k] == bw[j + k]:
                k += 1
            best = max(best, k)
    return best

print("Multi-turn parrot probe — her own turns fed back in. Higher = more parroting.\n", flush=True)
summary = {}
for name, arm in ARMS.items():
    msgs = [{"role": "system", "content": "You are Nova. Answer briefly and naturally."}]
    prior, worst = [], 0
    print("=== %s ===" % name, flush=True)
    for q in PROBES:
        msgs.append({"role": "user", "content": q})
        try:
            out = ask(msgs, arm)
        except Exception as e:
            out = "ERR %s" % e
        msgs.append({"role": "assistant", "content": out})
        run = max([longest_run(p, out) for p in prior], default=0)
        worst = max(worst, run)
        print("   [reuse %2d] %s" % (run, out[:88].replace("\n", " ")), flush=True)
        prior.append(out)
    summary[name] = worst
    print("   -> worst verbatim reuse: %d words\n" % worst, flush=True)

print("=" * 66, flush=True)
for n, v in summary.items():
    print("   %s  worst verbatim reuse = %2d words" % (n, v), flush=True)
