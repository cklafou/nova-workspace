# PATCHES/
_Last updated: 2026-05-29 16:52:23_

PowerShell patch scripts for server-side files that can't be edited directly from the VM
(server.py, nova.py, workspace_context.py, etc.).

Run all scripts from the **workspace root**:

```powershell
.\PATCHES\patch_depth_server.ps1 -DryRun   # verify first
.\PATCHES\patch_depth_server.ps1            # then apply
```

---

## Active Patches

| Script | Purpose | Status |
|---|---|---|
| `patch_depth_server.ps1` | Adds depth slider + autonomous toggle to server.py + nova.py | **Needs to be run** |
| `apply_bootup_reorganization.ps1` | Patches workspace_context.py to load from BOOTUP/ + removes root originals | **Needs to be run** |
| `patch_nova_payload.ps1` | Adds repeat_penalty + min_p to Nova's llama.cpp API payload | **Needs to be run** |
| `patch_workspace_context.ps1` | Adds UPGRADE_PROTOCOL.md to nova_chat context injection list | **Needs to be run** |
| `patch_eyes_server.ps1` | Adds live eyes streaming endpoints + background task to server.py | **Needs to be run** |
| `patch_autonomous_behavior.ps1` | Fixes autonomous mode (injects real directive into Nova's prompt), adds temperature/top_p runtime control, strips Nova's erroneous "Nova:" prefix | **Needs to be run after patch_depth_server.ps1** |
| `patch_claude_client.ps1` | **CRITICAL** — Fixes Claude hallucinating full conversations (adds identity system prompt) and guards nova_bridge so only Nova's messages trigger EXEC/READ/WRITE directives | **Run immediately** |

## Archived/

Superseded patches — kept for reference only, do not run.

| Script | Reason Archived |
|---|---|
| `patch_autonomous_server.ps1` | Superseded by patch_depth_server.ps1 (which covers autonomous toggle + depth slider together) |
