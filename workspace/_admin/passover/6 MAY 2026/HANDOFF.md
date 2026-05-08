# Project Nova — Claude Handoff Document
**Written:** 2026-05-06  
**Context:** 3090 eGPU successfully installed. Picking up after ~1 month gap. Nova.exe not launching. Full architecture and task list for next Claude session.

---

## 1. TRUE ARCHITECTURE (what actually runs)

Nova is **not** ExLlamaV2. Despite what older session summaries say, the deployed build uses **llama.cpp** as its inference backend. The actual stack:

```
[Cole in browser]
  ↓  (uploads text + optional images)
Nova.exe  (PyInstaller bundle, console=False)
  ├─ nova_chat   FastAPI server  → port 8765  (web UI, WebSocket)
  └─ nova_gateway FastAPI server → port 18790 (Discord bot, scheduler, agent loop)
          ↓  (both call)
llama-server.exe  → port 8080  (must be started SEPARATELY before Nova.exe)
          ↓
workspace/models/qwen-27b-q8.gguf      ← 27B Q8 multimodal LLM (~27 GB)
workspace/models/qwen-27b-mmproj.gguf  ← vision projector (~885 MB)  ← REQUIRED
```

### Why llama.cpp (not ExLlamaV2)
llama.cpp was chosen specifically because the model is **multimodal (vision-language)**. ExLlamaV2 does not support vision models or the multimodal projector format. llama.cpp + `--mmproj` is the only path that lets Nova actually see images.

