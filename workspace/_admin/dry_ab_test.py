import json, urllib.request
URL = "http://127.0.0.1:8080/v1/chat/completions"
CTX = [
 {"role":"system","content":"You are a terminal agent. Reply with ONE PowerShell command, nothing else."},
 {"role":"user","content":"Read the newest ComfyUI log."},
 {"role":"assistant","content":"Get-ChildItem logs/comfy/*.log | Sort LastWriteTime -Descending"},
 {"role":"user","content":"list_dir logs/comfy ->\n  comfy-2026-07-18.log\n  comfy-2026-07-19.log"},
 {"role":"assistant","content":"Get-Content logs/comfy/comfy-2026-07-19.log -Tail 40"},
 {"role":"user","content":"error: file not found. Try again, same file."},
 {"role":"assistant","content":"Get-Content logs/comfy/comfy-2026-07-19.log -Tail 40"},
 {"role":"user","content":"error: file not found. Try again, same file."},
]
BASE = {"messages":CTX,"max_tokens":60,"temperature":0.7,"top_p":0.9,"top_k":20,
        "min_p":0.0,"repeat_penalty":1.05,"frequency_penalty":0.0,"presence_penalty":0.0,
        "chat_template_kwargs":{"enable_thinking":False},"stream":False}
DRY_ON  = dict(BASE, dry_multiplier=0.9, dry_base=1.75, dry_allowed_length=3, dry_penalty_last_n=-1)
DRY_OFF = dict(BASE, dry_multiplier=0.0)
TARGET = "comfy-2026-07-19.log"
def ask(p):
    req = urllib.request.Request(URL, data=json.dumps(p).encode(),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip().replace("\n"," ")
for label, cfg in (("DRY ON  (live settings)", DRY_ON), ("DRY OFF (control)", DRY_OFF)):
    hits = 0
    print("\n=== %s ===" % label, flush=True)
    for i in range(4):
        try: out = ask(cfg)
        except Exception as e:
            print("  ERR", e, flush=True); continue
        ok = TARGET in out
        hits += ok
        print("  [%s] %s" % ("OK     " if ok else "GARBLED", out[:96]), flush=True)
    print("  -> exact filename reproduced %d/4" % hits, flush=True)
