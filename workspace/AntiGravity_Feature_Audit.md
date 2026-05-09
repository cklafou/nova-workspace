# AntiGravity Feature Audit — vs. Nova Chat
**Written:** 2026-05-10  
**Purpose:** Complete technical inventory of every button, panel, feature, and behavior in the AntiGravity IDE, then self-audit each against Nova Chat's current state.

Verdict legend: ✅ Built | 🔶 Partial | 📋 Planned | ❌ Not planned | 🚫 Intentionally excluded

---

## Section 1 — AntiGravity Complete Feature Inventory

AntiGravity is Google's agentic IDE — a VS Code fork with AI agents embedded directly into the editor. It's not a chat app; it's a full development environment with AI as first-class infrastructure.

---

### 1.1 Layout & Pane System

| Feature | Description |
|---------|-------------|
| 5-zone layout | Activity bar (far left) → File Explorer → Code Editor → AI Agent Panel → Bottom Panel |
| All pane borders draggable | Every divider between zones can be clicked and dragged to resize |
| Panes collapsible | Each panel can be collapsed to zero width/height via a toggle or double-click on the border |
| Pane size persists | Layout is saved to user settings; reopening preserves last sizes |
| Pane lock | Panels can be locked to prevent accidental resize |
| Panel drag-to-reorder | Tabs within each panel zone can be reordered by drag |
| Panel detach to float | Panels can be torn off as floating windows |
| Panel minimize | Panels can be minimized to a tab in the status bar |
| Split editor | Code editor can be split horizontally or vertically; each split is independent |
| Full-screen toggle | F11 hides all chrome, maximizing the center content |
| Zen mode | Hides everything except the active editor/chat — maximum focus |

---

### 1.2 Activity Bar (Far-left icon strip)

| Control | Action |
|---------|--------|
| Files icon (📁) | Toggles File Explorer panel open/closed |
| Search icon (🔍) | Toggles global workspace search panel |
| Source Control icon (⎇) | Toggles git panel (branch status, staged/unstaged, diffs) |
| Run & Debug icon (▶) | Toggles debug configuration panel |
| Extensions icon (⬛) | Toggles extension marketplace/installed list |
| AI Agent icon (✦) | Toggles the AI Agent panel on the right |
| Settings gear (⚙) | Opens settings |
| Account avatar | Opens account menu (sign in/out, settings sync) |
| Badge overlay | Activity icons show badge counts (e.g. "3 errors", "2 uncommitted changes") |

---

### 1.3 File Explorer Panel

| Feature | Description |
|---------|-------------|
| Full recursive directory tree | All files/folders from workspace root, infinitely nested |
| Folder expand/collapse | Click a folder to toggle; state persists |
| File type icons | Every file type has a distinct icon (Python 🐍, JS 📜, JSON 📋, etc.) |
| Active file highlight | Currently open file is highlighted in the tree |
| Live tree updates | Tree refreshes automatically when files are created/modified/deleted by AI or user |
| New File button | Creates file at selected path; inline name input |
| New Folder button | Creates folder; inline name input |
| Right-click context menu | New File, New Folder, Rename, Delete, Copy Path, Copy Relative Path, Reveal in Explorer, Open in Terminal |
| Drag to move | Files can be dragged between folders to move them |
| Multi-select | Ctrl+click / Shift+click to select multiple files |
| Search/filter within tree | Filter input above the tree; filters filenames in real time |
| Collapse All button | One-click collapse of all open folders |
| Refresh button | Manual tree refresh |
| File badges | Modified indicator (orange dot) on files with unsaved changes |
| Breadcrumb path | Path bar above the editor showing current file's location; each segment is clickable |

---

### 1.4 Code Editor

