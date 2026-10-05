<!-- @nova: Explain how to run, inspect, verify and recover Project Nova. -->
# Operations and verification

_Facts regenerated 2026-10-05T18:05:33+00:00 from source (input `6be81c8b902b`). Explanations carry their own review dates, and ⚠ marks a section whose sources changed since its review. Source-derived facts are not runtime certification._

## Run and stop

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/NovaLauncher.py`, `general_tools/nova_chat/server.py::startup_event`, `general_tools/nova_chat/server.py::stop_endpoint`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Run and stop"`.

| Operation | Entry point | Check |
|---|---|---|
| Normal stack | `NovaStart.cmd` | `/api/version`, model readiness and actual generation |
| Controller with Nova off | `NovaChatOnly.cmd` or `python nova_start.py --chat-only` | `/api/version` reports `chat_only`; no model, witness, guardian, watcher or autonomy is started |
| Start/stop Nova; keep controller open | Conversation widget power button; POST `/api/nova/start` or `/api/nova/stop` | `/api/nova/lifecycle` reaches `on` or `off`; verify service ports and generation separately |
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

The Services menu (and optional Services widget) provides Restart app and services / Shut down
app and services. These controls stop current work and request launcher-owned teardown. HTTP 202 acknowledges acceptance; it is not proof of completion. Confirm
old processes exit and, for restart, new PIDs become ready. The launcher gives the accepted request
one second to flush its response before teardown; repeated requests do not extend that deadline.
The launcher stops the guardian before
services and refuses a replacement while owned ports remain occupied. Repeated matching requests
are idempotent; a competing shutdown/restart request is rejected. Model-only Stop targets port 8080
and leaves the independent witness on 8081 running. Model stop/restart waits up to ten seconds for the old socket
to close; failure is reported instead of acknowledging a skipped restart. KoELS propagates that
failure. Starting an already starting model is a no-op.

Chat-only mode retains the desktop controller and the separate Collaboration widget. It does not
turn on Nova when a message arrives. Conversation's compact power button below the composer offers
**Start Nova**, explicitly enabling the full stack, or **Stop Nova**, which drains work, saves the active
session and returns to chat-only. Voice has a separate **End call** action: it stops local audio and
requests cancellation of only its owned pending response, while Nova and the controller remain on. The launcher
stops its guardian/watcher before replacing workers and refuses a worker teardown without a
successful quiesce acknowledgment. The inner full worker allows the same 60-second startup window as
the controller, while an exited server thread fails promptly. A slow import must not be killed
by the former shorter 25-second inner timeout before the controller's deadline. New body input and updater mutations are blocked while a switch
is pending. Failed startup attempts return to a usable chat-only controller when recovery succeeds.
The main window and console stay open; the page reconnects and restores its unsent composer draft.
The launcher uses `start_llama_qwen36.cmd`, so its model selection matches the updater's boot files.
A launcher predating this feature needs one full app restart; refreshing the page alone cannot
upgrade that process. Start/Stop remains unavailable when lifecycle support cannot be reached. It
refuses to attach to an already-running full server as though that server were dormant. The
Collaboration room also works during a normal launch without being fed to Nova's conversation.
Both modes start the updater catalog check after a cancellable delay; this does not start the model
or enumerate installed weights. The controller status bar distinguishes Chat only from Nova running.
Starting Nova can recover body-admitted unfinished work even when autonomous scheduling is paused.
It waits for model readiness, restores original sessions where available and otherwise resumes via
the body transcript. Explicitly stopped inputs stay cancelled. An uncertain prior action is held for
observation/reconciliation before further mutations; inspect the runtime recovery status if it waits.

## Configuration and evidence

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/nova_chat/server.py::_CODE_FILES`, `nova_body/nova_cortex/workspace_context.py`; new `general_tools/NovaLauncher.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Configuration and evidence"`.

Collaboration is a detachable controller service (`general_tools/nova_chat/collaboration.py`). Its
SQLite history and per-agent credentials live outside the repository at
`%USERPROFILE%/ProjectNovaData/Collaboration`. Messages never enter chat sessions, runtime transcripts,
semantic indexing, task inboxes or autonomy events. Mentioning Nova there does not invite her.
This is exclusion from automatic routing, not an OS restriction on her deliberately trusted tools.
`NOVA_COLLABORATION_DIR` may select an explicit shared location. The default avoids AppData:
Windows can redirect packaged Codex and ordinary desktop processes to different AppData copies.
The October 4 repair preserved and merged the two stores; old histories remain in backup.
Do not silently fall back to an older AppData room or credential file.
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
Its Latest control appears above a 60-pixel bottom gap, including manual scroll; incoming messages
preserve the older reading position until Latest is chosen. This changes the view, not room routing.
`general_tools/nova_collaboration` provides a CLI and a Cowork local MCP plugin. Neither substitutes
an API model for the actual app session nor automatically wakes an ended Codex/Cowork turn.

Body settings live in `nova_body/nova_config.json`; live knobs in
`nova_body/memory/tunables.json`. The Variables widget reads the cortex registry and updates
those knobs. The provider launcher still has its own flags, and some body modules retain constants:
editing one configuration file does not imply every subsystem obeys it.

Adapter intent is in `nova_body/memory/active_lora.*`; KoELS desired/boot state lives beside it.
Model intent is in `active_model.txt` / `active_mmproj.txt` beside them (model updater).
Read the runtime's configured adapter status first; inspect relevant model metadata when needed. Keep secrets excluded
from both Git and Drive, including relocated `.auth_token` and `nova_users.json`.

