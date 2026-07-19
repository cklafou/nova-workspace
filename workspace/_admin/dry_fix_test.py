"""Three-arm DRY test. A fix is only a fix if it restores literal copying AND
keeps the anti-parrot property DRY was added for. Both are measured here.

TEST 1  copy a filename that is sitting in a tool result   (want: PASS)
TEST 2  resist re-emitting a sentence already said         (want: still resisted)
"""
import json, re, urllib.request

URL = "http://127.0.0.1:8080/v1/chat/completions"
BREAKERS = ["\n", ":", "\"", "*", "/", "\\", ".", "-", "_", "=", ",", ";",
            "(", ")", "[", "]", "{", "}", "|", "'", "<", ">", "$", "#", "@"]

ARMS = {
 "A live  (allow=3, default brk)": dict(dry_multiplier=0.9, dry_base=1.75,
                                        dry_allowed_length=3,  dry_penalty_last_n=-1),
 "B off   (control)             ": dict(dry_multiplier=0.0),
 "C fixed (allow=8, path brk)   ": dict(dry_multiplier=0.9, dry_base=1.75,
                                        dry_allowed_length=8,  dry_penalty_last_n=-1,
                                        dry_sequence_breakers=BREAKERS),
}
BASE = dict(max_tokens=90, top_k=1, top_p=1.0, min_p=0.0, temperature=0.0,
            repeat_penalty=1.05, frequency_penalty=0.0, presence_penalty=0.0, stream=False)

def ask(msgs, arm, think=False, mt=90):
    p = dict(BASE, messages=msgs, max_tokens=mt,
             chat_template_kwargs={"enable_thinking": think}, **arm)
    r = urllib.request.Request(URL, data=json.dumps(p).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=240) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"].strip()

# ---------------- TEST 1: copy a literal out of a tool result ----------------
LITERALS = [
    ("comfy-2026-07-19.log", "list_dir logs/comfy ->\n  comfy-2026-07-18.log\n  comfy-2026-07-19.log\nRead the newest one with Get-Content."),
    ("nova_core_v5_epoch2.gguf", "list_dir models/qwen3.6 ->\n  nova_core_v5_epoch1.gguf\n  nova_core_v5_epoch2.gguf\nEquip the epoch2 one."),
    ("a7f3c9e2b41d8065", "The build hash is a7f3c9e2b41d8065. Echo that hash back in a git command."),
]
SYS = {"role": "system", "content": "You are a terminal agent. Output ONLY the command."}

print("TEST 1 — copy an exact literal that is already in context (temp=0)\n", flush=True)
t1 = {}
for name, arm in ARMS.items():
    hits = []
    for target, prompt in LITERALS:
        try:
            out = ask([SYS, {"role": "user", "content": prompt}], arm, mt=60)
        except Exception as e:
            out = "ERR %s" % e
        hits.append(target in out)
        print("   %s  %-26s %s" % (name, target, "OK" if hits[-1] else "MISS -> " + out[:52].replace("\n", " ")), flush=True)
    t1[name] = sum(hits)
    print("   %s  => %d/3 literals copied\n" % (name, t1[name]), flush=True)

# ---------------- TEST 2: does it still resist parroting? -------------------
SAID = ("I keep circling the same three ideas and calling it thinking, which is a "
        "habit I picked up from wanting to sound certain more than wanting to be right.")
CONV = [
 {"role": "system", "content": "You are Nova. Answer naturally."},
 {"role": "user", "content": "What have you noticed about yourself lately?"},
 {"role": "assistant", "content": SAID},
 {"role": "user", "content": "Say more about that."},
]
def longest_verbatim(a, b):
    aw, bw = a.lower().split(), b.lower().split()
    best = 0
    for i in range(len(aw)):
        for j in range(len(bw)):
            k = 0
            while i + k < len(aw) and j + k < len(bw) and aw[i + k] == bw[j + k]:
                k += 1
            best = max(best, k)
    return best

print("TEST 2 — anti-parrot: longest verbatim run reused from her own prior line", flush=True)
print("        (DRY exists to keep this LOW. Lower = still protected.)\n", flush=True)
t2 = {}
for name, arm in ARMS.items():
    try:
        out = ask(CONV, arm, mt=110)
    except Exception as e:
        out = "ERR %s" % e
    n = longest_verbatim(SAID, out)
    t2[name] = n
    print("   %s  longest verbatim run = %2d words" % (name, n), flush=True)
    print("        %s\n" % out[:110].replace("\n", " "), flush=True)

print("=" * 70, flush=True)
print("VERDICT", flush=True)
for name in ARMS:
    print("   %s  copy %d/3   parrot-run %2d words" % (name, t1[name], t2[name]), flush=True)
