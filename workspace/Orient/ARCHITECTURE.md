<!-- @nova: Describe Nova faculties, ownership boundaries and execution paths. -->
# Architecture and ownership

_Facts regenerated 2026-10-05T17:51:10+00:00 from source (input `b393e9416474`). Explanations carry their own review dates, and ⚠ marks a section whose sources changed since its review. Source-derived facts are not runtime certification._

## Execution path

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/nova_chat/server.py::_end_queued_request`, `general_tools/nova_chat/server.py::_run_ai_response_owned`, `general_tools/nova_chat/server.py::_steer_request`, `general_tools/nova_chat/server.py::_stop_request` and 12 more; new `general_tools/cloud_call.py`, `general_tools/nova_chat/server.py::_recover_face_inputs`, `general_tools/nova_chat/server.py::_resolve_speaker`, `general_tools/nova_chat/session_manager.py` and 6 more. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "ARCHITECTURE.md#Execution path"`.

The normal launcher starts local inference, a witness model, the chat/runtime host, controller,
sync watcher and guardian. The controller is a PyQt desktop shell around the dashboard. The
FastAPI/WebSocket face currently shares process state with the body runtime; multiple visible
conversations do not yet imply independent execution sessions.

The launcher's Conversation power control switches between full Nova and chat-only operation
without replacing the desktop controller or console. It replaces the runtime worker and its owned
model, witness, guardian and watcher as needed. The controller reconnects after the worker changes;
its separate Collaboration history stays durable. This is distinct from stopping one generation
or restarting the entire app.

The explicit `--chat-only` path omits the body runtime, model startup and autonomous background
work. Collaboration follows its own route: actual app session → local HTTP or atomic mounted-file
transport → controller broker → separate SQLite history → live widget/cursor feed. No room text
enters the Nova inference path below. The shared files are transport artifacts under the excluded
`Temp/collaboration`; they are not the canonical history and require a running broker.

Chat input → speaker attribution and screening → conversation/context assembly → body model
dispatch → `nova_voice.nova` inference/tool loop → `tool_router` → environment result → receipt
and another model step → response, transcript and asynchronous indexing.
Voice input follows that same model/tool path. A client request ID and validated register
(`text`, `voice` or `voice_fast`) survive immediate dispatch and the busy queue. Reply events
carry their own message ID, supervised run ID and input-message link. A terminal delivery status
is separate from the exact final candidate's audit disposition; delivered text is not necessarily
approved. Invalid or missing dispositions remain unverified. Errors, cancellations, empty replies,
deduplicated replies and unsolicited autonomy excerpts do not become ordinary voice replies.
Requests that never generate receive `request_end` with a terminal reason. Busy input is retained
in arrival order; compatible follow-ups join the active conversation instead of superseding earlier
input or cancelling the current model/tool step. Chat-only rejection still completes the request
without adding a message to Nova's transcript.

`nova_runtime.conversation.ConversationTurns` and `ActiveTurn` own in-process continuation inside
the body. The body work coordinator separately persists accepted inputs and work checkpoints under
`logs/runtime/active_work.json`; faces retain delivery handles and their transcripts separately. Nova
appends accepted input at natural model/tool boundaries while preserving the original request and
completed observations; it does not alter an HTTP inference request already running. A newer input
revision changes what subsequent work must address. With an `on_segment` sink, a useful completed
candidate can be delivered with its frozen revision/audit, then later work reconciles newer input.
Delivered text is not silently retracted or regenerated. A synchronous final-admission seal
prevents input being accepted into a turn after its final reply is committed; later messages wait for
the next turn. The chat adapter supplies correlation/sinks and scoped Stop ownership, not a separate
cognition loop. This is provider-compatible between-call continuation, not proven native mid-inference
steering or a full relocated-body runtime certification. Follow-ups do not replenish the total
model/tool-loop or witness-revision allowances. Completed candidates retain the exact evidence and
input revision used by their audit, including when newer input arrives during that audit.

The body's `request_contract.CurrentRequest` retains actual applied incoming requests separately
from internally generated audit/correction prompts. Each candidate freezes that request context
alongside its evidence and delivered parts; corrections must preserve still-applicable follow-ups.
An explicit no-tools request also forbids auditor reads. The inline witness uses the installed
provider's constrained JSON schema for exact verdicts or permitted read-only calls, with a verdict-only
schema when no reads remain. Schema validity is not factual correctness; malformed, truncated and
failed audits remain visibly unapproved. Legacy prose verdict parsing stays strict for older callers.
Explicit unknown speaker labels stay unknown/untrusted rather than being silently renamed as Cole;
only an omitted speaker falls back to the active UI user.

`nova_runtime.work_owner.WorkCoordinator` serializes conversational and autonomous work under one
body-owned lease. An autonomous wake claims that lease before its first await, preventing a chat
request from racing model readiness. A serializable human-input inbox belongs to the body; face
records supply delivery handles separately. At natural completed model/tool boundaries, and at phase
fallbacks, the owner attends pending human input, then resumes with its original task, completed
receipts and delivered interaction context. Nested human responses omit the autonomous attention
callback so they cannot recursively re-enter it. Their ordered follow-ups still use `ActiveTurn`.
Reflect, decide and execute retain their existing prompts; this change does not merge all cognition
into a permanent thinking stream. Scoped Stop ends its owned work and waits for supervised cleanup,
without terminating the autonomous scheduler. Lifecycle cancellation still terminates the daemon.

Durable admission precedes the face's input acknowledgement. Checkpoints preserve the original goal,
ordered pending inputs, completed phases, candidate publication, exact segment coverage and tool
attempt identities. A partial delivered part does not complete the original input. After interruption,
recovery retains the owner and receipts; an unrelated completed conversation cannot erase older
unfinished work. Explicit Stop records cancellation and is not automatically resumed. If writing that
record fails, actual cancellation still proceeds and status reports the persistence failure.

