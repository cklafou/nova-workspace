# Nova architecture — generated source inventory

Generated: 2026-09-30T17:38:31.228919+00:00 · revision `f79dca212bd9d8e6`

Open `index.html` for all three levels. SVGs are overview exports; the explorer and tables contain the complete mapped inventory.

Static imports are dependencies, not execution order. Source-checked seams are reviewed annotations. Unresolved receivers are reported, never guessed.

78 modules · 217 import references · 1494 resolved call sites · 37 reviewed seams.

## Launch boundary

Starts llama.cpp and installs one shared NovaRuntime before attaching the chat application. Launch utilities are shown only at their connection to the body.

| Module | Purpose |
|---|---|
| `general_tools/NovaLauncher.py` | Sets NOVA_WORKSPACE, installs a shared body runtime before importing the server, and hosts the chat attachment on port 8765. |
| `nova_start.py` | Chooses local executables, starts model services and NovaLauncher, then opens the controller. This is the normal stack entry point. |

## Chat attachment

Receives messages, assembles file and memory context, passes generation callbacks, and streams replies. This external attachment still performs context assembly for the normal chat path.

| Module | Purpose |
|---|---|
| `general_tools/nova_chat/nova_bridge.py` | Parses structured directives from responses and translates supported directives into body/task operations. Shows the attachment seam, not each detachable tool. |
| `general_tools/nova_chat/runtime_host.py` | Creates and registers a NovaRuntime before attaching the FastAPI chat app. It retains the chat application's rich autonomy callbacks. |
| `general_tools/nova_chat/server.py` | Accepts HTTP/WebSocket messages, mediates access, builds context, supplies autonomy callbacks, calls model dispatch, indexes messages and publishes UI output. Individual tool endpoints are not expanded in the architecture diagram. |
| `general_tools/nova_chat/session_manager.py` | Creates and switches chat sessions, manages session metadata and compresses inactive transcript files. |
| `general_tools/nova_chat/transcript.py` | Appends session messages to JSONL and formats conversation plus workspace context into model messages. |
| `general_tools/nova_chat/workspace_context.py` | Compatibility import forwarding the detachable face to body-owned context assembly. |

## Computer faculty

Defines a backend-neutral computer, selects local Linux or WSL, and offers shell and GUI actions through Hands. Standalone setup/diagnostic entry points also live here.

| Module | Purpose |
|---|---|
| `nova_body/nova_computer/__init__.py` | Exposes Nova's backend-neutral computer faculty. |
| `nova_body/nova_computer/backends.py` | Implements probing and operations for local POSIX, WSL and unavailable-backend cases. |
| `nova_body/nova_computer/computer.py` | Selects a backend and exposes shell, lifecycle and snapshot operations while keeping backend details behind one interface. |
| `nova_body/nova_computer/first_boot.py` | Standalone provisioning entry point for the computer environment; not a normal chat callback. |
| `nova_body/nova_computer/hands.py` | Uses the computer's shell channel to run scrot and xdotool on a separate X display for screenshots and GUI actions. |
| `nova_body/nova_computer/pluck_check.py` | Standalone diagnostic for imports and backend behavior. Diagnostics are not evidence that the main response loop is wired to Hands. |
| `nova_body/nova_computer/reach.py` | Configures the WSL computer's access to host files and Windows interoperability. |
| `nova_body/nova_computer/toolkit.py` | Standalone setup utility that installs software into the guest computer. |
| `nova_body/nova_computer/tune_up.py` | Standalone repair and diagnostic pass for guest account, display and authentication issues. |

## Config helper

Defines a configuration loader and fallback defaults. An existing package or configuration file does not establish that the running paths consume it.

| Module | Purpose |
|---|---|
| `nova_body/nova_config/__init__.py` | Loads nova_config.json and supplies fallback defaults. No ordinary import consumer was found in the initial mapped inventory. |

## Cortex

Builds reflection and decision prompts, applies actions to the task board, tracks drives, checks evidence, identifies speakers and chooses specialist loadouts.