Useful evidence lives under `nova_body/logs/`: `tool_calls.jsonl`, `generation_trace.jsonl`,
events, runtime transcript, chat sessions and launcher/model logs. Read current receipts and loaded
source before changing prompts. `/api/version` compares normalized content hashes of watched
sources against startup, including task/context assembly, `nova_runtime/conversation.py`,
`nova_cortex/context_budget.py`, request/audit contracts, durable recovery, transcript/session
publication, optional heavy-audit adapter and the opt-in provider diagnostic helper, while
ignoring watcher header timestamps and line endings. This detects even
same-size edits with unchanged timestamps; it is not a census of every imported module.
New structured receipts distinguish success, failure, refusal,
timeout, cancellation and unknown. Guest receipts include their shell/display context. Pipeline
shows tool start and terminal outcomes rather than only witness work; its operation IDs link to
the tool ledger. Unknown terminal tool outcomes use neutral `tool_finished`, not a successful
completion label. Witness reads show attempted/returned/refused/failed counts, not a blanket
verified label; returned output is not proof that the claim was checked. Witness incomplete/error
statuses are unverified, never approval. A historical
`witness_answered` with an incomplete/error status remains visibly unverified. Historical
Pipeline rows whose recorded approval contains a tool request are shown as incomplete by the
controller without rewriting the original log. Historical receipts retain their original values; older
`ok: true` entries can mislabel nonzero exits. Validate their artifacts independently. A running
port does not prove successful inference. The Control widget exposes task scheduling, verification,
stop/resume, memory ingestion health and VM handoff through `/api/runtime/state` and related routes.

For active continuation, a queued `mode="steer"` acknowledges admission, not that the model has read
it. `message_context` records applied input with an `input_revision` and aligned request/reply lists;
final delivery carries the covered inputs for that response/run. Acknowledgement now follows durable
body inbox admission; checkpoint failure produces a correlated terminal rejection. Completed parts
are atomically persisted before coverage is committed. Saved output and recovery checkpoints are
reconciled by exact run/part/text, not a guessed success. Nullable request IDs belong to
foreign typed entries, not an acknowledged local voice request. Compact protected action facts keep
IDs/status and hashes when ordinary observations are shortened; inspect the actual ledger/output for
details. A hash or retained status is not independent verification or a copy of the full observation.

## Access and practical debugging

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/voice_gateway/control_worker.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Access and practical debugging"`.

Nova's host access is intentional. The chat server has loopback exemptions, bearer authentication
for remote HTTP clients, and restrictions on remote routes. Speaker capability checks are a separate
layer: an unknown display name resolves to untrusted. A name added in the UI is not automatically
an owner principal. Inspect the current middleware and principal registry before changing exposure;
these source observations are not a fresh penetration test. The separate Collaboration routes
add a local Host/Origin/forwarding gate; this does not repair older HTTP or WebSocket gaps.
Secrets stay out of Git and Drive.

Conversation power uses a separate local lifecycle gate and launcher status. If it reports that a
restart is needed, inspect both the chat worker and launcher versions; a fresh static page can still
be connected to old processes. `starting`/`stopping` acknowledge work in progress, not readiness.

For desktop voice, open **Widgets → Voice → Settings & tests**. Run
`voice_gateway/setup_windows.py` to recreate the isolated CPU environment and pinned speech assets.
The default is faster-whisper large-v3-turbo, CPU int8, English, with local Silero VAD and temporary
Windows system speech. Readiness checks dependencies and selected assets without audio capture;
choose a listed compatible device, apply while stopped and explicitly run microphone/speaker tests.
A playback API receipt still needs human confirmation on the intended output. Call Nova is explicit
and does not restart automatically after a worker error or Nova restart.

Voice's Delivery & playback details show the current request/message/run IDs, delayed/suppressed
reply reason and actual output phases. A requested unit is not yet playback; process launch is not a
measured audio start. Check `last_turn` versus `last_playback`, output device, audit disposition and
source fingerprint before attributing silence to the model. Check the confirmed microphone and speaker
mute indicators first: output mute deliberately makes replies silent. Hearing you, Finishing your turn,
Recognizing speech and Waiting for Nova describe separate capture/processing stages. The default
2,000 ms quiet interval is an endpointing allowance, not a reply-time guarantee; continued speech during
CPU recognition may be combined before one transcript is sent.
New utterances retire obsolete local audio and join active body work at completed model/tool steps;
they do not issue Stop or discard already committed queued speech. Inspect the applied `message_context` revision rather than interpreting the
admission badge as an immediate provider interruption. End call retires local output immediately and
requests cancellation through its owned pending request IDs. An ID already incorporated into shared
active conversation work selects that combined run, not a reversible deletion of one input. It waits
briefly for final scoped acknowledgement; an unconfirmed receipt does not justify claiming all
provider computation ended.

For a bounded provider investigation, `Temp/provider-diagnostics/capture.json` explicitly enables
capture with a unique `capture_id` and timezone-aware `expires_at` for at most ten minutes. Receipts
preserve fitted provider JSON fields and context/memory/provider/audit timings, with image data URLs
removed and file/count/byte caps. Capture is off without a valid marker; remove it when the diagnostic
run ends. It records transient conversation content, so keep receipts local in excluded Temp and
never treat them as ordinary project documentation.

The voice loop parses tool reaches from both content and reasoning streams. Receipt-backed context
helps distinguish executed work from earlier narration. Check loaded source, actual receipts,
adapter status, and call order before changing personality or training. Rendering/mount artifacts
can resemble damaged source: compare actual local bytes before repairing a supposed truncation.
On remote training hosts, stop GPU use while retrieving/verifying results; after successful local
preservation, delete the disposable training pod to release its attached storage. Keep unverified
results recoverable and surface any retained-storage charge. The Hugging Face cache belongs on local
disk rather than a slow network mount.

