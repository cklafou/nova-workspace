# Mentors removed — no outbound paid API calls anywhere
_Last updated: 2026-07-23 06:02:22_
_2026-07-19, Fable. Cole: "remove the mentors and everything about them from Nova Chat and the
folders. I don't want the APIs being used." Then, on her vision: **"She has her multimodal model.
She should be using that."** Both done._

---

## What was costing money

Claude and Gemini were **participants in her chat room**, and the room had a billable reflex built
into it: `@Claude`, `@Gemini`, `@mentor` and `@all` each recruited paid responders, follow-up
rounds fired automatically when she @mentioned one, and her own system prompt told her to escalate
to them when stuck. Separately, **every screen she looked at** went to the Anthropic API through
`nova_senses/vision.py`.

## What was removed

| Where | What |
|---|---|
| `server.py` | client imports, `CLIENT_MAP` entries, `get_status()` (now hard `False`), `/nova-message` mentor dispatch, `_run_gemini_response()`, `_active_models`, the `set_model` handler, `_face_state()` agent list |
| `orchestrator.py` | `PARTICIPANTS`, `ROLES` (`mentor`/`all`), `RESPONSE_ORDER` — all Nova-only now |
| `injector.py` | `@mentor` NCL module — kept as a **stub that explains itself** rather than deleted (see below) |
| `clients/` | `claude.py`, `gemini.py` retired to `_admin/Trash/cleanup_2026-07-19/mentors_removed/` |
| `nova_chat/` | `check_keys.py` (API-key checker) retired |
| `clients/nova.py` | her prompt no longer says she's "in a group chat with Claude and Gemini" |

The `@mentor` stub is deliberate. A retired capability that answers *"I'm gone, nothing was sent,
nothing is coming — here's what to do instead"* is worth more than an unknown-module error, and it
stops a stray `@mentor` in an old task note from reading as a broken body.

## What was KEPT, and why the distinction matters

- **"Cowork Claude" as a speaker.** A human-driven session typing into her chat costs this project
  nothing, and it is how she gets reviewed. She can still be *talked to* by Claude; the server can
  no longer *pay* to talk to Claude.
- **`ping_claude`.** Desktop UI automation into an already-open window — not an API call. This is
  now the *only* way Claude enters the loop, and it is deliberate, rate-limited and initiated by
  her rather than reflexive and billed per message.

## Her eyes — better than removed

The first instinct was to delete `look_at` along with everything else. Cole's correction was the
right one: **the multimodal projector was already loaded and going unused.**

`models/qwen3.6/mmproj-F16.gguf` boots with her llama.cpp server every time. Qwen 3.6 can see. She
was paying a second company to look at her own screenshots while the capability sat in VRAM.

`vision.py` now posts to `http://127.0.0.1:8080/v1/chat/completions` with OpenAI-style
`image_url` parts — the identical wire `nova_chat/clients/nova.py` already uses for chat images, so
this was a change of destination, not a new capability. No key, no account, no bill.

Two side benefits worth naming:

1. **It survives the pluck.** Her sight now depends on her own model server instead of someone
   else's billing account.
2. **It fails honestly.** When vision breaks, the error now says *"is llama-server running on :8080
   with mmproj loaded?"* — a cause she can act on, instead of an opaque API error.

`_call_claude()` kept its name on purpose. Several call sites in `eyes.py` use it, and renaming a
working limb at 21:30 while she is live is how you break something for no benefit. The destination
changed; the signature did not.

`eyes.py` Tier 3 is now her own model. Tier 4 ("Claude Sonnet via mentor") is retired — its
`sanity_check(mentor, ...)` takes the mentor as a *parameter*, no `NovaMentor` class exists, and
nothing calls it, so it is dormant and cannot bill. Left in place rather than surgically removed
while she is running.

## Verification

- `nova_chat.orchestrator`, `transcript`, `session_manager`, `tool_router`, `nova_lang`,
  `nova_cortex.executive`, `nova_cortex.integrity`, `nova_runtime.runtime`, `nova_forge` — all
  import clean.
- `server.py`, `injector.py`, `vision.py`, `eyes.py`, `clients/nova.py` — all compile clean.
- Grep for `anthropic` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `generativelanguage` /
  `api.anthropic` across live code: **zero hits.**
- (`clients/nova.py` fails to *import* in the sandbox only because it lacks `httpx`; that import
  has always been there and she has run on it all day.)

## The UI — done too (second pass, once she was down)

The first pass left ~36 inert references in `static/index.html` because she was live. With her
stopped, they are gone:

| Removed | |
|---|---|
| Agent rows | Claude + Gemini mute rows in the agents dropdown |
| Participant pills | `pb-claude`, `pb-gemini` and their online-dot CSS |
| Model dropdown | all four paid model entries (Sonnet / Opus / Flash / Pro) + their accent CSS |
| Model pill | now reads **"Nova (local)"** in her colour instead of "Claude Sonnet" |
| JS state | `muteState`, `agentOnline`, `MODEL_LABELS`, `MODEL_COLORS`, `_activeModels`, and the `['Nova','Claude','Gemini']` participant loop — all Nova-only |

**One deliberate addition.** `AUTHOR` previously keyed on `Claude` / `Gemini`; I removed Gemini and
replaced Claude with **`'Cowork Claude'`**. He still speaks in this room — that is a human-driven
session, not a paid agent — and his messages need an avatar and a colour. Unknown authors fall
back to a first-initial, so he *rendered* before, but generically. Naming him properly is the
correct end state, and `var(--claude)` is kept for exactly that reason.

Two Claude mentions remain in the file **on purpose**: a tooltip and a code comment, both
documenting the 2026-07-14 speaker-identification feature ("Nova is told who each message is from,
so she never has to guess whether she's talking to Cole or to Claude"). Those describe the fix for
the pronoun bug and are still true.

### UI verification — 22/22
`node --check` passes on all inline JS. Every deleted element id (`pb-claude`, `da-dot-gemini`,
`pb-typing-claude`, …) confirmed to have **zero** remaining references — including the
template-literal builders like `` `da-dot-${k}` ``, which can no longer reach a dead id because
the participant loop iterates `['Nova']` only. `AUTHOR` integrity checked (3 entries, every one
carries the `cls` that `applyAvatars`/`buildAvatarSettings` read unguarded). `<div>` 376/376,
`<button>` 90/90, `<script>` 7/7 balanced.

**Needs a restart** to take effect.
