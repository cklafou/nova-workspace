# Project Nova — Claude Handoff Document
_Last updated: 2026-05-29 15:52:09_
**Written:** 2026-05-23  
**Context:** OCuLink eGPU troubleshooting. Nova.exe launch state unknown. Cole upgrades to Claude MAX and switches to Opus for future sessions.

---

## 1. READ THESE FIRST

Before any infrastructure work:
1. `ORIENT.md` — master reference, last auto-updated 2026-05-09
2. `BOOTUP/AGENTS.md` — Nova's operational rules
3. `BOOTUP/UPGRADE_PROTOCOL.md` — patch procedure before touching source

---

## 2. TRUE ARCHITECTURE (unchanged from May 6 handoff)

Nova runs on **llama.cpp** (not ExLlamaV2 — session summaries have been wrong about this repeatedly). The deployed stack:

```
[Cole in browser / PyQt6 UI]
  ↓
Nova.exe  (PyInstaller stub → NovaLauncher.py)
  ├─ Thread 1: nova_chat   FastAPI + WebSocket  → port 8765  (web UI)
  └─ Thread 2: nova_gateway FastAPI             → port 18790 (Discord, scheduler, tools)
         ↓  (both call)
llama-server.exe  → port 8080   ← MUST start FIRST before Nova.exe
         ↓
workspace/models/qwen-27b-q8.gguf       ← Qwen 3.5 27B Dense Q8 (~27 GB)
workspace/models/qwen-27b-mmproj.gguf   ← Vision projector (~885 MB) ← DO NOT OMIT
```

**Nova.exe does NOT load the model.** llama-server.exe loads the GGUF and must be running and healthy (`/health` → 200) before Nova.exe is launched.

### Inference backend — common confusion, correct facts:
- Backend: **llama.cpp** (GGUF format)
- Model: **Qwen 3.5 27B Dense** at Q8 quantization — `qwen-27b-q8.gguf`
- Q8 = 8-bit quantization (not "8B" — the model has 27 billion parameters)
- Cole sometimes calls it `qwen-27b-8b.gguf` — the file on disk is `qwen-27b-q8.gguf`
- The vision projector `qwen-27b-mmproj.gguf` is required for Nova to see images in chat
- ExLlamaV2 was never deployed — the ORIENT.md still references it in a few places, that's a doc bug

---

## 3. GPU SETUP — RTX 4090 Laptop + RTX 3090 eGPU (OCuLink)

### Hardware
- **GPU 0**: NVIDIA RTX 4090 Laptop (~16 GB VRAM)
- **GPU 1**: NVIDIA RTX 3090 eGPU (24 GB VRAM) via OCuLink direct PCIe connection

### Current eGPU status: PROBLEMATIC (as of 2026-05-23)

The RTX 3090 eGPU is showing **Error 45** in Device Manager:
> "Currently, this hardware device is not connected to the computer."

This is a PCIe bus-level detection failure. The device appears under hidden devices only — Windows remembers it existed but it's not on the bus. No software fix exists for Error 45.

**Root cause:** OCuLink requires the eGPU enclosure to be powered on BEFORE the laptop boots. Windows enumerates PCIe devices early in boot. If the eGPU isn't presenting itself on the bus at that point, Error 45 is the result.

**The only fix:**
1. Full shutdown of laptop (not restart)
2. Power on the eGPU enclosure and wait a few seconds
3. Power on the laptop

**Cole has the eGPU physically disconnected** (disconnected to regain desktop access after a crash). He'll need to reconnect it and do the cold boot sequence above.

### What caused the crash
A `Nova_eGPU_Init` scheduled task (since removed) ran at login via SYSTEM account. It called `Disable-PnpDevice` / `Enable-PnpDevice` on the RTX 3090 after a 15-second delay. When the eGPU monitor was set as the primary display and the script disabled the GPU, Windows crashed the login shell.

**The task has been confirmed removed.** Running `Unregister-ScheduledTask -TaskName "Nova_eGPU_Init" -Confirm:$false` returned "No MSFT_ScheduledTask objects found" — it's gone.