## Test meaningful behavior

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/nova_chat/tests/test_segment_metadata.py`, `general_tools/nova_chat/tests/test_voice_transport.py`, `nova_body/tests/test_model_client.py`, `nova_body/tests/test_witness_delivery.py` and 1 more; new `general_tools/NovaLauncher.py`, `general_tools/cloud_call.py`, `general_tools/nova_chat/server.py::_recover_face_inputs`, `general_tools/nova_chat/server.py::_resolve_speaker` and 8 more. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Test meaningful behavior"`.

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
8. For the updater, run the Nova Chat integration tests and `nova_updater/tests` against disposable
   fixtures, plus `node general_tools/nova_chat/tests/test_updater_ui.cjs`. The Windows launcher tests
   replace llama-server with an argument recorder. They prove parsing, not a real model load.
   A successful simulated install or GPU quote does not certify a real download or paid training run.
   The opt-in pod compatibility tests exercise a tiny actual model, assistant masks and GGUF conversion;
   Linux venv tests check dependency isolation and local storage. A full run additionally needs actual
   optimizer progress, retrieved/checksummed epoch adapters, complete saved provenance and confirmed
   pod deletion. Cleanup tests must also prove failed verification retains remote recovery data and
   failed deletion reports a storage warning instead of claiming costs have ended.
   Behavioral A/B evaluation and runtime activation remain separate from training completion.
9. For the controller, verify menu opening does not rearrange widgets, layout changes survive reload,
   old popouts close before switching layouts, and small windows keep controls reachable.
10. For Conversation power, run `test_lifecycle.py`, `test_launcher_mode.py` and
    `node general_tools/nova_chat/tests/test_conversation_power.cjs`. Fixtures cover draining,
    updater conflicts, inherited transition guards, failed startup, app-quit cancellation and draft
    restoration. A browser fixture can prove buttons/reconnection with simulated services; the
    separate live check must confirm full start/stop, model readiness and native window continuity.

11. For voice, run `general_tools/nova_chat/tests/test_voice_transport.py`, `nova_body/tests/test_model_client.py`,
    `nova_body/tests/test_witness_delivery.py` and the gateway's `test_voice_flow.py`,
    `test_link_socket.py` and `test_committer.py`. Use fake providers/audio and disposable state first.
    Distinguish a local socket fixture from a live Nova turn; test wrong identities, delayed replies,
    cancellation during synthesis, Stop, queue replacement and audit status before native playback.
    Measure mic/STT, first-audio latency, interruption and avatar timing separately on real hardware.
    The Voice widget and controller also have `test_voice_control.py` and `test_voice_ui.cjs` coverage;
    native/API/segmentation tests are in `voice_gateway/test_native_voice.py` and
    `test_worker_readiness.py`. Include acknowledgement delays past 300 seconds, scoped Stop that cannot
    cancel another socket's request, recognizing-state reporting, device/output failures and actual
    request/message/run correlation. `--smoke-link` remains silent; `--smoke-audio` uses real TTS and
    refuses NullTTS. Both exercise the request sweeper. Status-only checks must never acquire devices.
    Keep microphone capture,
    silent WAV transcription, audible playback, live Nova replies and native avatar timing distinct.
    Cole authorized Nova and audio tests on October 5; future restrictions override that permission.
12. For active conversation continuation, include `nova_body/tests/test_conversation.py`,
    `nova_chat/tests/test_voice_transport.py`, gateway `test_voice_steering.py` / `test_stt_turns.py`,
    and `nova_chat/tests/test_queue_badge.cjs` (the latter paths are under `general_tools/`). Check
    ordered follow-ups during provider/tool work, retained original input and completed-action facts,
    no execution of an obsolete proposal, audit/final revision agreement, final-seal admission races,
    explicit Stop and other-conversation isolation. Protected input that exceeds the context budget
    must fail explicitly rather than disappear. Mixed typed/voice aliases must match exact local
    acknowledgement pairs, response/run identity and input revision before speech is eligible.
    The relocation case in `test_conversation.py` copies selected Python packages into a temporary body
    and runs two continuation cases plus segment, natural-boundary and work-owner/headless suites
    with fake providers/tools in a fresh subprocess without the chat face. It proves those code paths
    can run there; it does not test personal-state migration, real inference,
    all faculties or denied access to the original workspace. It is not a substitute for step 5.
    For committed segments add gateway `test_voice_segments.py` and controller
    `test_conversation_segments.cjs`: prove a part is delivered before final closure, a frozen earlier
    revision uses its exact recorded binding, duplicate/gap frames cannot replay audio, final aggregate
    is not spoken/stored twice, and explicit Stop preserves delivered text while cancelling remaining
    work. Barge-in must retain queued committed units but pause them through recognition; close/Stop
    must prevent held or synthesizing units from playing later. Open bound input must retain exact
    correlation past the delay threshold until terminal closure. Include controller
    `test_segment_metadata.py` and body `test_conversation_context.py` for durable audit attribution
    and identical face/headless formatting. Body `test_work_owner.py` and `test_autonomy_boundaries.py`
    cover exclusive admission before awaits, natural-step attention without recursive human turns,
    retained tool receipts, task-change reconciliation, scoped Stop with cleanup, scheduler survival,
    headless captured-sequence coverage and no terminal aggregate duplication. Keep these isolated
    checks separate from live task continuity and full personal-state relocation evidence.

13. For durable ongoing work, run `nova_body/tests/test_work_recovery.py`, the face's
    `tests/test_voice_transport.py`, `test_segment_metadata.py` and `test_session_pins.py`.
    Exercise pre-ack disk failure, crash between segment publication/checkpoint, Stop on a full disk,
    unrelated input during recovery, uncertain effects and real-receipt reconciliation. Relocation
    must use disposable identity/memory/task fixtures and deny reads of the source body; report model
    dependencies separately from files carried by the body. Never edit personal records for fixtures.
14. Run gateway `test_capture_output_gate.py`: a reply arriving mid-capture must stay queued;
    recognition completion/reset/error must release output, while mute/Stop still prevents it.
    Score ASR errors separately from transport order. WAV synthesis proves a file, not audible
    playback. Natural microphone/speaker quality and final voice selection need their own evidence.

