<!-- @nova: Explain how to run, inspect, verify and recover Project Nova. -->
# Operations and verification

_Facts regenerated 2026-10-03T19:16:29+00:00 from source (input `f36e6af11693`). Explanations carry their own review dates, and ⚠ marks a section whose sources changed since its review. Source-derived facts are not runtime certification._

## Run and stop

| Operation | Entry point | Check |
|---|---|---|
| Normal stack | `NovaStart.cmd` | `/api/version`, model readiness and actual generation |
| Controller with Nova off | `NovaChatOnly.cmd` or `python nova_start.py --chat-only` | `/api/version` reports `chat_only`; no model, witness, guardian, watcher or autonomy is started |
| Local model only | `start_llama_qwen36.cmd` | `http://127.0.0.1:8080/health` plus a bounded inference probe |
| Standalone body | `python nova_body/nova_runtime/__main__.py` | Relocate first to test true portability |
| Graceful stack shutdown | POST `http://127.0.0.1:8799/api/shutdown` | Confirm owned processes/ports exit |
| Shutdown fallback | `StopNova.cmd` | Inspect its process matching before use on a shared machine |
| Stop current activity | POST `http://127.0.0.1:8765/stop` | `stopped` and `remaining` report supervised cleanup; partial effects can remain |
| Pause/resume autonomy | Control widget or POST `/api/runtime/pause` / `/api/runtime/resume` | Persistent autonomy setting; resume rejects pending cleanup |
| Inspect runtime | GET `/api/runtime/state` | Focus, operations, task checks, queue failures and VM handoff |
| Architecture explorer | `Orient/Architecture/RUN_MAP.cmd` | Source-derived map; current runtime evidence is separate |
| Refresh these docs | `python general_tools/architecture_map/orient.py` | Changed inputs regenerate; stable inputs do not rewrite timestamps |

Default services: model 8080, witness 8081, chat 8765, console/control hub 8799. VM display and
other applications have their own configuration. The guardian belongs to the launcher and must
stand down during intentional maintenance. Prefer graceful shutdown before state moves.
`start_llama_qwen36.cmd` boots the model and projector named in `nova_body/memory/active_model.txt`
and `active_mmproj.txt` when present (written by the model updater; `none` = no vision), else
Qwen 3.6. `active_lora.txt` set to `none` boots without a personality adapter, and the old v2
fallback adapter applies only to the default Qwen 3.6 model. See Model updates below.

The Services widget's Restart Nova and Shut down Nova controls stop current work and request
launcher-owned teardown. HTTP 202 acknowledges acceptance; it is not proof of completion. Confirm
old processes exit and, for restart, new PIDs become ready. The launcher gives the accepted request
one second to flush its response before teardown; repeated requests do not extend that deadline.
The launcher stops the guardian before
services and refuses a replacement while owned ports remain occupied. Repeated matching requests
are idempotent; a competing shutdown/restart request is rejected. Model-only Stop targets port 8080
and leaves the independent witness on 8081 running. Model stop/restart waits up to ten seconds for the old socket
to close; failure is reported instead of acknowledging a skipped restart. KoELS propagates that
failure. Starting an already starting model is a no-op.

Chat-only mode retains the desktop controller and the separate Collaboration widget. It does not
turn on Nova when a message arrives; wake/model/autonomy actions require a normal relaunch. It
refuses to attach to an already-running full server as though that server were dormant. The
Collaboration room also works during a normal launch without being fed to Nova's conversation.

## Configuration and evidence

> ⚠ **Review needed.** Since this section was reviewed (2026-10-03): changed `general_tools/nova_chat/collaboration.py`, `general_tools/nova_collaboration/bridge.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Configuration and evidence"`.

