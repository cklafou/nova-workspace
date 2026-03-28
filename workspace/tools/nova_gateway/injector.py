"""
nova_gateway/injector.py — NCL Context Injector & Module Dispatcher
====================================================================
Phase 4A.4: Executes parsed NCLCall objects from Nova Chat.

For each ModuleCall in an NCLCall, the injector:
  1. Reads <<context_file.md>> files from workspace and builds a context block
  2. Builds the full prompt: context + [[instructions]] + $$prev if chained
  3. Dispatches to the correct module handler based on @role
  4. Posts the result to Nova Chat with [TASK_ID] prefix for inbox routing
  5. If >>output_target is specified, also writes the result to that path

Parallel groups (;; separator) are dispatched concurrently via asyncio.gather.
Sequential chains (:: separator) run in order, each step receiving the prior
step's output via $$prev substitution.

── Module dispatch strategies (Phase 4A.4) ────────────────────────────────
  @eyes    → NovaEyes direct import (pywinauto Tier 1 + Claude Haiku Tier 4)
             Falls back gracefully if pywinauto unavailable (e.g. Linux dev)
  @mentor  → Posts @Claude @Gemini message to Nova Chat (fire-and-forget).
             Claude + Gemini respond naturally; inbox routing (4A.5) picks up
             the response when they echo the [task_id] header.
  @coder, @browser, @thinkorswim, @memory, @voice
           → "not yet implemented" notice posted to Nova Chat + Master_Inbox
             stub written so the Thoughts system knows the call was attempted.

── Usage from nova_chat/server.py ─────────────────────────────────────────
    from nova_gateway.injector import NCLInjector
    from nova_chat.nova_lang import parse_ncl
    from nova_chat.orchestrator import is_ncl_message

    if author == "Nova" and is_ncl_message(content):
        ncl = parse_ncl(content)
        if ncl:
            injector = NCLInjector()
            asyncio.create_task(injector.execute(ncl))
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Workspace root — 3 levels up: nova_gateway/ → tools/ → workspace/
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

# Nova Chat server base URL
_NOVA_CHAT_URL = "http://127.0.0.1:8765"

# Max bytes to read per context file (keeps prompts manageable)
_CONTEXT_FILE_MAX_BYTES = 6_000

# Default module timeout when %%N is not specified
_DEFAULT_TIMEOUT_S = 60


# ── Main class ─────────────────────────────────────────────────────────────────

class NCLInjector:
    """
    Executes a parsed NCLCall by dispatching each ModuleCall to the
    appropriate module handler and routing results back to Nova Chat.

    Instantiate once per NCL call (or reuse across multiple calls — it is
    stateless except for the workspace path and nova_chat URL).
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        nova_chat_url: str = _NOVA_CHAT_URL,
    ):
        self.workspace    = (workspace_root or _WORKSPACE_ROOT).resolve()
        self.nova_chat_url = nova_chat_url

    # ── Public entry point ────────────────────────────────────────────────────

    async def execute(self, ncl_call) -> list[dict]:
        """
        Execute an NCLCall.

        Parallel groups (;;) are dispatched concurrently.
        Sequential steps within a chain (::) run in order.

        Returns a list of result dicts:
            {"chain_output": str, "error": str|None}
        One dict per chain across all parallel groups.
        """
        from nova_chat.nova_lang import summarize_ncl
        log.info("[NCL] Executing: %s", summarize_ncl(ncl_call))

        tasks = []
        for group in ncl_call.parallel_groups:
            for chain in group.chains:
                tasks.append(self._execute_chain(chain))

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict] = []
        for r in raw_results:
            if isinstance(r, Exception):
                log.error("[NCL] Chain raised exception: %s", r, exc_info=True)
                results.append({"chain_output": f"[NCL ERROR] {r}", "error": str(r)})
            else:
                results.append(r)
        return results

    # ── Chain execution ───────────────────────────────────────────────────────

    async def _execute_chain(self, chain) -> dict:
        """
        Execute a :: chain sequentially.
        Each step's output is available to the next step via $$prev injection.
        """
        prev_output = ""
        final_output = ""

        for step in chain.steps:
            context_text = self._read_context_files(step.context_files)
            prompt = step.instructions or ""

            # $$prev substitution: inject prior step's output into prompt
            if step.uses_prev and prev_output:
                prompt = f"Previous step output:\n{prev_output}\n\n{prompt}"

            output = await self._dispatch_step(step, context_text, prompt)
            prev_output  = output
            final_output = output

        return {"chain_output": final_output, "error": None}

    # ── Context file reading ──────────────────────────────────────────────────

    def _read_context_files(self, files: list[str]) -> str:
        """
        Read all <<context_file.md>> files and return a concatenated block.
        Each file is labelled with its workspace-relative path.
        Unreadable files produce an error note rather than raising.
        """
        if not files:
            return ""

        parts: list[str] = []
        ws_resolved = self.workspace.resolve()

        for f in files:
            # Normalize separators and resolve
            clean = f.replace("\\", "/").strip()
            target = (self.workspace / clean).resolve()

            # Security: refuse paths that escape the workspace
            try:
                target.relative_to(ws_resolved)
            except ValueError:
                parts.append(f"--- {f} ---\n[BLOCKED: path escapes workspace]")
                continue

            try:
                raw = target.read_bytes()
                text = raw[:_CONTEXT_FILE_MAX_BYTES].decode("utf-8", errors="replace")
                suffix = ""
                if len(raw) > _CONTEXT_FILE_MAX_BYTES:
                    suffix = f"\n[...truncated at {_CONTEXT_FILE_MAX_BYTES} bytes]"
                parts.append(f"--- {clean} ---\n{text}{suffix}")
            except FileNotFoundError:
                parts.append(f"--- {clean} ---\n[FILE NOT FOUND]")
            except Exception as e:
                parts.append(f"--- {clean} ---\n[READ ERROR: {e}]")

        return "\n\n".join(parts)

    # ── Step dispatcher ───────────────────────────────────────────────────────

    async def _dispatch_step(self, step, context_text: str, prompt: str) -> str:
        """
        Route a single ModuleCall to the correct handler, enforcing timeout.
        Always posts output to Nova Chat with [task_id] prefix.
        Optionally writes to >>output_target.
        """
        role     = step.role.lower()
        task_id  = (step.criteria.task_id if step.criteria else "") or ""
        timeout  = step.timeout_s or _DEFAULT_TIMEOUT_S

        log.info(
            "[NCL] Dispatching @%s (task_id=%r, timeout=%ds, ctx_files=%d)",
            role, task_id or "none", timeout, len(step.context_files),
        )

        try:
            handler = self._get_handler(role)
            output = await asyncio.wait_for(
                handler(context_text, prompt, task_id, step),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            ts = datetime.utcnow().strftime("%H:%M:%SZ")
            output = (
                f"[{task_id}] ⚠ @{role} timed out after {timeout}s at {ts}. "
                f"Task remains open — retry or check module status."
            )
            log.warning("[NCL] @%s timed out after %ds", role, timeout)
            await self._post(output)
        except Exception as e:
            output = f"[{task_id}] ✗ @{role} error: {type(e).__name__}: {e}"
            log.error("[NCL] @%s dispatch error: %s", role, e, exc_info=True)
            await self._post(output)

        # Write to >>output_target if specified
        if step.output_target and output:
            await self._write_output(step.output_target, output, task_id, role)

        return output

    def _get_handler(self, role: str):
        """Return the coroutine handler for a given module role."""
        _DISPATCH = {
            "eyes":   self._module_eyes,
            "mentor": self._module_mentor,
        }
        return _DISPATCH.get(role, self._module_not_implemented_factory(role))

    # ── Module: @eyes ─────────────────────────────────────────────────────────

    async def _module_eyes(
        self, context_text: str, prompt: str, task_id: str, step
    ) -> str:
        """
        @eyes handler.

        Calls NovaEyes from nova_perception.eyes with the [[instructions]] as
        the vision query and <<context_files>> prepended as framing context.

        NovaEyes tier fallback (defined in nova_perception/eyes.py):
          Tier 1: pywinauto accessibility tree (free, instant, structured)
          Tier 4: Claude Haiku screenshot analysis (API fallback)
          Tiers 2-3 (moondream2, LLaVA 13B) added in Phase 4A.7.

        Gracefully handles ImportError when pywinauto is unavailable
        (e.g. running on a Linux dev machine without a display).
        """
        # Build full query: context framing + instruction
        full_query = prompt
        if context_text:
            full_query = f"CONTEXT:\n{context_text}\n\nINSTRUCTION:\n{prompt}"

        result_text = ""
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.workspace / "tools"))
            from nova_perception.eyes import NovaEyes
            eyes = NovaEyes()

            # Prefer describe() (returns rich text); fall back to verify() (bool)
            if hasattr(eyes, "describe"):
                result_text = str(eyes.describe(full_query))
            else:
                ok = eyes.verify(full_query)
                result_text = "Yes" if ok else "No"

        except ImportError as e:
            result_text = (
                f"@eyes: vision module unavailable in this environment. "
                f"({type(e).__name__}: {e})\n"
                f"Ensure pywinauto is installed and a display is available."
            )
            log.warning("[NCL] @eyes ImportError: %s", e)
        except Exception as e:
            result_text = f"@eyes: error during vision call — {type(e).__name__}: {e}"
            log.error("[NCL] @eyes error: %s", e, exc_info=True)

        response = (
            f"[{task_id}] @eyes result:\n{result_text}"
            if task_id
            else f"@eyes result:\n{result_text}"
        )
        await self._post(response)
        return response

    # ── Module: @mentor ───────────────────────────────────────────────────────

    async def _module_mentor(
        self, context_text: str, prompt: str, task_id: str, step
    ) -> str:
        """
        @mentor handler — routes to Claude + Gemini via Nova Chat.

        Posts a directed @Claude @Gemini message with:
          - task_id echo instruction (so inbox routing picks up the response)
          - context block from <<files>>
          - [[instructions]] as the actual task

        This is fire-and-forget: Claude + Gemini respond naturally in Nova
        Chat.  Inbox routing (Phase 4A.5) picks up their response when they
        echo the [task_id] header as instructed.

        Returns an acknowledgement string immediately.
        """
        parts: list[str] = []

        if task_id:
            parts.append(
                f"⚠ IMPORTANT: Begin your response with [{task_id}] exactly "
                f"(including brackets) so Nova's inbox router can file your answer."
            )

        if context_text:
            parts.append(f"CONTEXT:\n{context_text}")

        if prompt:
            parts.append(f"TASK:\n{prompt}")

        # Build the mentor request message
        separator = "\n\n"
        body = separator.join(parts)
        message = f"@Claude @Gemini {body}"

        await self._post(message, author="Nova")

        ack = (
            f"[{task_id}] @mentor request dispatched → @Claude + @Gemini. "
            f"Awaiting response (will appear in Nova Chat with [{task_id}] prefix)."
            if task_id
            else "@mentor request dispatched → @Claude + @Gemini. Awaiting response."
        )
        log.info("[NCL] @mentor dispatched (task_id=%r)", task_id)
        return ack

    # ── Module: not yet implemented ───────────────────────────────────────────

    def _module_not_implemented_factory(self, role: str):
        """Return a handler coroutine for an unimplemented module."""

        async def _handler(context_text: str, prompt: str, task_id: str, step) -> str:
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

            # Build a notice for Nova Chat
            header = f"[{task_id}] " if task_id else ""
            notice = (
                f"{header}@{role} is registered but not yet implemented. "
                f"(Phase 4A — planned.) Task recorded at {ts}."
            )
            if prompt:
                notice += f"\nRequested: {prompt[:200]}"

            await self._post(notice)

            # Write a stub to Master_Inbox so the Thoughts system sees it
            stub_content = (
                f"# Unimplemented Module: @{role}\n\n"
                f"- **Task ID:** {task_id or '(none)'}\n"
                f"- **Time:** {ts}\n"
                f"- **Status:** Module not yet implemented — recorded for Phase 4A\n\n"
                f"## Requested Prompt\n\n{prompt[:2000]}\n\n"
                f"## Context Files\n\n{context_text[:1000] if context_text else '(none)'}\n"
            )
            await self._write_to_master_inbox(task_id, role, stub_content)
            log.info("[NCL] @%s not implemented — stub written to Master_Inbox", role)
            return notice

        return _handler

    # ── Output routing helpers ────────────────────────────────────────────────

    async def _post(self, content: str, author: str = "Nova") -> bool:
        """
        Post a message to Nova Chat via /api/inject_message.
        Non-blocking: runs the HTTP call in a thread-pool executor so it
        doesn't block the event loop.
        Returns True on success, False on failure (with a warning logged).
        """
        try:
            import urllib.request as _req
            import json as _json

            payload = _json.dumps({"author": author, "content": content}).encode("utf-8")
            req = _req.Request(
                f"{self.nova_chat_url}/api/inject_message",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            loop = asyncio.get_event_loop()

            def _do_post():
                with _req.urlopen(req, timeout=6) as resp:
                    return resp.status

            status = await loop.run_in_executor(None, _do_post)
            log.debug("[NCL] Posted to Nova Chat: %d chars, HTTP %s", len(content), status)
            return True
        except Exception as e:
            log.warning("[NCL] Failed to post to Nova Chat: %s", e)
            return False

    async def _write_output(
        self, target: str, content: str, task_id: str, role: str
    ) -> None:
        """
        Write module output to the specified >>output_target path.

        If target ends with '/' or points to a directory, creates a
        timestamped file inside it named <timestamp>_<role>_<task_id>.md.
        Otherwise writes directly to the named file.
        Workspace path escapes are blocked silently.
        """
        clean_target = target.replace("\\", "/").rstrip("/")
        target_path = (self.workspace / clean_target).resolve()

        # Security: stay inside workspace
        try:
            target_path.relative_to(self.workspace.resolve())
        except ValueError:
            log.warning("[NCL] >>output_target escapes workspace: %s", target)
            return

        try:
            # If target path looks like a directory (original target ends with /)
            # or the path already exists as a directory, create a file inside it
            if target.endswith("/") or target_path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                fname = (
                    f"{ts}_{role}_{task_id}.md"
                    if task_id
                    else f"{ts}_{role}.md"
                )
                target_path = target_path / fname
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)

            target_path.write_text(content, encoding="utf-8")
            log.info("[NCL] Output written: %s (%d chars)", target_path.name, len(content))
        except Exception as e:
            log.warning("[NCL] Failed to write output to %s: %s", target, e)

    async def _write_to_master_inbox(
        self, task_id: str, role: str, content: str
    ) -> None:
        """
        Drop a .md file into Thoughts/Master_Inbox/.
        Used by unimplemented module stubs and timeout/error notices.
        The heartbeat cycle (Phase 4A.5+) processes these on the next tick.
        """
        inbox = self.workspace / "Thoughts" / "Master_Inbox"
        try:
            inbox.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            name = (
                f"{ts}_{role}_{task_id}.md"
                if task_id
                else f"{ts}_{role}_noid.md"
            )
            (inbox / name).write_text(content, encoding="utf-8")
            log.info("[NCL] Master_Inbox item written: %s", name)
        except Exception as e:
            log.warning("[NCL] Failed to write to Master_Inbox: %s", e)


# ── Module-level convenience function ─────────────────────────────────────────

async def dispatch_ncl(content: str, workspace_root: Optional[Path] = None) -> list[dict]:
    """
    Parse and execute an NCL message in one call.
    Returns [] if the content has no NCL calls.

    Convenience wrapper used by nova_chat/server.py.
    """
    from nova_chat.nova_lang import parse_ncl
    ncl = parse_ncl(content)
    if not ncl:
        return []
    injector = NCLInjector(workspace_root=workspace_root)
    return await injector.execute(ncl)
