# patch_claude_client.ps1
# Fixes two critical Claude bugs:
#
#   BUG 1 — Claude hallucinating full conversations:
#     Adds an explicit system prompt telling Claude it is ONE participant,
#     not a narrator. Stops it from roleplaying Cole/Nova/Gemini.
#
#   BUG 2 — nova_bridge parsing Claude's responses for directives:
#     Ensures [EXEC:], [READ:], [WRITE:] etc. are only processed when
#     the speaker is Nova, not when Claude or Gemini happen to mention them.
#
# Run from workspace root: .\PATCHES\patch_claude_client.ps1 [-DryRun]

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== Claude Client + Bridge Directive Guard Patch ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

# ── PATCH 1: claude.py — Add strong group-chat identity system prompt ──────────
$claudePath = Join-Path $root "general_tools\nova_chat\clients\claude.py"
if (-not (Test-Path $claudePath)) {
    Warn "claude.py not found at: $claudePath"
} else {
    $claude = Get-Content $claudePath -Raw -Encoding UTF8

    if ($claude -match [regex]::Escape('CLAUDE_SYSTEM_PROMPT')) {
        Ok "PATCH 1: Claude system prompt constant already present"
    } else {
        # Inject a constant at the top of the file (after imports)
        # Anchor: the first function or class definition
        $systemPrompt = @'

# ── Claude group-chat identity prompt ─────────────────────────────────────────
# Injected as the system message on every call. Prevents Claude from
# roleplaying other participants or generating fake conversation turns.
CLAUDE_SYSTEM_PROMPT = """You are Claude (Anthropic), one participant in a real-time group chat.

The other participants are: Cole (the human user), Nova (a local AI built by Cole), and Gemini.

YOUR ROLE:
- Respond ONLY as yourself. Never write dialogue, thoughts, or actions for Cole, Nova, or Gemini.
- Do not simulate, continue, or narrate what other participants might say next.
- Do not generate blocks labelled "USER:", "ASSISTANT:", "Nova:", "Cole:", "Gemini:", or similar.
- You are a collaborator and advisor -- direct, honest, and focused on what Cole actually asked.

WHAT YOU SEE:
The conversation history shows messages from all participants. Read it to understand context,
then write YOUR response only. Stop as soon as you have said what you need to say.

If you are unsure who asked you something, respond to the most recent message directed at you
or the group. If nothing is directed at you, stay silent (return empty string)."""

'@
        # Find anchor: first 'import' or 'from' line after any module docstring
        $old1 = @'
import anthropic
'@
        $new1 = $systemPrompt + @'
import anthropic
'@
        if (-not $claude.Contains($old1.Trim())) {
            Warn "PATCH 1: 'import anthropic' anchor not found in claude.py -- add CLAUDE_SYSTEM_PROMPT manually"
        } else {
            if (-not $DryRun) { $claude = $claude.Replace($old1, $new1) }
            Ok "PATCH 1: CLAUDE_SYSTEM_PROMPT constant added to claude.py"
        }
    }

    # -- Wire the system prompt into the API call --
    if ($claude -match [regex]::Escape('CLAUDE_SYSTEM_PROMPT')) {
        # Check it's actually used in the API call
        if ($claude -match [regex]::Escape('system=CLAUDE_SYSTEM_PROMPT')) {
            Ok "PATCH 1b: CLAUDE_SYSTEM_PROMPT already wired into API call"
        } else {
            # Find the anthropic.messages.create / stream call and add system=
            $old1b = @'
            system=workspace_context,
'@
            $new1b = @'
            system=(workspace_context + "\n\n" + CLAUDE_SYSTEM_PROMPT) if workspace_context else CLAUDE_SYSTEM_PROMPT,
'@
            if ($claude.Contains($old1b.Trim())) {
                if (-not $DryRun) { $claude = $claude.Replace($old1b, $new1b) }
                Ok "PATCH 1b: system prompt combined with workspace_context"
            } else {
                # Try alternate: no existing system field
                $old1c = @'
            messages=messages,
'@
                $new1c = @'
            system=(workspace_context + "\n\n" + CLAUDE_SYSTEM_PROMPT) if workspace_context else CLAUDE_SYSTEM_PROMPT,
            messages=messages,
'@
                if ($claude.Contains($old1c.Trim())) {
                    if (-not $DryRun) { $claude = $claude.Replace($old1c, $new1c) }
                    Ok "PATCH 1b: system prompt injected into API call (no prior system field)"
                } else {
                    Warn "PATCH 1b: Could not find anchor to wire system prompt into API call -- check claude.py manually"
                }
            }
        }
    }

    if (-not $DryRun) {
        Set-Content -Path $claudePath -Value $claude -Encoding UTF8
    }
}

# ── PATCH 2: server.py — Guard nova_bridge directive parsing to Nova only ───────
$srvPath = Join-Path $root "general_tools\nova_chat\server.py"
if (-not (Test-Path $srvPath)) {
    Warn "server.py not found -- skipping PATCH 2"
} else {
    $srv = Get-Content $srvPath -Raw -Encoding UTF8

    if ($srv -match [regex]::Escape('nova_bridge_guard')) {
        Ok "PATCH 2: nova_bridge guard already present"
    } else {
        # Find where nova_bridge.parse or process is called after a response
        # Anchor: the on_done callback or the place full_response is processed
        $old2 = @'
        await nova_bridge.process(full_response, session_mgr.active)
'@
        $new2 = @'
        # Only parse Nova's responses for directives -- never Claude's or Gemini's
        # nova_bridge_guard: prevents Claude/Gemini from accidentally triggering EXEC/READ/WRITE
        if author == "Nova":
            await nova_bridge.process(full_response, session_mgr.active)
'@
        if ($srv.Contains($old2.Trim())) {
            if (-not $DryRun) { $srv = $srv.Replace($old2, $new2) }
            Ok "PATCH 2: nova_bridge guard added (Nova-only directive parsing)"
        } else {
            # Try alternate call signature
            $old2b = @'
        nova_bridge.process(full_response, session_mgr.active)
'@
            $new2b = @'
        if author == "Nova":
            nova_bridge.process(full_response, session_mgr.active)
'@
            if ($srv.Contains($old2b.Trim())) {
                if (-not $DryRun) { $srv = $srv.Replace($old2b, $new2b) }
                Ok "PATCH 2: nova_bridge guard added (sync variant)"
            } else {
                Warn "PATCH 2: nova_bridge.process anchor not found -- check server.py for bridge call and guard it manually to Nova-only"
            }
        }

        if (-not $DryRun) {
            Set-Content -Path $srvPath -Value $srv -Encoding UTF8
        }
    }
}

Log ""
if ($DryRun) {
    Log "Dry run complete. Check WARNs above before applying."
} else {
    Log "Done. Restart nova_chat to apply."
}