15. Run body `test_request_contract.py`, `test_audit_protocol.py`, witness delivery/replay checks
    and ModelClient forwarding tests. Verify actual admitted request identity, no stale cancelled
    restrictions, late permission changes before dispatch, frozen candidate obligations, explicit
    follow-up relevance, and no-tools enforcement across main, inline and optional heavy paths.
    Constrained JSON only proves valid format; real response content requires live acceptance.

## Files and recovery

Local Python `.venv/` and `venv/` trees are dependencies, including any model assets installed inside
them. Root/workspace Git rules exclude them; built-in filters also keep them out of watcher events,
audit queues, timestamp/PUP writes, Drive scans/indexes, weekly source backups, the committed-file
Drive reading copy, path repair and automatic context injection. Orient already prunes both names.
Deliberate file/host tools remain available. The watcher reads the repository-root `.aignore` once at
startup; `workspace/.aignore` is a reference list, not a shared live configuration consumed by every
sync component. Do not assume editing it updates all filters or the running watcher.
Adding Git ignore rules does not untrack an existing dependency tree: verify the exact path before
index-only removal and retain its installed files. Existing processes need a normal restart to load
source-level exclusions. Reconstruct environments from their setup instructions, rather than relying
on source backup archives to contain third-party packages.

Temporary diagnostics belong in `Temp/` beside their owner. Retired files go to
`_admin/Trash/<change>_<date>/` with a manifest and `WHY.md`; preserve original relative paths,
refuse collisions, and never delete personal history. `_admin/Trash/` is a
short-term holding area that Cole empties; git history is the long-term record. Stop all writers before moving databases
or transcripts. Hash-check the checkpoint and destination before restarting. Keep rollback copies
out of active lookup paths so they cannot hide a broken migration.
The watcher preserves `_admin/Trash/` bytes: timestamp maintenance and PUP replacement skip
archived originals while normal change/backup queues still work. Dated manifests record source
paths, reasons and hashes. This October 4 archive is read-only to block the already-running
older watcher until its next normal restart loads the exclusion.

The pre-October orientation files (GOTCHAS, SECURITY, TUNABLE_VARIABLES, NOVA_CREATED_TOOLS, WIRING,
TOOLS and others) were folded into these documents on 2026-10-01/02; their original text stays in git
history on this computer (`git show a8e44727:workspace/Orient/<NAME>.md`); the completed history repair
preserved that commit on the local branch `backup/before-fix-git`. Do not regenerate them
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

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/NovaLauncher.py`, `general_tools/nova_chat/server.py::_resolve_speaker`, `general_tools/nova_chat/server.py::_stop_request`, `general_tools/nova_chat/server.py::websocket_endpoint`. Re-read it against the code, update it in `general_tools/architecture_map/notes/security.md`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Security model"`.

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
   session list; `_resolve_speaker` accepts a claimed registered name. An explicitly unknown name now
   stays unknown/untrusted, but omitting the name still defaults to the active user, normally Cole.
   Whoever reaches the socket can still claim that identity; fixing fallback attribution is not authentication.
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

### Conversation lifecycle boundary

`nova_chat/lifecycle.py` shares the updater's loopback, literal Host, same-Origin, no-forwarding and
JSON-write checks. It proxies mode requests to the launcher hub. The hub's new mode POST routes
require direct loopback JSON requests without browser Origin or forwarding headers; browser clients
use the guarded chat route. Pending transitions reject new body operations over HTTP and WebSocket
and block updater mutations. This is lifecycle coordination, not a repair of the older transport
identity gaps. Quiesce is accepted only during a pending transition and must acknowledge drained
operations and saved session state before the owned worker is terminated.

Voice request IDs, reply links and run IDs are correlation fields, not authentication. They let
clients reject unrelated or stale output; they do not close the WebSocket exposure described
above. Chat-only and lifecycle rejections may complete a correlated request without storing its
text in Nova's body. Request-scoped `stop` additionally matches the request ID to the exact originating
WebSocket; stale, invalid or another socket's IDs cannot select its work and never fall back to global
Stop. When several inputs have joined the same active body turn, an owned incorporated request ID
selects that shared run: explicit Stop can end the combined work, not merely retract that input.
Aligned continuation request/reply lists and input revisions preserve correlation; a foreign typed
entry with a null request ID cannot act as an acknowledged local voice request. These fields add no
authentication or cross-conversation authority. Final acknowledgement has `stopped`, the request ID
and `matched`; pending cleanup is explicitly `stop_pending`. This bounds cancellation ownership,
not who can connect or claim a speaker name.
A future remote voice gateway still needs the transport identity work above.

### Local audio controls

`nova_chat/voice_control.py` exposes `/api/voice` only to direct loopback requests with a literal local
Host, matching browser Origin, no forwarding headers and JSON writes. This controls host audio devices;
remote chat access does not grant microphone activation through this API. Status probes never capture
or play audio. Explicit commands own one hidden worker, with cooperative Stop and a bounded owned-PID
tree fallback; runtime shutdown closes it. Device IDs live in detachable `_admin/voice_devices.json`.
The worker's speech transport still uses the existing WebSocket, whose identity limits are described
above; an audio-control route guard is not a replacement for transport authentication.

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

Audit evidence controls include `witness_receipt_chars` (default 2,400 per output),
`witness_total_receipt_chars` (24,000 shared across outputs) and `witness_max_images` (four across
attachments and tool frames). Truncated output and omitted images are explicitly disclosed;
they do not certify an unseen claim. `computer_launch_wait_seconds` defaults to ten seconds
for guest window verification. These defaults change the earlier narrow evidence slices and
three-second launch wait; no personal tunables store was rewritten.

