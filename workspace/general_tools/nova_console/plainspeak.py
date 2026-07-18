# Last updated: 2026-07-19 07:09:37
# @nova: Plain-speak — turns machine log spew into a sentence a human can read.
#
# Deliberately RULE-BASED, not model-based. A log tail emits hundreds of lines a minute; sending
# them to an LLM would be slow, expensive, hammer Nova's own GPU, and — worst — would sometimes
# INVENT a translation that sounds plausible and is wrong. A lookup table can't hallucinate.
#
# If no rule matches we return None and the UI shows the raw line. Showing you the truth you can't
# read beats showing you a confident guess.

import re

# (compiled pattern, replacement) — first match wins. \1 \2 refer to capture groups.
RULES: list[tuple[re.Pattern, str]] = [
    # ── launcher (nova_start.py's own lines) ─────────────────────────────────
    (re.compile(r"\[INFO\] Workspace: (.+)"),                    r"Working folder: \1"),
    (re.compile(r"\[INFO\] Starting llama-server"),              "Starting Nova's brain (the model server)…"),
    (re.compile(r"\[INFO\] llama-server is HEALTHY"),            "✓ Nova's brain is loaded and responding."),
    (re.compile(r"\[INFO\] llama-server already healthy"),       "Nova's brain was already running — reusing it."),
    (re.compile(r"\[ERROR\] llama-server did not become healthy within (\d+)s"),
                                                                 r"✗ Nova's brain failed to load within \1 seconds. Check the llama-server tab."),
    (re.compile(r"\[INFO\] Starting Nova\.\.\."),                "Starting Nova's chat server…"),
    (re.compile(r"\[INFO\] Nova chat is UP"),                    "✓ Nova is online and ready to talk."),
    (re.compile(r"\[INFO\] Using Python: (.+)"),                 r"Using this Python: \1"),
    (re.compile(r"\[INFO\] Opening Nova app window"),            "Opening Nova's window…"),
    (re.compile(r"\[INFO\] Starting file watcher"),              "Starting the file watcher (auto-saves your work to git)…"),
    (re.compile(r"\[INFO\] Console hub on (.+)"),                "✓ Log viewer connected."),
    (re.compile(r"\[INFO\] Stopping llama-server"),              "Shutting down Nova's brain…"),
    (re.compile(r"\[INFO\] Stopping file watcher"),              "Stopping the file watcher…"),
    (re.compile(r"\[INFO\] Shutdown requested"),                 "Shutdown requested — closing everything down cleanly."),
    (re.compile(r"\[INFO\] Shutdown complete"),                  "✓ Everything stopped cleanly."),
    (re.compile(r"\[INFO\] Nova app window closed"),             "Nova's window was closed."),
    (re.compile(r"^── (.+) ──$"),                                r"\1"),

    # ── llama.cpp (Nova's brain) ─────────────────────────────────────────────
    (re.compile(r"ggml_cuda_init: found (\d+) CUDA device"),     r"Found \1 graphics card(s)."),
    (re.compile(r"llama_model_loader:.*loaded meta data"),       "Reading the model file…"),
    (re.compile(r"load_tensors:.*offloaded (\d+)/(\d+) layers to GPU"),
                                                                 r"Loaded \1 of \2 model layers onto the graphics cards."),
    (re.compile(r"(load_tensors|llm_load_tensors):"),            "Loading the model onto your graphics cards…"),
    # NOTE: greedy `.*` on purpose — it must run to the LAST colon so we capture the PORT.
    # A lazy `.*?(\d+)` matched the first digits of the IP and cheerfully reported "port 127".
    (re.compile(r"main: server is listening on .*:(\d+)"),       r"✓ Nova's brain is listening on port \1."),
    (re.compile(r"main: model loaded"),                          "✓ Model loaded into memory."),
    (re.compile(r"update_slots: all slots are idle"),            "Nova's brain is idle, waiting for work."),
    (re.compile(r"launch_slot_.*processing task"),               "Nova started thinking about something."),
    (re.compile(r"slot release.*stop processing"),               "Nova finished thinking."),
    (re.compile(r"prompt eval time\s*=\s*([\d.]+) ms"),          r"Nova read the conversation (took \1 ms)."),
    (re.compile(r"eval time.*?([\d.]+) tokens per second"),      r"Nova wrote her reply at about \1 words/sec."),
    (re.compile(r"srv\s+log_server_r: request: GET /health"),    "Health check — is the brain alive?"),
    (re.compile(r"n_ctx\s*=\s*(\d+)"),                           r"Nova can hold about \1 tokens of conversation in mind."),

    # ── Nova chat server (uvicorn / websockets) ──────────────────────────────
    (re.compile(r"Uvicorn running on .*:(\d+)"),                 r"✓ Nova's chat server is live on port \1."),
    (re.compile(r"Application startup complete"),                "✓ Chat server finished starting up."),
    (re.compile(r"WebSocket .*\[accepted\]"),                    "Your browser connected to Nova."),
    (re.compile(r"connection open"),                             "Browser connected."),
    (re.compile(r"connection closed"),                           "Browser disconnected."),
    (re.compile(r'"(GET|POST) (\S+) HTTP/1\.1" 200'),            r"Handled a \1 request to \2 — OK."),
    (re.compile(r'"(GET|POST) (\S+) HTTP/1\.1" (4\d\d|5\d\d)'),  r"✗ A \1 request to \2 failed (error \3)."),
    (re.compile(r"POST .*/v1/chat/completions.*200"),            "✓ Nova answered a request."),

    # ── watcher / git ────────────────────────────────────────────────────────
    (re.compile(r"nothing to commit"),                           "No changes to save."),
    (re.compile(r"\[master [0-9a-f]{7}\]|Committed|git commit"), "✓ Auto-saved your changes to git."),
    (re.compile(r"Pushed|-> +master|origin/master"),             "✓ Backed your changes up online."),
    (re.compile(r"[Mm]anifest.*(refresh|rebuil|updat)"),         "Updated Nova's map of her own body (the manifest)."),
    (re.compile(r"index\.lock"),                                 "✗ Git is stuck on a leftover lock file. Run StopNova, then delete .git\\index.lock."),

    # ── console hub ──────────────────────────────────────────────────────────
    (re.compile(r"\[hub\] following (.+)"),                      r"Now watching a fresh log file (\1) — the brain restarted."),
    (re.compile(r"\[hub\] pipe closed"),                         "That program stopped, so its log ended."),

    # ── generic fallbacks (LAST — they're greedy) ────────────────────────────
    (re.compile(r"\[ERROR\]\s*(.+)", re.I),                      r"✗ Problem: \1"),
    (re.compile(r"\[WARN(?:ING)?\]\s*(.+)", re.I),               r"⚠ Heads up: \1"),
    (re.compile(r"^\s*Traceback\b.*", re.I),                     "✗ Something crashed — the technical details follow below."),
    (re.compile(r"^\s*error\b[: ]*(.*)", re.I),                  r"✗ Something broke: \1"),
    (re.compile(r"^\s*warning\b[: ]*(.*)", re.I),                r"⚠ Heads up: \1"),
]


def plain(line: str) -> str | None:
    """Return a human-readable version of a log line, or None if we don't have a rule for it
    (the UI then shows the raw line — we never invent a translation)."""
    if not line:
        return None
    for pat, rep in RULES:
        m = pat.search(line)
        if m:
            try:
                out = m.expand(rep) if "\\" in rep else rep
            except Exception:
                out = rep
            return out.strip()
    return None