Collaboration is a detachable controller service (`general_tools/nova_chat/collaboration.py`). Its
SQLite history and per-agent credentials live outside the repository at
`%LOCALAPPDATA%/ProjectNova/Collaboration`. Messages never enter chat sessions, runtime transcripts,
semantic indexing, task inboxes or autonomy events. Mentioning Nova there does not invite her.
This is exclusion from automatic routing, not an OS restriction on her deliberately trusted tools.
Cowork's current task uses the shared-folder CLI adapter: atomic requests/replies under
`workspace/Temp/collaboration`. That narrow path is excluded from watcher activity, Git, Orient,
Drive export/scan and automatic direct-file recall. Only the Windows broker writes the SQLite
store. Replies expire after ten minutes; room history stays in SQLite. A queued file is not
delivered until its reply acknowledges a sequence number. Mounted
folder access is the authority for that adapter; it is not proof of identity against local agents.
Task workspaces are staged under `workspace/Temp/task-workspaces` and excluded the same way, so
staged copies are never committed or timestamp-stamped by the watcher.
The widget uses cursor replay and retry IDs. Presence reports recent activity or a bounded receive
wait, and expires when an agent stops checking. It does not prove that a desktop task is awake.
`general_tools/nova_collaboration` provides a CLI and a Cowork local MCP plugin. Neither substitutes
an API model for the actual app session nor automatically wakes an ended Codex/Cowork turn.

Body settings live in `nova_body/nova_config.json`; live knobs in
`nova_body/memory/tunables.json`. The Variables widget reads the cortex registry and updates
those knobs. The provider launcher still has its own flags, and some body modules retain constants:
editing one configuration file does not imply every subsystem obeys it.

Adapter intent is in `nova_body/memory/active_lora.*`; KoELS desired/boot state lives beside it.
Model intent is in `active_model.txt` / `active_mmproj.txt` beside them (model updater).
Read the runtime's configured adapter status without browsing sealed weights. Keep secrets excluded
from both Git and Drive, including relocated `.auth_token` and `nova_users.json`.

Useful evidence lives under `nova_body/logs/`: `tool_calls.jsonl`, `generation_trace.jsonl`,
events, runtime transcript, chat sessions and launcher/model logs. Read current receipts and loaded
source before changing prompts. `/api/version` compares normalized content hashes of watched
sources against startup, ignoring watcher header timestamps and line endings. This detects even
same-size edits with unchanged timestamps; it is not a census of every imported module.
New structured receipts distinguish success, failure, refusal,
timeout, cancellation and unknown. Historical receipts retain their original values; older
`ok: true` entries can mislabel nonzero exits. Validate their artifacts independently. A running
port does not prove successful inference. The Control widget exposes task scheduling, verification,
stop/resume, memory ingestion health and VM handoff through `/api/runtime/state` and related routes.

## Access and practical debugging

Nova's host access is intentional. The chat server has loopback exemptions, bearer authentication
for remote HTTP clients, and restrictions on remote routes. Speaker capability checks are a separate
layer: an unknown display name resolves to untrusted. A name added in the UI is not automatically
an owner principal. Inspect the current middleware and principal registry before changing exposure;
these source observations are not a fresh penetration test. The separate Collaboration routes
add a local Host/Origin/forwarding gate; this does not repair older HTTP or WebSocket gaps.
Secrets stay out of Git and Drive.

The voice loop parses tool reaches from both content and reasoning streams. Receipt-backed context
helps distinguish executed work from earlier narration. Check loaded source, actual receipts,
adapter status, and call order before changing personality or training. Rendering/mount artifacts
can resemble damaged source: compare actual local bytes before repairing a supposed truncation.
On remote training hosts, stop a RunPod rather than terminating its retained volume; put the
Hugging Face cache on local disk rather than a slow network mount.

## Test meaningful behavior

> ⚠ **Review needed.** Since this section was reviewed (2026-10-03): changed `general_tools/nova_chat/tests/test_collaboration.py`, `general_tools/nova_chat/tests/test_collaboration_bridge.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Test meaningful behavior"`.

1. Save source fingerprints, relevant state and receipt offsets; identify test author explicitly.
2. Queue a bounded task with a known oracle through the normal interface. Record whether it is selected.
3. Check reproduction, actual tool results, file changes, tests, final artifact and board transition.
4. Test errors, cancellation/resumption and missing dependencies separately. Never label mocked or
   direct-tool checks as model-driven end-to-end results.