**Context limits are currently source-defined, not live Variables controls.** The model client
passes its configured window/output reserve to `nova_cortex/context_budget.py`; the default window
is 65,536 tokens and output allowance is 16,384. A 4,096-token reserve and 3.4 characters/token
estimate determine the text budget, additionally capped at 174,000 characters. Ordinary message
text is capped at 24,000 characters; the merged system context is instead fitted to the total budget.
Active continuation exempts the original request, accepted follow-ups and compact completed-action
facts from per-message clipping and eviction. If these protected anchors alone exceed the available
text budget, fitting fails explicitly. Raw observations and older history can still be shortened;
a retained action ID/status/hash does not preserve the full output or independently verify success.
Images and exact tokenizer costs are not measured. Keep the client's window value aligned with the
inference launcher's context setting; changing a Variables entry cannot change these constants.
The saved resume block is at most 6,000 characters across three unfinished tasks. Checkpoint field
validation permits next_step text up to 1,000 characters, eight constraints up to 400 each, and eight
observations up to 600 each; the prompt may shorten them while preserving the complete saved record.

**Voice settings are separate interface configuration.** `voice_gateway/config.py` loads
`_admin/voice_gateway.json` and `VOICE_GW_<FIELD>` environment overrides. The prepared Windows baseline
uses faster-whisper large-v3-turbo, CPU int8, English (`speech_language="en"`) and Silero;
`whisper_cpu_threads` defaults to eight. Moonshine is an explicit optional backend, not a silent fallback.
The gateway register defaults to `voice_fast`: with `voice_fast_thinking_off` enabled, first-loop
provider reasoning is disabled while subsequent tool loops retain thinking. Set `register="voice"`
for the ordinary thinking-enabled voice path. Neither bypasses final auditing or guarantees response
time; no utterance classifier selects a register automatically.
The temporary Windows system voice honors an installed name supplied through `windows_voice`; with
no explicit name it prefers an installed English female voice, otherwise the system default. Segmentation defaults are minimum speech 192 ms, onset pre-roll 288 ms and retained
trailing silence 192 ms, with a 2,000 ms end-of-utterance interval. Continued speech during CPU decoding
is combined within a bounded 60-second capture buffer before a transcript is sent; the quiet interval
is not a response-time or recognition-quality guarantee. `/api/voice/status` exposes the worker's
configured interval as read-only `settings.end_of_turn_silence_ms`; device Apply does not change it.
`request_timeout_s` defaults to 300
seconds: the current acknowledged request remains correlated and gains a delayed warning;
unacknowledged and retired requests expire. The separate Voice widget stores only selected input
and output device IDs in `_admin/voice_devices.json`; apply them while stopped. These are not body
Variables controls and do not alter Nova's identity or model settings.

Currently registered, read from `REGISTRY`:

| Knob | Label | Category | Default | Range |
|---|---|---|---|---|
| `autonomy_wake_budget_seconds` | Time per autonomous wake | Autonomy | `300` | 30–1800 |
| `max_tool_loops` | Max tool-chain depth | Cognition | `60` | 10–120 |
| `computer_launch_wait_seconds` | Application window verification wait | Computer | `10` | 1–20 |
| `voice_fast_thinking_off` | Voice-fast skips reasoning | Voice | `True` | on / off |
| `binding_cloud_escalation` | Binding cloud escalation | Witness | `True` | on / off |
| `heavy_witness_enabled` | Cloud heavy witness | Witness | `True` | on / off |
| `hold_back_streaming` | Hold-back streaming | Witness | `True` | on / off |
| `witness_deadlock_repeats` | Deadlock threshold | Witness | `3` | 2–10 |
| `witness_max_images` | Total images per witness audit | Witness | `4` | 1–8 |
| `witness_max_rounds` | Witness rounds — text | Witness | `20` | 1–40 |
| `witness_max_rounds_voice` | Witness rounds — voice | Witness | `2` | 1–8 |
| `witness_receipt_chars` | Output characters per audit receipt | Witness | `2400` | 400–12000 |
| `witness_total_receipt_chars` | Total output characters in audit receipts | Witness | `24000` | 4000–80000 |

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
skip subfolders, so syncing the repository uploaded `.git`, large model weights and token files, and
its temp folder stopped autosave (lesson 7 above).

- `Nova_Drive/read/` holds the text files of the last commit under `workspace/`, plus `AGENTS.md`:
  code, docs, Orient, configs and notes. Git already leaves out secrets, weights and logs; the copy
  also skips binaries, `node_modules`, `.venv`, `venv`, files over 5 MB and
  `workspace/Temp/collaboration` (even if a dependency or transport artifact were accidentally tracked). The private Collaboration room is not
  part of this remote reading copy. The watcher refreshes it after every
  autosave (`general_tools/nova_sync/drive_copy.py`). It is a copy, so edits made there are
  overwritten.
- `Nova_Drive/inbox/` is where Cole puts anything he writes away from this PC. Nothing modifies or
  deletes it automatically; agents read it when he mentions it.

`Nova_Drive/` is ignored by git and by the watcher, and Orient does not index it.

## Controller menus and layouts

Nova Chat has one workspace. The top application bar contains expandable menus; opening Services,
Advanced or Appearance leaves the dock arrangement alone. Widgets opens the widget choices, including
Voice, Collaboration and Model updates. The optional Services and Generation widgets mirror the original menu
controls and forward their actions; the menu controls keep their unique IDs and existing handlers.
The dock contains legacy panel layers, so Live log and Console cannot cover menus or intercept
their clicks. Dialogs and updater notifications remain above docked content.
Services calls the chat server Controller. The status bar explicitly shows Nova off / Chat only
when Nova is not running, separately from controller connectivity.

