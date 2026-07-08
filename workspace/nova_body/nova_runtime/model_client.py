# Last updated: 2026-07-09 05:14:59
# @nova: ModelClient — the act of generation as a body faculty (layer 2). It owns HOW Nova
#        (and the mentors) are driven to produce a response: the model dispatch + each model's
#        call convention, lifted faithfully out of the chat server's run_ai_response. It does
#        NOT broadcast — the caller injects sinks (on_token / on_done / on_error / …). A face's
#        sinks render to the UI; a headless daemon's sinks can log or no-op. THIS is what lets
#        her generate with no chat server attached — the Step-5 autonomy daemon will call
#        generate() directly instead of reaching into the server.
"""
nova_runtime/model_client.py — relocated faithfully from general_tools/nova_chat/server.py
(the model-dispatch tail of run_ai_response). Behavior is unchanged; the dispatch just lives
in the body now and takes its output sinks AND the client modules by injection, so it imports
no chat-server module and runs with or without a face.

Step 4 split — "model-call vs token-broadcast": generation (this) and rendering (the sinks)
used to be one monolith. Pulling the model-call into the body makes the thing that *makes*
tokens a faculty; the thing that *shows* them stays a detachable face concern. The guard
(ModelGuard) and the success/error bookkeeping stay in the caller's sinks for now — this step
moves only the dispatch, nothing else, so behavior is identical.
"""


class ModelClient:
    def __init__(self):
        # Injected by a host (see register): the body imports no client module itself, so it
        # stays pluckable. _gemini_runner is the one odd convention — a coroutine, not a client
        # object with .stream_response — injected the same way (cf. LlamaControl's OS hooks).
        self._clients: dict = {}
        self._gemini_runner = None

    def register(self, clients: dict = None, gemini_runner=None) -> None:
        """A host registers the model client modules (keyed by AI name) and the Gemini runner
        coroutine. Called once at startup; generate() resolves the client by ai_name after."""
        if clients:
            self._clients.update(clients)
        if gemini_runner is not None:
            self._gemini_runner = gemini_runner

    def has(self, ai_name: str) -> bool:
        """True if this faculty can generate for `ai_name` (client registered, or Gemini runner)."""
        if ai_name == "Gemini":
            return self._gemini_runner is not None
        return ai_name in self._clients

    async def generate(self, ai_name: str, transcript, *,
                       on_token, on_done, on_error,
                       on_think_token=None, on_progress=None, on_tool_executed=None,
                       workspace_context: str = "", images=None,
                       autonomous: bool = False,
                       temperature: float = 0.7, top_p: float = 0.9) -> None:
        """Drive one generation. The caller supplies the output sinks (what to do with each
        token, on done, on error); this owns only WHICH client and HOW it is called. Faithful
        to run_ai_response's three branches:
          • Gemini — the injected runner coroutine (no transcript arg; word-chunk "streaming").
          • Nova   — the rich signature: <think> parsing, live progress, tool callback, sampling.
          • else   — the basic mentor signature (Claude): transcript + sinks + context + images.
        """
        if ai_name == "Gemini":
            if self._gemini_runner is None:
                raise RuntimeError("ModelClient: no gemini_runner registered")
            await self._gemini_runner(on_token, on_done, on_error, workspace_context, images=images)
            return

        client_mod = self._clients.get(ai_name)
        if client_mod is None:
            raise RuntimeError(f"ModelClient: no client registered for {ai_name!r}")

        if ai_name == "Nova":
            # Nova supports <think> tag parsing — pass on_think_token and on_progress. The
            # transcript is whatever the caller resolved (HeartbeatContext for HB ticks, or the
            # active session for normal turns); the faculty stays agnostic to which.
            await client_mod.stream_response(
                transcript, on_token, on_done, on_error,
                on_think_token=on_think_token,
                on_progress=on_progress,
                on_tool_executed=on_tool_executed,
                workspace_context=workspace_context, images=images,
                autonomous=autonomous,
                temperature=temperature,
                top_p=top_p,
            )
        else:
            await client_mod.stream_response(
                transcript, on_token, on_done, on_error,
                workspace_context=workspace_context, images=images,
            )
