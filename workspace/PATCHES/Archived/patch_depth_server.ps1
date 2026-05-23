# patch_depth_server.ps1
# Run from workspace root.
# Patches server.py + nova.py for the Fast/Balanced/Deep/Max depth slider
# and the autonomous mode toggle (idempotent -- safe to run again).

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== Depth Slider + Autonomous Mode -- Server Patch ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

# ============================================================
# PATCH 1 -- nova.py  (add max_tokens param to stream_response)
# ============================================================
$novaPath = Join-Path $root "general_tools\nova_chat\clients\nova.py"
if (-not (Test-Path $novaPath)) {
    Warn "nova.py not found at: $novaPath"
} else {
    $nova = Get-Content $novaPath -Raw -Encoding UTF8

    if ($nova -match [regex]::Escape('max_tokens: int = 0,   # 0 = use default')) {
        Ok "nova.py already patched (max_tokens param present)"
    } else {
        $old1 = @'
async def stream_response(
    transcript,
    on_token:       Callable[[str], Awaitable[None]],
    on_done:        Callable[[str], Awaitable[None]],
    on_error:       Callable[[str], Awaitable[None]],
    on_think_token: Optional[Callable[[str], Awaitable[None]]] = None,
    on_progress:    Optional[Callable[..., Awaitable[None]]] = None, # Unused with basic POST but kept for signature
    workspace_context: str = "",
    images: list = None,
):
'@
        $new1 = @'
async def stream_response(
    transcript,
    on_token:       Callable[[str], Awaitable[None]],
    on_done:        Callable[[str], Awaitable[None]],
    on_error:       Callable[[str], Awaitable[None]],
    on_think_token: Optional[Callable[[str], Awaitable[None]]] = None,
    on_progress:    Optional[Callable[..., Awaitable[None]]] = None, # Unused with basic POST but kept for signature
    workspace_context: str = "",
    images: list = None,
    max_tokens: int = 0,   # 0 = use default (MAX_TOKENS_CHAT); set by depth slider
):
'@
        $old2 = @'
                # First loop = chat response; subsequent loops = agentic tool work
                tok_budget = MAX_TOKENS_CHAT if loop_counter == 1 else MAX_TOKENS_AGENT
                full_response = await _fetch_llama_streaming(messages, token_handler, max_tokens=tok_budget)
'@
        $new2 = @'
                # First loop = chat response; subsequent loops = agentic tool work.
                # max_tokens override (from depth slider) applies to the first loop only.
                if loop_counter == 1:
                    tok_budget = max_tokens if max_tokens > 0 else MAX_TOKENS_CHAT
                else:
                    tok_budget = MAX_TOKENS_AGENT
                full_response = await _fetch_llama_streaming(messages, token_handler, max_tokens=tok_budget)
'@
        if (-not $nova.Contains($old1)) {
            Warn "nova.py: stream_response signature anchor not found -- check manually"
        } elseif (-not $nova.Contains($old2)) {
            Warn "nova.py: tok_budget anchor not found -- check manually"
        } else {
            if (-not $DryRun) {
                $nova = $nova.Replace($old1, $new1).Replace($old2, $new2)
                Set-Content -Path $novaPath -Value $nova -Encoding UTF8
            }
            Ok "nova.py patched -> max_tokens param + depth-aware tok_budget"
        }
    }
}

# ============================================================
# PATCH 2 -- server.py  (depth global + WS handlers + wire max_tokens)
# ============================================================
$srvPath = Join-Path $root "general_tools\nova_chat\server.py"
if (-not (Test-Path $srvPath)) {
    Warn "server.py not found at: $srvPath"
} else {
    $srv = Get-Content $srvPath -Raw -Encoding UTF8

    # -- 2a. Add globals after is_processing / _stop_requested --
    if ($srv -match [regex]::Escape('_depth_max_tokens:  int  = 0')) {
        Ok "server.py: _depth_max_tokens global already present"
    } else {
        $old2a = @'
is_processing: bool = False
_stop_requested = asyncio.Event()  # set by STOP; cleared at start of every new response
'@
        $new2a = @'
is_processing: bool = False
_stop_requested = asyncio.Event()  # set by STOP; cleared at start of every new response

# Depth slider: max_tokens for Nova (0 = use nova.py default MAX_TOKENS_CHAT)
_depth_max_tokens:  int  = 0

# Autonomous mode toggle (set via "autonomous_toggle" WS message)
autonomous_mode: bool = False
'@
        if (-not $srv.Contains($old2a)) {
            Warn "server.py: is_processing anchor not found for globals -- check manually"
        } else {
            if (-not $DryRun) {
                $srv = $srv.Replace($old2a, $new2a)
            }
            Ok "server.py: depth + autonomous globals added"
        }
    }

    # -- 2b. Add WS handlers before the "message" handler --
    if ($srv -match [regex]::Escape('"set_depth"')) {
        Ok "server.py: set_depth WS handler already present"
    } else {
        $wsAnchor = '            if data.get("type") == "message":'
        if (-not $srv.Contains($wsAnchor)) {
            Warn "server.py: 'message' WS handler anchor not found -- check manually"
        } else {
            $wsHandlers = @'
            if data.get("type") == "set_depth":
                global _depth_max_tokens
                _depth_max_tokens = int(data.get("max_tokens", 0))
                continue

            if data.get("type") == "autonomous_toggle":
                global autonomous_mode
                autonomous_mode = bool(data.get("enabled", False))
                status_text = "ON" if autonomous_mode else "OFF"
                _amsg = session_mgr.active.add("System",
                    f"[Autonomous Mode: {status_text}]")
                await broadcast({
                    "type": "user_message",
                    "author": "System",
                    "content": f"[Autonomous Mode: {status_text}]",
                    "id": _amsg["id"],
                    "timestamp": _amsg["timestamp"],
                })
                continue

            if data.get("type") == "message":
'@
            if (-not $DryRun) {
                $srv = $srv.Replace($wsAnchor, $wsHandlers)
            }
            Ok "server.py: set_depth + autonomous_toggle WS handlers added"
        }
    }

    # -- 2c. Wire max_tokens into the Nova stream_response call --
    if ($srv -match [regex]::Escape('max_tokens=_depth_max_tokens')) {
        Ok "server.py: max_tokens=_depth_max_tokens already wired"
    } else {
        $old2c = @'
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            workspace_context=ws_context, images=images
        )
'@
        $new2c = @'
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            workspace_context=ws_context, images=images,
            max_tokens=_depth_max_tokens,   # 0 = use nova.py default
        )
'@
        if (-not $srv.Contains($old2c)) {
            Warn "server.py: nova stream_response call anchor not found -- check manually"
        } else {
            if (-not $DryRun) {
                $srv = $srv.Replace($old2c, $new2c)
            }
            Ok "server.py: max_tokens=_depth_max_tokens wired into Nova stream_response"
        }
    }

    if (-not $DryRun) {
        Set-Content -Path $srvPath -Value $srv -Encoding UTF8
    }
}

Log ""
Log "Done. Restart nova_chat (or Nova.exe) to apply changes."
Log "Use the Fast/Balanced/Deep/Max slider in Nova Qt to control response depth."
