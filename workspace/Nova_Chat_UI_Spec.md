# Nova Chat UI Design Specification
**Status:** Active Development  
**Last Updated:** 2026-05-09 (Session — Three-App Comparison Update)  
**Purpose:** Drive a phased, methodical redesign of the nova_chat HTML interface to production quality. Every feature implemented has a spec entry, a comparison reference, and a clear done-state.

---

## Part 1 — Three-App Comparison

This section documents what each reference app does best, observed live on Cole's machine. Every feature implemented in Nova's roadmap is sourced from one of these three reference points.

---

### 1.1 Claude Desktop (claude.ai)
**Category:** Polished consumer AI chat  
**Architecture:** Electron/web app, cloud-only, single model at a time

**What it does best:**

**Interaction polish**
- Every UI element responds correctly to the OS. Right-click shows a real context menu (Copy, Paste, Select All, Look Up). Keyboard shortcuts (Cmd+C, Cmd+V, Cmd+A) all work.
- Text selection behavior is indistinguishable from a native text editor.
- Scrollbars appear only on hover — a 3px thumb, soft fade in/out.
- Hover states are 60–80ms, subtle, consistent everywhere.
- No stray broken states. Nothing in the UI is ever empty without an explanation.

**Message quality**
- Full markdown rendering: headers, bold, italic, code blocks, tables, blockquotes, numbered lists, nested bullets.
- Code blocks: dark background, language label top-left, copy button top-right. Copy button changes to a checkmark on success — no toast.
- Streaming cursor: a blinking `|` at the stream head. Nothing else animated during streaming.
- Think blocks are intentionally hidden from users — Nova should consider whether to surface them inline.

**Input area**
- Pill-shaped multiline textarea, centered, ~700px max-width, floating.
- Send button is inside the pill — circular arrow-up icon. Becomes a stop square during streaming.
- Attach, voice, project-context on the left inside the pill.
- Shift+Enter = new line, Enter = send.
- Feedback is always inline. No toasts for copy, no modal for confirmation of harmless actions.

**Layout discipline**
- Strict 2-column: sidebar + chat. No right panel. No tabs except in the sidebar.
- Radical simplicity — if something is visible, it has a purpose.
- No status bar. Connection state is never shown because it's always assumed stable.
- No redundant information anywhere.

**Sidebar**
- Model selector pill at the top (Claude 3.x + ▾).
- "New chat" button full-width with a ✦ icon.
- Session list: one line per session, title truncated. No timestamps, no icons by default.
- Active item: slightly brighter background, white text.
- Hover: item background lightens + ••• ellipsis appears at right edge.
- Ellipsis opens: Rename, Delete. Hidden behind hover to keep the list clean.
- Projects section (collapsible group with folder icon).
- Bottom: user avatar + account menu.

**What Nova should steal from Claude Desktop:**
- [ ] Copy button behavior (inline checkmark, no toast)
- [ ] Send/stop unified button (one button, two states)
- [ ] Ellipsis-behind-hover on session items
- [ ] Pill-shaped input area styling
- [ ] All text interactions working (right-click, select, copy) ← DONE ✅
- [ ] Zero redundant information principle
- [ ] Hover tooltip pattern for non-obvious controls

---

### 1.2 Antigravity (VS Code + AI)
**Category:** Agentic IDE — AI embedded in a full code editor  
**Architecture:** VS Code fork, local + cloud models, full file system access

**What it does best:**

**File system integration**
- Left panel: full file explorer with folder expand/collapse, file type icons, context menus (New File, New Folder, Rename, Delete, Copy Path).
- Active file is highlighted in the tree. Tree updates live as files are created/modified by the AI.
- Multiple files open as tabs. Tabs show modified indicator (dot) when unsaved.

**Terminal integration**
- Bottom panel: real PowerShell/bash terminal at the project root. Interactive — you can type.
- Terminal persists across AI responses. AI output goes to terminal and you see it live.
- Multiple terminal tabs (PowerShell 1, PowerShell 2).