| Module | Purpose |
|---|---|
| `nova_body/nova_cortex/__init__.py` | Package entry for executive, tasking and context faculties. |
| `nova_body/nova_cortex/checkin.py` | Checks for human interruptions or instructions between actions. Its presence alone is not proof that the normal response loop invokes it. |
| `nova_body/nova_cortex/context_builder.py` | Provides lightweight token estimates and context budget helpers; references indicate which paths actually use them. |
| `nova_body/nova_cortex/discourse.py` | Determines what is happening in the conversation, who is present, and whether a response belongs in the room; includes recent actions as grounding. |
| `nova_body/nova_cortex/drives.py` | Maintains boredom, wants and novelty feedback that influence what Nova chooses to do during autonomous wakes. |
| `nova_body/nova_cortex/executive.py` | Maintains autonomy state; builds reflection, decision and execution prompts; applies structured decisions and records progress or rest. |
| `nova_body/nova_cortex/integrity.py` | Parses action calls, records actual results, retrieves receipts and reconciles demonstrated work with the task board. |
| `nova_body/nova_cortex/loadout.py` | Reads KoELS manifests and makes pure loadout decisions from task text. Physical adapter changes belong to the runtime equip mechanism. |
| `nova_body/nova_cortex/nova_status.py` | Writes Nova's status record for external observers. |
| `nova_body/nova_cortex/principals.py` | Classifies known principals, checks capabilities and validates untrusted input. The server enforces this body-owned policy at its boundary. |
| `nova_body/nova_cortex/rules.py` | Contains operating-rule text and access helpers. Import evidence, not its legacy bootstrap description, determines its mapped consumers. |
| `nova_body/nova_cortex/tasking.py` | Reads and updates the id-keyed task board, including status, priorities and progress. Completed and abandoned tasks remain records. |
| `nova_body/nova_cortex/tunables.py` | Reads and validates tunable inference and behavior settings from the administrative JSON store, with cached reads and defaults. |
| `nova_body/nova_cortex/witness.py` | Builds present-tense evidence, flags checkable claims, prepares audit prompts, interprets verdicts and records witness pipeline events. |
| `nova_body/nova_cortex/workspace_context.py` | Body-owned grounding: loads self-model, memory and mentioned files for both chat and headless execution. |

## Forge

Discovers, classifies, loads and tests created capabilities. The discovery and dispatch boundary is mapped; individual created tools are excluded.

| Module | Purpose |
|---|---|
| `nova_body/nova_forge/__init__.py` | Requires designs, resolves body/tool locations, dynamically loads created modules and tracks their tests before dispatch. |

## Imagination

Builds image workflows, selects checkpoints and LoRAs, submits work to ComfyUI and collects output. Service availability is separate from code wiring.

| Module | Purpose |
|---|---|
| `nova_body/nova_imagination/__init__.py` | Exposes image-creation faculty operations. |
| `nova_body/nova_imagination/imagination.py` | Builds and submits image workflows, polls results, manages model resources and retrieves created images. |
| `nova_body/nova_imagination/palette.py` | Describes available visual mediums/checkpoints and helps select an appropriate image-generation setup. |

## Searchable memory

Queues chat and image entries, embeds them, stores them in local LanceDB tables, and returns bounded text excerpts for automatic or deliberate recall.

| Module | Purpose |
|---|---|
| `nova_body/nova_lancedb/__init__.py` | Package entry for embedding, storage and background ingestion. |
| `nova_body/nova_lancedb/embedder.py` | Lazily loads MiniLM for text and CLIP for images. Converts inputs into vectors; failed embedding operations currently return zero vectors. |
| `nova_body/nova_lancedb/hippocampus.py` | Opens local LanceDB tables, stores text and image embeddings, applies similarity-based retention and formats bounded recall excerpts. |
| `nova_body/nova_lancedb/indexer.py` | Runs a worker thread that takes queued chat/image entries and passes them to the persistent store. |

## Logging and retention

Provides logging helpers and retention policy. Some faculties also write dedicated receipts directly; this package is not the sole writer of all records.

| Module | Purpose |
|---|---|
| `nova_body/nova_logs/__init__.py` | Package entry for log writers and retention helpers. |
| `nova_body/nova_logs/logger.py` | Writes categorized application records and generates its logging index. |
| `nova_body/nova_logs/retention.py` | Applies retention/rotation rules to supported log files so they do not grow without bounds. |

## Journal and state helpers

Provides append-only journaling, goal proposals, log reading and precondition helpers. The main router currently writes journal files directly; this package is distinct from LanceDB.