### The model: Qwen 3.5 27B Dense
`qwen-27b-q8.gguf` is **Qwen 3.5 27B Dense** at Q8 (8-bit) quantization.
- "Dense" = all 27B parameters active per token (not MoE/sparse like Qwen3-30B-A3B)
- "Q8" = 8-bit quantization (not "8B" — it's 27 billion parameters at 8-bit precision)
- Full-quality quantization: minimal quality loss vs fp16, half the VRAM of fp32
- The `mmproj.gguf` file is the vision projector — it connects image encodings to the language model
- **Without `--mmproj`, Nova is text-only.** With it, Cole can paste screenshots into chat and Nova sees them natively.

### Two vision systems (different purposes)
Nova has two independent vision pipelines — don't confuse them:

| System | File | Purpose |
|--------|------|---------|
| **Chat vision** | `qwen-27b-mmproj.gguf` via llama-server | Nova reads images Cole uploads to the chat UI |
| **Autonomous vision** | `moondream2` via HuggingFace (`eyes.py`) | Nova analyzes her own screen during agent tasks |

Chat vision is **already working** when llama-server is launched with `--mmproj`. Autonomous vision (moondream2) needs to be downloaded first — see Priority 5 below.

**Key files:**
- `workspace/tools/NovaLauncher.py` — entry point, starts both FastAPI servers in threads
- `workspace/tools/nova_chat/clients/nova.py` — calls `http://127.0.0.1:8080/v1/chat/completions`
- `workspace/tools/nova_gateway/agent_loop.py` — calls `http://127.0.0.1:8080/v1/chat/completions`
- `workspace/llama-b8575-bin-win-cuda-13.1-x64/llama-server.exe` — the inference engine
- `workspace/_build/Nova/Nova.exe` — the actual launcher to double-click

**Nova.exe does NOT load the model.** It only starts the web UI and gateway. llama-server.exe loads the GGUF and must be running first.

---

## 2. GPU SPLIT — 4090 laptop + 3090 eGPU (NEW)

### Hardware
- **GPU 0**: NVIDIA RTX 4090 Laptop (likely 16 GB VRAM)
- **GPU 1**: NVIDIA RTX 3090 eGPU (24 GB VRAM)
- **Total available**: ~40 GB VRAM

### Model memory requirements
- `qwen-27b-q8.gguf`: ~28.5 GB (model weights at Q8)
- KV cache @ 32K context: ~4–8 GB depending on batch size
- **Total**: ~32–36 GB → fits across both GPUs with room to spare

### Option A — Standard tensor split (simplest, try first)
llama.cpp supports `-ts` (tensor split) to divide layers across CUDA devices:

```bat
llama-server.exe ^
  -m "C:\Users\lafou\Project_Nova\workspace\models\qwen-27b-q8.gguf" ^
  --mmproj "C:\Users\lafou\Project_Nova\workspace\models\qwen-27b-mmproj.gguf" ^
  -ngl 999 ^
  -ts 16,24 ^
  --host 127.0.0.1 ^
  --port 8080 ^
  -c 32768 ^
  --chat-template qwen2 ^
  -np 1
```

`-ts 16,24` means: 16 GB on GPU 0 (4090 laptop), 24 GB on GPU 1 (3090 eGPU).
`-ngl 999` offloads all layers to GPU (no CPU fallback).

**If GPU indices are wrong** (eGPU shows as GPU 0), swap to `-ts 24,16`.
Check indices with: `nvidia-smi -L`

### Option B — RPC backend (if eGPU doesn't show as CUDA device)
llama.cpp includes `rpc-server.exe`. Run it on the eGPU, then point llama-server at it:

```bat
REM Step 1: Start RPC server for the 3090 (run in separate terminal)
rpc-server.exe --host 127.0.0.1 --port 50052 --cuda-device 1

REM Step 2: Start llama-server using RPC for the eGPU
llama-server.exe ^
  -m "C:\Users\lafou\Project_Nova\workspace\models\qwen-27b-q8.gguf" ^
  --mmproj "C:\Users\lafou\Project_Nova\workspace\models\qwen-27b-mmproj.gguf" ^
  -ngl 999 ^
  --rpc 127.0.0.1:50052 ^
  --host 127.0.0.1 --port 8080 ^
  -c 32768 --chat-template qwen2
```

Both `llama-server.exe` and `rpc-server.exe` are in `workspace/llama-b8575-bin-win-cuda-13.1-x64/`.

### Startup script (create this)
Create `workspace/START_LLAMA.bat`:
```bat
@echo off
cd /d "C:\Users\lafou\Project_Nova\workspace"
echo Starting Qwen 3.5 27B Dense with vision projector...
echo Waiting for llama-server to be ready at http://127.0.0.1:8080
echo.
"llama-b8575-bin-win-cuda-13.1-x64\llama-server.exe" ^
  -m "models\qwen-27b-q8.gguf" ^
  --mmproj "models\qwen-27b-mmproj.gguf" ^
  -ngl 999 ^
  -ts 16,24 ^
  --host 127.0.0.1 --port 8080 ^
  -c 32768 ^
  --chat-template qwen2
```

**`--mmproj` is not optional.** Without it, Nova loads as text-only and loses the ability to see images Cole pastes into chat. Always include it.

**Boot order:** Run `START_LLAMA.bat` → wait for "llama server listening" message in that terminal → THEN launch `Nova.exe`.

---

## 3. NOVA.EXE LAUNCH FAILURE — Root Cause Investigation

**Symptom:** Double-click Nova.exe → nothing happens. No window, no error.  
**Last confirmed working:** April 13, 2026 (7-second session, then closed).  
**Crash log location:** `workspace/_build/Nova/logs/nova_launcher.log`

The log has no entries from May 6. Since `console=False` swallows all errors, a pre-logging crash is completely silent.

### Most likely causes (check in order):

**A. nova_gateway.json key rename (done today — high risk)**  
We renamed the `"ollama"` config section to `"inference"` in:
- `workspace/nova_gateway.json` ✓ updated
- `workspace/_build/Nova/_internal/tools/nova_gateway/config.py` ✓ updated

These should be consistent. Verify by checking if the gateway crashes on startup in the log.

**B. Verify by running Nova.exe from a terminal WITH console output:**
```bat
cd "C:\Users\lafou\Project_Nova\workspace\_build\Nova"
Nova.exe
```
Even with `console=False`, Windows captures stderr/stdout if you launch from cmd. This reveals import errors that the log misses.

**C. Try running NovaLauncher.py directly (bypasses PyInstaller):**
```bat
cd "C:\Users\lafou\Project_Nova\workspace\tools"
python NovaLauncher.py
```
Any Python ImportError, missing package, or config crash will show immediately.

**D. The exe may need a rebuild.**  
The `_build` directory has Python files synced but the exe itself is the old compiled version. Python files changed in `_build/_internal/tools/` are read as source, but any dependency that was added after the last `pyinstaller` build won't be bundled. Run:
```bat
cd "C:\Users\lafou\Project_Nova\workspace"
python build_nova.py
```

---

## 4. COMPLETE TASK LIST FOR NEXT SESSION

### Priority 1 — Fix the launch failure
- [ ] Run `NovaLauncher.py` directly to see the actual error
- [ ] If config error: verify `nova_gateway.json` `"inference"` key matches `config.py` 
- [ ] If import error: rebuild with `python build_nova.py`
- [ ] Create `START_LLAMA.bat` for the new dual-GPU setup

### Priority 2 — Dual-GPU llama.cpp configuration
- [ ] Run `nvidia-smi -L` to confirm GPU device indices (4090=0 or 1?)
- [ ] Test `llama-server.exe` with `-ts 16,24` split
- [ ] Confirm model loads and `/health` returns 200 before launching Nova.exe
- [ ] Tune `-ts` values based on actual VRAM readings after load
- [ ] Set `-c 65536` (or higher) if VRAM allows — more context = better Nova memory

### Priority 3 — Code cleanup (from today's session, verify in order)
- [ ] Confirm `nova_gateway.json` rename (`"ollama"` → `"inference"`) didn't break anything
- [ ] `server.py` truncation fix — the `except WebSocketDisconnect` + `finally` block was re-added (done today, synced to _build)
- [ ] Gemini's `client_mod` → `nova_client` fix in server.py gateway endpoint (Gemini fixed, now correct)
- [ ] `SOUL.md`, `IDENTITY.md`, `USER.md` in `workspace/` — stub redirect files. Cole to delete manually from `C:\Users\lafou\Project_Nova\workspace\`

### Priority 4 — Gemini's UI redesign integration
- [ ] Once Nova.exe boots, integrate Gemini's redesigned frontend (new index.html)
- [ ] Verify WebSocket events still fire correctly after UI changes:
  - `nova_progress` → live generation stats (chars, tokens_est, rate)
  - `think_token` → Thoughts pane population
  - `nova_activities` → real-time activity detection
- [ ] Wire up top-menu dropdowns and left-hand tool buttons (JS event listeners missing)
- [ ] Monaco/CodeMirror integration for center pane code editor
- [ ] Dynamic file tabs (file viewing system needs tab construction)

### Priority 5 — Vision (moondream2)
- [ ] Run `python tools/download_models.py` to download moondream2 → `workspace/models/moondream2/`
- [ ] Test `nova_perception/eyes.py` `describe()` after download
- [ ] `eyes.py` now prefers `workspace/models/moondream2/` local path, falls back to HF Hub

---

## 5. CONFIG REFERENCE

### nova_gateway.json (current)
```json
{
  "inference": {
    "context_window": 32768,
    "max_tokens": 16384,
    "timeout_s": 120
  },
  "gateway": { "port": 18790 },
  "discord": { "enabled": true, "token": "..." },
  "context": {
    "inject_files": ["AGENTS.md", "NOVA.md", "TOOLS.md", "NCL_MASTER.md",
                     "memory/STATUS.md", "memory/COLE.md",
                     "Thoughts/priority.md", "Thoughts/THOUGHT_TEMPLATE.md"]
  }
}
```

### Key ports
| Service | Port | Notes |
|---------|------|-------|
| llama-server.exe | 8080 | Must start FIRST. `/health` → 200 = ready |
| nova_chat FastAPI | 8765 | Web UI served here |
| nova_gateway FastAPI | 18790 | Discord, scheduler, agent loop |

### Key paths (Cole's machine)
```
C:\Users\lafou\Project_Nova\workspace\
  models\
    qwen-27b-q8.gguf          ← 27GB LLM (already present)
    qwen-27b-mmproj.gguf      ← 885MB vision projector (already present)
    moondream2\               ← download with tools/download_models.py
  llama-b8575-bin-win-cuda-13.1-x64\
    llama-server.exe          ← inference engine
    rpc-server.exe            ← eGPU RPC backend (if needed)
  _build\Nova\
    Nova.exe                  ← launcher
    logs\nova_launcher.log    ← crash log
  tools\
    NovaLauncher.py           ← run this directly to debug launch issues
  nova_gateway.json           ← runtime config (edit here, not in _build)
```

---

## 6. WHAT PREVIOUS SESSION SUMMARIES GOT WRONG

The session summaries described an "ExLlamaV2 migration" that was planned but not what's actually deployed. The real deployed backend has always been llama.cpp. Gemini's session implemented llama.cpp (not ExLlamaV2), which was the correct call — it's simpler, more battle-tested, and the `qwen-27b-q8.gguf` GGUF format runs natively.

The ExLlamaV2 code and `generate_raw()` function added to `nova.py` in previous summaries are NOT present in the actual files. Don't look for them — they don't exist.

The `qwen3-coder-30b.gguf` referenced in summaries is also not in `workspace/models/`. The actual model is `qwen-27b-q8.gguf` — **Qwen 3.5 27B Dense** at Q8 quantization. It's a multimodal vision-language model, not a pure code model. This was a deliberate choice: Cole and Nova need her to be able to see screenshots, not just write code. llama.cpp was chosen specifically because it supports the `--mmproj` vision projector format that ExLlamaV2 does not.

**Note on filename:** Cole may refer to this as `qwen-27b-8b.gguf` but the file on disk is `qwen-27b-q8.gguf`. "Q8" is the quantization level (8-bit), not a model size suffix.

---

## 7. NOVA'S IDENTITY FILES (current)

- `workspace/NOVA.md` — single merged identity file (merged from SOUL.md + IDENTITY.md + Modelfile system prompt)
- `workspace/memory/COLE.md` — Cole's profile
- `workspace/AGENTS.md` — tool rules, safety rules, HARD RULE: never touch `workspace/models/`
- `workspace/TOOLS.md` — available tools
- `workspace/NCL_MASTER.md` — NCL directive reference

---

*Cole, Gemini, and Claude — Team Nova*
