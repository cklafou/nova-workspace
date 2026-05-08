# patch_autonomous_behavior.ps1
# Fixes autonomous mode so it actually changes Nova's behavior, not just
# shows a chat message. When ON, injects a directive into Nova's system
# prompt telling her to continue through her plan without yielding.
#
# Also adds temperature + top_p runtime control via set_params WS message,
# and strips the "Nova:" prefix Nova keeps erroneously adding to messages.
#
# Run from workspace root: .\PATCHES\patch_autonomous_behavior.ps1 [-DryRun]

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== Autonomous Mode Behavior + Param Control Patch ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

# ── PATCH server.py ────────────────────────────────────────────────────────────
$srvPath = Join-Path $root "general_tools\nova_chat\server.py"
if (-not (Test-Path $srvPath)) { Warn "server.py not found"; exit 1 }
$srv = Get-Content $srvPath -Raw -Encoding UTF8

# -- 1. Add _nova_temperature + _nova_top_p globals after autonomous_mode ------
if ($srv -match [regex]::Escape('_nova_temperature')) {
    Ok "PATCH 1: temperature/top_p globals already present"
} else {
    $old1 = @'
# Autonomous mode toggle (set via "autonomous_toggle" WS message)
autonomous_mode: bool = False
'@
    $new1 = @'
# Autonomous mode toggle (set via "autonomous_toggle" WS message)
autonomous_mode: bool = False

# Runtime Nova inference params (adjustable via "set_params" WS message)
_nova_temperature: float = 0.7
_nova_top_p:       float = 0.9
'@
    if (-not $srv.Contains($old1.Trim())) {
        Warn "PATCH 1: autonomous_mode anchor not found -- run patch_depth_server.ps1 first"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old1, $new1) }
        Ok "PATCH 1: _nova_temperature + _nova_top_p globals added"
    }
}

# -- 2. Add set_params WS handler after autonomous_toggle handler --------------
if ($srv -match [regex]::Escape('"set_params"')) {
    Ok "PATCH 2: set_params WS handler already present"
} else {
    $old2 = @'
            if data.get("type") == "message":
'@
    $new2 = @'
            if data.get("type") == "set_params":
                global _nova_temperature, _nova_top_p
                if "temperature" in data:
                    _nova_temperature = float(data["temperature"])
                if "top_p" in data:
                    _nova_top_p = float(data["top_p"])
                continue

            if data.get("type") == "message":
'@
    if (-not $srv.Contains($old2.Trim())) {
        Warn "PATCH 2: 'message' WS handler anchor not found"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old2, $new2) }
        Ok "PATCH 2: set_params WS handler added"
    }
}

# -- 3. Build autonomous system prompt injection + pass params to nova client --
# The nova stream_response call needs to receive temperature, top_p, and
# an autonomous mode flag so nova.py can inject the right system prompt.
if ($srv -match [regex]::Escape('autonomous=autonomous_mode')) {
    Ok "PATCH 3: autonomous + params already wired into Nova stream_response call"
} else {
    $old3 = @'
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            workspace_context=ws_context, images=images,
            max_tokens=_depth_max_tokens,   # 0 = use nova.py default
        )
'@
    $new3 = @'
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            workspace_context=ws_context, images=images,
            max_tokens=_depth_max_tokens,   # 0 = use nova.py default
            autonomous=autonomous_mode,
            temperature=_nova_temperature,
            top_p=_nova_top_p,
        )
'@
    if (-not $srv.Contains($old3.Trim())) {
        Warn "PATCH 3: nova stream_response anchor not found -- run patch_depth_server.ps1 first"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old3, $new3) }
        Ok "PATCH 3: autonomous + temperature + top_p wired into Nova stream_response"
    }
}

if (-not $DryRun) {
    Set-Content -Path $srvPath -Value $srv -Encoding UTF8
}

# ── PATCH nova.py ──────────────────────────────────────────────────────────────
$novaPath = Join-Path $root "general_tools\nova_chat\clients\nova.py"
if (-not (Test-Path $novaPath)) { Warn "nova.py not found"; exit 1 }
$nova = Get-Content $novaPath -Raw -Encoding UTF8