Conversation has a compact **power button** below its composer, beside Users and Options, including
when all conversation tabs are closed or the controller is chat-only. Its accessible label and status
tooltip say **Start Nova / Stop Nova**; its green state indicates Nova is on. It reports starting/stopping and disables competing actions until
the launcher resolves the transition. Stopping keeps the controller window and Collaboration usable;
starting uses the configured model. The page reconnects after the runtime worker changes and preserves
unsent text, selection, attached images and mentioned files. A draft-storage failure is shown instead
of silently discarding the draft. Older launchers show a restart instruction rather than a working
button. This control differs from stopping the current reply, muting Nova or closing a conversation.

**Voice** is a separate dockable widget opened from Widgets or the widget library. It can be resized,
stacked or popped out and participates in the normal active-widget checkmarks. Adding it does not
replace a saved layout or save any arrangement automatically. **Call Nova / End call** owns the
shared audio session; closing or moving the widget only changes its UI. Microphone and speaker mute
are independent. Prominent confirmed mute indicators explain when input is not sent or replies will
be silent; a failed status refresh shows unknown, and output mute cannot look like Speaking. The
primary surface distinguishes listening, Hearing you, Finishing your turn, Recognizing speech and
waiting/thinking, with delayed/suppressed reply notices. The backend's configured pause allowance is
shown when known; it is not a reply-time promise. No audio levels or countdown are invented. New
utterances continue active body work while retaining committed queued speech. Explicit End call keeps
its scoped cancellation behavior. Conversation's **added to active work** badge means input was
accepted for the next completed model/tool step; it does not mean the pending provider call was
interrupted or the input has already been applied. The ordinary queued badge means waiting for admission; during autonomous work this can be the next natural body boundary, while input that cannot join waits for a later turn.
Conversation frames tagged for another session do not create bubbles in the selected tab, including
late echoes, thinking tokens and final replies. The separate Thoughts feed remains global; untagged
legacy/global frames retain their previous behavior. The current server session-switch path still cancels its active task; filtering also guards late frames already in flight.
Audited committed segments grow one response bubble, labelled Reply in progress with delivered-part
count and the actual audit disposition. The terminal aggregate reconciles that same bubble without a
second reply; Turn complete/ended distinguishes final closure from continuing work. Reloaded history
retains separate delivered parts with their saved part number and actual audit disposition. Voice likewise
reports a delivered part while work continues and never speaks the final aggregate again. New input
retains committed queued speech; full-duplex barge-in cuts current audio and pauses the rest through
recognition, while explicit End call/Stop/output mute flushes it.

Expand **Settings & tests** for compatible 16 kHz mono inputs/outputs, Apply while stopped and bounded
microphone/speaker tests. **Stop test** cancels a test. Page load/status polling never opens devices;
device discovery is explicit. Tests work while Nova is off; a call needs Nova on. The installed English
Whisper large-v3-turbo recognizer runs CPU int8; Windows system speech is labelled temporary.
**Latest words** and **Delivery & playback details** are secondary: captions retain their actual audit
status, missing approval is never PASS, and correlated request/message/run IDs expose delay, suppression,
output submission and completion/failure. A playback API receipt does not prove audible output.

Conversation and Collaboration each anchor **↓ Latest** inside their message viewport. The control
appears when the reader is more than 60 pixels above the bottom, including manual scrolling without
new messages. New incoming messages leave the older scroll position alone and update the unread
count; choosing Latest scrolls to the bottom and clears it. Hidden-browser checks confirmed the
Collaboration scroll/show/click/hide behavior; its messages remain separate from Nova.

Widget layouts save **manually**. Drag tabs to reorder, stack or split, resize dividers, or pop widgets
into separate windows; these edits stay temporary until **Save layout** captures the live arrangement,
split sizes and popouts. The status distinguishes **Unsaved changes**, **Saving…**, **Saved** and
**Save failed**. Save success requires a successful local-storage write; failure keeps the arrangement
open without changing its last saved copy. Native window size persists separately.

Choose a name in the Layout selector, then **Load layout** to apply it. Selecting alone does nothing;
Load discards the departing layout's unsaved edits and does not automatically save its arrangement or
selected layout. **Revert** restores the currently loaded layout's last saved baseline, regardless of
which name is pending in the selector. **Undo** and **Redo** traverse up to 100 layout snapshots in the
current session, with a drag/resize treated as one edit; Revert is itself undoable. Loading another
layout or reloading the page resets that edit history. Reload/close discards unsaved widget edits;
no dock-change, switch or unload handler automatically saves them.

The management control explicitly creates, renames, duplicates or deletes named layouts, keeping at
least one. Those button actions persist their intended change. **Duplicate current** saves the draft
as a new named layout without overwriting the original. Appearance's **Use starter arrangement
(unsaved)** is an undoable draft change and needs Save layout to persist. Widget menu/library checkmarks
include hidden dock tabs and live popouts. Choosing an open widget focuses it; choosing a closed widget
opens it.

Storage is `nova.controller.layouts.v2` in that profile's local storage. The previous mode selection and
saved Together/Observe/Focus layouts migrate into editable named layouts; the old keys remain intact.
Deletion retains a recovery copy, bounded to twenty records; older reset/recovery records remain available.
An unrestorable saved layout is left unchanged. Saved popouts return to the main dock on restore.
Loading another arrangement closes the old popouts before loading, without saving the departing draft.
A native Nova Chat window and a separate browser have independent layout profiles.

The October 4 screenshot is available as a separate **Screenshot reference** named layout. A one-time
`screenshotReference: "2026-10-04"` migration adds it without selecting it or replacing Default Workspace.
Select it and choose Load layout to use it. Existing layouts and prior recovery copies remain intact;
there is no second automatic active-layout reset.