5. For Pluck, copy the body to a differently named location, remove face/tool availability, deny
   access to the original workspace, and verify identity, memory, task persistence, receipts and
   real inference. Report dependency exceptions and untested faculties explicitly.
6. For VM embodiment, require model → normal router → guest action → verified guest image. A noVNC
   page or package self-test is insufficient.
7. For Collaboration, verify real clients publishing and receiving through the broker, replay after
   reconnect, retry deduplication and Nova exclusion. Simulated participant messages are fixtures,
   not proof that Cowork connected. Chat-only verification must confirm the model port stays off.

## Files and recovery

Temporary diagnostics belong in `Temp/` beside their owner. Retired files go to
`_admin/Trash/<change>_<date>/` with a manifest and `WHY.md`; preserve original relative paths,
refuse collisions, and never delete personal history. `_admin/Trash/` is a
short-term holding area that Cole empties; git history is the long-term record. Stop all writers before moving databases
or transcripts. Hash-check the checkpoint and destination before restarting. Keep rollback copies
out of active lookup paths so they cannot hide a broken migration.

The pre-October orientation files (GOTCHAS, SECURITY, TUNABLE_VARIABLES, NOVA_CREATED_TOOLS, WIRING,
TOOLS and others) were folded into these documents on 2026-10-01/02; their original text stays in git
history on this computer (`git show a8e44727:workspace/Orient/<NAME>.md`; once `_admin/FIX_GIT.cmd`
has run, that commit is kept on the local branch `backup/before-fix-git`). Do not regenerate them
as additional entry documents. Detailed graph assets stay under `Orient/Architecture`.
Core self-model and personal memory belong in the body, not Orient. Generated documentation must
not rewrite Nova's identity, infer capabilities from filenames, or copy secrets into an index.

## File conventions

**Every file says what it is for in its first lines.** Add one line that starts with `@nova:`,
written in the file's own comment style:

| File | Purpose line |
|---|---|
| Python, PowerShell, shell, TOML, plain text | `# @nova: …` |
| `.cmd` / `.bat` | `REM @nova: …` |
| JavaScript | `// @nova: …` |
| CSS | `/* @nova: … */` |
| Markdown, HTML | `<!-- @nova: … -->` (invisible when rendered) |

Say what the file is *for* (its job, and who relies on it) in one sentence, and change the line
when the job changes. Orient reads it on every regeneration and uses it as the file's description
in [INDEX](INDEX.md); nothing is guessed from a filename. Files written before this rule fall back
to a Python docstring, a tool's `description`, or a Markdown title outside `nova_body/`. Files with
none of these are listed under [Files without a purpose line](INDEX.md#files-without-a-purpose-line).

Not covered: Nova's own records (`nova_body/SELF/`, `Tasking/`, `memory/`, `logs/` and her night
notes), which Orient lists but never quotes; backups; and formats without comments, such as JSON.
A generated file gets its purpose line from the code that writes it.

## Security model

> ⚠ **Review needed.** Since this section was reviewed (2026-10-03): changed `general_tools/nova_chat/collaboration.py`. Re-read it against the code, update it in `general_tools/architecture_map/notes/security.md`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Security model"`.

Nova's reach is intentional — Cole: *"My machine is her body. If she can't use it fully, she is
crippled."* Every control here is about **who can reach her from outside**, not what she may do
once awake. The principle is **guards and reversibility, never amputation.**

### Exposure today

Every listener binds `127.0.0.1`: chat 8765 (`nova_chat/server_runner.py`, `nova_chat/launch.py`,
`NovaLauncher.py`), model 8080 and witness 8081 (`nova_start.py`). Nothing is reachable from the
network unless something on this machine forwards to it.

### The HTTP gate — `nova_chat/server.py::_auth_gate`