**Agent scope awareness**
- The AI panel shows the current scope: "Project_Nova" — derived from the open folder.
- `@file` mentions in the chat attach specific files as context for the AI.
- `/workflow` commands trigger predefined multi-step AI workflows.
- Agent can reference any open tab as context automatically.

**Status bar richness**
- Bottom status bar: git branch (master) + staged/unstaged indicators, error count, warning count, encoding (UTF-8), language mode (PowerShell, Python, etc.), a settings shortcut.
- All information is always visible, always accurate.
- Every status item is clickable to take action (click branch → git panel; click errors → problems panel).

**Multi-panel layout**
- Left: File Explorer (collapsible)
- Center: Code Editor (multi-tab)
- Right: AI Agent panel
- Bottom: Terminal / Problems / Output / Debug Console (tabbed)
- Every border between panels is draggable to resize.

**Agent panel**
- Compact vertical panel on the right edge.
- Chat input at the bottom with "@ to mention, / for workflows" placeholder.
- Model selector pill (Gemini 3 Flash ▾) with Plan mode toggle.
- Microphone button for voice input.
- Agent tasks show as collapsible items above the input: "Optimizing Nova's Inference Engine — 1m ago".

**What Nova should steal from Antigravity:**
- [ ] Clickable status bar items (every status = action)
- [ ] Git branch indicator in status bar
- [ ] Interactive terminal panel (not just read-only output) ← Phase 7 stretch goal
- [ ] `@file` context mentions in chat input
- [ ] Agent scope display (show current session name prominently)
- [ ] Task cards persisting above input with timestamps
- [ ] File tree updates live as Nova modifies files ← DONE ✅ (FILES tab working)
- [ ] Model selector pill visible at all times, not buried in menus

---

### 1.3 Nova Chat (Current — as of 2026-05-09)
**Category:** Multi-AI orchestration chat + autonomous agent interface  
**Architecture:** FastAPI + WebSocket server, pywebview (Edge WebView2), HTML/CSS/JS UI

**What Nova does uniquely that neither Claude Desktop nor Antigravity does:**
- Multi-model real-time group chat: Nova (local LLM), Claude (Anthropic API), Gemini (Google API) all respond in the same conversation thread simultaneously.
- Local-first AI: Nova runs entirely on Cole's hardware. No cloud dependency for the core.
- Autonomous heartbeat: Nova drives herself in a continuous loop without user prompts. Claude Desktop and Antigravity both require user input for every response.
- Tool execution visibility: every tool Nova uses is surfaced with status (the TOOLS panel shows live execution, not abstracted away like Claude Desktop does).
- Thought monitoring: Nova's internal reasoning (THOUGHTS panel) is visible and inspectable.
- Per-agent muting: individual participants can be silenced mid-conversation.
- Inference depth control: max_tokens slider gives direct control over response length.
- Nova bridge directives: [WRITE:], [EXEC:], [READ:] let Nova directly modify files and run commands, with results injected back into conversation.

**What is confirmed working today (2026-05-09):**
- ✅ Boots cleanly via Nova.bat (pywebview window, server on :8765, gateway on :18790)
- ✅ WebSocket connects — "Connected" pill is accurate
- ✅ Menu bar (Nova / File / View / Agents / Services / Advanced)
- ✅ Multi-participant bar with Nova/Claude/Gemini status dots and muting
- ✅ THOUGHTS / TOOLS / MONITOR / FILES / EYES panel tabs all present
- ✅ TOOLS panel shows correct empty state ("No tool calls yet. Executions stream in live.")
- ✅ FILES tab loads full workspace directory tree (fixed: server returns root node object, JS now uses `.children`)
- ✅ Pane resize by drag (fixed: switched mousedown→pointerdown + setPointerCapture for WebView2)
- ✅ Right-click context menu — Copy, Cut, Paste, Select All (fixed: custom JS menu, pywebview blocks native)
- ✅ GW and LLM status dots in status bar (GW = gateway, LLM = llama.cpp)
- ✅ Services menu shows live Nova/llama.cpp status
- ✅ Autonomous ON toggle
- ✅ Inference depth slider (Normal/Try/Infer)
- ✅ Session list sidebar with session management
- ✅ Code blocks with copy button and language label