| Module | Purpose |
|---|---|
| `nova_body/nova_memory/__init__.py` | Package entry for journal, goal, state and log-reading helpers, separate from vector memory. |
| `nova_body/nova_memory/goals.py` | Prepares goal/status changes using a proposal workflow rather than directly replacing the status document. |
| `nova_body/nova_memory/journal.py` | Provides safe append operations for journal records; compare incoming references with the router's separate journal implementation. |
| `nova_body/nova_memory/log_reader.py` | Reads previous session logs and supports reviewing actual events and failures. |
| `nova_body/nova_memory/state.py` | Checks state preconditions for actions; the map shows whether callers use this helper. |

## nova_paths.py

New package discovered; explanation needs review.

| Module | Purpose |
|---|---|
| `nova_body/nova_paths.py` | Nova's persistent-state ownership, independent of the face or current directory. NOVA_BODY may name a relocated body directory. NOVA_WORKSPACE identifies the optional surrounding project (tools, authored artifacts, inference launchers). No reads fall back to old workspace-level state: missing body data must not silently select another Nova. |

## Play

Selects unexpected material, including a random encyclopedia topic, and saves chosen curios to a shelf.

| Module | Purpose |
|---|---|
| `nova_body/nova_play/__init__.py` | Package entry for curiosity-driven activity. |
| `nova_body/nova_play/curio.py` | Selects surprising material from local/external sources and saves chosen curios to a shelf. |

## Runtime

Owns the wake loop, event bus, transcript view, model dispatch, model guard, memory indexer, model-server control and adapter equip mechanism.

| Module | Purpose |
|---|---|
| `nova_body/nova_runtime/__init__.py` | Package entry for Nova's runtime and lifecycle machinery. |
| `nova_body/nova_runtime/__main__.py` | Adds body/workspace import roots and runs NovaRuntime without a chat application. |
| `nova_body/nova_runtime/event_bus.py` | Publishes lifecycle events into bounded asyncio subscriber queues. With no attached subscriber, the body does not need a UI to accept its events. |
| `nova_body/nova_runtime/koels_equip.py` | Persists desired specialist adapters, adjusts loaded adapter scales over HTTP, and coordinates restart-based loadout changes through LlamaControl. |
| `nova_body/nova_runtime/llama_control.py` | Checks the local model service and provides start/stop/restart operations through injected or default operating-system hooks. |
| `nova_body/nova_runtime/model_client.py` | Registers a response client and forwards generation arguments and output callbacks. The registered Nova client performs the actual model request. |
| `nova_body/nova_runtime/model_guard.py` | Tracks repeated model failures and rate/backoff limits to prevent uncontrolled retries. |
| `nova_body/nova_runtime/runtime.py` | Coordinates boot, perception, the memory worker and the reflect-decide-act wake cycle. Host callbacks supply conversation and generation; headless boot uses the shared body-owned grounding builder. |
| `nova_body/nova_runtime/transcript_store.py` | Reads persistent conversation records and tracks which human messages have already been attended to. |

## Senses

Reads time, presence, environment, interaction state, hardware/UI state, images and web information. Host-screen vision and the separate Linux desktop are distinct paths.

| Module | Purpose |
|---|---|
| `nova_body/nova_senses/__init__.py` | Package entry for perception modules. Individual imports provide current wiring evidence; the package's old scaffold comments are not authoritative. |
| `nova_body/nova_senses/clock.py` | Reads real time and supports timed wake decisions. |
| `nova_body/nova_senses/environment.py` | Observes watched paths and changes in Nova's surroundings for wake/perception context. |
| `nova_body/nova_senses/eyes.py` | Combines host UI inspection, screenshot capture and local image understanding. This does not establish a connection to the separate Linux Hands display. |
| `nova_body/nova_senses/presence.py` | Observes whether another participant is present instead of inferring presence from old conversation text. |
| `nova_body/nova_senses/proprioception.py` | Inspects host application windows, UI elements and system state for higher-level sensing. |
| `nova_body/nova_senses/quiet_part_watcher.py` | Inspects activity evidence for capabilities that have stopped being used and surfaces those gaps. |
| `nova_body/nova_senses/sight.py` | Resolves and shrinks image inputs, calls the local multimodal endpoint and records what was actually viewed. |
| `nova_body/nova_senses/stretch.py` | Observes prolonged inactivity and prepares a stretch-related reach-out. The runtime also contains a separately loaded created watcher, shown as a dynamic boundary. |
| `nova_body/nova_senses/touch.py` | Tracks who or what is interacting with Nova and which surfaces are active. |
| `nova_body/nova_senses/vision.py` | Captures the host screen with pyautogui and sends image requests to the local vision-capable model endpoint. |
| `nova_body/nova_senses/web.py` | Searches or reads external web material and returns it through the body's perception interface. |

