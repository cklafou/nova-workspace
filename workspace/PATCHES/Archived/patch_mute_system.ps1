# patch_mute_system.ps1
# Adds the mute/unmute system to server.py:
#
#   - _mute_states dict: all AI agents start muted on server launch
#   - "mute_agent" WS message handler: mutes/unmutes and broadcasts state
#   - Message dispatch filter: muted agents only respond when @mentioned
#   - @mute[Name] / @unmute[Name] text command parsing in chat messages
#
# Run from workspace root: .\PATCHES\patch_mute_system.ps1 [-DryRun]

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== Mute System Patch ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

$srvPath = Join-Path $root "general_tools\nova_chat\server.py"
if (-not (Test-Path $srvPath)) { Warn "server.py not found"; exit 1 }
$srv = Get-Content $srvPath -Raw -Encoding UTF8

# ── PATCH 1: Add _mute_states global (all agents muted at startup) ─────────────
if ($srv -match [regex]::Escape('_mute_states')) {
    Ok "PATCH 1: _mute_states global already present"
} else {
    $old1 = @'
# Eyes streaming flag — toggled by /api/eyes/start and /api/eyes/stop
_eyes_running: bool = False
'@
    $new1 = @'
# Eyes streaming flag — toggled by /api/eyes/start and /api/eyes/stop
_eyes_running: bool = False

# Mute states — agents start muted and only respond to @ mentions by default.
# Unmute via badge click in Nova Qt, or @unmute[Name] in chat.
_mute_states: dict = {"Nova": True, "Claude": True, "Gemini": True}
'@
    # Fallback anchor if eyes patch hasn't been run yet
    if (-not $srv.Contains($old1.Trim())) {
        $old1 = @'
# Autonomous mode toggle (set via "autonomous_toggle" WS message)
autonomous_mode: bool = False
'@
        $new1 = @'
# Autonomous mode toggle (set via "autonomous_toggle" WS message)
autonomous_mode: bool = False

# Mute states — agents start muted and only respond to @ mentions by default.
# Unmute via badge click in Nova Qt, or @unmute[Name] in chat.
_mute_states: dict = {"Nova": True, "Claude": True, "Gemini": True}
'@
    }

    if (-not $srv.Contains($old1.Trim())) {
        Warn "PATCH 1: Could not find anchor for _mute_states global -- add manually after autonomous_mode"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old1, $new1) }
        Ok "PATCH 1: _mute_states global added"
    }
}

# ── PATCH 2: Add mute_agent WS handler ────────────────────────────────────────
if ($srv -match [regex]::Escape('"mute_agent"')) {
    Ok "PATCH 2: mute_agent WS handler already present"
} else {
    $old2 = @'
            if data.get("type") == "message":
'@
    $new2 = @'
            if data.get("type") == "mute_agent":
                global _mute_states
                agent  = data.get("agent", "")
                muted  = bool(data.get("muted", True))
                if agent in _mute_states:
                    _mute_states[agent] = muted
                    await broadcast({"type": "mute_state", "agent": agent, "muted": muted})
                continue

            if data.get("type") == "message":
'@
    if (-not $srv.Contains($old2.Trim())) {
        Warn "PATCH 2: 'message' WS handler anchor not found"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old2, $new2) }
        Ok "PATCH 2: mute_agent WS handler added"
    }
}

# ── PATCH 3: Parse @mute/@unmute commands in chat messages ────────────────────
if ($srv -match [regex]::Escape('@mute')) {
    Ok "PATCH 3: @mute/@unmute command parsing already present"
} else {
    # Anchor: right after content is extracted from the message payload
    # We look for where 'content' is read and add command parsing after it
    $old3 = @'
            content = data.get("content", "").strip()
            if not content:
                continue
'@
    $new3 = @'
            content = data.get("content", "").strip()
            if not content:
                continue

            # Parse @mute[Name] / @unmute[Name] text commands
            import re as _re
            _mute_cmd   = _re.fullmatch(r'@mute\[?(\w+)\]?',   content, _re.IGNORECASE)
            _unmute_cmd = _re.fullmatch(r'@unmute\[?(\w+)\]?', content, _re.IGNORECASE)
            if _mute_cmd or _unmute_cmd:
                _agent = (_mute_cmd or _unmute_cmd).group(1).capitalize()
                if _agent in _mute_states:
                    _muted = bool(_mute_cmd)
                    _mute_states[_agent] = _muted
                    await broadcast({"type": "mute_state", "agent": _agent, "muted": _muted})
                    _state_str = "muted" if _muted else "listening"
                    _emoji     = "\U0001f507" if _muted else "\U0001f442"
                    _sys_msg   = session_mgr.active.add("System", f"{_emoji} {_agent} is now {_state_str}")
                    await broadcast({
                        "type": "user_message", "author": "System",
                        "content": f"{_emoji} {_agent} is now {_state_str}",
                        "id": _sys_msg["id"], "timestamp": _sys_msg["timestamp"],
                    })
                    continue
'@
    if (-not $srv.Contains($old3.Trim())) {
        Warn "PATCH 3: content extraction anchor not found -- @mute command parsing must be added manually"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old3, $new3) }
        Ok "PATCH 3: @mute/@unmute command parsing added"
    }
}