The native profile now lives at `~/ProjectNovaData/Controller` (`%USERPROFILE%/ProjectNovaData/Controller`
on Windows), outside AppData virtualization. On the first actual desktop launch, if that destination does
not yet exist, the app stages a copy of the caller's old `%LOCALAPPDATA%/ProjectNova/Controller/window.ini`
and `storage/`, then publishes the complete profile. The legacy profile stays intact; disposable cache
is not copied. Migration failure displays an error and exits rather than silently opening a blank
profile. An existing new profile is authoritative; explicit `--profile-dir` previews stay isolated.

Native movement, resizing and window-state changes save after a 350 ms debounce; tray-close and
application quit flush immediately. Minimized windows retain their last normal geometry, maximized
state is restored, and Qt clamps a saved window to available screens. A settings-write failure appears
in the native status bar. Closing the main window hides it when a tray is available; **Nova → Quit Nova**
or the tray's **Quit Nova** exits the app. **Ctrl+R** reloads renderer changes only; desktop Python changes
and profile migration require a full quit and relaunch.

Verification for this persistence repair: 15 isolated desktop tests passed, including resize/move
restoration between two fresh offscreen Qt processes and migration success/failure fixtures. Twenty-two
Node scenarios cover manual saving/loading, Revert, Undo/Redo, screenshot reference and widget checks.
Live browser checks verified draft discard on reload, Undo/Redo, Revert, explicit Save surviving reload,
select-then-Load behavior, screenshot reconstruction and open-widget checks, with no browser errors.
The user's running native app was not restarted or its real profile migrated during this repair;
native reopening remains a separate verification.

Live log includes recorded history as well as new events. Earlier dates are displayed beside the time;
event labels distinguish scheduled reminders from model responses. A `stretch_nudge` comes from the
existing shelf watcher called at autonomy startup: its canned wording does not demonstrate fresh model
inference. Its posture record freshness is a separate runtime issue; the controller does not alter it.

Pipeline pairs tool starts and terminal results by operation ID. Unknown outcomes remain neutral
and count as finished steps; they are not displayed as successful. A revised answer whose audit
is INCOMPLETE or ERROR retains that status instead of appearing as a successful correction.
Witness read attempts show attempted/returned/refused/failed counts; output is not labelled successful
verification. The October 5 follow-through passes 24 isolated Pipeline scenarios, including refusals.

## Model updates

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/nova_chat/server.py::startup_event`. Re-read it against the code, update it in `general_tools/architecture_map/notes/model_updates.md`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "OPERATIONS.md#Model updates"`.

`general_tools/nova_updater/` is a general tool; its README has the full route contract. At each Nova
Chat start one cached catalog query looks for a newer dense Qwen of 27-32B with a permissive license,
and Nova Chat offers Update / Decline / "Remember my decision". The manual widget searches Hugging Face
and ModelScope (installable) and the Ollama library (link only).

Open **Widgets → Model updates** for Updates, Find models, Train adapters and Settings. The
notification's Update action opens the same installation review. Select a build, quantization,
projector and optional replacements, build a dry-run plan, review its disk/compatibility warnings,
then explicitly confirm it. Projector choices resolve an exact catalog path first, or a unique
filename; unknown or ambiguous choices fail. Changing choices discards the previous review. Jobs displays progress,
cancellation and separate recovery outcomes. Startup/status read configuration and catalog metadata;
installed-file inventory is requested only when entering an install or adapter workflow.

The router is attached in normal and chat-only launches. Its catalog check runs after a cancellable
three-second startup delay, outside the event loop; a catalog failure cannot block startup. Shutdown
cancels the task, while any already-running network request finishes under the catalog timeout.
Chat-only installs prepare the next model start and never invoke a model restart callback.
Nova start/stop transitions share the updater's exclusive-operation guard; updater writes return 409
until the launcher resolves the switch, including when a replacement worker inherits that switch.
When a displayed job finishes, the widget refreshes status once so completed work cannot leave a
stale busy flag disabling recovery controls.

Status reads the current boot selection on every request; a cached catalog result keeps its own
checked selection and is marked stale when those differ. Neither is proof that llama-server is running.

Training starts from a stored preview. Its `review_id` binds the start request to the reviewed
parameters and dataset checksums; changed input files require a new preview (HTTP 409).
Export creates training inputs only; it does not produce a finished adapter. Keeping an adapter means
no copy, conversion or retraining. A known cross-base adapter cannot be kept, and selected adapters
cannot also be quarantined. The installer rechecks those conditions before writing boot settings
and before finishing a pending switch. A second activation cannot overwrite a pending rollback snapshot.
RunPod requires explicit consent to the reviewed paid run (`paid: true`), with no per-run spending cutoff. Credentials are entered in Settings; blank fields leave saved values unchanged and
explicit clear checkboxes remove them. Secret values are not returned or saved in browser storage.

Installing never edits the launcher. It writes boot files that `start_llama_qwen36.cmd` reads from
`nova_body/memory/`: `active_model.txt`, `active_mmproj.txt` (`none` = no vision) and `active_lora.txt`
(`none` = no adapter); absent files mean the Qwen 3.6 defaults. The exact old boot files are saved to
the updater state BEFORE the first write, so a crash mid-switch is undone with `POST /api/updater/rollback`
(`/finish` refuses an interrupted switch). The install restarts the model and confirms llama-server
loaded the NEW file (`/props`, not just `/health`). If the restart fails, the file never loads, or the
user cancels while it loads, it restores the old boot files and restarts the previous model. The job
result keeps three facts apart: boot files restored, restart accepted, and the previous model confirmed
running again at `/props`. Only after a verified load are replaced files moved to
`_admin/Trash/<stamp>_model_update/` with a manifest. In chat-only mode the switch completes after the
next model start (`POST /api/updater/finish`). Finish and rollback take the same exclusive job
slot as installation and training; either returns HTTP 409 while another job holds it.

