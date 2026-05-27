# Nova Chat — UI Overhaul + Wake/Reasoning Session (2026-05-27)

_Written by the Opus session that took over from PASSOVER_2026-05-27_opus.md. Captures the
Nova Chat docking/UI rebuild and two behavioral additions, so nothing is lost on handoff.
All work is in `general_tools/nova_chat/static/index.html` (frontend) and
`general_tools/nova_chat/server.py` (backend) unless noted._

## TL;DR
Cole's priority — the Nova Chat docking/UI upgrade (§6A of the passover) — is largely done and
verified live in his Chrome. The whole window is now a dockable Golden Layout workspace; chat,
sessions, and dashboard panes are all movable widgets. Added an Editor and a Browser-Preview
widget, a Wake button, and live streaming of Nova's autonomous reasoning into the Thoughts pane.

## What shipped

### Docking engine (LIVE on browser reload — no restart)
- **Golden Layout v2** added as a *switchable* engine beside the original Gridstack, gated by
  an `engine` field in `/api/layout` and a **Grid/Golden toggle** in the Widgets menu. Nothing
  was removed — Grid still works; flip back anytime. GL loads via ESM `import()` from CDN
  (esm.sh, jsdelivr fallback); CSS = goldenlayout-base + dark theme, re-themed to the violet
  palette via `.lm_*` overrides in the dashboard `<style>`.
- **Full-window dock**: Golden Layout mounts over the whole `#main-area` (not just the right
  panel). Every module is a movable widget: **Chat** (`#chat-main`), **Sessions** (`#sidebar`),
  Tasks, Live Logs, Thoughts, Tools, Monitor, Files, Eyes, Terminal, **Editor**, **Preview**.
  Flex handles + the old `#right-panel` are hidden in golden mode. Default layout =
  Sessions | Chat | right column (Tasks/Thoughts/Tools tab group + Live Logs).
- **Layout version flag** `GLV=2`: old (right-panel-only) saved golden configs are discarded so
  everyone gets the full-window default; new arrangements persist via `/api/layout`.
- **Tab close (X)** fixed (was oversized/overlapping the title): sized ~13px, tucked right,
  tab padded to make room.
- **Per-pane opacity**: gated behind **View ▸ Widget Opacity** (off by default — Cole disliked
  the always-on hover). When on, a shared slider popover anchors just under the hovered
  widget's tab (above if there's room), dashboard widgets only (Chat/Sessions excluded).
- **Editor widget**: VS-style code viewer. Click any file in the Files widget → opens here with
  syntax highlighting (highlight.js atom-one-dark, lazy-loaded from cdnjs). Toolbar:
  reload / word-wrap / copy. Reads via `/api/files/read`.
- **Browser Preview widget**: URL bar + reload + open-in-tab + iframe. Frontend-only.

### Behavioral additions (NEED A SERVER RESTART to activate)
- **Wake button** (`⏰ WAKE` in the participant bar): `POST /api/wake` sets a module-level
  `_force_wake` asyncio.Event. The autonomy daemon honors it immediately — even if Autonomous
  Mode is off — bypassing the `should_wake` gate, and (on a forced wake with no pending Cole
  message) runs the Phase-3 execution pass *even if she leaned toward rest*, so she actually
  takes her next task step. This is a manual override, NOT a root-cause fix for her
  over-sleeping (see Open threads).
- **Autonomous reasoning → Thoughts pane**: previously her `<think>` reasoning during silent
  autonomy ticks was dropped (to avoid empty chat bubbles). Now `on_think_token` broadcasts it
  on a dedicated channel (`auto_think_start`/`auto_think_token`/`auto_think_end`) that the
  frontend routes ONLY into the Thoughts pane — live in the reasoning block (labeled
  "NOVA — THINKING · AUTONOMOUS") and archived into the Session Log. Never touches chat.
- **Session Log**: now open by default, scrollable, ever-populating (cap 200, shows 80), fed by
  both chat reasoning and autonomous reasoning.
- **`TEXT_EXTS` widened** in server.py so the Editor can open code files (.js/.ts/.html/.css/
  .sh/.xml/.sql/.rs/.go/.c/.cpp/.h, etc.), not just .py/.md/.json/.txt.