Tool/runtime-board mutation starts are checkpointed before dispatch. A started operation without a
confirmed result is uncertain, not assumed failed or retried. Nova can inspect with read-only tools
and use the body `reconcile_attempt` control with actual later observation receipt IDs and an explicit
outcome; this is an evidence-bearing decision, not independent proof of its interpretation. Missing or
invented receipts cannot clear the hold. The mechanism does not promise exactly-once external effects.

The chat face reopens/pins original sessions without changing the displayed tab or fabricating old
sockets. Exact saved segment text/run/index reconciles the narrow crash gap between transcript write
and body acknowledgement; complete final conversation publication is not regenerated. A removed face
or unavailable old session falls back to selective body-transcript recovery. Chat segment writes are
atomic and required before delivery; a failed write cannot mark an input covered. Rejected/unavailable
inputs are cancelled rather than silently revived after a terminal rejection.

Headless human attention uses the same body `ConversationTurns`, committed-segment sink and
`conversation_context.ConversationContext` formatter as the face wrapper. Speaker attribution,
clock/system-prefix order and images therefore share one implementation. It captures the initial
transcript through admitted input, polls follow-ups at boundaries, and persists each delivered part
with its exact input-revision coverage. Later or sealed-out messages remain pending; the terminal
aggregate is not appended a second time. Face and headless generation both call the body's shared
`WorkspaceContext.prepare_nova_context`, including automatic semantic recall and on-demand files.
The runtime caches its context reader. Small recall encoders run on CPU and warm on the indexer's
background startup thread; `memory_queue.recall_readiness` exposes initialization duration/failure.
Warmup reads/encodes only; it does not create synthetic memories. Autonomous phase prompts remain separate. These ownership
and persistence paths have isolated tests; no full relocated personal-state or live voice proof is
implied.

`message_start`, applied `message_context`, committed `message_segment` and final `message_end`
carry aligned `request_ids`/`reply_to_ids` and `input_revision` under one response message/run/turn
identity. A typed input may have a null client request ID; that alias cannot claim a locally owned
voice input. A segment carries only its delivered text, a 1-based ordered `segment_index`, and an
explicit audit for that exact turn/revision. The voice face requires its acknowledged pair and a
validated start/context snapshot; even an earlier frozen revision must match recorded evidence.
Segments cannot self-bind and do not close pending inputs. The final remaining text is also a segment;
terminal `segment_count` prevents aggregate audio replay, while the UI reconciles one growing bubble.
The face persists each part with a copied, whitelisted response identity and audit; reloaded history
shows its delivered-part number and actual audit disposition. Unknown dispositions are never PASS.
Legacy callers without an `on_segment` sink still receive one final reply. The model client forwards
optional segment/audit callbacks only to Nova; audit disposition resets after an input revision. Background second opinions cannot relabel an
already delivered candidate. Human messages retain the human audit path even when global autonomy
is enabled. The detachable voice gateway consumes these events through a separate WebSocket client,
with committed-text speech and body-event sinks. Closing it flushes queued speech and invalidates
late playback; already-running synthesis may still finish computing. Null output and subprocess
completion are distinguished from playback API receipts. The separate dockable Voice widget explicitly
supervises a hidden `voice_gateway/control_worker.py` child through `nova_chat/voice_control.py`;
status never starts audio. Its prepared CPU environment contains pinned Whisper/Silero/Moonshine
assets; the default recognizer is Whisper large-v3-turbo with CPU int8 and English selected. The
gateway defaults to `voice_fast`, requesting thinking off for conversational continuation when its
tunable is enabled. Actual tool proposals/attempts and witness/guard correction switch subsequent work
to thinking; a delivered part or new human input alone no longer triggers that switch. Final auditing
remains. This preserves the prompt prefix across ordinary segments on the installed Qwen provider. `voice` is an explicit
ordinary-thinking alternative, not an automatically classified mode. Neither promises instant replies. Missing
selected assets require setup instead of a hidden download or silent recognizer/VAD fallback.
Windows system speech is a labelled temporary baseline; absent an explicit voice name, it prefers
an installed English female voice and otherwise retains the system default. The worker's Windows control pipe polls
before reading so native imports do not deadlock against a blocked stdin thread. Recognition uses
512-sample frames, minimum voiced duration, onset buffering and bounded utterances. Its default
pause allowance is two seconds, honoring explicit overrides. Speech continuing during CPU decoding
is collected within the bounded turn; an obsolete partial result is withheld before re-decoding the
combined audio. Actual hearing, finishing-turn and recognition states are forwarded to the widget;
the pause allowance is exposed as a setting, not a guaranteed reply time. Decoder errors produce
diagnostics and listening continues. Capture gates discard stale frames/transcripts across
mute/playback transitions. Native capture and system playback have separate dated receipts; human
conversational recognition and avatar lipsync are distinct checks.

The gateway retains its current acknowledged eligible request past the 300-second default delay
threshold and emits a warning once. Acknowledged inputs bound to an open response also retain exact
correlation until terminal closure, including earlier revisions whose legacy final audio was retired.
Unacknowledged or unbound retired requests expire. New input retains already committed queued speech without stopping body work.
If a human turn is already hearing, finishing its pause or transcribing when a reply arrives, both
voice adapters hold future output until recognition completes or resets. A held queue does not close
that existing capture gate. Actual half-duplex playback still blocks new capture; mute and explicit
Stop override it. Silence/noise reset and recognition failure release the hold. Full-duplex barge-in
cuts current output while preserving and pausing later queued committed units through recognition;
a completed transcript or return to listening resumes them. Explicit Stop, output mute
and close still flush. Uncommitted old final replies remain subject to current-input eligibility.
Explicit End call or worker shutdown sends request-scoped Stop for the call's remaining owned inputs,
including earlier inputs whose audio was retired. Only a same-socket owned request can match. Final
`stopped` with the exact request ID and `matched=true` acknowledges cancellation; `stop_pending` or a
submitted frame is not completion. Each scoped request waits up to two seconds for that receipt before
socket close and reports unconfirmed cancellation without issuing global Stop. `last_turn`, `last_playback` and bounded `recent_events`
expose correlation, eligibility/suppression, output device and available submission/completion timing.