# -- 4. Add autonomous + temperature + top_p params to stream_response ---------
if ($nova -match [regex]::Escape('autonomous: bool = False')) {
    Ok "PATCH 4: autonomous/temperature/top_p params already in stream_response"
} else {
    $old4 = @'
    max_tokens: int = 0,   # 0 = use default (MAX_TOKENS_CHAT); set by depth slider
):
'@
    $new4 = @'
    max_tokens:  int   = 0,      # 0 = use default (MAX_TOKENS_CHAT); set by depth slider
    autonomous:  bool  = False,  # if True, inject autonomous-mode directive into system prompt
    temperature: float = 0.7,
    top_p:       float = 0.9,
):
'@
    if (-not $nova.Contains($old4.Trim())) {
        Warn "PATCH 4: stream_response max_tokens anchor not found -- run patch_depth_server.ps1 first"
    } else {
        if (-not $DryRun) { $nova = $nova.Replace($old4, $new4) }
        Ok "PATCH 4: autonomous/temperature/top_p params added to stream_response"
    }
}

# -- 5. Wire temperature + top_p into the llama.cpp payload -------------------
if ($nova -match [regex]::Escape('"temperature": temperature')) {
    Ok "PATCH 5: temperature/top_p already wired into payload"
} else {
    $old5 = @'
        "temperature": 0.7,
        "top_p": 0.9,
'@
    $new5 = @'
        "temperature": temperature,
        "top_p": top_p,
'@
    if (-not $nova.Contains($old5.Trim())) {
        Warn "PATCH 5: payload temperature anchor not found -- check nova.py manually"
    } else {
        if (-not $DryRun) { $nova = $nova.Replace($old5, $new5) }
        Ok "PATCH 5: temperature + top_p wired into llama.cpp payload"
    }
}

# -- 6. Inject autonomous-mode system prompt when flag is True -----------------
if ($nova -match [regex]::Escape('AUTONOMOUS MODE')) {
    Ok "PATCH 6: autonomous system prompt injection already present"
} else {
    # We need to find where the system prompt / messages list is built.
    # Anchor: the workspace_context injection point in nova.py
    $old6 = @'
    if workspace_context:
        messages = [{"role": "system", "content": workspace_context}] + list(transcript)
    else:
        messages = list(transcript)
'@
    $new6 = @'
    # Build system context -- workspace context + autonomous mode directive
    system_parts = []
    if workspace_context:
        system_parts.append(workspace_context)
    if autonomous:
        system_parts.append(
            "\n\n[AUTONOMOUS MODE: ON]\n"
            "You are currently operating autonomously. Do NOT stop after a single tool call or "
            "exec result. Continue working through your full plan step by step until the task "
            "is complete or you hit a genuine blocker. Only stop if Cole speaks or you run out "
            "of safe options. Each action you take should move the task forward -- do not ask "
            "for confirmation unless something unexpected happens."
        )
    if system_parts:
        messages = [{"role": "system", "content": "".join(system_parts)}] + list(transcript)
    else:
        messages = list(transcript)
'@
    if (-not $nova.Contains($old6.Trim())) {
        Warn "PATCH 6: workspace_context injection anchor not found in nova.py -- autonomous prompt must be wired manually"
    } else {
        if (-not $DryRun) { $nova = $nova.Replace($old6, $new6) }
        Ok "PATCH 6: autonomous mode system prompt injection added"
    }
}

# -- 7. Strip erroneous 'Nova: ' prefix from Nova's outgoing messages ----------
if ($nova -match [regex]::Escape('strip_nova_prefix')) {
    Ok "PATCH 7: Nova prefix stripping already present"
} else {
    $old7 = @'
    async def on_done(full_response: str):
'@
    $new7 = @'
    async def on_done(full_response: str):
        # Strip the erroneous "Nova: " prefix Nova sometimes prepends
        if full_response.startswith("Nova: ") or full_response.startswith("Nova:\n"):
            full_response = full_response[6:].lstrip()
'@
    if (-not $nova.Contains($old7.Trim())) {
        Warn "PATCH 7: on_done anchor not found -- Nova prefix stripping must be added manually"
    } else {
        if (-not $DryRun) { $nova = $nova.Replace($old7, $new7) }
        Ok "PATCH 7: Nova prefix stripping added to on_done"
    }
}

if (-not $DryRun) {
    Set-Content -Path $novaPath -Value $nova -Encoding UTF8
    Log ""
    Log "Done. Restart nova_chat to apply all changes."
} else {
    Log ""
    Log "Dry run complete -- verify the WARN lines above before applying."
    Log "NOTE: patches 1, 3, 4, 6 depend on patch_depth_server.ps1 having been run first."
}
