# NCL_MASTER.md — Nova Command Language Grammar Reference
_Read this to know how to call your modules. Injected at every session boot._
_Source of truth: workspace/NCL_MASTER.md | Parser: tools/nova_chat/nova_lang.py_

---

## What Is NCL

Nova Command Language (NCL) is the syntax Nova uses in Nova Chat to dispatch work
to specialized AI modules. When Nova writes an NCL call in chat, the server parses
it and routes it to the correct module with the correct context.

NCL calls are NOT casual conversation. Never use NCL tokens in a message that is
primarily a reply to Cole or a chat with Claude/Gemini. Only use them when firing
a real module task.

---

## Token Reference

| Token | Meaning | Example |
|-------|---------|---------|
| `@role` | Call to a module by name | `@eyes`, `@thinkorswim`, `@coder` |
| `<<file.md>>` | Inject a context file into the module's system prompt | `<<Thoughts/Trade_0328/scratch/brief.md>>` |
| `[[instructions]]` | Specific instructions from Nova for this call | `[[focus on the options chain only]]` |
| `((criteria))` | Completion criteria — what the module must return | `((task_id:TradeCheck_0328; list open positions))` |
| `;;` | Parallel separator — groups on each side run at the same time | `@eyes [[...]] ;; @coder [[...]]` |
| `::` | Sequential pipe — steps run in order, each can use $$prev | `@browser [[research]] :: @mentor $$prev [[validate]]` |
| `**text**` | Emphasis — marks critical info Nova wants noticed | `**do not execute any trades**` |
| `>>path` | Output routing — where the module writes its result | `>>Thoughts/Trade_0328/inbox/` |
| `$$prev` | Reference to the previous step's output in a :: chain | `@mentor $$prev [[confirm or refute]]` |
| `%%N` | Timeout in seconds — call is failed if not returned by then | `%%60` |

---

## Rules

**One @role per segment.** Each `;;` block and each `::` step contains exactly one
@role with its modifiers. Do not stack multiple roles in one segment.

Wrong:  `@eyes @mentor [[do both things]]`
Right:  `@eyes [[do vision thing]] ;; @mentor [[do reasoning thing]]`

**task_id format.** Task IDs must match the Thought folder name exactly. Use
underscores, no spaces. Include the date if the task is time-specific.
Format: `((task_id:TaskFolderName; what must be returned))`

**Keep context files workspace-relative.** The `<<file>>` path is always relative
to the workspace root. Use paths like `Thoughts/Trade_0328/scratch/brief.md` or
`memory/STATUS.md`.

**;; means truly parallel.** Use `;;` only when the calls are independent — they
do not need each other's output to run. If B needs A's output, use `::` instead.

**:: means strictly sequential.** Each step blocks until the previous one returns.
Only the last step in a chain can have a `((task_id:...; ...))` criteria — earlier
steps use `[[instructions]]` to describe what they contribute.

**Emphasis is for Cole's benefit.** `**text**` does not affect execution. It marks
things Cole should notice when he reads the call log.

---

## Registered Modules

| @name | Purpose | Status |
|-------|---------|--------|
| `@eyes` | Screenshot, UI perception, pywinauto tree, visual Q&A | partial (Tiers 2-3 pending) |
| `@mentor` | High-reasoning review — routes to Claude + Gemini | active |
| `@thinkorswim` | Trading platform analysis, order management | planned |
| `@browser` | Web research, page reading, form interaction | planned |
| `@memory` | Semantic search over Nova's history and journal | planned |
| `@coder` | Code generation, debugging, review | planned |
| `@voice` | Audio transcription, speech-to-text | planned |

Modules marked `planned` are registered but not yet implemented. Calling them
will result in a "module not available" response routed to the task inbox.

To see live module status: read `workspace/modules.json` if it exists.

---

## Example Calls

### Simple — single module, one task

```
@eyes [[screenshot the ThinkOrSwim positions panel and describe all open positions]]
((task_id:TradeCheck_0328; list all open positions with symbol, qty, P&L))
```

### Parallel — two independent modules at the same time

```
@eyes [[screenshot the current AAPL chart on the 1-minute timeframe]]
>>Thoughts/AAPL_Decision_0328/inbox/chart.md
((task_id:AAPL_Decision_0328; describe chart pattern and key price levels))
;;
@thinkorswim <<Thoughts/AAPL_Decision_0328/scratch/strategy.md>>
[[what are today's key support and resistance levels for AAPL]]
((task_id:AAPL_Decision_0328; return support and resistance levels))
```

### Sequential chain — research then validate

```
@browser <<Thoughts/Research_0328/scratch/brief.md>>
[[find the top 3 analyst ratings for AAPL published this week]]
((task_id:Research_0328; return analyst name, rating, price target for each))
::
@mentor $$prev
[[validate the research — check recency, source quality, and flag any conflicts]]
((task_id:Research_0328; confirm findings or flag concerns))
```

### With emphasis and timeout

```
@thinkorswim <<memory/STATUS.md>>
[[check if any positions are approaching max loss limit]] **do not place any orders**
%%45
((task_id:RiskCheck_0328; list any positions within 10% of max loss))
```

---

## Task ID and Inbox Routing

Every NCL call that needs a response back must include `task_id:NAME` in the
criteria block. The NAME must exactly match the Thought folder name.

When a module responds, it begins its message with `[TaskFolderName]`. The server
reads this tag and drops the response as a `.md` file into `Thoughts/Master_Inbox/`.
On the next heartbeat, Nova routes it to `Thoughts/TaskFolderName/inbox/`.

If a call has no task_id, the response is a one-shot reply in Nova Chat. It will
not be automatically routed to any inbox.

**Task ID format:** Short, descriptive, underscores only, date suffix recommended.
Examples: `TradeCheck_0328`, `AAPL_Research_0328`, `SystemAudit_0328`

---

## What NCL Is Not

NCL tokens are for module dispatch only. They are NOT used for:
- Replying to Cole (just write normally)
- Chatting with Claude or Gemini (use @Claude, @Gemini, @mentor — those are
  orchestrator mentions, not NCL)
- Writing files (use `[WRITE:path]...[/WRITE]` bridge syntax)
- Running commands (use `[EXEC:command]` bridge syntax)
- Sending Discord messages (use `[DISCORD: text]` bridge syntax)

---

## Parser Location

`tools/nova_chat/nova_lang.py` — parse_ncl(), summarize_ncl(), ncl_to_dict()
`tools/nova_chat/orchestrator.py` — MODULE_REGISTRY, get_module(), list_modules()

The parser is invoked automatically by the Nova Chat server when Nova sends a
message. If the message contains valid NCL, it is routed; otherwise it is treated
as a normal chat message.

---

_Last updated: 2026-03-28 | Phase 4A.3_
