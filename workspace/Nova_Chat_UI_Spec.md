# Nova Chat UI Design Specification
**Status:** Research & Planning Phase  
**Last Updated:** 2026-05-09  
**Purpose:** Drive a phased, methodical redesign of the nova_chat HTML interface to production quality. No code is written without a spec entry justifying it.

---

## Part 1 — Reference Analysis

### 1.1 Claude.ai Web Chat (claude.ai)

Carefully observed design patterns:

**Layout**
- Strict 2-column: narrow left sidebar (≈260px) + full-height main chat. Nothing else.
- No right panel. No tabs. Radical simplicity.
- The sidebar is collapsible on narrower windows.
- Statusbar: none. All status is inline or in the sidebar header.

**Sidebar**
- Top: Claude logo + model selector (dropdown pill — "Claude Sonnet 4.x" with a ▾ caret).
- Below logo: "New chat" button — full-width, subtle background, left-aligned ✦ icon + "New chat" text.
- Section label "Recents" in small all-caps muted text.
- Conversation list: each item is a single line — title truncated. No timestamps, no icons, no session dots.
- Active item: slightly brighter background + white text. No border, no glow.
- Hover: item background lightens slightly. A ••• (ellipsis) icon appears at the right edge.
- Ellipsis menu on hover: opens a small popover with "Rename", "Delete" options.
- No inline rename/delete buttons — they are behind the ellipsis.
- "Projects" section below Recents: collapsible group. Project items have a folder icon.
- Bottom of sidebar: user avatar circle + name. Click opens account/settings menu.

**Chat area**
- No tab bar. One session per view — switch via sidebar click.
- Message layout: sender label (bold "You" or "Claude") then content below it — no avatar, no timestamp shown by default.
- Messages are wide, centered, max-width ~700px, with generous left/right margin.
- Code blocks: dark background, syntax-highlighted, copy button top-right, language label.
- Streaming cursor: a blinking | character at the very end of the stream.
- Think blocks: NOT visible to the user in Claude.ai by default (reasoning is hidden).
- No tool cards visible inline — tool use is abstracted away.

**Input area**
- A pill-shaped multiline textarea at the bottom, centered, ≈700px wide, floating (not full-width).
- Send button inside the pill on the right: circular arrow-up icon, enabled only when there's text.
- Attach (paperclip), "Projects" context (book icon), voice button on the left inside the pill.
- Below the pill: small row with model selector shortcut and formatting toggle.
- No autonomous toggle, no depth slider, no stop button (stop is shown INSIDE the send button as a ■ when streaming).
- Shift+Enter = new line, Enter = send.

