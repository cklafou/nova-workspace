# Last updated: 2026-07-08 08:43:32
"""
nova_cortex/context_builder.py
================================
Lightweight context/token helpers for the cortex.

History: this module used to assemble Nova's whole system prompt for the old
Discord/gateway path (build_system_prompt + Discord overrides). That path is
retired — her system prompt is now built by the chat tool's
workspace_context.build_nova_context_block() (which loads SELF/core). The only
piece still used elsewhere is the token estimator below, so the dead builders
and their gateway_config dependency were removed.
"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token).
    Good enough for compaction-threshold decisions in session_store."""
    return max(1, len(text) // 4)


if __name__ == "__main__":
    sample = "hello world " * 100
    print(f"{len(sample)} chars -> ~{estimate_tokens(sample)} tokens")