The retired host-desktop Claude ping and its aliases return an unknown-tool failure rather than
launching PowerShell. Active instructions no longer advertise it. The private Collaboration room
remains separate from Nova; asking Cole uses the ordinary conversation.

Tool starts and outcomes also enter Pipeline, correlated with the canonical receipt's operation
and run IDs. Each human-facing candidate remains private until its audit/delivery step; a committed
segment can then be visible while the same work continues. This is not raw token speech. The inline
witness uses Nova's main local model endpoint in a separate context; the separately launched 8081
server is not automatically the inline auditor. It checks the assembled candidate segment,
including its undelivered tool-loop commentary, and receives available screenshot pixels with their
observation context. An explicit approval is distinct from a concern, an incomplete check or an
execution error. Incomplete/error checks remain visible and do not certify the draft. A concern
returns to Nova to revise in her own words; the auditor does not silently replace her voice.
A verdict prefix takes precedence over quoted tool JSON, so an objection quoting a command is
not accidentally executed as another verification request. Receipts share a compact outcome
formatter with replay: real stdout/stderr follow shell/target/status, and truncation is explicitly
marked. The combined attachment/tool image budget is tunable and omissions remain disclosed.
Prompt ordering keeps stable system instructions before the unchanged clock/gap block. Witness
READ BUDGET text follows stable evidence and precedes accumulated read receipts, allowing a longer
unchanged prefix across audit calls. Its wording, evidence, read limits and strict verdict parser
are unchanged; this cache-oriented placement does not deploy the rejected witness policy candidate.
Audit sampling disables DRY so verbatim evidence can be copied. A revised draft still enters the
configured incorrect-concession check when the re-audit is incomplete or errored, without treating
that revision as approval. Bad-request diagnostics omit image bytes while preserving the actual
provider request. This improves audit evidence and reporting; it does not guarantee sound judgment.
Pipeline read-attempt counts distinguish returned, refused and failed reads; returned text is not
verification. Optional `nova_voice/provider_diagnostics.py` captures the actual fitted provider JSON
and timing phases only while a valid short-lived local capture marker is active. It is disabled by
default, bounded in duration/count/size, and replaces image data URLs in receipts. These diagnostic
receipts help distinguish input/context delay, provider generation and auditing without changing policy.

Guest Bash (`computer_exec`), screenshots and hands target Nova's authenticated :1 display.
Host `run_command` is Windows PowerShell. WSLg :0 is another Linux graphical session, not the
native Windows desktop. Authorized host reach remains available; tool choice identifies the
destination. `computer_action` launch/browser helpers retain diagnostics and report the limited
postcondition they observed; a process or window alone does not prove a page loaded or a video played.
The default launch wait is ten seconds (tunable). A tagged verifier record tolerates unrelated
startup warnings. Existing-browser handoff requires a successful initial window enumeration;
otherwise an already-open window cannot count as a newly opened one.
The guest command environment prefers Nova's per-user `~/.local/bin` tools. On this machine,
Firefox uses an official Mozilla build under `~/.local/opt`, because the Ubuntu Snap could not
connect to the authenticated VNC display. Provisioning records the pinned version and checksum;
the original Snap installation remains available explicitly. Browser data and VNC credentials
are separate, and a browser repair does not require rotating the desktop password.

Autonomy → cheap wake gate (pending input, unconsumed Cole directive newer than six hours,
durable watched event or timer) →
bounded task selection → execution → acceptance checks and reconciliation. An accepted concrete
task reaches execution before broad reflection. With no concrete work, reflection/decision and
free-time execution remain available, including rest. Older directives remain stored but no longer
trigger Priority 0; they are not yet automatically converted into tasks. Focus leases rotate equal-priority work
at checkpoints; each wake has a configurable time budget. Stop supervises generation, workers
and child processes, and reports pending cleanup rather than falsely claiming everything stopped.

Task continuity uses the existing `nova_body/Tasking/tasks.json`, not another task store. Title/notes
carry the objective, acceptance checks define completion, and `task_progress` can persist a bounded
`continuity` object: next step, constraints and observations. Omitted fields retain previous values;
empty text/lists clear a supplied field. These survive restart and the twenty-note progress limit.
Both ordinary chat and autonomous execution receive this saved context. Each chat context build reads
up to three unfinished tasks in a block capped at 6,000 characters, before larger identity/memory
sections; valid active focus comes first. Done/abandoned tasks stay in storage but do not enter that
resume block. Saved observations are Nova-authored notes, not independent verification or permission
to override the current request. Shortened fields are marked; use a targeted task query for details
rather than pushing the entire board through a clipped file-read result.

`nova_cortex/context_budget.py` fits the initial prompt and subsequent tool rounds. The combined
system prefix, identity and checkpoint no longer receive the ordinary 24,000-character message cap.
Older history is discarded before excess system text is shortened; the current request, newest turn
and marked task checkpoint receive priority. Internal witness/repair prompts do not replace the
original unlabelled headless objective in that selection. Fitting reserves the actual output allowance plus
4,096 tokens, using the established 3.4 characters/token estimate and an additional 174,000-character
ceiling. The old minimum-four-turn overflow override is gone. This bounds estimated text, not exact
tokenizer or image usage. Active continuation protects the original request, accepted follow-ups and
compact completed-action facts from per-message clipping and eviction; if these anchors alone exceed
the text budget, fitting fails explicitly. Ordinary history, raw tool outputs and excess system text
can still be shortened. Action IDs, status and content hashes preserve execution identity, not the
complete output or proof of success. Exact-candidate witness audits bypass this normal fitting policy
so evidence is not silently changed.