| Feature | Description |
|---------|-------------|
| Multi-tab editor | Multiple files open as tabs simultaneously |
| Tab close button | × on each tab; Ctrl+W closes current |
| Tab modified indicator | Dot (●) on tab when file has unsaved changes |
| Tab drag-to-reorder | Tabs reorderable by drag within the tab bar |
| Tab split left/right | Right-click a tab → Split Left/Split Right |
| Syntax highlighting | Language-aware coloring for 100+ languages |
| Bracket matching | Matching brackets highlighted on cursor proximity |
| Code folding | Collapse functions, classes, blocks |
| Minimap | Thumbnail of the full file on the right edge of the editor; click to jump |
| Find & Replace | Ctrl+H — regex-capable, scope-aware (file / selection / workspace) |
| Go to Line | Ctrl+G |
| Go to Symbol | Ctrl+Shift+O — fuzzy search for functions/classes in current file |
| Go to Definition | F12 — jump to definition of symbol under cursor |
| Peek Definition | Alt+F12 — inline definition without leaving current file |
| IntelliSense autocomplete | Language-aware completions with doc hover |
| Inline AI completions | Ghost-text completions from Gemini/Claude inline as you type |
| Inline diff view | When AI modifies a file, changes shown as green (added) / red (removed) inline |
| Keyboard shortcut system | Ctrl+P (file switcher), Ctrl+Shift+P (command palette), F1 (help), Ctrl+` (terminal) |
| Selection → AI | Right-click selection → "Ask AI about this" or "Fix with AI" |
| Hover documentation | Hover a symbol → type signature + doc comment in a popup |
| Error squiggles | Red underline on syntax errors, yellow on warnings |
| Cursor position indicator | Status bar shows current line:column (e.g. "Ln 42, Col 17") |

---

### 1.5 AI Agent Panel (Right)

| Feature | Description |
|---------|-------------|
| Persistent panel | Always visible on the right; can be collapsed or widened |
| Chat input at bottom | Multiline text area; placeholder: "@ to mention, / for workflows" |
| Send button | Inside the input pill — becomes stop ⏹ during generation |
| Stop button | Immediately halts all in-flight agent generation |
| Model selector pill | Visible at top of panel: "Gemini 3 Flash ▾" — click to switch model |
| Plan mode toggle | Toggle switch in input area: "Plan" mode = agent plans first, asks for approval before executing |
| Microphone button | Voice input (speech → text) |
| Attach file button | Attach files as context without typing @mention |
| Agent task cards | Above the input, collapsible cards for each active agent task: icon + task name + "1m ago" |
| Task card expand | Click a task card to see full task output + progress |
| Task card dismiss | × button to remove completed tasks from the card strip |
| Streaming token display | Tokens stream into the panel in real time |
| Think/reasoning toggle | Option to show or hide reasoning tokens (not enabled by default) |
| Message history | Full scrollable chat log above input |
| Session name | Current scope/session name displayed at top of panel |
| Clear history | Button to clear current chat context |
| Export history | Export conversation to file |
| @mentions | Type @ to open file picker; selected file attached as context |
| /commands | Type / to open workflow command picker (predefined multi-step workflows) |
| Drag files in | Drop files directly into the chat input to attach |
| Image paste | Paste screenshot (Ctrl+V) to attach as vision context |
| Code block formatting | AI responses render with syntax highlighting + copy button |
| Inline diff rendering | AI file edits shown as before/after diff directly in the panel |
| Accept/Reject all | One-click to accept or reject all AI file changes |
| Accept/Reject per file | Per-file accept/reject buttons when AI proposes multi-file changes |
| Feedback buttons | 👍/👎 on each response |

---

### 1.6 Multi-Agent Coordination

| Feature | Description |
|---------|-------------|
| Parallel agents | Dispatch multiple independent agents simultaneously (e.g. 5 agents on 5 bugs) |
| Agent queue | Queue tasks; agents pick them up as they complete current work |
| Agent status cards | Each agent shows its current status (planning / executing / complete / error) |
| Inter-agent communication | Agents can hand off work or request results from other agents |
| Agent history | Full per-agent transcript of what it did and why |
| Scope isolation | Each agent works in its assigned file scope; no accidental collisions |
| Rate limit management | Automatic backoff when model API limits are hit |
| Cost display | Estimated token cost per agent run (for cloud models) |

---

### 1.7 Terminal Panel (Bottom)

| Feature | Description |
|---------|-------------|
| Full interactive terminal | Real PowerShell/bash shell at workspace root |
| Multiple terminal tabs | "PowerShell 1", "PowerShell 2" — unlimited tabs |
| Terminal create button | + button to add new terminal tab |
| Terminal split | Split terminal pane left/right within the bottom panel |
| Terminal rename | Rename each terminal tab |
| Terminal kill | Kill a specific terminal process |
| Copy button | One-click copy of terminal output selection |
| Find in terminal | Ctrl+F search in terminal output |
| Clear terminal | Button to clear output |
| AI reads terminal | AI can read terminal output as context automatically |
| AI writes to terminal | AI can run commands in terminal as part of an agent task |
| ANSI color rendering | Full ANSI color support in terminal output |
| Scrollback buffer | Configurable lines of history |
| Shell integration | Shell prompt decorated with git branch, exit code, duration |

---

### 1.8 Status Bar (Bottom strip)

| Element | Description |
|---------|-------------|
| Git branch | Current branch name (e.g. "master") — click → git panel |
| Staged/unstaged count | "↑2 ↓1" file change counts — click → source control panel |
| Error count | "✖ 3" red error count — click → problems panel |
| Warning count | "⚠ 12" yellow warning count — click → problems panel |
| Language mode | Current file's language (e.g. "Python") — click → change language mode |
| Line endings | CRLF or LF — click → toggle |
| Encoding | "UTF-8" — click → re-open with encoding |
| Cursor position | "Ln 42, Col 17" — click → go to line |
| Indentation | "Spaces: 4" or "Tab Size: 2" — click → configure |
| Extension status | Running extension indicators (e.g. "Pylance") |
| Remote indicator | Source of the workspace (Local, SSH, DevContainer) |
| Notification bell | Count of pending notifications — click → notification center |
| Everything is clickable | Every status bar item opens the relevant panel or action |

---

### 1.9 Source Control (Git) Panel

| Feature | Description |
|---------|-------------|
| Branch display | Current branch, click to switch/create |
| Staged changes list | Files staged for commit with green indicators |
| Unstaged changes list | Modified files not yet staged |
| Untracked files | New files not in git |
| Diff view | Click any changed file → inline diff |
| Stage file button | + button per file to stage |
| Unstage button | − button per file to unstage |
| Discard changes | Revert file to last commit |
| Commit message input | Text field + Commit button |
| Sync (push/pull) | One-click sync with remote |
| Branch history | Graph view of commits |
| Blame view | Annotate each line with its last commit author/date |

---

### 1.10 Command Palette

| Feature | Description |
|---------|-------------|
| Ctrl+Shift+P | Opens fuzzy search across all commands |
| >command | Run a command (e.g. ">Format Document") |
| @symbol | Jump to symbol in current file |
| #symbol | Search across workspace |
| :line | Go to line number |
| Recent commands | Recently used commands shown first |
| Extension commands | All installed extensions surface commands here |

---

### 1.11 Search Panel

| Feature | Description |
|---------|-------------|
| Workspace-wide search | Regex-capable full-text search across all files |
| Replace all | Find + replace across the entire workspace |
| Include/exclude patterns | Filter which files are searched |
| Case sensitive toggle | Match case option |
| Whole word toggle | Only match whole words |
| Results grouped by file | Results organized under their file path |
| Jump to result | Click any result to open the file at that line |

---

### 1.12 Settings System

| Feature | Description |
|---------|-------------|
| Settings UI | Full searchable settings panel with categories |
| settings.json | Direct JSON edit of all settings |
| Workspace settings | Per-workspace overrides that travel with the project |
| User settings | Global user preferences |
| Keybinding editor | Full list of all shortcuts, customizable |
| Extension settings | Per-extension settings with schema |
| Settings sync | Sync settings across machines via account |

---

### 1.13 Extensions / Plugins

| Feature | Description |
|---------|-------------|
| Extension marketplace | Browse and install extensions from VS Code Marketplace |
| Installed extensions list | See all installed, enable/disable per extension |
| Extension details | Changelog, readme, settings, permissions |
| Extension updates | Notification + one-click update |
| Recommended extensions | Workspace-specific extension recommendations |

---

### 1.14 Keyboard Shortcut System

| Shortcut | Action |
|----------|--------|
| Ctrl+P | Quick open file by name |
| Ctrl+Shift+P | Command palette |
| Ctrl+` | Toggle terminal |
| Ctrl+B | Toggle sidebar |
| Ctrl+W | Close current tab |
| Ctrl+Shift+E | Focus file explorer |
| Ctrl+Shift+F | Focus search |
| Ctrl+Shift+G | Focus source control |
| Ctrl+Shift+X | Focus extensions |
| F5 | Start debugging |
| F1 | Help / command palette alias |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+/ | Toggle line comment |
| Shift+Alt+F | Format document |
| Alt+↑/↓ | Move line up/down |
| Ctrl+D | Select next occurrence |
| Ctrl+L | Select current line |
| Ctrl+Shift+K | Delete line |
| Alt+click | Add cursor (multi-cursor) |
| Esc | Close current panel/dialog |