# ── PATCH 4: Add _should_agent_respond() helper ───────────────────────────────
if ($srv -match [regex]::Escape('_should_agent_respond')) {
    Ok "PATCH 4: _should_agent_respond helper already present"
} else {
    $old4 = @'
async def _bg_nova_status_poll():
'@
    $helper = @'
def _should_agent_respond(agent: str, content: str) -> bool:
    """
    Returns True if the agent should respond to this message.
    - Unmuted agents respond to everything.
    - Muted agents only respond when @AgentName appears in the message.
    """
    if not _mute_states.get(agent, True):
        return True   # unmuted — respond to all
    # Muted — check for direct mention
    import re as _re
    return bool(_re.search(rf'@{re.escape(agent)}', content, _re.IGNORECASE))

async def _bg_nova_status_poll():
'@
    if (-not $srv.Contains($old4.Trim())) {
        Warn "PATCH 4: _bg_nova_status_poll anchor not found -- add _should_agent_respond() manually"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old4, $helper) }
        Ok "PATCH 4: _should_agent_respond() helper added"
    }
}

# ── PATCH 5: Gate each AI client call with _should_agent_respond ──────────────
# This patch is highly dependent on the exact dispatch loop structure in server.py.
# We try two common patterns and warn if neither matches.
if ($srv -match [regex]::Escape('_should_agent_respond')) {
    if ($srv -match [regex]::Escape('if _should_agent_respond')) {
        Ok "PATCH 5: dispatch guard already applied"
    } else {
        # Try to find the per-client stream_response calls and wrap each one.
        # Pattern A: Nova is called separately (which we know from earlier patches)
        $old5a = @'
        if client_name == "Nova":
            await client_mod.stream_response(
'@
        $new5a = @'
        if client_name == "Nova" and _should_agent_respond("Nova", content):
            await client_mod.stream_response(
'@
        if ($srv.Contains($old5a.Trim())) {
            if (-not $DryRun) { $srv = $srv.Replace($old5a, $new5a) }
            Ok "PATCH 5a: Nova dispatch guard added"
        }

        # Pattern B: generic loop guard
        $old5b = @'
        for client_name, client_mod in active_clients:
'@
        $new5b = @'
        for client_name, client_mod in active_clients:
            if not _should_agent_respond(client_name, content):
                continue
'@
        if ($srv.Contains($old5b.Trim())) {
            if (-not $DryRun) { $srv = $srv.Replace($old5b, $new5b) }
            Ok "PATCH 5b: generic dispatch loop guard added"
        } else {
            Warn "PATCH 5: Could not auto-apply dispatch guard -- locate the AI client dispatch loop in server.py and wrap each call with: if _should_agent_respond(agent_name, content):"
        }
    }
}

if (-not $DryRun) {
    Set-Content -Path $srvPath -Value $srv -Encoding UTF8
    Log ""
    Log "Done. Restart nova_chat to apply."
    Log ""
    Log "Usage:"
    Log "  Click a badge in Nova Qt to toggle mute state"
    Log "  Type @unmute[Claude] to unmute Claude from chat"
    Log "  Type @mute[Nova] to mute Nova from chat"
    Log "  All agents start MUTED on every server launch"
} else {
    Log ""
    Log "Dry run complete. Review WARNs above before applying."
    Log "NOTE: PATCH 5 may need manual adjustment depending on server.py dispatch structure."
}