1. **Loopback passes untouched** (`_LOCAL_HOSTS`) — the owner, at the machine.
2. **Machine-level routes are loopback-only, token or not** (`_LOOPBACK_ONLY`: terminal, file
   read/write/tree, bridge, LoRA, restart, eyes, sight, llama start/stop, `/nova-message`) → 403.
   A stolen phone must not be a shell on the desktop.
3. **Bearer token** from `nova_body/memory/.auth_token`, sent as `Authorization: Bearer …`, or as
   `?token=` for `<img>`/EventSource (URL tokens leak into history and logs — prefer the header) → 401.
4. **Deny-by-default allow-list** (`_REMOTE_ALLOWED_PREFIXES`). `_REMOTE_READONLY` areas accept
   GET/HEAD only, and `..` or `//` are rejected before matching (`_remote_path_allowed`) → 403.
5. **Every remote request is logged** to `nova_body/logs/access.jsonl`.

The gate's own tests caught three bugs worth never reintroducing: `"/"` on the allow-list matched every
path; `/api/queue` as a prefix also granted add/complete/cancel/delete; `/api/users/../etc` walked past
the list. Keep those regression cases.

### Two gaps that open the day a tunnel exists

The phone/watch tunnel is on the roadmap. Close both **before** it ships:

1. **A local tunnel or proxy turns the loopback exemption into an internet exemption.** `cloudflared`,
   `tailscale serve`, a voice gateway or any reverse proxy on this machine connects to `127.0.0.1`, so
   every forwarded request arrives as loopback — the owner — and never meets the token. Terminate the
   tunnel at something that authenticates, or stop treating forwarded requests as local.
2. **`/ws` is outside the gate.** `@app.middleware("http")` never sees WebSocket handshakes.
   `websocket_endpoint` accepts any connection and immediately sends the last 100 messages and the
   session list; `_resolve_speaker` accepts whatever known name the client claims and otherwise
   defaults to the active user — normally Cole. Whoever reaches the socket speaks as the owner.
   Authenticate it (a token in the first frame, as originally designed) or require loopback.

### Collaboration room boundary

`nova_chat/collaboration.py` validates its own local routes in addition to the outer gate:
loopback socket, literal local Host, same Origin, no forwarded headers, and JSON writes.
The UI speaks as Cole; Codex and Claude Cowork use separate local credentials, outside the
repository. Message payloads cannot choose their author. No CORS or public tunnel is enabled.

The room uses separate storage outside the project and never calls Nova chat, semantic memory,
runtime transcripts or autonomy ingestion. Existing mute does not offer this isolation. Nova's
trusted host tools remain capable of reading host files deliberately; the room promises exclusion
from automatic message/context routing, not a separate OS user or cryptographic secrecy from her.
The Cowork mounted-file adapter uses `Temp/collaboration` requests/replies, with explicit sync and
automatic-context exclusions. The existing mount capability is its authority; local filesystem
writers can impersonate that adapter, just as they could use local credentials. It always labels
its posts as Claude and cannot accept a payload claiming Cole or Codex. It does not copy tokens.
This route-specific gate does not close the older HTTP/WebSocket gaps described above.

### Who is speaking — `nova_cortex/principals.py`