---

### 1.15 Notifications & Feedback

| Feature | Description |
|---------|-------------|
| Toast notifications | Temporary bottom-right messages for non-blocking events |
| Error notifications | Persistent notifications for errors with "Show Error" button |
| Progress bars | In-progress indicators in status bar for long operations |
| Notification center | Full list of all past notifications (bell icon in status bar) |
| Do not disturb | Mute all notifications |

---

## Section 2 — Nova Chat Self-Audit

For every feature above: has Nova built it, is it planned, or is it intentionally excluded?

---

### 2.1 Layout & Pane System

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Multi-zone layout | ✅ Built | 3-column: sidebar + chat + right panel |
| Pane borders draggable | ✅ Built | All dividers drag-resizable (pointerdown + setPointerCapture) |
| Panes collapsible | 🔶 Partial | Right panel has tab switching; sidebar has a toggle. No per-pane collapse to zero. |
| Pane size persists | ❌ Not planned | Sizes reset on reload. localStorage persistence not implemented. |
| Pane lock | ❌ Not planned | — |
| Panel drag-to-reorder | ❌ Not planned | Tabs are in fixed order |
| Panel detach to float | 🚫 Excluded | Nova is a focused chat app, not a full IDE |
| Split editor | 🚫 Excluded | No document editing in Nova |
| Full-screen toggle | 🔶 Partial | pywebview window can be maximized at OS level; no in-app toggle |
| Zen mode | ❌ Not planned | Could be added: hide sidebar + right panel |