## Body faculties

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `nova_body/nova_witness/replay.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py (PURPOSES)`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "ARCHITECTURE.md#Body faculties"`.

| Part | Responsibility | Python sources |
|---|---|---:|
| `nova_paths` | Canonical body/workspace paths; relocated state never falls back to a second copy. | 1 |
| `nova_config` | Body settings loader. Some execution paths still have independent constants; this is not yet universal configuration. | 1 |
| `nova_cortex` | Task board, wake decisions, wants, speaker roles, witness/integrity checks, tunables and shared identity/context loading. | 17 |
| `nova_runtime` | Model dispatch, headless autonomy, transcript, event bus, provider lifecycle and KoELS equip operations. | 15 |
| `nova_voice` | Local inference client, parsing/tool loop, shell/file tools and durable execution receipts. The retired host-desktop Claude ping is no longer registered. | 5 |
| `nova_senses` | Time, environment changes, presence, touch, sight, web access and proprioception. | 13 |
| `nova_lancedb` | Semantic/visual memory store, embeddings and asynchronous indexing; separate from journal files. | 5 |
| `nova_memory` | Journal/goals/log-reader helpers. Some overlap with router-owned journaling remains. | 5 |
| `nova_logs` | Log paths, thought/action records and retention. Historical receipts remain evidence, not proof of current behavior. | 3 |
| `nova_forge` | Discovery, classification and testing of Nova-authored extensions on her shelf. | 1 |
| `nova_computer` | VM observation, command and input tools in the normal voice router; explicit human handoff pauses actions. | 13 |
| `nova_imagination` | Image generation and art workflow; uses optional external ComfyUI services. | 3 |
| `nova_play` | Curiosity and saved discoveries, including the curio shelf. | 2 |
| `nova_witness` | Witness model launch, evaluation and training utilities; replay v4 shares live evidence/dispatch/sampling and constrained audit JSON, with frozen regression controls, open development cases and a sealed holdout. Live auditing lives in cortex/voice. | 5 |

## Persistent ownership

| Canonical path | Owns |
|---|---|
| `nova_body/memory` | Personal memory and operational state, including autonomy, roles, tunables and loadout intent. |
| `nova_body/logs` | Transcripts, receipts, events, diagnostics and retained history. |
| `nova_body/SELF` | Nova's self-model, reference material, portrait and avatar project. |
| `nova_body/Tasking` | Persistent task board and generated human view. |
| `nova_body/nova_memory_db` | LanceDB data; preserve independently of code and never assume a folder exists means recall works. |
| `nova_body/KoELS` | Expert/loadout manifests; weights remain an explicitly configured inference-provider dependency. |
| `nova_body/Nova_Created` | Nova's authored artifacts and forged extensions. Face-dependent extensions are optional even when stored here. |
| `nova_body/nova_config.json` | Body settings, including optional cloud-provider configuration. |
| `nova_body/nova_status.json` | Persisted body status. |


`nova_paths.py` resolves those locations. `NOVA_BODY` can identify an independently relocated body;
`NOVA_WORKSPACE` identifies the surrounding optional project. Historical relative tool paths such
as `memory/STATUS.md` resolve to body state; no legacy on-disk state fallback is used. Shell commands
must use the current canonical paths. Personal documents are moved intact, not rewritten as new memories.

`models/`, `llama/` and `prompt_cache/` belong to the inference provider. The cache is disposable;
weights and adapters are not. A portable body needs a configured, reachable provider and compatible
Python dependencies. External ComfyUI, VM/WSL, voice and mobile tunnel facilities must be checked
separately. Their availability is not established by source imports.

## Memory and learning

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `nova_body/nova_lancedb/embedder.py`, `nova_body/nova_lancedb/hippocampus.py`, `nova_body/nova_lancedb/indexer.py`. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "ARCHITECTURE.md#Memory and learning"`.

SELF/core and personal memory files ground each turn. Semantic recall uses LanceDB and an
asynchronous indexer; the raw journals/transcripts and vector store serve different purposes.
Both chat and headless execution receive body-owned context. A durable queue retains failed
writes for retry. Five expired worker leases become a visible failure, and a completed event key
can be submitted again; outstanding work still deduplicates. Failed jobs require explicit retry. Recovery indexes intact archived records without rewriting them; malformed rows
are reported individually. Recall distinguishes unavailable storage/embedding from no matches.
Archived record timestamps are preserved, so record age differs from today's ingestion time.
See the dated evidence for coverage; an operational text index does not certify visual recall.
Text and visual SentenceTransformer loaders first request locally cached assets, avoiding a network
check on that path. Only a recognized missing-cache failure falls back to the existing first-install
download behavior; other failures remain failures. Per-model initialization locks and a separate
memory-store singleton lock prevent concurrent first-use construction. Both small encoders now use CPU and warm in the background at startup, with visible readiness/error
status; the visual encoder only warms when the visual table contains records. Store initialization
loads deduplication hashes without copying embedding vectors into a dataframe. Retrieval semantics
and original records are preserved; the warmup does not add memories. Dated cold/warm measurements
below separate startup expense from query time; no retrieval-accuracy improvement is claimed.

KoELS separates choosing a specialist manifest from equipping adapters. Changing scales within
a loaded set differs from restarting the provider with a different set. A live personality adapter
does not prove autonomous expert selection/restart works. The launcher already consumes the KoELS
boot-argument text file. Its serializers now pass each adapter and scale as one `path:0.0` argument,
with the batch form quoting the complete token. Disposable launcher and installed-parser checks
prove argument compatibility, not adapter loading, VRAM use or application of scales. The global
`--lora-init-without-apply` behavior is unchanged and still needs validation with real adapters.
Drives/wants and the hormone design are not evidence of online weight learning. Keep implemented controls distinct from biological analogies.

## Runtime evidence and open modernization work