**What is still broken or missing (2026-05-09):**
- ❌ MONITOR tab mostly empty (requires llama.cpp running on :8080)
- ❌ EYES tab — never tested with live Nova screenshot data
- ❌ F5 / Ctrl+R reload doesn't work in pywebview (shortcuts only wired for Qt fallback)
- ❌ No model selector pill visible at all times (buried in Advanced menu)
- ❌ No token counter / context window display
- ❌ Session search/filter not implemented
- ❌ Depth/verbosity controls have no tooltips explaining them
- ❌ Tool cards haven't been tested with real Nova activity (only HEARTBEATs seen)
- ❌ EYES tab streaming never tested live
- ❌ No git branch indicator or file-change indicator
- ❌ Markdown rendering only tested on HEARTBEAT text (no rich messages seen yet)
- ❌ Send button doesn't become a stop button during streaming (separate ⏹ button instead)
- ❌ No `@file` context mention system

---

## Part 2 — Design Principles

These govern every decision in the phased implementation. If a proposed feature conflicts with one, discuss before building.

1. **Nova's uniqueness is the product.** Don't sand off what makes Nova special (multi-model, local-first, autonomous, tool-visible) to imitate Claude Desktop. Borrow polish, not personality.

2. **One thing at a time, clearly.** Every UI element has exactly one obvious purpose. If you have to explain what a button does, it's poorly placed or labelled.

3. **Progressive disclosure.** Show the minimum needed by default. Advanced controls live behind a clearly-labelled access point.

4. **Status is always visible, never buried.** Connection state, agent state, active session name — readable at a glance without any clicks.

5. **Actions are one-click unless destructive.** Muting, toggling mode — one click. Deleting a session — initiate + confirm.

6. **No redundant information.** If something is shown once, it isn't shown again somewhere else.

7. **Hover tooltips everywhere a non-obvious control exists.**

8. **Regressions are P0.** If something worked before and doesn't now, fix it before adding anything new.

9. **Tested before marked done.** Every phase requires a live Nova.bat session + manual verification of the done-state.

---

## Part 3 — Phased Implementation Plan

Each phase has a clear done-state. No phase begins until the previous phase's done-state is verified by running Nova.bat and manually testing every item.

**Current progress:**
- Phase 0 (regressions): ✅ done — resize ✅, right-click ✅, FILES ✅, eyes_frame ✅ (already wired), Reload UI ✅ (F5 + View menu)
- Phase 1 (participant bar): ✅ done (participant bar already built and working)
- Phase 2 (services indicator): ✅ done (GW + LLM dots in status bar)
- Phase 3 (tooltip system): ✅ done — 500ms delay, 15+ data-tooltip attributes on all key controls
- Phase 4 (sidebar polish): ✅ done — active session left-border accent, ellipsis-on-hover already present
- Phase 5 (input polish): ✅ done — unified send/stop button (purple ↑ → red ⏹), per-message 📋 copy button on hover
- Phase 6 (model selector): ✅ done — pill in tab bar, Claude Sonnet/Opus + Gemini Flash/Pro runtime switching via set_model WS; server + client both updated
- Phase 7 (status bar): ✅ done — token counter (chars÷4 → "~1.2k ctx") in status bar right, resets on session switch
- Phase 8 (@file mentions): ✅ done — type @ in input → filtered file picker, arrow key navigation, chip bar, file content prepended on send (max 3)
- Phase 9 (thought cards): ✅ done — collapsible tcard strip above input during Nova's active thoughts, auto-clears on processing_end
- Phase 10 (terminal output): ✅ done — bridge exec results broadcast as terminal_output WS → colored lines in Terminal tab + unread dot