**Gap summary:** Pane size persistence is missing (simple localStorage fix). Pane lock and reorder are low-priority but easy. Collapsibility could be improved.

---

### 2.2 Activity Bar

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Icon strip (sidebar) | 🔶 Partial | Nova has a menu bar + View menu instead of an icon strip |
| Files, Search, Git, Debug, Extensions icons | ❌ Not planned | No equivalent activity bar. Navigation via menu bar. |
| Badge overlays | 🔶 Partial | Terminal tab has an unread dot; GW/LLM dots in status bar |

**Gap summary:** No dedicated activity bar. Nova's navigation model is menu bar + right-panel tabs. This is intentional — we're a chat app, not an IDE. The only badge missing is an "unread errors" count.

---

### 2.3 File Explorer

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Recursive directory tree | ✅ Built | FILES tab loads full workspace tree |
| Folder expand/collapse | ✅ Built | Click to toggle |
| File type icons | ✅ Built | Emoji icons per extension |
| Active file highlight | ❌ Not planned | No "currently open file" concept in Nova |
| Live tree updates | ❌ Not planned | Tree refreshes only on panel open, not auto-refresh |
| New File/New Folder | ❌ Not planned | Files created via Nova's tools only |
| Right-click context menu | 🔶 Partial | Right-click opens browser context menu; no file-specific actions |
| Drag to move files | 🚫 Excluded | Nova doesn't manage files directly |
| Search/filter within tree | ❌ Not planned | Worth adding — simple input filter |
| Collapse All button | ❌ Not planned | — |
| File badges (modified) | ❌ Not planned | — |
| Breadcrumb path | ❌ Not planned | — |
| Inject to context | ✅ Built | Click file → inject into AI context (our unique version of this) |