**Participant system**
- None (it's a single-agent app). Not applicable to Nova.

**Visual polish details**
- Font: Claude's own system font stack — -apple-system, Segoe UI, etc. NOT Inter.
- Text is very slightly warm (not pure white), background is very slightly warm dark.
- Scrollbar: hidden until hover, then a 3px soft thumb.
- Hover states: 60-80ms transitions, subtle.
- No toasts — feedback is inline (e.g., copy button changes to a checkmark).
- Zero decorative elements. No glows, no gradients on UI chrome, no borders except where truly needed.
- Animations: very subtle — fade in/up for new messages (≈150ms), nothing else animated.

---

### 1.2 Claude Code Desktop App (2026 Redesign)

**Layout philosophy: Pane Orchestration**
- The core metaphor is panes — independent, draggable panels arranged in a 2D grid.
- You drag a pane by its header bar to reposition it anywhere.
- Available panes: Chat, Terminal, File Editor, Diff Viewer, Preview (HTML/PDF), Plan, Tasks, Subagent.
- Not all panes are always open — you open what you need.
- Pane headers show: pane name, a collapse/expand button, and a ✕ close button.
- When collapsed, a pane becomes a narrow strip you can click to re-expand.

**Session sidebar (left)**
- Wider than Claude.ai's — more like 300px.
- Shows all running sessions with status indicators (idle, running, waiting for input).
- Sessions can be filtered by status, project, or environment.
- Sessions can be grouped by project.
- Active session is highlighted with a colored left border.
- A "New Session" button at the top.
- Each session shows: session name + repo/directory name + status icon.
- Right-clicking a session gives: Rename, Duplicate, Archive, Delete.

**Top area**
- Very thin top bar: Mode switcher (Chat / Cowork / Code) on the left as icon-only buttons.
- Right side: settings gear, account avatar.
- NO traditional File/Edit/View menu bar.

**Pane interaction details**
- Drag the header of any pane to move it. A blue drop zone appears where it will land.
- Panes snap to a grid layout.
- You can have multiple panes side by side or stacked.
- Each pane has its own scrollbar.
- Pane resize: drag the border between adjacent panes.

**View modes**
- Three verbosity modes for tool calls: Verbose (shows every tool call), Normal (shows summaries), Summary (shows only results).
- Toggled via a small control in the chat pane header.

**Side chat**
- Cmd+; opens a side chat overlaid on the current view.
- Side chat inherits context from the main thread but adds nothing back.
- Used for quick questions without polluting the main task context.

**Key UX patterns**
- No modal dialogs for anything routine. Actions are inline or in context menus.
- Status is shown in the pane headers, not in a global statusbar.
- File tree updates live as the agent creates/modifies/deletes files.
- The diff viewer shows changes in real time as they happen.

---

### 1.3 Antigravity (Google — Agentic IDE)

Less directly applicable, but notable patterns:
- Artifact cards: agent outputs appear as tangible cards (task list, plan, screenshot) that you can comment on.
- Knowledge base: agent can save snippets for future use — visible as a browsable panel.
- Multi-model: model selector is prominent, easy to switch mid-task.
- Agent status: clear visual state — Planning / Executing / Waiting / Done — shown in a persistent status area.

---

## Part 2 — Current State Audit

### What works in Nova Chat today
- WebSocket connection and reconnect loop
- Session init, switch, new, delete (WS + REST)
- Message streaming with streaming cursor
- Think block (collapsible reasoning accordion)
- Tool execution cards (inline + right panel feed)
- Autonomous mode toggle
- Depth / max-tokens slider
- Image attach + drag-drop
- Thought cards polling (/api/thoughts)
- Monitor panel (tokens/s, model, uptime, vigilance)
- Export session
- Settings (temp, top-p via Advanced menu)
- File tree panel (polling /api/files/tree)
- Logs viewer
- Session rename (inline double-click + modal)
- Session delete (modal)
- Right-click context menu on sessions
- Keyboard shortcuts (Ctrl+T, Ctrl+B, Ctrl+E, Ctrl+K, Escape)
- Toast notifications
- Markdown renderer (code blocks, bold, lists, tables, headers, blockquotes)
- Eyes panel (static grid, no streaming)

### What is broken or regressed
- [ ] **Nova.eyes no longer streams** — previous Qt app pushed screenshots live; HTML version has a static grid with no WebSocket updates wiring it to the eyes data
- [ ] **Pane resize doesn't work** — initResize() attached to CSS variable approach; the right panel ignores the drag because `width: var(--panel-w)` conflicts with direct style.width assignment; sidebar similar issue
- [ ] **Server doesn't start alongside Nova** — this was a NovaLauncher responsibility, not index.html; need to verify NovaLauncher still starts gateway and nova_chat in sequence
- [ ] **Agent mute buttons are buried in Agents menu** — not discoverable or quick to press; muting an agent mid-conversation requires 2 clicks + dropdown hunt
- [ ] **No participant status indicators visible in main UI** — user can't see at a glance which agents are online without opening the Agents menu
- [ ] **Services menu redundancy** — "Nova Chat" and "Gateway" are the same process from the user's perspective; showing both confuses rather than informs
- [ ] **llama toggle endpoint doesn't actually start llama** — it just reports that you need to start it manually; the button is misleading

### What is missing vs the Qt widget app
- [ ] Per-agent mute with clear visual state visible without opening a menu
- [ ] One-click server/service indicators in a persistent location (not buried in a dropdown)
- [ ] Nova.eyes streaming (live screenshots pushed via WebSocket)
- [ ] Tooltip / hover explanations on controls (what does "Depth" mean? What does "Autonomous" mean?)
- [ ] Visual distinction between autonomous-mode messages and direct-reply messages
- [ ] Terminal panel (was in Qt app as a dockable pane)
- [ ] Session search / filter in sidebar
- [ ] Verbosity control (Verbose / Normal / Summary for tool calls — like Claude Code's view modes)

---

## Part 3 — Design Principles

These govern every decision in the phased implementation. If a proposed feature conflicts with one, we discuss before building.

1. **One thing at a time, clearly.** Every UI element should have exactly one obvious purpose. If you have to explain what a button does, it's poorly placed or labelled.

2. **Progressive disclosure.** Show the minimum needed by default. Advanced controls live behind a clearly-labelled access point, not buried in a dropdown that looks like something else.

3. **Status is always visible, never buried.** Connection state, agent state, active session name — these must be readable at a glance without any clicks.

4. **Actions are one-click unless they're destructive.** Muting an agent, toggling a mode — one click. Deleting a session — one click to initiate, one click to confirm.

5. **No redundant information.** If something is shown once, it isn't shown again somewhere else. Gateway + Server = same thing; show one.

6. **Hover tooltips everywhere a non-obvious control exists.** `title=""` at minimum. Ideally a richer hover card.

7. **Regressions are P0.** Eyes streaming is broken. Fix before adding anything new.

---

## Part 4 — Phased Implementation Plan

Each phase has a clear done-state. No phase begins until the previous phase's done-state is verified by running Nova.bat and manually testing every item.

---

### Phase 0 — Fix Regressions (P0, ~1 hour)
**Goal:** Nothing that worked before is broken.

Items:
- [ ] **0.1** Fix Nova.eyes streaming — add `case 'eyes_update':` to the WebSocket message handler; the server already sends this event; the HTML was not listening. Display each incoming screenshot in the eyes grid (prepend, keep last 8).
- [ ] **0.2** Fix pane resize — rewrite initResize() to use flex `flex-basis` instead of CSS variables; this is what browsers actually respect during a flex layout drag.
- [ ] **0.3** Verify NovaLauncher still starts gateway + nova_chat in sequence (read NovaLauncher.py — do not change it unless broken).
- [ ] **0.4** Remove the misleading llama Toggle button; replace with an honest status-only indicator and a label "Start via llama.bat".

**Done-state:** Eyes panel shows live screenshots when Nova takes them. Dragging the sidebar handle visibly moves the border. Dragging the panel handle visibly moves the border. No llama toggle button.

---

### Phase 1 — Persistent Participant Bar (~2 hours)
**Goal:** Agent status is always visible; mute is one click from anywhere.

Design:
- A slim horizontal bar sits between the menu bar and the session tabs. Height: 32px.
- It contains: one pill per participant (Nova, Claude, Gemini, Cole).
- Each pill shows: colored dot (live status) + agent name + mute icon (🔊/🔇).
- Dot colors: green = online, amber = degraded/busy, grey = offline.
- Clicking a pill's mute icon: immediately sends `mute_agent` WS message, toggles the icon, grays out the pill.
- Offline agents: pill is dimmed (opacity 0.3), mute icon hidden.
- Cole's pill: shows "You" — always online, no mute button.
- The bar has no other controls. It is ONLY for participant status.
- WS event `status` updates all dots. WS event `autonomous_state` toggles the auto indicator (see below).
- A small "AUTO" badge appears in the bar right-aligned when autonomous mode is on.

**Done-state:** At any point during a conversation, you can see who is online and mute any agent with one click, without opening any menu.

---

### Phase 2 — Clean Services Indicator (~1 hour)
**Goal:** Server status is visible at a glance; one click to act; zero redundancy.

Design:
- Remove the "Services" dropdown menu entirely.
- In the menu bar's right section (currently shows "Connected"), add two small inline indicators:
  - `● Nova` — dot color = green (WS connected) or red (disconnected). Clicking it does nothing (server is managed by NovaLauncher — explain this in a tooltip).
  - `● llama` — dot color = green (port 8080 responds) or grey. Clicking it opens a small popover saying "Start llama via llama.bat or your launcher. Port 8080." — not a toggle, just honest information.
- Remove "Gateway" as a concept visible to the user (it's an internal process).
- The menu bar now shows: `◈ Nova | File ▾ | View ▾ | Agents ▾ | Advanced ▾ | [spacer] | ● Nova  ● llama | Connected | Session Name`

**Done-state:** At a glance, you can see Nova server status and llama status. No toggle buttons that don't work. No redundant "Gateway" entry.

---

### Phase 3 — Tooltip System (~1 hour)
**Goal:** Every non-obvious control has a hover explanation.

Design:
- Use a custom tooltip component (not just `title=""`) — a small dark bubble that appears 500ms after hover, 200ms above the element, with up to 40 words of plain English explanation.
- Tooltips to add (at minimum):
  - **Autonomous** toggle: "When ON, Nova plans and acts in multi-step loops without asking for your approval after each step. Turn OFF to require explicit confirmation before each action."
  - **Depth** slider: "Maximum tokens Nova can generate in a single response. 0 = model default. Increase for very long tasks."
  - **Temperature** (Advanced): "Controls randomness. 0 = deterministic and focused. 2 = highly creative and unpredictable. Start at 0.7."
  - **Top-P** (Advanced): "Alternative randomness control. Lower = picks from fewer token choices. Usually leave at 0.9."
  - **Stop button**: "Immediately stops the current generation."
  - **Mute button** on each agent pill: "Mute this agent — Nova will not route messages to it until unmuted."
  - Each panel tab (Thoughts, Tools, Monitor, Files, Eyes): brief description of what lives there.

**Done-state:** Hovering any non-obvious control for 0.5 seconds shows a plain-English tooltip.

---

### Phase 4 — Sidebar Polish (~1 hour)
**Goal:** Session list is clean, fast, and powerful.

Design:
- Add a search/filter input at the top of the session list (a small `🔍` icon that expands to an input on click).
- Sessions are filtered in real-time as you type (client-side, no server call needed).
- Each session item: name (truncated) + a very faint last-message timestamp on the right (shown only on hover).
- The ••• ellipsis icon (appears on hover, right side) opens a small popover: Rename / Duplicate / Delete. No inline buttons.
- Remove the two sidebar footer icon buttons for Export and Logs — these are already in the File menu. Keep only the Panel toggle button.
- Sidebar header: just the Nova logo pulse ring + name + state. No extra controls.

**Done-state:** Sidebar feels as clean as Claude.ai's sidebar. Session operations are discoverable via ••• menu. Search works.

---

### Phase 5 — Verbosity Control (~45 min)
**Goal:** User can choose how much tool call detail they see, like Claude Code's Verbose/Normal/Summary modes.

Design:
- A small 3-way toggle in the chat pane header (right side, next to session tabs): `[Verbose] [Normal] [Summary]` — styled as a segmented control.
- **Verbose**: shows all tool cards inline in messages as they arrive.
- **Normal**: collapses multiple tool calls into one summary line per response (e.g., "5 tools used ▸"). Click to expand.
- **Summary**: hides all tool cards inline. Tool results are only in the Tools panel.
- Default: Normal.
- State is remembered in localStorage (the one UI state worth persisting).

**Done-state:** Users who find tool cards noisy can switch to Summary. Users who want full transparency can switch to Verbose.

---

### Phase 6 — Eyes Streaming Polish (~30 min)
*Depends on Phase 0 fixing the basic stream.*
**Goal:** Eyes panel feels live, not static.

Design:
- Each screenshot card in the Eyes panel shows:
  - The image (max-height 120px, object-fit cover, click to zoom)
  - Timestamp (relative: "2 minutes ago")
  - A tiny label if the image has metadata (e.g., "Screen capture" / "Clipboard")
- When a new screenshot arrives, the panel tab shows a subtle dot indicator ("Eyes ●") if it's not the active panel.
- Maximum of 12 screenshots retained in the grid.
- A "Clear" button at the top right of the Eyes panel.

**Done-state:** Eyes panel shows live screenshots with timestamps. New screenshots are indicated even when the panel isn't active.

---

### Phase 7 — Terminal Panel (~2 hours)
*This is a new feature, not a fix. Do not start until Phases 0–3 are done.*
**Goal:** Restore the terminal pane that existed in the Qt app.

Design:
- A new "Terminal" panel tab (right panel, after Eyes).
- Displays a read-only stream of Nova's terminal output (stdout from run_command tool calls, formatted with ANSI stripping).
- NOT an interactive terminal — Nova is in control of the terminal; this is a window to observe it.
- A "Clear" button. Auto-scrolls to bottom.

**Done-state:** When Nova runs shell commands, the output appears in the Terminal panel in real time.

---

## Part 5 — What We Are NOT Building

To keep scope controlled:

- ❌ Drag-and-drop pane rearrangement (like Claude Code) — Nova Chat is a chat app, not an IDE. Fixed 3-column layout is correct for its purpose.
- ❌ Multiple simultaneous sessions displayed side by side — Nova has one active session at a time; this is by design.
- ❌ Integrated file editor — files are managed through Nova's tools, not directly through the UI.
- ❌ Diff viewer — not relevant to Nova Chat's current use case.

---

## Part 6 — Implementation Rules

1. **One phase at a time.** Complete Phase 0 fully before touching Phase 1.
2. **Every phase starts with a review of the done-state from the previous phase** (run Nova.bat, manually test each item).
3. **No phase touches code outside its defined scope** without creating a new spec entry first.
4. **CSS changes are minimal and additive** — don't rewrite the whole stylesheet to fix one thing.
5. **JavaScript changes are surgical** — fix the broken function, don't restructure the whole file.
6. **If something new is discovered** (e.g., a WS event we forgot about), it goes into the spec first, then into the appropriate phase, then into code.

---

## Part 7 — Open Questions

These need answers before the relevant phase can begin:

- **Q1 (Phase 0.1):** What is the exact WebSocket message type for eyes screenshots? Is it `eyes_update`, `screenshot`, or something else? → Check nova_chat/server.py.
- **Q2 (Phase 0.3):** Does NovaLauncher.py still start both gateway and nova_chat? When was this last verified? → Read NovaLauncher.py.
- **Q3 (Phase 1):** Does the `status` WS message include all four participants (Nova, Claude, Gemini, Cole) or just the AI agents? What fields does it contain per participant?
- **Q4 (Phase 7):** Is there a WS event that streams terminal output, or does it need to be added to the server?

---

## Appendix A — Files Involved

| File | Role |
|------|------|
| `general_tools/nova_chat/static/index.html` | The entire HTML UI |
| `general_tools/nova_chat/server.py` | FastAPI server, WS handler, all REST endpoints |
| `general_tools/NovaLauncher.py` | Starts gateway + nova_chat; manages process lifecycle |
| `general_tools/gateway.py` | Background gateway; `/api/thoughts`, `/api/files`, `/api/logs`, etc. |
| `general_tools/nova_qt/main.py` | pywebview wrapper; opens the browser window |
| `workspace/Nova_Chat_UI_Spec.md` | This document |

---

## Appendix B — WS Message Reference

**Incoming (server → client):**

| Type | Trigger | Key Fields |
|------|---------|-----------|
| `status` | Participant state change | `participants: [{name, status}]` |
| `sessions_init` | On WS connect | `sessions: [...]`, `active_id` |
| `session_switched` | After switch | `session_id`, `history: [...]` |
| `sessions_updated` | After new/delete | `sessions: [...]` |
| `user_message` | User message echoed back | `author`, `content`, `id`, `images` |
| `token` | Streaming response chunk | `author`, `id`, `token` |
| `think_token` | Streaming thought chunk | `id`, `token` |
| `done` | Response complete | `id` |
| `processing` | Start/stop indicator | `active: bool` |
| `error` | Server error | `message` |
| `autonomous_state` | Mode changed | `enabled: bool` |
| `nova_status` | Periodic heartbeat | `pulse`, `model`, `tps`, `uptime`, `active_task`, `errors` |
| `tool_executed` | Tool completed | `tool`, `result`, `error` |
| `thought_update` | Thought card change | `id`, `action`, `name`, `priority`, `status`, `summary`, `progress`, `step` |
| `vigilance` | Nova attention state | `state` (sleeping/awake/working), `reason` |
| `export_ready` | Export completed | `claude_export` |
| `pong` | Keepalive reply | — |
| `eyes_update` *(Q1)* | New screenshot | TBD |

**Outgoing (client → server):**

| Type | Purpose | Key Fields |
|------|---------|-----------|
| `new_session` | Create new session | — |
| `switch_session` | Switch to session | `session_id` |
| `message` | Send chat message | `content`, `autonomous`, `images` |
| `stop` | Stop generation | — |
| `autonomous_toggle` | Toggle auto mode | `enabled: bool` |
| `set_depth` | Set max tokens | `max_tokens` |
| `set_params` | Update gen params | `temperature`, `top_p` |
| `mute_agent` | Mute/unmute agent | `agent`, `muted: bool` |
| `export_context` | Request export | — |
| `rename_session` | Rename session | `session_id`, `name` |
| `ping` | Keepalive | — |

---

*Next action: Answer the Open Questions (Part 7), then begin Phase 0.*