---

### Phase 0 — Fix Remaining Regressions (P0)
**Remaining items only — resume from current state**

- [ ] **0.4** Replace misleading llama "Start/Stop" buttons in Services menu with honest indicators. The server sends `llama_status` but can't actually start llama — say so. Replace Start/Stop with a label: "Start via llama.bat" and a copy-path button.
- [ ] **0.5** Wire EYES panel to `eyes_update` WebSocket message. Server sends it — client must handle it. Each incoming screenshot goes into the eyes grid (prepend, keep last 12). Show timestamp relative ("2 min ago").
- [ ] **0.6** Add a "F5 → reload" mechanism for pywebview. Since WebView2 doesn't fire F5 through our Python shortcuts, inject a JavaScript `window.location.reload()` call via the Nova menu → "Reload UI" menu item.

**Done-state:** EYES panel shows live screenshots when Nova takes them. No misleading llama toggle. Reload UI exists in Nova menu.

---

### Phase 3 — Tooltip System
**Goal:** Every non-obvious control has a hover explanation. Borrow Claude Desktop's pattern of explaining everything inline.

Design:
- Custom tooltip component (not `title=""`): a small dark bubble, 500ms delay, appears above element, max 40 words plain English.
- Tooltips to implement (minimum):
  - **Autonomous toggle:** "When ON, Nova plans and acts in multi-step loops without asking for approval. Turn OFF to require confirmation before each action."
  - **Depth slider:** "Max tokens Nova can generate per response. 0 = model default. Increase for complex long tasks."
  - **Normal/Try/Infer:** "Response length hint sent to Nova. Normal = balanced. Concise = brief. Verbose = thorough."
  - **Stop button:** "Immediately cancel all in-flight AI responses."
  - **GW dot:** "Nova gateway server (port 18790). Manages Discord, tools, scheduler. Starts automatically with Nova.bat."
  - **LLM dot:** "Local LLaMA model (port 8080). Run llama.bat to start. Required for Nova's local inference."
  - **Panel tabs (Thoughts/Tools/Monitor/Files/Eyes):** brief description of each.
  - **Mute buttons on participant pills:** "Mute this agent — Nova will not route messages to it until unmuted."
  - **AUTO badge:** "Autonomous mode is active — Nova is driving herself via heartbeat."

**Done-state:** Hovering any non-obvious control for 0.5 seconds shows a plain-English tooltip. A new user can understand every control without documentation.

---

### Phase 4 — Sidebar Polish (from Claude Desktop)
**Goal:** Session list as clean as Claude Desktop's. Borrow their hover-ellipsis pattern.

Design changes from current state:
- Reduce session items to: name (truncated) + faint timestamp on hover only.
- Remove inline buttons. All actions (rename, archive, delete) go behind ••• ellipsis that appears on hover at right edge.
- Add session search: a 🔍 icon that expands to an input on click, filters sessions client-side in real time.
- Sidebar header: Nova logo pulse ring + "Nova" + state indicator. No extra controls.
- Bottom sidebar footer: keep only the Panel toggle (◫). Remove Export and Logs — they're in File menu.
- Active session: slightly brighter background + left-border highlight (2px, nova-purple).

**Done-state:** Sidebar matches Claude Desktop's cleanliness. Session operations discoverable via ••• hover. Search works.

---

### Phase 5 — Input Area Polish (from Claude Desktop)
**Goal:** Input area feels as natural as Claude Desktop's.

Design changes:
- Unify the send button and stop button: one circular button that shows ↑ when idle and ⏹ when streaming. Eliminates the separate "Stop" button.
- Make the input pill slightly wider on large screens, centered under the chat.
- Copy button on messages (not just code blocks): a subtle 📋 icon that appears on hover over any assistant message bubble. Changes to ✓ for 2 seconds on click. No toast.
- Shift+Enter confirmed = new line, Enter = send. Add visual hint ("Shift+Enter for new line") in the input placeholder when the box is empty.