## The single restart
One server restart (NovaStart.cmd or in-app Full Restart) activates ALL backend changes at once:
the Wake button (`/api/wake` + daemon force-wake), the autonomous reasoning stream
(`auto_think_*`), and the wider openable file types. `server.py` passes `py_compile`; all four
inline `<script>` blocks in index.html pass `node --check`.

## Verified vs pending
- VERIFIED live in Chrome: Golden engine, full-window dock, chat/sessions as widgets, tab-X fix,
  opacity toggle + anchored popover, Editor opening STATUS.md with highlighting.
- PENDING visual verify (server was mid-restart at session end): Browser-Preview iframe render;
  and the restart-gated features (Wake actually waking her, auto-reasoning streaming live).

## Gotchas confirmed this session
- **Torn mount is real**: right after edits, the Linux sandbox's view of index.html was stale
  (grep/py_compile saw OLD content). It re-syncs after a bit. The **Read/Grep tools are ground
  truth**; only trust bash `node --check`/`py_compile` once markers confirm the mount is fresh.
- The app's viewport is ~2560px CSS-wide (HiDPI); Chrome screenshots are scaled to ~1513px.
  `getBoundingClientRect` + `position:fixed` use the 2560 space — accounted for in the opacity
  popover positioning.

## Open threads / next
- **Why Nova over-sleeps** (root cause behind the Wake button): `executive.should_wake()` keeps
  returning false and/or the decision phase keeps choosing rest despite an open board. This is
  the same unverified decomposition/decision thread flagged in the passover. The Wake button is
  a workaround; the real fix lives in `nova_cortex/executive.py`.
- More Antigravity-style widgets remain candidates: an Artifacts/diffs pane (needs a backend
  git-diff endpoint), a Notes/Scratchpad (could persist in the layout doc), workspace search.
- Readability/contrast: best done with eyes on the live app, not blind.

## §6D Autonomy hardening — findings & actions (this session)
Investigated read-only; executed only the one airtight-safe change. All changes here need a
restart to take effect, and the torn mount blocked sandbox runtime-validation (imports lie) —
so safety is established by static proof + Read-tool ground truth, to be restart-tested by Cole.

- **DONE — decoupled pyautogui from the cortex.** `nova_cortex/__init__.py` was wildcard-importing
  `rules`, `prefrontal_cortex`, `checkin`; `rules.py` does `import pyautogui; pyautogui.size()` at
  module load, so EVERY `from nova_cortex import executive` dragged pyautogui into her brain.
  Removed the three wildcard imports. **Proven safe:** nothing anywhere does `from nova_cortex
  import <X>` except `executive`/`tasking` (submodules, unaffected); `__all__=[]`; `executive.py`
  references none of those names; `tasking.py`'s only hit is the word "prefrontal" in a comment.
  Baseline confirmed in-sandbox: `import nova_cortex` failed at `rules.py:88 import pyautogui`.
  REVERT if ever needed = re-add the 3 import lines. Restart-test: `from nova_cortex import
  executive, tasking` must still work and llama/chat must boot.
- **rules.py / checkin.py / prefrontal_cortex.py**: confirmed retired old-architecture, now
  unimported by the live cortex. Only other reference is `nova_motor/motor_cortex.py` (itself
  dead). Left on disk (archive-don't-delete). Optional next step: move them + `nova_motor` to an
  `_admin` archive — low urgency now that they're off the live path.
- **nova_motor, nova_memory**: DEAD — nothing live imports them (the `server.py` "nova_motor"
  mention is a comment). Archive candidates.
- **nova_senses {eyes, vision, proprioception}**: scaffolded; `nova_senses/__init__.py` has NO
  wildcard imports, so they're NOT auto-loaded — no coupling. `vision.py` imports pyautogui only
  if explicitly imported (nothing live does). Safe to leave as-is until the GUI-automation phase.
- **nova_status**: LIVE on the READ side — `server._bg_nova_status_poll()` calls
  `nova_cortex.nova_status.read_summary()` every 30s and injects it to the AIs. OPEN: confirm the
  WRITE/`update()` path still runs so that summary isn't stale (passover concern). Needs the
  running system — left for Cole.
- **NCL `@module` subsystem**: the PARSER is live/wired (`server.py` imports `is_ncl_message`;
  `orchestrator.py` + `nova_lang.py` are in the message flow). The module TARGETS
  (`@eyes`/`@thinkorswim`) are the dormant trading/vision pieces. Harmless while no modules are
  registered; revisit at the trading-autonomy phase.