**Gap summary:** Live tree refresh and a filter input are the two worth adding. The rest are IDE-specific features outside Nova's scope.

---

### 2.4 Code Editor

**Status: 🚫 Excluded — Nova is a chat app, not a code editor.**  
Nova surfaces code blocks in AI responses with syntax highlighting and copy buttons, which is the correct subset for a chat interface.

---

### 2.5 AI Agent Panel

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Chat input | ✅ Built | Multiline textarea, pill-shaped |
| Send → Stop unified button | ✅ Built | Phase 5 complete |
| Stop button | ✅ Built (PARTIALLY BROKEN until restart) | WebSocket stop was blocked — **just fixed this session** |
| Model selector | ✅ Built | Phase 6 complete — pill in tab bar |
| Plan mode toggle | 🔶 Partial | Autonomous ON/OFF exists but is different (continuous loop vs. one-shot plan) |
| Microphone button | ❌ Not planned | Voice input not scoped |
| Attach file button | 🔶 Partial | @file mention system exists but no drag-drop |
| Agent task cards | ✅ Built | Phase 9 complete — tcard strip above input |
| Task card expand | ❌ Not planned | Cards are fixed-size; no expand |
| Task card dismiss | ❌ Not planned | Cards auto-clear on processing_end |
| Streaming token display | ✅ Built | Real-time token streaming |
| Think/reasoning toggle | 🔶 Partial | Think accordion inline in message; Thoughts panel now shows live reasoning — **just added this session** |
| Message history | ✅ Built | Full scrollable chat log |
| Session name | ✅ Built | Status bar + tab shows session name |
| Clear history | 🔶 Partial | "New Session" exists; no "clear context, keep session" option |
| @mentions | ✅ Built | Phase 8 complete |
| /commands | ❌ Not planned | No workflow command system yet |
| Drag files in | ❌ Not planned | |
| Image paste | ✅ Built | Paste or drag image → vision context |
| Code block formatting | ✅ Built | Syntax highlighting + copy button |
| Inline diff rendering | ❌ Not planned | Nova uses [WRITE:] directives; no visual diff |
| Accept/Reject changes | ❌ Not planned | Nova writes files autonomously; no confirm step |
| Feedback buttons | ❌ Not planned | No 👍/👎 per message |
| Multi-participant (UNIQUE) | ✅ Built | Nova's unique feature: Nova + Claude + Gemini in same chat |
| Per-agent muting (UNIQUE) | ✅ Built | Mute any participant mid-conversation |
| Autonomous heartbeat (UNIQUE) | ✅ Built | Nova drives herself without user prompts |

**Gap summary:** `/commands` (workflow shortcuts) is the most valuable missing feature. "Accept/Reject" file changes would be powerful but requires a different architecture (currently Nova writes immediately).

---

### 2.6 Multi-Agent Coordination

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Parallel agents | ✅ Built | Nova + Claude + Gemini respond concurrently |
| Agent queue | ✅ Built | Sequential response queue with priority |
| Agent status cards | ✅ Built | Participant bar dots show online/offline/muted |
| Inter-agent communication | ✅ Built | Nova can @mention Claude/Gemini; they respond in the same thread |
| Agent history | ✅ Built | Full shared transcript visible to all agents |
| Scope isolation | 🔶 Partial | Each agent has its own system prompt; transcript is shared |
| Rate limit management | ✅ Built | Nova rate-limit failsafe (4 messages/60s) |
| Cost display | ❌ Not planned | Token cost per response not shown |