## Voice and action router

Calls the language model, handles reasoning and response channels, recognizes action requests, dispatches them, and runs evidence checks before the reply is committed.

| Module | Purpose |
|---|---|
| `nova_body/nova_voice/__init__.py` | Package boundary for the body-owned model response loop and action dispatcher. |
| `nova_body/nova_voice/nova.py` | Assembles model messages, streams local inference, recognizes action calls in content/thinking, feeds results back, and runs witness checks before returning a reply. |
| `nova_body/nova_voice/tool_router.py` | Dispatches model-requested operations through body faculties and external tools, leaves receipts, and directly implements journal and recall entry points. Individual tool internals are excluded from this map. |

## Witness evaluation

Contains golden-case extraction and replay utilities, not the live witness faculty. Live witness decisions are implemented in nova_cortex/witness.py.

| Module | Purpose |
|---|---|
| `nova_body/nova_witness/extract_golden.py` | Reads recorded witness events and extracts cases for later evaluation. |
| `nova_body/nova_witness/replay.py` | Replays recorded audit cases against a specified inference endpoint. This is an evaluation entry point, not the live witness loop. |

## Supporting launch and provisioning definitions

- `nova_body/nova_computer/HANDS.cmd`
- `nova_body/nova_computer/PLUCK_CHECK.cmd`
- `nova_body/nova_computer/provision/setup_guest.sh`
- `nova_body/nova_computer/REACH.cmd`
- `nova_body/nova_computer/RUN_SETUP.cmd`
- `nova_body/nova_computer/SNAPSHOT.cmd`
- `nova_body/nova_computer/TOOLKIT.cmd`
- `nova_body/nova_computer/TUNE_UP.cmd`
- `nova_body/nova_witness/fetch_witness_model.cmd`
- `nova_body/nova_witness/start_witness.cmd`
- `NovaStart.cmd`
- `start_llama_qwen36.cmd`
- `StopNova.cmd`
## Parse failures

[]

## Reviewed seams requiring another review

- Invoke host-supplied generation callback on chat-hosted wakes: Enclosing source changed since this explanation was reviewed
- Register Nova response client and supply token/result callbacks: Enclosing source changed since this explanation was reviewed
- Call the registered Nova stream_response implementation: Enclosing source changed since this explanation was reviewed
- Subscriber queues carry lifecycle events to the attached face: Enclosing source changed since this explanation was reviewed
- Headless generation passes empty workspace_context: Evidence no longer contains 'workspace_context=""'; Enclosing source changed since this explanation was reviewed
- Read SELF/core and selected memory files into chat context: Missing source/symbol: general_tools/nova_chat/workspace_context.py WorkspaceContext.build_nova_context_block; Missing source/symbol: general_tools/nova_chat/workspace_context.py _get_always_load
- Automatic recall with latest message through WorkspaceContext: Enclosing source changed since this explanation was reviewed; Missing source/symbol: general_tools/nova_chat/workspace_context.py WorkspaceContext.build_nova_memory_context
- Queue chat replies for background embedding: Enclosing source changed since this explanation was reviewed
- Stream chat completions from local llama.cpp: Enclosing source changed since this explanation was reviewed
- Task board owns durable task records: Evidence no longer contains '"Tasking" / "tasks.json"'; Enclosing source changed since this explanation was reviewed
- Persist autonomy, focus and reflection state: Enclosing source changed since this explanation was reviewed
- Persist wants, boredom and novelty feedback: Enclosing source changed since this explanation was reviewed
- Router directly appends consolidated journal entries: Enclosing source changed since this explanation was reviewed
- Persist chat sessions separately from vector memory: Enclosing source changed since this explanation was reviewed
- Read live settings from _admin/tunables.json: Enclosing source changed since this explanation was reviewed
- Load a created stretch watcher by file path: Enclosing source changed since this explanation was reviewed
- Retrieve an unexpected encyclopedia topic: Enclosing source changed since this explanation was reviewed
- Serve the chat app on CHAT_PORT; the body shares this process: Enclosing source changed since this explanation was reviewed