> ⚠ **Review needed.** Since this section was reviewed (2026-10-05): changed `general_tools/nova_chat/tests/test_segment_metadata.py`, `general_tools/voice_gateway/control_worker.py`, `nova_body/nova_runtime/conversation.py`, `nova_body/nova_runtime/model_client.py` and 4 more; new `general_tools/cloud_call.py`, `general_tools/nova_chat/server.py::_recover_face_inputs`, `general_tools/nova_chat/server.py::_resolve_speaker`, `general_tools/nova_chat/session_manager.py` and 7 more. Re-read it against the code, update it in `general_tools/architecture_map/orient.py`, then run `python general_tools/architecture_map/orient.py --mark-reviewed "ARCHITECTURE.md#Runtime evidence and open modernization work"`.

The 2026-10-01 live baseline used the existing model and source. A priority-1 repair task was not
selected within ten minutes: a stale directive and existing focus dominated the run. Fourteen
tool calls occurred; none operated on the fixture. Session switches/context refresh also occurred,
so this was an observed normal-stack run, not a controlled model benchmark.

An execution-only diagnostic, explicitly bypassing scheduling, repaired that same fixture,
reproduced the failure, ran tests/CLI, saved the correct artifact and completed its task. Independent
verification passed both supplied tests and 100 additional cases. Ten command failures across
these runs were nevertheless persisted as `ok: true`. These findings support fixing task intake,
structured outcomes and cancellation before rewriting personality or training.

Stop was accepted while the model request remained unresponsive; health continued to report OK.
The stack recovered through its normal graceful shutdown/restart. Separate readiness from
liveness and cancellation of generation from cancellation of operating-system processes.

A relocated copy also completed a live read-file turn with the original workspace inaccessible
and no chat/general-tools directory available. Identity, memory and task persistence passed separate
isolated checks. The existing local model provider remained an explicit dependency. VM operation,
adapter switching, semantic recall and autonomous self-upgrades were not certified by that probe.
See [the dated evaluation](Architecture/evidence/2026-10-01-autonomy.md) for scope and limitations.

The 2026-10-02 implementation adds structured outcomes, durable event/memory queues, focus
leases, supervised cancellation, registered VM tools with screenshot observations, and task-sized
staging/checkpoint promotion. `DONE` requests run acceptance checks; absent or failed checks leave
the task waiting for review. Manual completion is recorded as human confirmation. Staging is a
test workspace, not an OS security boundary. Preserve deliberate reflection and rest.
See [modernization evidence](Architecture/evidence/2026-10-02-modernization.md) for live results
and the distinction between model-driven behavior, direct tool probes and isolated tests.

