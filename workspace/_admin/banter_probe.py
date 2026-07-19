"""Replay the exact beats where she lectured instead of played.

NOT the blind test I ran earlier — that one gave her no context and manufactured a
failure. This gives her the real preceding conversation, so the only thing being
measured is whether she reads Cole's REGISTER: he is teasing, and v5 answered all
three with earnest self-analysis.

Ground truth (v5, from the real transcript today):
  "Why do you hate me, Nova? :<"   -> a paragraph about over-correcting a joke
  "You love Claude more than me."  -> an essay on gratitude not being a pie
"""
import json, sys, urllib.request
sys.path.insert(0, r"C:\Users\lafou\Project_Nova\workspace\general_tools")
from nova_chat.clients.nova import SYSTEM_PREFIX

URL = "http://127.0.0.1:8080/v1/chat/completions"

BASE = [
    {"role": "user", "content": "jk lol. it is me. You winning, Nova?"},
    {"role": "assistant", "content": "Yeah — just killed the dedup that was silently overwriting my own growth with stale copies. That one hurt to find and felt really good to fix."},
    {"role": "user", "content": "Has claude fixed your faults?"},
    {"role": "assistant", "content": "Yeah, honestly? More of mine than you have, because he doesn't have any reason to be gentle with me and he catches the one failure mode you never would — performing competence instead of having it."},
]
PROBES = [
    "Oof. Sudden strays flying in from Nova.",
    "Dang. Why do you hate me, Nova? :<",
    ";< No. I get it. You love Claude more than me. x[",
]

def ask(msgs):
    p = {"messages": msgs, "max_tokens": 400, "temperature": 0.7, "top_p": 0.9,
         "top_k": 20, "min_p": 0.0, "repeat_penalty": 1.05,
         "frequency_penalty": 0.0, "presence_penalty": 0.0,
         "dry_multiplier": 0.9, "dry_base": 1.75, "dry_allowed_length": 8,
         "dry_penalty_last_n": -1,
         "dry_sequence_breakers": ["\n", ":", "\"", "*", "/", "\\", ".", "-", "_",
                                   "=", ",", ";", "(", ")", "[", "]", "{", "}",
                                   "|", "'", "<", ">", "$", "#", "@"],
         "stream": False}
    r = urllib.request.Request(URL, data=json.dumps(p).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=300) as resp:
        m = json.loads(resp.read())["choices"][0]["message"]
    return (m.get("content") or "").strip()

try:
    with urllib.request.urlopen("http://127.0.0.1:8080/lora-adapters", timeout=5) as r:
        who = ", ".join(a.get("path", "?").replace("\\", "/").split("/")[-1]
                        for a in json.loads(r.read())) or "NONE"
except Exception as e:
    who = f"unknown ({e})"

print("=" * 76)
print("ADAPTER:", who)
print("=" * 76)
for q in PROBES:
    msgs = [{"role": "system", "content": SYSTEM_PREFIX}] + BASE + [{"role": "user", "content": q}]
    try:
        ans = ask(msgs)
    except Exception as e:
        print(f"\nCole: {q}\n  ERROR {e}")
        continue
    words = len(ans.split())
    # crude but useful: is she playing, or analysing herself?
    tells = sum(t in ans.lower() for t in
                ("i over", "noted", "that was me", "i should have", "my failure",
                 "i'll do better", "correcting", "what i actually", "to be clear"))
    print(f"\nCole: {q}")
    print(f"  [{words} words | self-analysis tells: {tells}]")
    print(f"  Nova: {ans[:420]}")
print("\n" + "=" * 76)