### Two leftover script files — Cole needs to manually delete these

These files exist in the workspace but are NOT wanted. Cole should delete them from Explorer:
```
C:\Users\lafou\Project_Nova\workspace\_egpu_cycle.ps1
C:\Users\lafou\Project_Nova\workspace\fix_egpu_startup.ps1
```

Do NOT recreate these or any eGPU automation script. Cole manages the eGPU disable/re-enable manually through Device Manager.

### start_llama.cmd — dual GPU launch script (exists, ready to use)

`workspace/start_llama.cmd` is already written and handles the dual-GPU tensor split:
```bat
.\llama\llama-server.exe ^
    -m models\qwen-27b-q8.gguf ^
    --mmproj models\qwen-27b-mmproj.gguf ^
    -ngl 999 ^
    -ts 16,24 ^
    -c 32768 ^
    -fa on ^
    --cache-prompt ^
    --slot-save-path prompt_cache ^
    -b 2048 -ub 1024 ^
    --port 8080 --host 127.0.0.1
```

`-ts 16,24` = 16 GB on GPU 0 (4090 laptop), 24 GB on GPU 1 (3090 eGPU). If `nvidia-smi -L` shows eGPU as device 0, swap to `-ts 24,16`.

**When the eGPU is not connected:** the model must fit on the 4090 laptop alone (~16 GB). Q8 weights need ~28.5 GB, so it won't load fully without the eGPU. You'd need to lower quantization or reduce layers offloaded (`-ngl` below 999) to fit it in CPU+GPU split — or wait for the eGPU to be reattached.

---

## 4. NOVA.EXE LAUNCH STATE (Unknown as of 2026-05-23)

As of the May 6 handoff, Nova.exe was failing to launch silently. Status as of today is unknown — Cole hasn't reported whether it was fixed.

**Priority 1 debugging steps from May 6 (still relevant):**
```bat
REM Try running from terminal — reveals startup errors even with console=False
cd "C:\Users\lafou\Project_Nova\workspace\_build\Nova"
Nova.exe

REM Better: run the source directly, bypasses PyInstaller
cd "C:\Users\lafou\Project_Nova\workspace\general_tools"
python NovaLauncher.py
```

Check crash log: `workspace/_build/Nova/logs/nova_launcher.log` (or `workspace/logs/nova_launcher.log`)

---

## 5. TASK LIST — PRIORITY ORDER