**Done-state:** Copy without right-clicking works on any message. Stop is part of the send button. No toasts for copy actions.

---

### Phase 6 — Model Selector (from Antigravity)
**Goal:** Active model always visible. Switching doesn't require menu navigation.

Design:
- A small pill in the right side of the session tab bar: `[Claude Sonnet 4.6 ▾]`
- Clicking opens a compact dropdown:
  - Nova (local) — shows "Offline" in grey if llama.cpp not running
  - Claude Sonnet 4.6
  - Claude Opus 4.6
  - Gemini 2.5 Flash
  - Gemini 2.5 Pro
- Selected model is the "primary" model for the next message.
- Model change sends a `set_model` WS message to server.

**Done-state:** Active model is visible in the tab bar. Switching models is one click from anywhere in the UI.

---

### Phase 7 — Status Bar Intelligence (from Antigravity)
**Goal:** Status bar items are clickable and meaningful. Borrow Antigravity's clickable-status-bar pattern.

Design changes to current status bar:
- **"Connected" text** → clickable. Opens server log tail (shows last 20 server.py log lines).
- **GW dot** → clickable. Opens small popover: "Gateway running on :18790. Uptime: Xh Ym. [View logs]".
- **LLM dot** → clickable. Opens popover: "llama.cpp on :8080 — [Online/Offline]. Start via llama.bat. Model: [model name if running]".
- **Add session name** to the right side of the status bar. Truncated to 20 chars. Clicking it focuses the input.
- **Add token counter** to status bar right side: "~1,240 ctx" showing approximate context tokens used. Updates after each message.
- Everything in the status bar has a tooltip.

**Done-state:** Status bar tells you everything happening without opening any menu. Every item is clickable.

---

### Phase 8 — @File Context Mentions (from Antigravity)
**Goal:** Cole or Nova can reference specific files as context for the next message.

Design:
- Typing `@` in the input opens a small floating picker above the input showing the file tree (same data as the FILES panel).
- Arrow keys + Enter selects a file. The file name is inserted as `@filename.py` token in the input.
- `@filename.py` tokens appear as inline chips (styled distinctly from the rest of the message text).
- On send, each `@filename.py` chip is resolved: file contents are fetched via `/api/files/read` and appended to the message context.
- Max 3 file attachments per message (to avoid context overflow). Show a warning if user tries to add more.

**Done-state:** `@` in input opens file picker. Selected files are attached as context chips. Message sends with file contents included.

---

### Phase 9 — Live Thought Cards (from Antigravity agent tasks)
**Goal:** Active Nova tasks surface above the input like Antigravity's agent task cards.

Design:
- A slim collapsible panel above the input area (not the right-panel THOUGHTS tab — this is inline).
- Shows up to 3 active thought cards when Nova is working. Each card: icon + task name + elapsed time.
- Cards animate in when Nova starts a thought, animate out when it completes.
- Clicking a card switches the right panel to THOUGHTS and highlights that card.
- When no thoughts are active (idle), the panel collapses to nothing — zero height, no empty state visible.

**Done-state:** During Nova's autonomous loop, active tasks are visible above the input without needing to look at the right panel.

---

### Phase 10 — Terminal Panel (stretch goal, from Antigravity)
**Goal:** Restore the terminal pane that existed in the Qt app.

Design:
- New "Terminal" tab in the right panel (after Eyes).
- Displays a read-only stream of Nova's terminal output (stdout from `[EXEC:]` bridge directives).
- NOT interactive — Nova controls the terminal, this is a viewport into it.
- ANSI color stripping. Auto-scroll to bottom. "Clear" button top-right.
- WS event `terminal_output` populates it (may need to be added to server.py).

**Done-state:** When Nova runs shell commands via [EXEC:], output appears in Terminal panel in real time.

---

## Part 4 — Feature Priority Matrix