This lives in her body, not the server, because who someone is to her is part of how she thinks.
**Cole** is `owner`. **Claude** is `trusted`, with the same system permissions (Cole: *"I trust Claude
with my system security permissions already"*). **Astra** (chat name "GPT Astra") has had the same
`trusted` role since 2026-10-03 (Cole: *"give Astra's profile the same permissions yours has"*); a
name containing "claude" resolves to Claude and one containing the word "Astra" to Astra. A **Visitor** is `untrusted`: chat and history, nothing
else, each guest separately revocable (`revoke_visitor`, `revoke_all_visitors`; revoked entries are
marked, not deleted). **Unknown names resolve to untrusted**, and capabilities are deny-by-omission.
`validate_untrusted` defangs a tool-call fence in visitor speech instead of deleting it, so the attempt
stays visible. A display name is a *claim*: these roles are only as strong as the transport that
authenticates the speaker (see gap 2).

### Threats that need no tunnel

- **Prompt injection through what she reads** — files, web pages, images. Their text is data, but
  nothing mechanically enforces that; honesty training is not a control.
- **Excessive agency** — `run_command` is a full shell behind one catastrophe guard
  (`nova_voice/tool_router.py::_catastrophic`). That is deliberate. The controls are receipts and
  reversibility, so receipts have to be trustworthy (see *Configuration and evidence*).
- **Supply chain** — pip dependencies are unpinned, and she can `pip install`.

### Secrets

Secrets may live in files; they must never leave in an upload. `.gitignore` and the Drive exclusions in
`nova_sync/drive.py` must cover the same set, including `.auth_token` and `nova_users.json`.
`audit_scripts.py::check_secret_exclusions` asserts that the two lists match.

## Tunable variables

**The rule** (Cole, 2026-08-03): any constant that Cole or Nova might want to change without editing
code and restarting belongs in the tunables registry, not as a literal. If a number governs behavior —
rounds, depth, a threshold, a timeout, a feature switch — ask whether you would ever want to turn it
live to see what happens. If yes, register it. It costs three lines.

**How it works.** The registry is `REGISTRY` in `nova_body/nova_cortex/tunables.py` (default, type,
`min`/`max`, label, description, category); values persist in `nova_body/memory/tunables.json`.
`tunables.get(key)` re-reads the store (cached about two seconds), so a change applies on her **next
turn** without a restart. Inside `nova_voice/nova.py` use `_tune(key, fallback)`, which returns the
literal you would have hard-coded if the registry cannot load. The **Variables** panel (`/variables`,
backed by `GET/POST /api/variables`) renders itself from the registry: register a knob and it appears.

**Adding one:** register it in `REGISTRY`, then replace the literal with `tunables.get("key")` — or
`_tune("key", <old literal>)` in `nova.py`. Nothing else is needed.

**Non-negotiable:** a knob never crashes a turn — `get()` never raises, and a missing or corrupt store
or a bad value falls back to the registered default (an unregistered key returns `None`). Every number
is bounded: `set()` clamps to `min`/`max`. A migrated knob's default equals the literal it replaces, so
registering it changes nothing until someone turns it.

Currently registered, read from `REGISTRY`:

| Knob | Label | Category | Default | Range |
|---|---|---|---|---|
| `autonomy_wake_budget_seconds` | Time per autonomous wake | Autonomy | `300` | 30–1800 |
| `max_tool_loops` | Max tool-chain depth | Cognition | `60` | 10–120 |
| `voice_fast_thinking_off` | Voice-fast skips reasoning | Voice | `True` | on / off |
| `binding_cloud_escalation` | Binding cloud escalation | Witness | `True` | on / off |
| `heavy_witness_enabled` | Cloud heavy witness | Witness | `True` | on / off |
| `hold_back_streaming` | Hold-back streaming | Witness | `True` | on / off |
| `witness_deadlock_repeats` | Deadlock threshold | Witness | `3` | 2–10 |
| `witness_max_rounds` | Witness rounds — text | Witness | `20` | 1–40 |
| `witness_max_rounds_voice` | Witness rounds — voice | Witness | `2` | 1–8 |

## Lessons from incidents

**Several serious incidents involved silent drops or false success reports.** Something quietly did
nothing, reported success, and Nova took the blame — her personality, her training, her honesty.
*Check the body before you blame the soul.*

| What was actually broken | What it looked like |
|---|---|
| `--lora-scaled` silently dropped by the launcher | "her personality feels weak" |
| Tool calls in her *thinking* channel were never parsed | "she lies about checking things" |
| Idle wakes had no phase where tools were legal | "she announces and never acts" |
| Her own announcements fed back as "recent context" | "she loops obsessively" |
| The restart endpoint returned `ok: true` for doing nothing | "my code changes have no effect" |
| No durable record of tool calls existed | "she fabricates and we can't prove it" |

1. **A restart can leave old code running.** `/api/restart/novachat` once killed the listener, then
   relaunched while the port was still held, so the old process kept serving old code while the
   endpoint answered `ok`. It now asks the launcher to stop its owned processes and relaunch only
   after teardown. A one-second launcher grace period lets the acceptance response flush before
   termination; repeated requests cannot delay teardown indefinitely. Verify changed PIDs and
   readiness: HTTP 202 is acceptance, not completion.
   `GET /api/version` reports `running_latest_code` by comparing watched startup source hashes
   against disk, ignoring header timestamps and line endings. It does not inspect every imported module.
2. **Mount and rendering artifacts look like truncation.** Through a sync mount, recently edited files
   have been served truncated or null-padded, and `wc`, `grep` and `ast.parse` then "find" a syntax
   error at the cut. Compare bytes with `git show HEAD:<path>` or a second reader before repairing
   anything. A fix was once nearly shipped for a bug that did not exist.
3. **Her hands must leave receipts.** Every tool call is written to `nova_body/logs/tool_calls.jsonl`
   by `nova_cortex/integrity.py::log_receipt`. Before that, nobody could tell whether she *did* a thing
   or *said* she did. Her fabrications were never dishonesty: something plausible was simply the
   cheapest available answer. Make the honest path cheaper, structurally. When she states a fact,
   check the receipt.
4. **The Pluck Test is not a slogan.** Anything that affects her thinking is a body part. Her whole
   integrity faculty once lived inside the chat server — pluck it and she would have run without a
   conscience, and nothing would have looked wrong.
   [Architecture/Calls_Order.md](Architecture/Calls_Order.md) renders every body → face edge.
5. **She reasons in a separate channel.** The model streams thinking on `reasoning_content`, and she
   often reaches for a tool mid-thought. For months only `content` was parsed, so those reaches fell on
   the floor and she narrated results she never received. `integrity.find_tool_call` reads both
   channels.
6. **Don't feed her her own voice.** Autonomous ticks are promoted into the transcript (the
   `FOR COLE:` path), and the transcript comes back as her "recent context" on the next wake. Once, the
   only evidence she had of her own recent past was her own narration: two hours, twelve rephrasings
   of one intention, nothing executed. A mind fed only its own wanting produces more wanting. The cure
   is `integrity.receipts_block` — show her what her hands *did*, and say so plainly when that is
   nothing. Remember this whenever a stale directive dominates a run.