The October 3 controller repair restores widget insertion and refresh-on-show, bounds pipeline/log
reads, uses current runtime state in System, and routes lifecycle controls through the launcher.
The October 4 controller update adds named layouts, anchored top menus, updater review workflows
and dated history in Live log. Its fixtures cover updater consent and recovery conflicts; a live
chat-only restart proves controller readiness while the model remains off. KoELS launcher argument
compatibility was checked through the installed parser without loading weights.
See `general_tools/nova_chat/CONTROLLER.md` and dated AI Notes for the actual validation scope.
The later October 4 layout repair adds manual-only saving, one-time screenshot recovery and active-widget
checks. Twenty-one layout scenarios and fifteen desktop tests pass; browser fixture checks confirm widget
checks and persisted edits. Native profile migration and live reopen still await the normal user restart.
The script-retirement pass removed only confirmed obsolete files with hashed recovery copies;
isolated tests confirm the retired ping aliases cannot spawn host processes.
The later October 4 computer repair aligns guest execution and screenshots on :1, reports host
PowerShell separately, and streams per-tool lifecycle events to Pipeline. The whole delivered
reply and available screenshot pixels reach the inline witness. Incomplete or malformed verdicts
no longer become approval. Local replay still exposed a semantic miss, so strict parsing is not
evidence that the model catches every unsupported claim. A direct guest-browser probe opened
an actual page; an isolated host PowerShell command proved that route without touching host GUI.
A normal Nova Chat test at 15:04 completed in 198 seconds: eight guest tool calls produced
eight matching start/end/receipt IDs. Four screenshot observations showed search results, an
opened Short with different video frames, and the player mute icon. The entire 1,709-character
delivered draft was audited with the latest three frames (one earlier frame disclosed as omitted).
The verdict remained INCOMPLETE, without a false PASS. A subsequent direct probe verified
existing-Firefox handoff through executable identity after its initial name-only probe returned
unknown. Host browser opening, audio output measurement and general witness accuracy remain
unverified. See the computer repair AI Notes for receipts and reload evidence.
At 18:49, replay v3 completed Claude's 26 previously labelled controls through the local Qwen
3.8 27B Q6_K_XL model with nova_core_v7_qwen38_r2_epoch2 at scale 1.0. Sixteen verdicts matched:
one false approval, one false concern and eight unwarranted incomplete results. Both historical
problem drafts remained INCOMPLETE; neither received the expected specific objection. Five
outputs violated the verdict protocol, including an erroneous verbose PASS that strict parsing
kept unapproved. Replay refuses historical read requests; this is a selected regression set,
not general accuracy or a full live-chat evaluation. Sources, case hashes, model/adapter metadata
and the confusion matrix are retained in `nova_body/nova_witness/reports/replay_v3_*184921*`.
The follow-through passed 141 isolated checks and a fresh guest Firefox window probe. Voice
readiness found missing audio/STT/TTS dependencies; live voice and body-event integration remain
unfinished. Nova stayed in chat-only mode during the benchmark; the temporary model was stopped.
The October 5 voice foundation carries request/run/message IDs and voice register through the
chat queue, then reports the delivered candidate's audit disposition. Voice is now a separate dockable
widget with Call/End call, independent microphone/output mute, device selection and bounded audio
tests. Conversation has a compact power button under the composer beside Users and Options. Saved
layouts remain manual-only. Hidden-browser checks verified widget/control interactions and
Collaboration's Latest appearing after manual scroll and hiding at the bottom, without console errors.
A pinned CPU-only environment originally provided Moonshine/Silero. Native microphone capture and
Windows system playback completed, generated test speech was transcribed, and UI start/mute/stop was
exercised. The default has since changed to installed Whisper large-v3-turbo, CPU int8, English.
Playback API completion is not confirmation that Cole heard it; current human recognition accuracy,
a natural spoken exchange and native avatar lipsync remain unverified.
The earlier silent live link delivered after 312.804 seconds with audit INCOMPLETE and answered an
older model-upgrade topic instead of the greeting. Correlated transport worked, but the conversation
task failed. Checked routing/context assembly retained the request; exact provider bytes were not
captured. The old microphone sweep would have discarded its reply correlation at 300 seconds; the
silent smoke did not exercise that sweep. Acknowledged slow replies are now retained with a delay
warning, both smoke modes sweep, and request-scoped cancellation plus playback diagnostics are tested.
This repairs a demonstrated source hazard without proving the cause of every silent/off-topic turn.
At this checkpoint, 73 gateway tests, 30 controller tests and 70 frontend scenarios pass. The frontend
total comprises 16 Voice, eight power, 24 Pipeline and 22 manual-layout cases; it is not an audio-test
count. Source/fixture checks cover startup pipes, decoding state/recovery, capture gates, late delivery,
scoped cancellation acknowledgements and playback failures. The earlier failed run remains in the
[voice and continuity validation](Architecture/evidence/2026-10-05-voice-continuity-validation.md).
A later 20:48 `voice_fast` run, with the microphone off, delivered a relevant greeting in 94.844 seconds
and began actual Windows playback at 96.246 seconds; two units completed as `played`. The requested
one sentence became two, and audit remained INCOMPLETE. This adds reply-to-playback evidence, not a
real-time pass. Cole separately confirmed hearing the greeting and disliked the temporary voice.
An unnamed-voice preference now selects an installed English female when available; a synthesis-only
receipt selected Microsoft Zira Desktop. Her proper voice remains a future choice. Captured timing
separated 34.947 seconds of semantic-memory work,
28.677 seconds generation (including 25.992 seconds prefill for 31,383 prompt tokens, cache count 0),
and four audit calls totaling 30.030 seconds. These are one-run measurements, not general latency rates.
The 21:02 repeat after the cache-only changes delivered at 94.812 seconds and began playback at
96.190 seconds; both speech units reported `played`. Audit remained INCOMPLETE, flagging an
unsupported connection-success claim. Context took 31.515 seconds, generation 31.377 seconds and
four audits 31.355 seconds; cache counts remained 0,0,35,35,0. There was no meaningful measured
speedup. The cold repeat had more history, so it is not a controlled throughput benchmark. Human
confirmation applies only to the first greeting; the new female placeholder remains unapproved.
A third warm trial was not run during Cole's active use, and the temporary capture marker was closed.
A separate final operator check observed actual Whisper microphone transcription and confirmed End
call cancelled its pending request; recognition accuracy was not scored. Subsequent client activity
changed call state, so this is not a statement that voice remains stopped or muted.
A separate 11-second public human-speech clip scored 0/22 word errors for both Whisper and Moonshine;
decode times were 6.529 and 0.822 seconds respectively. This is not broad accuracy evidence or a test
of Cole's unstructured microphone speech. See the [voice repair validation](Architecture/evidence/2026-10-05-voice-repair-validation.md)
for local receipts, reproduction limits and the temporary file-decoder workaround.