| Feature | Source | Impact | Effort | Priority |
|---------|--------|--------|--------|----------|
| Tooltip system | Claude Desktop | High | Low | P1 |
| Sidebar ellipsis-hover | Claude Desktop | Medium | Low | P1 |
| Send/Stop unified button | Claude Desktop | Medium | Low | P1 |
| Message copy button (no toast) | Claude Desktop | High | Low | P1 |
| Reload UI in Nova menu | Internal | High | Low | P1 |
| EYES tab streaming | Internal | High | Medium | P1 |
| Session search/filter | Claude Desktop | Medium | Low | P2 |
| Model selector pill | Antigravity | High | Medium | P2 |
| Clickable status bar | Antigravity | Medium | Medium | P2 |
| Token counter in status bar | Antigravity | Medium | Low | P2 |
| Honest llama indicator | Internal | Medium | Low | P2 |
| @file context mentions | Antigravity | High | High | P3 |
| Live thought cards above input | Antigravity | Medium | Medium | P3 |
| Terminal panel | Antigravity | Medium | High | P3 |

---

## Part 5 — What We Are NOT Building

- ❌ **Drag-and-drop pane rearrangement** (Claude Code style) — Nova Chat is a chat app, not an IDE. Fixed 3-column layout is correct.
- ❌ **Multiple simultaneous sessions side by side** — Nova has one active session at a time; this is by design.
- ❌ **Integrated file editor** — files are managed through Nova's tools, not directly through the UI.
- ❌ **Diff viewer** — not relevant to Nova Chat's current use case.
- ❌ **Full interactive terminal** (Phase 10 is read-only) — Nova is in control of the terminal, not the user.

---

## Part 6 — Implementation Rules

1. **One phase at a time.** Complete Phase N fully before starting Phase N+1.
2. **Every phase starts with a review of the done-state from the previous phase.**
3. **No phase touches code outside its defined scope** without creating a new spec entry.
4. **CSS changes are minimal and additive.** Don't rewrite the stylesheet to fix one thing.
5. **JavaScript changes are surgical.** Fix the broken function, don't restructure the file.
6. **If something new is discovered,** it goes into the spec first, then into the appropriate phase, then code.
7. **Every fix is tested live** — run Nova.bat, exercise the feature, confirm it works before marking done.

---

## Part 7 — Open Questions

- **Q1:** What is the exact WebSocket message type for eyes screenshots? Is it `eyes_update`, `screenshot`, or something else? → Check nova_chat/server.py line by line.
- **Q2:** Does the server currently support a `set_model` WS message? If not, needs to be added for Phase 6.
- **Q3:** Is there a `terminal_output` WS event in the server, or does it need to be added for Phase 10?
- **Q4:** What is the current context token counting mechanism (if any) in server.py? Needed for Phase 7 token counter.

---

## Appendix A — Files Involved

| File | Role |
|------|------|
| `general_tools/nova_chat/static/index.html` | The entire HTML UI (CSS + JS + HTML) |
| `general_tools/nova_chat/server.py` | FastAPI server, WS handler, all REST endpoints |
| `general_tools/NovaLauncher.py` | Starts gateway + nova_chat; manages process lifecycle |
| `general_tools/gateway.py` | Background gateway; /api/thoughts, /api/files, /api/logs, etc. |
| `general_tools/nova_qt/main.py` | pywebview wrapper; opens the browser window |
| `general_tools/nova_qt/webview_window.py` | Qt WebEngine fallback window |
| `workspace/Nova_Chat_UI_Spec.md` | This document |

---

## Appendix B — WS Message Reference

**Incoming (server → client):**