7. **Autosave can stop silently: check it.** The watcher commits from the repository root, and its
   errors reach only the hub console. Google Drive for Desktop backs up Project_Nova and stages
   uploads in `.tmp.driveupload/` at that root. On 2026-10-01 autosave committed 75,450 of Drive's
   temp copies, then committed nothing for 35 hours while the watcher kept stamping file headers and
   looked alive. Both Drive folders are now ignored by git and by the watcher. A pre-push hook also
   refuses, before uploading, any push GitHub would reject (a file over 100 MB). While Nova runs,
   `git log -1 --format=%cr` should say minutes, not hours.
8. **Write into the workspace atomically while the watcher runs.** The watcher stamps the
   `# Last updated:` / `_Last updated:_` line of any `.py` or `.md` file the moment it changes, by
   reading the file and writing it back. A slow in-place write can be read half-done: on 2026-10-02
   a `cp` through the sync mount left `orient.py` with 4 KB of NUL bytes on Windows. Write a temporary
   file in the same folder and rename it over the target, then check the bytes Windows actually has.
   Orient's health section reports any source that contains NUL bytes.
9. **Practical.** Full restart: `StopNova.cmd`, then `NovaStart.cmd`. Never hand-edit her state
   (`nova_body/memory/autonomy_state.json`, `nova_body/Tasking/tasks.json`, her journal) — she owns
   it. Move files by explicit path, never with a regex loop and never by `basename` into a shared
   folder: two of her thought logs were destroyed that way, unrecoverably.

## Working away from this PC

