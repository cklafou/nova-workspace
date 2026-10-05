<!-- @nova: Explain Nova access boundaries, identity and known exposure gaps. -->
_Last updated: 2026-10-04 15:06:16_
---
doc: OPERATIONS.md
order: 10
---
<!-- @nova: Orient note: Nova's security model and its known gaps, published in OPERATIONS.md. -->
## Security model

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
text in Nova's body. A future remote voice gateway still needs the transport identity work above.

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
