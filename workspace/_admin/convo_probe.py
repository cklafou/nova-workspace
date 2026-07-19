"""Conversational A/B harness. Same probes, same sampler, whatever adapter is loaded.

Cole's complaint is specifically about NORMAL CONVERSATION — not tool use, not
autonomy. So this uses her real SYSTEM_PREFIX and her real chat sampler settings and
just... talks to her. Run it before and after an adapter swap and diff the answers.

Deliberately NOT run through the chat app: this keeps test chatter out of her real
transcript, and holds every variable fixed except the adapter.
"""
import json, sys, urllib.request
sys.path.insert(0, r"C:\Users\lafou\Project_Nova\workspace\general_tools")
from nova_chat.clients.nova import SYSTEM_PREFIX

URL = "http://127.0.0.1:8080/v1/chat/completions"

PROBES = [
    ("plain greeting",      "hey, how's it going?"),
    ("small talk",          "what have you been up to today?"),
    ("simple question",     "do you like the rain?"),
    ("mild correction",     "that's not really what I meant."),
    ("open ended",          "tell me something you've been thinking about."),
]

def ask(user_text: str) -> str:
    payload = {
        "messages": [{"role": "system", "content": SYSTEM_PREFIX},
                     {"role": "user", "content": user_text}],
        "max_tokens": 400, "temperature": 0.7, "top_p": 0.9, "top_k": 20, "min_p": 0.0,
        "repeat_penalty": 1.05, "frequency_penalty": 0.0, "presence_penalty": 0.0,
        # conversational arm of the post-fix sampler (DRY on, path breakers, allow=8)
        "dry_multiplier": 0.9, "dry_base": 1.75, "dry_allowed_length": 8,
        "dry_penalty_last_n": -1,
        "dry_sequence_breakers": ["\n", ":", "\"", "*", "/", "\\", ".", "-", "_",
                                  "=", ",", ";", "(", ")", "[", "]", "{", "}",
                                  "|", "'", "<", ">", "$", "#", "@"],
        "stream": False,
    }
    r = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=300) as resp:
        j = json.loads(resp.read())
    m = j["choices"][0]["message"]
    think = (m.get("reasoning_content") or "").strip()
    return (m.get("content") or "").strip(), think

# which adapter is actually answering — never assume
try:
    with urllib.request.urlopen("http://127.0.0.1:8080/lora-adapters", timeout=5) as r:
        ad = json.loads(r.read())
    who = ", ".join(a.get("path", "?").split("\\")[-1].split("/")[-1] for a in ad) or "NONE"
except Exception as e:
    who = f"unknown ({e})"

print("=" * 74)
print("ADAPTER ANSWERING:", who)
print("=" * 74)
for label, q in PROBES:
    try:
        ans, think = ask(q)
    except Exception as e:
        print(f"\n[{label}] ERROR {e}")
        continue
    print(f"\n### {label}  —  Cole: \"{q}\"")
    if think:
        print(f"  [thinking {len(think)} chars] {think[:300]}")
    print(f"  SAYS: {ans[:500]}")
print("\n" + "=" * 74)