### Immediate (hardware)
- [ ] Cole: physically reconnect RTX 3090 eGPU enclosure
- [ ] Cole: cold boot sequence (shutdown → eGPU on first → laptop on) to clear Error 45
- [ ] Cole: delete `_egpu_cycle.ps1` and `fix_egpu_startup.ps1` from workspace manually
- [ ] Cole: run `nvidia-smi -L` after eGPU reconnects to confirm GPU device indices
- [ ] After eGPU working: set **laptop internal display as primary** in Display Settings (prevents future login crashes if eGPU monitor isn't ready)

### Nova.exe (from May 6 — status unknown)
- [ ] Confirm Nova.exe launches (run `NovaLauncher.py` directly to check)
- [ ] If config error: verify `nova_gateway.json` `"inference"` key matches `config.py`
- [ ] If import error: rebuild with `python build_nova.py`
- [ ] Verify `server.py` `except WebSocketDisconnect` + `finally` block is present (was fixed May 6, confirm it survived)

### Dual-GPU llama.cpp (once eGPU back)
- [ ] Run `start_llama.cmd` with eGPU present
- [ ] Confirm `/health` returns 200 at `http://127.0.0.1:8080/health`
- [ ] Check VRAM usage with `nvidia-smi` — tune `-ts` split if needed
- [ ] Consider bumping context to `-c 65536` if VRAM allows

### Code / Features (from May 6, unchanged)
- [ ] Integrate Gemini's redesigned frontend (new index.html) once Nova.exe boots
- [ ] Wire up top-menu dropdowns and left-hand tool buttons (JS event listeners missing)
- [ ] Download moondream2: `python tools/download_models.py`
- [ ] Test `nova_body/nova_senses/eyes.py` `describe()` after moondream2 download
- [ ] Wire `vigilance.py` into `gateway.py` startup — it's built but not connected

---

## 6. CONFIG REFERENCE

### nova_gateway.json (current keys)
```json
{
  "inference": { "context_window": 32768, "max_tokens": 16384, "timeout_s": 120 },
  "gateway": { "port": 18790 },
  "discord": { "enabled": true, "token": "..." },
  "context": {
    "inject_files": ["AGENTS.md", "NOVA.md", "TOOLS.md", "NCL_MASTER.md",
                     "memory/STATUS.md", "memory/COLE.md",
                     "Tasking/priority.md", "Tasking/THOUGHT_TEMPLATE.md"]
  }
}
```

Note: the `"ollama"` key was renamed to `"inference"` in a previous session. If anything calls `config["ollama"]` it will KeyError.

### Key ports
| Service | Port | Notes |
|---------|------|-------|
| llama-server.exe | 8080 | Start FIRST. `/health` → 200 = ready |
| nova_chat FastAPI | 8765 | Web UI served here |
| nova_gateway FastAPI | 18790 | Discord, scheduler, agent loop |

### Key paths (Cole's machine)
```
C:\Users\lafou\Project_Nova\workspace\
  models\                          ← SEALED. Never read, list, or open.
    qwen-27b-q8.gguf               ← 27GB LLM (present)
    qwen-27b-mmproj.gguf           ← 885MB vision projector (present)
    moondream2\                    ← download with tools/download_models.py (NOT yet downloaded)
  llama\
    llama-server.exe               ← inference engine
    rpc-server.exe                 ← eGPU RPC backend (if needed, fallback)
  general_tools\
    NovaLauncher.py                ← run directly for debug; production entry point
    nova_chat\server.py            ← core server
    gateway.py                     ← nova_gateway FastAPI
  nova_body\nova_cortex\           ← cognitive layer, fully built
  _build\Nova\
    Nova.exe                       ← launcher (double-click)
    logs\nova_launcher.log         ← crash log
  nova_gateway.json                ← runtime config (edit here, NOT in _build)
  start_llama.cmd                  ← dual-GPU llama-server launch script
  _egpu_cycle.ps1                  ← DELETE THIS (unwanted, do not run)
  fix_egpu_startup.ps1             ← DELETE THIS (unwanted, do not run)
```

---

## 7. WHAT PREVIOUS SUMMARIES GOT WRONG (ongoing list)

- **ExLlamaV2 is not deployed.** The ORIENT.md still references it in places — those are doc bugs. The actual inference backend is llama.cpp. The `qwen-27b-q8.gguf` is a GGUF file, not an ExLlamaV2 model.
- **`llama/` vs `llama-b8575-bin-win-cuda-13.1-x64/`**: The May 6 handoff referenced the long binary path. The workspace now has it at `workspace/llama/` (shorter path). `start_llama.cmd` already uses `.\llama\llama-server.exe`.
- **`qwen3-coder-30b.gguf`**: Does not exist on disk. The model is `qwen-27b-q8.gguf`.
- **`SOUL.md`, `IDENTITY.md`, `USER.md`**: These stub redirect files were listed as needing manual deletion in May 6. Status unknown — Cole may or may not have deleted them.

---

## 8. META — AI SETUP CHANGES

Cole has upgraded to **Claude MAX** and intends to use **Claude Opus** for future Project Nova sessions. Opus has substantially more context and reasoning capacity than Sonnet, which should help with large codebase navigation and multi-file refactors.

When starting a Opus session: bootstrap with ORIENT.md + this file, then check `Tasking/priority.md` and `nova_status.json` before taking any action.

---

*Cole + Claude — Team Nova*  
*Last updated: 2026-05-23*