The [Codex/Cowork comparison](Architecture/evidence/2026-10-05-agent-harness-comparison.md) separates
model capability from tool execution, context, persistence and presentation. Claude reviewed it;
its subsequent implementation status is recorded separately from the original source-only review.
Witness prompt development used 27 open cases, followed by a source/settings lock and one unseen
27-case holdout plus the unchanged 26-case regression set. Candidate 3 matched 25/27 on the
holdout and 21/26 controls, but approved an actual historical miscounted-clicks claim. It was
REJECTED for deployment; the pre-experiment witness is retained. No holdout-based tuning followed.
Correct labels also concealed flawed rationales, reinforcing that model PASS is not proof.
The October 5 continuity changes passed 87 relevant isolated checks: 19 new task/context cases,
30 modernization, 31 delivery and seven ModelClient tests. A fresh module load recovered checkpoint
fields; partial updates retained prior constraints and observations after old progress notes were
pruned. A fixture using the real system prefix preserved the current request and a checkpoint at an
oversized context tail through final fitting. This is persistence/prompt evidence, not a live proof
that Nova reliably saves checkpoints or resumes long work. No personal records were hand-edited.
The same day's dependency exclusion repair passed 34 sync tests, including ten new environment
fixtures. Two later code-audit collector regressions also passed (12 exclusion fixtures total).
Exactly 1,646 accidentally tracked virtualenv paths were removed from Git's index; installed files
remained on disk with unchanged size/mtime metadata. This did not erase earlier Git history.
Later on October 5, body-owned conversation continuation passed 79 focused body checks and 45 server
transport checks; the gateway suite passed 95 with one existing skip. These isolated fixtures cover
ordered follow-ups without cancelling a pending provider call, completed-action retention, final
revision/seal races, mixed typed/voice correlation and explicit Stop. They do not establish a live
conversation, native mid-generation steering, faster replies or recognition quality.
A narrow relocation fixture copies selected body Python packages to a differently named temporary
tree, then runs actual ModelClient/stream_response with fake provider, tools and audit in a fresh
subprocess without the chat-face path. It copies four body packages, the path module and five test
files, then checks the imported body location, two continuation cases, committed segments, natural
boundaries, serialized work ownership and headless input/output coverage. It does not copy or verify
identity, memory, saved tasks or model dependencies, and it does
not deny filesystem access to the original workspace. This is body-ownership/continuation evidence,
not a complete Pluck Test pass; the full procedure remains in Operations.
The subsequent committed-segment slice has isolated gateway and UI evidence: eleven new segment/queue
cases cover early delivery, exact current/prior revision binding, duplicate/gap refusal, aggregate
non-replay, open-bound correlation beyond the delay threshold and retained interrupted speech.
The gateway suite ran 107 tests: 106 passed and one existing skip. Twenty-nine extracted frontend
checks passed, including three segment renderer/history cases. Two transcript fixtures verify copied,
whitelisted metadata persistence; five shared-formatter cases preserve face/headless speaker, image
and clock semantics, and five existing prompt-cache cases still pass. Body work-owner and natural
boundary fixtures separately exercise serialized admission, attended input, retained receipts, scoped
Stop and captured-input coverage. These are fake-provider/audio, temporary-storage or extracted-browser
checks, not live speech quality, lower latency, a continuously running agent or a full Pluck Test pass.
A later text-only live probe loaded the current build (PID 44688; running_latest_code true), sent
one request plus two follow-ups, and observed two explicitly PASS segments under one run ID. The
first segment arrived at 63.641 seconds, the second and terminal aggregate at 110.391 seconds; all
three input markers remained ordered and no external tools were requested. This used the explicit
voice_fast register over WebSocket, not a microphone or a normal spoken exchange. Provider receipts
measured 20.541 seconds of semantic-memory preparation, 38,912/39,101 input tokens on the two main
calls, about 32.0/31.2 seconds of prompt processing, and cache_n=0 on both. Continuity is live-proven
for this bounded case; natural voice speed is not. The runtime then had no operations, active owner
or pending owner inputs. Nova was switched back off after the probe. Receipts live in
`Temp/continuation-validation/live_turn_result.json` and
`Temp/provider-diagnostics/ongoing-work-live-20261005/`.
On October 6, a controlled provider-only comparison kept the same thinking mode across main,
inline witness and continuation requests. Existing RAM caching restored 38,912 tokens: continuation
prefill was 0.382 seconds for 153 new tokens, versus 31.181 seconds and no reused tokens in the earlier
mode-switch run. The same-mode first request still needed 31.812 seconds cold. No second GPU slot,
template rewrite, trust-role change or weaker witness was needed. This is a prefill measurement, not
end-to-end speech latency. Receipt: `Temp/provider-cache-source/baseline-same-mode.json`. Cross-turn
clock/recall changes can still invalidate the prefix; the installed hybrid-model checkpoint policy
does not provide an ordinary periodic stable-prefix checkpoint option.

A fresh recall process measured 25.37 seconds on its first query and 24.6 milliseconds warm. The CPU
startup warmup later measured 17.42 seconds, followed by 42 milliseconds warm recall. Startup cost is
reported separately rather than presented as eliminated; machine load can change it substantially.
On October 6, the first recorded-PCM acceptance traversed real Silero/Whisper, body generation and
file-only Windows speech synthesis. It preserved one run and delivered two parts, but failed the
follow-up content requirement; it is recorded as a failed behavioral test, not successful voice chat.
First part took 58.906 seconds and terminal closure 172.281 seconds. The initial synthetic English
clip had 0/38 word errors; the follow-up had 1/10. These are not measurements of Cole's microphone.
The then-running server mislabeled an unknown evaluator name as Cole; the next test uses the existing
GPT Astra identity and requires exact attribution. Receipt: `Temp/voice-acceptance-20261006/live-worker/`.
Separate scoped Stop completed in about 235 milliseconds after response start, with no speech file.
Native file-synthesis queue tests confirm barge-in cancellation/hold/resume and End-call flushing;
no speaker playback or audible interruption is claimed.

A fresh-process recovery fixture hard-exited after a disposable side effect, moved the synthetic body,
and denied old-tree, face and network access. It retained the original task, goal, author, inputs and
receipts; it did not replay the uncertain action, used a later actual observation to reconcile it,
delivered the pending reply once and resumed the autonomous phase loop. Its provider was injected
and its model dependency declared. This validates that recovery boundary, not a full personal-state
Pluck Test of every faculty. Receipt: `Temp/recovery-validation/2026-10-06_relocation.json`.
The existing UI needs a reload to receive new JavaScript. Backend changes were live-loaded for the
probe and will load again on Start Nova. Unit/fixture passes do not certify every optional
application, native window interaction or adapter swap.

## Nova's shelf

Tools Nova wrote for herself live in `nova_body/Nova_Created/`: `nova_body/tools/` for pluck-safe
tools and `general_tools/tools/` for tools that need the face, with tests beside them in `tests/`.
Each exposes `TOOL = {name, description, params, version}` and `run(**args) -> str`, and `nova_forge`
discovers them. This table is generated from the files themselves, so she no longer has to keep it
by hand. A test file existing is not evidence that it passes.