A LoRA trained for another base may fail to load or behave incorrectly. Choose no adapter or retrain
for the new base; the updater clears incompatible old KoELS selections. Keep is permitted only when
no known incompatibility or replacement conflict exists. Training
(`pod/`) generalises the v7 pipeline: inputs checksummed, the loss-mask template rebuilt from the new
model's own chat template and proven (GATE A/B) before training, every epoch converted. New adapters
are installed but not activated: A/B the epochs first. Activation with a restart is proven at
llama-server's `/lora-adapters`; running without the adapter counts as failure and restores the previous
adapter line (HTTP 502). RunPod runs first request a pod stop after completion, failure or cancellation.
Once all expected epoch adapters and complete runtime details have been verified and saved locally,
successful runs delete the pod and confirm it is gone. Its attached pod storage is released; a matching
saved pod ID is cleared so the next run creates a fresh pod. Unverified downloads, failed training and
cancellations retain the stopped pod for recovery and explicitly warn that storage can keep billing.
Delete failures retry a stop and report unresolved cleanup. Independent network volumes are never
deleted automatically. A killed updater process or unreachable provider can prevent cleanup; check
RunPod when the reported outcome is unconfirmed.

Final training inputs live in `models/Training Files/<friendly base-model name>/<training name>/`: a
frozen dataset, recipe, scripts, checksums and short README. Completed runs also retain checksummed
`Run Details/<job id>/` receipts for the exact base revision, tokenizer loss-mask audit, model config
and Python environment. Finished GGUF adapters live beside the base model, outside Training Files.
New pod packages isolate dependencies in a per-job virtual environment on container-local storage
while reusing the image's CUDA Torch; the Hugging Face weight cache also stays on local disk.
The durable input package, checkpoints and recovery outputs remain on the `/workspace` volume. Temporary ZIP exports, downloaded outputs and logs use
`Temp/updater/`; exporting is not training. Existing v6/v7 inputs are copied with matching hashes;
the historical originals are preserved in the dated script-retirement archive. Do not select both a complete corpus and its additive subset.
Frozen Training Files are excluded from the sync watcher's timestamp and PUP replacement writes;
change detection and backup queues still work. The eight restored October 4 inputs/receipts are also read-only
along with nineteen unchanged manifest entries, to protect their exact checksums from the older watcher until its next normal restart. Reproduce a
changed recipe in a new package rather than altering the checksummed originals.

The RunPod Settings credit check and paid-run preview query prepaid credit. New starts must meet
RunPod's one-hour minimum; a smaller balance than the estimated whole run produces a warning.
The prepaid wallet is the funding limit. Nova never adds funds automatically and has no separate
per-run spending cutoff. During training, the app refreshes wallet credit and shows the actual
pod hourly rate, elapsed time and estimated GPU spend; a manual top-up appears on a later refresh.
Low-credit warnings do not themselves stop an active run. Provider-enforced credit exhaustion is
separate from Nova's controls. Completed, failed and cancelled jobs retain their cost summary and
pod cleanup outcome: deleted, retained for recovery, or cleanup failed. Estimated GPU spend excludes
storage and is not a provider invoice. A stopped pod still incurs attached-storage charges; confirmed
pod deletion removes that pod's storage. Separate network-volume charges require separate cleanup.
Google browser sign-in does not configure the updater API key. New pods default to Japan
(`AP-JP-1`) near Korea; unavailability does not silently select a distant datacenter.

State lives in `general_tools/nova_updater/state/` (git-ignored), scratch in `Temp/updater/`, secrets in
`%USERPROFILE%\ProjectNovaData\Updater\credentials.json` beside the collaboration room's data. Not in
AppData: each MSIX-packaged launcher gets its own private AppData, which once split the room in two.

The launcher quotes the model and projector paths, so spaces work there. Boot-file paths must be plain
ASCII without cmd's special characters. Adapter paths with spaces are supported by quoting the
complete `path:scale` token; unsupported shell characters are refused. On Windows the
updater tests run the real launcher with llama-server replaced by an argument recorder.

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
| GET | `/api/updater/candidate` | `candidate` |
| GET | `/api/updater/credentials` | `get_credentials` |
| GET | `/api/updater/funding` | `funding` |
| GET | `/api/updater/inventory` | `get_inventory` |
| GET | `/api/updater/jobs` | `list_jobs` |
| GET | `/api/updater/jobs/{job_id}` | `get_job` |
| GET | `/api/updater/search` | `search` |
| GET | `/api/updater/sources` | `sources` |
| GET | `/api/updater/status` | `status` |
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
| POST | `/api/updater/check` | `run_check` |
| POST | `/api/updater/credentials` | `set_credentials` |
| POST | `/api/updater/decision` | `decision` |
| POST | `/api/updater/finish` | `finish` |
| POST | `/api/updater/forget` | `forget` |
| POST | `/api/updater/install` | `start_install` |
| POST | `/api/updater/jobs/{job_id}/cancel` | `cancel_job` |
| POST | `/api/updater/lora/activate` | `activate` |
| POST | `/api/updater/plan` | `make_plan` |
| POST | `/api/updater/rollback` | `rollback` |
| POST | `/api/updater/settings` | `settings` |
| POST | `/api/updater/train` | `start_training` |
| POST | `/api/updater/train/install` | `install_trained` |
| POST | `/api/updater/train/preview` | `train_preview` |
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

**Files without a purpose line:** 71, listed at the end of [INDEX.md](INDEX.md#files-without-a-purpose-line).

**Sections awaiting review:** `ARCHITECTURE.md#Body faculties`, `ARCHITECTURE.md#Execution path`, `ARCHITECTURE.md#Memory and learning`, `ARCHITECTURE.md#Runtime evidence and open modernization work`, `OPERATIONS.md#Access and practical debugging`, `OPERATIONS.md#Configuration and evidence`, `OPERATIONS.md#Model updates`, `OPERATIONS.md#Run and stop`, `OPERATIONS.md#Security model`, `OPERATIONS.md#Test meaningful behavior`.