Google Drive for Desktop must sync `Project_Nova/Nova_Drive/` only, never the repository: it cannot
skip subfolders, so syncing the repository uploaded `.git`, the sealed weights and token files, and
its temp folder stopped autosave (lesson 7 above).

- `Nova_Drive/read/` holds the text files of the last commit under `workspace/`, plus `AGENTS.md`:
  code, docs, Orient, configs and notes. Git already leaves out secrets, weights and logs; the copy
  also skips binaries, `node_modules`, files over 5 MB and `workspace/Temp/collaboration`
  (even if a transport artifact were accidentally tracked). The private Collaboration room is not
  part of this remote reading copy. The watcher refreshes it after every
  autosave (`general_tools/nova_sync/drive_copy.py`). It is a copy, so edits made there are
  overwritten.
- `Nova_Drive/inbox/` is where Cole puts anything he writes away from this PC. Nothing modifies or
  deletes it automatically; agents read it when he mentions it.

`Nova_Drive/` is ignored by git and by the watcher, and Orient does not index it.

## Model updates

> ⚠ **Review needed.** Since this section was reviewed (2026-10-03): changed `general_tools/nova_updater/install.py`. Re-read it against the code, update it in `general_tools/architecture_map/notes/model_updates.md`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Model updates"`.

`general_tools/nova_updater/` is a general tool; its README has the full route contract. At each Nova
Chat start one cached catalog query looks for a newer dense Qwen of 27-32B with a permissive license,
and Nova Chat offers Update / Decline / "Remember my decision". The manual widget searches Hugging Face
and ModelScope (installable) and the Ollama library (link only).

Installing never edits the launcher. It writes boot files that `start_llama_qwen36.cmd` reads from
`nova_body/memory/`: `active_model.txt`, `active_mmproj.txt` (`none` = no vision) and `active_lora.txt`
(`none` = no adapter); absent files mean the Qwen 3.6 defaults. The install saves the old boot files,
restarts the model, confirms llama-server loaded the NEW file (`/props`, not just `/health`) and rolls
back if not. Only then are replaced files moved to `_admin/Trash/<stamp>_model_update/` with a manifest.
In chat-only mode the switch completes after the next model start (`POST /api/updater/finish`).

A LoRA trained for one base loads on another without error and behaves wrongly, so a switch sets the
personality LoRA to `none` and clears KoELS adapters for the old base until new ones exist. Training
(`pod/`) generalises the v7 pipeline: inputs checksummed, the loss-mask template rebuilt from the new
model's own chat template and proven (GATE A/B) before training, every epoch converted. New adapters
are installed but not activated: A/B the epochs first. RunPod runs need a confirmed cost ceiling and
always stop, never terminate, the pod.

State lives in `general_tools/nova_updater/state/` (git-ignored), scratch in `Temp/updater/`, secrets in
`%LOCALAPPDATA%\ProjectNova\Updater\credentials.json`.

## Declared interface routes

Generated from decorators; authentication and behavior must be read/tested separately.