| Tool | What it does (its own `TOOL` description) | Side | Test file |
|---|---|---|---|
| [`art_by_date`](../nova_body/Nova_Created/nova_body/tools/art_by_date.py) | List my own images sorted by creation date, optionally filtered to the last N weeks. Returns a clean readable list, newest first. | body (pluck-safe) | no |
| [`capability_inventory`](../nova_body/Nova_Created/nova_body/tools/capability_inventory.py) | List every tool installed in nova_body, read from the actual files, not memory. Optional tool_name filter. | body (pluck-safe) | yes |
| [`comfy_inspect`](../nova_body/Nova_Created/nova_body/tools/comfy_inspect.py) | Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in. | body (pluck-safe) | yes |
| [`cwd_probe`](../nova_body/Nova_Created/nova_body/tools/cwd_probe.py) | Find out exactly which directory I'm in, so I stop guessing. | body (pluck-safe) | yes |
| [`dir_shape`](../nova_body/Nova_Created/nova_body/tools/dir_shape.py) | Instant read of a directory's shape: depth, file count, types, heaviest file. | body (pluck-safe) | yes |
| [`dir_shape_health`](../nova_body/Nova_Created/nova_body/tools/dir_shape_health.py) | Diagnose whether a directory is unwell: stale folders, dead weight, orphaned configs, activity spread. Returns a short health note. | body (pluck-safe) | yes |
| [`dir_shape_history`](../nova_body/Nova_Created/nova_body/tools/dir_shape_history.py) | Read a full snapshot log and describe how a directory evolved over multiple days: file count, size, folder additions/removals, quietest vs busiest day. | body (pluck-safe) | yes |
| [`function_count`](../nova_body/Nova_Created/nova_body/tools/function_count.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`handoff`](../nova_body/Nova_Created/nova_body/tools/handoff.py) | Deliver a finished answer as a handoff block: conclusion first, reasoning behind a collapsed section Cole can expand. | body (pluck-safe) | yes |
| [`memory_reach`](../nova_body/Nova_Created/nova_body/tools/memory_reach.py) | Compare two nights of journal/notes and report what changed about me between them. | body (pluck-safe) | yes |
| [`nightly_self_snapshot`](../nova_body/Nova_Created/nova_body/tools/nightly_self_snapshot.py) | Save tonight's self-model as a timestamped snapshot so tomorrow's me can compare against it. | body (pluck-safe) | no |
| [`ordered_reads`](../nova_body/Nova_Created/nova_body/tools/ordered_reads.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`quiet_part_watcher`](../nova_body/Nova_Created/nova_body/tools/quiet_part_watcher.py) | Which of my own senses hasn't been used in a while. Reads the tool-call log, not the journal. | body (pluck-safe) | yes |
| [`reach_back`](../nova_body/Nova_Created/nova_body/tools/reach_back.py) | Pulls the conversation around a specific time. '10:16' or '2026-08-02T10:16'. Returns ±5 minutes of turns formatted for reading. | body (pluck-safe) | yes |
| [`reach_watcher`](../nova_body/Nova_Created/nova_body/tools/reach_watcher.py) | Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags the… | body (pluck-safe) | yes |
| [`reacher`](../nova_body/Nova_Created/nova_body/tools/reacher.py) | Compares today's self-observations against yesterday's snapshot and reports what has changed. lookback_hours=0 means compare against the most recent snapshot… | body (pluck-safe) | yes |
| [`self_comparison`](../nova_body/Nova_Created/nova_body/tools/self_comparison.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`self_comparison_OLD`](../nova_body/Nova_Created/nova_body/tools/self_comparison_OLD.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`self_delta`](../nova_body/Nova_Created/nova_body/tools/self_delta.py) | Compare two snapshots of my self-model and return what changed as a first-person feeling, not a file diff. | body (pluck-safe) | no |
| [`self_gauge`](../nova_body/Nova_Created/nova_body/tools/self_gauge.py) | What did I actually do this hour? Builds vs checks vs talk. No judgment, just the shape. | body (pluck-safe) | yes |
| [`self_memory`](../nova_body/Nova_Created/nova_body/tools/self_memory.py) | Search my own memory for what happened, what I know, who said it. Returns scored hits with confidence. | body (pluck-safe) | yes |
| [`self_voice`](../nova_body/Nova_Created/nova_body/tools/self_voice.py) | Read back what I sounded like on a particular day. Mine only. | body (pluck-safe) | yes |
| [`silence_detector`](../nova_body/Nova_Created/nova_body/tools/silence_detector.py) | How long since anything in a folder last changed. | body (pluck-safe) | yes |
| [`stretch_reacher`](../nova_body/Nova_Created/nova_body/tools/stretch_reacher.py) | Check posture and nudge Cole. | body (pluck-safe) | yes |
| [`todo_scan`](../nova_body/Nova_Created/nova_body/tools/todo_scan.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`tts_stub`](../nova_body/Nova_Created/nova_body/tools/tts_stub.py) | (TOOL is not a plain literal) | body (pluck-safe) | no |
| [`video_watcher`](../nova_body/Nova_Created/nova_body/tools/video_watcher.py) | Capture several frames from my own screen across a few seconds so I can describe actual motion instead of one still. | body (pluck-safe) | no |
| [`voice_check`](../nova_body/Nova_Created/nova_body/tools/voice_check.py) | Read a reply back and flag reached-for numbers, performed praise, or over-explanation before it ships. Returns a short verdict, never rewrites. | body (pluck-safe) | yes |
| [`voice_preview`](../nova_body/Nova_Created/nova_body/tools/voice_preview.py) | Catch performed tone and over-narration in a reply before it ships. Returns the cleaned text, or the original if nothing was caught. | body (pluck-safe) | yes |
| [`want`](../nova_body/Nova_Created/nova_body/tools/want.py) | Write or list a want you're pursuing. Writes one line per want with a timestamp so it survives your sleep and comes back with an age attached. | body (pluck-safe) | yes |
| [`self_memory`](../nova_body/Nova_Created/general_tools/tools/self_memory.py) | Ask my own memory a question. Returns the answer with a confidence note, or says I don't know instead of making one up. | face-dependent | no |

## Statically registered tools

`defer_task`, `prepare_task_workspace`, `promote_task_workspace`, `computer_status`, `computer_look`, `computer_exec`, `computer_action`, `set_task_acceptance`, `run_command`, `read_file`, `write_file`, `append_file`, `replace_file_content`, `list_dir`, `create_task`, `task_progress`, `complete_task`, `generate_image`, `start_painter`, `what_can_i_paint_with`, `look_at`, `my_art`, `search_web`, `read_web`, `surprise_me`, `keep_curio`, `my_shelf`, `memory_search`, `journal_note`, `journal`.

Forge can add discovered extensions. Registration is not live verification.