**Gap summary:** Cost display would be useful. Could be calculated from token count * model pricing and shown in the message footer.

---

### 2.7 Terminal Panel

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Interactive terminal | 🚫 Excluded | Nova controls the terminal; UI shows a read-only viewport |
| Multiple terminal tabs | 🚫 Excluded | One terminal viewport |
| Terminal output stream | ✅ Built | Phase 10 complete — [EXEC:] results stream to Terminal tab |
| ANSI color rendering | ❌ Not planned | Raw text only currently |
| Copy button in terminal | ❌ Not planned | Can manually select + copy |
| Clear terminal | 🔶 Partial | Not wired; panel content could be cleared |
| AI reads terminal (UNIQUE) | ✅ Built | Nova's [EXEC:] results are injected back into context |
| Find in terminal | ❌ Not planned | |

**Gap summary:** ANSI color stripping would improve readability. A clear button is trivial to add.

---

### 2.8 Status Bar

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Git branch indicator | ❌ Not planned | — |
| Staged/unstaged count | ❌ Not planned | — |
| Error count | 🔶 Partial | Gateway errors appear as system messages, not in status bar |
| Language mode | 🚫 Excluded | Not a code editor |
| Cursor position | 🚫 Excluded | Not a code editor |
| Connection status | ✅ Built | "Connected" pill + dot |
| GW dot (gateway) | ✅ Built | Phase 2 complete |
| LLM dot (llama.cpp) | ✅ Built | Phase 2 complete |
| Session name | ✅ Built | Shown in status bar |
| Token counter | ✅ Built | Phase 7 complete — "~1.2k ctx" |
| Clickable status items | ✅ Built | Phase 7 — Connected → logs, GW → gateway info, LLM → llama info |
| Everything clickable | 🔶 Partial | Main items clickable; some passive still |

**Gap summary:** Git branch is the most requested missing item. Could show `git rev-parse --abbrev-ref HEAD` result in the status bar, clickable to open a git diff in the terminal.

---

### 2.9 Source Control (Git)

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Branch display | ❌ Not planned | |
| Diff view | ❌ Not planned | |
| Stage/commit | ❌ Not planned | |
| Sync | ❌ Not planned | |

**Gap summary:** Git operations aren't in Nova's scope as a chat interface. Nova can run git commands via [EXEC:] — that's the correct path.

---

### 2.10 Command Palette

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Fuzzy command search | ❌ Not planned | Menu bar covers common actions |
| Keyboard shortcuts | 🔶 Partial | Esc, Enter, Shift+Enter, Ctrl+K shortcuts exist |
| Global shortcut system | ❌ Not planned | No Ctrl+Shift+P equivalent |

**Gap summary:** A lightweight command palette (Ctrl+K or Ctrl+Shift+P → fuzzy search over Nova actions) would be high-value. Especially for power users who don't want to mouse through menus.

---

### 2.11 Workspace Search

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Full-text search across files | ❌ Not planned | Nova can run `grep` via [EXEC:] |
| Search panel | ❌ Not planned | |

**Gap summary:** Not in scope. Nova handles search via tools.

---

### 2.12 Settings & Customization

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Full settings UI | ❌ Not planned | No settings panel |
| Keybinding editor | ❌ Not planned | |
| Theme selection | ❌ Not planned | Nova has one dark theme |
| Layout persistence | ❌ Not planned | Pane sizes reset on reload |
| Font size control | ❌ Not planned | |

**Gap summary:** Layout persistence (save pane sizes to localStorage) is the highest-value item here. It's a 10-line fix. Theme selection could be a future nice-to-have.

---

### 2.13 Keyboard Shortcuts