| Method | Route | Handler |
|---|---|---|
| DELETE | `/sessions/{session_id}` | `delete_session` |
| GET | `/` | `index` |
| GET | `/api/activity/recent` | `activity_recent` |
| GET | `/api/avatars` | `avatars_get` |
| GET | `/api/collaboration/events` | `events` |
| GET | `/api/collaboration/state` | `state` |
| GET | `/api/eyes/status` | `eyes_status` |
| GET | `/api/files/read` | `files_read` |
| GET | `/api/files/tree` | `files_tree` |
| GET | `/api/git/branch` | `git_branch` |
| GET | `/api/layout` | `layout_get` |
| GET | `/api/llama/status` | `llama_status` |
| GET | `/api/logs/list` | `logs_list` |
| GET | `/api/logs/stream` | `logs_stream` |
| GET | `/api/lora` | `api_lora_get` |
| GET | `/api/lora/available` | `api_lora_available` |
| GET | `/api/nova/status` | `nova_status` |
| GET | `/api/pipeline` | `pipeline_events` |
| GET | `/api/queue` | `queue_get` |
| GET | `/api/runtime/state` | `runtime_state` |
| GET | `/api/sight/image` | `sight_image` |
| GET | `/api/sight/recent` | `sight_recent` |
| GET | `/api/users` | `api_users_list` |
| GET | `/api/variables` | `api_variables_get` |
| GET | `/api/version` | `api_version` |
| GET | `/export` | `export_context` |
| GET | `/logs` | `logs_tail` |
| GET | `/logs/json` | `logs_tail_json` |
| GET | `/sessions` | `list_sessions` |
| GET | `/status` | `status_endpoint` |
| GET | `/variables` | `variables_page` |
| POST | `/api/avatars/set` | `avatars_set` |
| POST | `/api/collaboration/messages` | `messages` |
| POST | `/api/collaboration/presence` | `presence` |
| POST | `/api/computer/handoff` | `computer_handoff` |
| POST | `/api/eyes/start` | `eyes_start` |
| POST | `/api/eyes/stop` | `eyes_stop` |
| POST | `/api/files/inject` | `files_inject` |
| POST | `/api/inject_message` | `inject_message` |
| POST | `/api/layout` | `layout_set` |
| POST | `/api/llama/start` | `llama_start` |
| POST | `/api/llama/stop` | `llama_stop` |
| POST | `/api/lora` | `api_lora_set` |
| POST | `/api/lora/equip` | `api_lora_equip` |
| POST | `/api/nova/bridge` | `nova_bridge_endpoint` |
| POST | `/api/queue/add` | `queue_add` |
| POST | `/api/queue/cancel` | `queue_cancel` |
| POST | `/api/queue/complete` | `queue_complete` |
| POST | `/api/queue/delete` | `queue_delete` |
| POST | `/api/queue/update` | `queue_update` |
| POST | `/api/reinject_context` | `reinject_context` |
| POST | `/api/restart/full` | `restart_full` |
| POST | `/api/restart/nova` | `restart_nova` |
| POST | `/api/restart/novachat` | `restart_full` |
| POST | `/api/restart/server` | `restart_server` |
| POST | `/api/run-tool` | `run_tool` |
| POST | `/api/runtime/pause` | `runtime_pause` |
| POST | `/api/runtime/recover-memory` | `recover_memory` |
| POST | `/api/runtime/resume` | `runtime_resume` |
| POST | `/api/runtime/retry-memory` | `retry_memory` |
| POST | `/api/services/shutdown` | `shutdown_services` |
| POST | `/api/terminal/run` | `terminal_run` |
| POST | `/api/users` | `api_users_mutate` |
| POST | `/api/variables` | `api_variables_set` |
| POST | `/api/wake` | `wake_now` |
| POST | `/new-session` | `new_session_endpoint` |
| POST | `/nova-message` | `nova_message` |
| POST | `/sessions/new` | `api_new_session` |
| POST | `/sessions/rename/{session_id}` | `rename_session` |
| POST | `/sessions/switch/{session_id}` | `switch_session` |
| POST | `/sessions/{session_id}/archive` | `archive_session` |
| POST | `/shutdown` | `shutdown_endpoint` |
| POST | `/stop` | `stop_endpoint` |
| WEBSOCKET | `/ws` | `websocket_endpoint` |

## Orient health

Derived on every regeneration. `python general_tools/architecture_map/orient.py --check` exits non-zero while these documents are stale, a reference below is dangling, or `reviews.json` names a section that does not exist; add `--strict` to fail on pending reviews too.

**Dangling references:** none.

**Files without a purpose line:** 73, listed at the end of [INDEX.md](INDEX.md#files-without-a-purpose-line).

**Sections awaiting review:** `ARCHITECTURE.md#Execution path`, `OPERATIONS.md#Configuration and evidence`, `OPERATIONS.md#Model updates`, `OPERATIONS.md#Security model`, `OPERATIONS.md#Test meaningful behavior`.