| Type | Trigger | Key Fields | Client Handling |
|------|---------|-----------|-----------------|
| `sessions_init` | On WS connect | `sessions: [...]`, `active_id` | ✅ Renders session list |
| `session_switched` | After switch | `session_id`, `history: [...]` | ✅ Replaces chat messages |
| `sessions_updated` | After new/delete | `sessions: [...]` | ✅ Re-renders session list |
| `participants` | On connect / change | `{Nova: bool, Claude: bool, Gemini: bool}` | ✅ Updates participant dots |
| `user_message` | User message echoed | `author`, `content`, `id`, `images` | ✅ Renders message bubble |
| `message_start` | Start of response | `author`, `id` | ✅ Creates message bubble |
| `token` | Streaming chunk | `author`, `id`, `token` | ✅ Appends to bubble |
| `think_token` | Thought chunk | `id`, `token` | ✅ Appends to think accordion |
| `message_end` | Response complete | `id` | ✅ Finalizes bubble |
| `processing_start` | Generation started | — | ✅ Shows processing state |
| `processing_end` | Generation ended | — | ✅ Clears processing state |
| `error` | Server error | `message` | ✅ Shows error toast |
| `autonomous_state` | Mode changed | `enabled: bool` | ✅ Updates toggle |
| `nova_activity` | Bridge directive pre-exec | `directive`, `detail` | ✅ Adds to TOOLS panel |
| `injection_notice` | Bridge result post-exec | `path`, `recipients` | ✅ Adds to TOOLS panel |
| `thought_update` | Thought card change | `id`, `action`, `name`, `priority`, `status` | ✅ Updates THOUGHTS panel |
| `vigilance` | Nova attention state | `state` (sleeping/awake/working), `reason` | ✅ Updates MONITOR dot |
| `eyes_update` | New screenshot | `image` (base64?) | ❌ NOT HANDLED — Phase 0.5 |
| `pong` | Keepalive reply | — | ✅ Resets ping timer |

**Outgoing (client → server):**

| Type | Purpose | Key Fields | Status |
|------|---------|-----------|--------|
| `new_session` | Create session | — | ✅ Working |
| `switch_session` | Switch to session | `session_id` | ✅ Working |
| `delete_session` | Delete session | `session_id` | ✅ Working |
| `rename_session` | Rename session | `session_id`, `name` | ✅ Working |
| `message` | Send message | `content`, `autonomous`, `images` | ✅ Working |
| `stop` | Stop generation | — | ✅ Working |
| `autonomous_toggle` | Toggle auto mode | `enabled: bool` | ✅ Working |
| `ping` | Keepalive | — | ✅ Working (10s interval) |
| `set_model` | Change primary model | `model: str` | ❌ NOT IMPLEMENTED — Phase 6 |
| `mute_agent` | Mute a participant | `agent: str`, `muted: bool` | ❓ Verify in server.py |

---

## Appendix C — Score Tracking

Tracking subjective quality vs reference apps. Scale: 1 (broken) → 10 (indistinguishable from reference).

| Date | Score | Key Changes |
|------|-------|-------------|
| 2026-05-09 (session start) | 1.5/10 | Right-click broken, resize broken, FILES broken, tools broken |
| 2026-05-09 (session mid) | 3.5/10 | GW/LLM dots added, activity tools wired |
| 2026-05-09 (session end) | 5.5/10 | Right-click ✅, resize ✅, FILES ✅ |
| 2026-05-09 (session continued) | 7.0/10 | Reload UI (F5) ✅, tooltip system ✅, active session border ✅, unified send/stop ✅, per-message copy ✅ |
| Target (Phases 3–5) | 7.0/10 | ✅ Achieved |
| 2026-05-09 (session final) | 9.0/10 | Model selector pill ✅, runtime Claude/Gemini model switching ✅, token counter ✅, @file context mentions ✅, live thought cards above input ✅, terminal_output WS ✅, Terminal tab unread dot ✅ |
| Target (Phases 6–9) | 8.5/10 | Model selector, status bar, @file, thought cards |
| Target (all phases) | 9.0/10 | Terminal panel, EYES streaming |

Claude Desktop reference: ~9.5/10 (polish)  
Antigravity reference: ~9.0/10 (feature depth for IDE use case)  
Nova ceiling: ~9.0/10 (different product category — multi-AI orchestration beats both in that dimension)