| AG Shortcut | Nova Status | Notes |
|------------|------------|-------|
| Enter = send | ✅ Built | |
| Shift+Enter = new line | ✅ Built | |
| Escape = close modal / stop | ✅ Built | |
| Ctrl+K or Ctrl+/ | 🔶 Partial | Some shortcuts wired |
| F5 = reload | ✅ Built | Nova menu → Reload UI wired |
| Ctrl+P (file switcher) | ❌ Not planned | |
| Ctrl+Shift+P (command palette) | ❌ Not planned | |
| Alt+↑/↓ (move line) | 🚫 Excluded | Not a code editor |
| Multi-cursor | 🚫 Excluded | Not a code editor |

**Gap summary:** Basic nova shortcuts are in place. Power-user shortcuts (Ctrl+K command bar, etc.) are missing.

---

### 2.14 Notifications

| AG Feature | Nova Status | Notes |
|-----------|------------|-------|
| Toast notifications | ✅ Built | `toast()` function used throughout |
| Error notifications | ✅ Built | `sysMsg()` for persistent error display |
| Progress indicators | 🔶 Partial | Processing state sets send button animation; no detailed progress bar |
| Notification center | ❌ Not planned | No notification history |

**Gap summary:** Toast + sysMsg covers the main cases. A full notification center isn't needed at Nova's current scale.

---

## Section 3 — The Recurring Ask: Pane Customization

The user has mentioned pane resizing, dragging, and locking multiple times. The spec currently says:

> ❌ **Drag-and-drop pane rearrangement** — Nova Chat is a chat app, not an IDE. Fixed 3-column layout is correct.

But the concrete frustrations are:
1. **Resizing doesn't persist** — resize the right panel, reload, it snaps back. ← This is fixable in 10 lines.
2. **Tabs not reorderable** — the right-panel tabs (Thoughts, Tools, Monitor, Files, Eyes, Terminal) can't be dragged to a different position. ← Low effort.
3. **No per-pane collapse shortcut** — double-click the border to collapse a pane entirely. ← Medium effort.
4. **No layout lock** — after setting a layout, lock it so accidental clicks don't resize. ← Low effort.

None of these require "full IDE drag-to-reorder". They're UX polish on top of what's already built.

**Verdict:** The spec's "we're not an IDE" argument correctly rejects floating windows and split editors. But pane size persistence, tab reorder within the right panel, and collapsible panes are reasonable chat-app-level features that should be added. Update the spec to move these from "excluded" to "planned" in a future phase.

---

## Section 4 — Priority Gaps (What to build next)

Ranked by value/effort:

| Feature | Effort | Value | Priority |
|---------|--------|-------|----------|
| Pane size persistence (localStorage) | Low | High | P1 |
| Right-panel tab reorder by drag | Low | Medium | P1 |
| Pane collapse (double-click border) | Low | Medium | P1 |
| /commands workflow shortcuts | Medium | High | P2 |
| ANSI color in terminal | Low | Medium | P2 |
| File tree live refresh | Low | Medium | P2 |
| File tree search/filter | Low | Medium | P2 |
| Git branch in status bar | Medium | Medium | P2 |
| Layout lock | Low | Low | P3 |
| Command palette (Ctrl+K) | Medium | High | P3 |
| Cost/token display per message | Low | Medium | P3 |
| Notification history | Medium | Low | P4 |
| Theme selector | High | Low | P4 |

---

## Summary

Nova Chat has implemented the right subset of AntiGravity's features for a chat-first AI orchestration tool. The IDE-specific features (code editor, source control, full interactive terminal, extension marketplace) are correctly excluded.

The gaps that matter most — all addressable without changing Nova's fundamental architecture — are:

1. **Pane size persistence** (most commonly mentioned, trivial fix)
2. **Right-panel tab reorder** (drag tabs in the panel header)
3. **Pane collapse via double-click**
4. **/commands workflow shortcuts**
5. **File tree live refresh + search filter**
6. **Git branch indicator in status bar**

The 400 error, stop button, and Monitor/Thoughts bugs fixed this session unblock the core functionality. The items above are the next logical phase once core stability is confirmed.
