"""
nova_gateway — Python replacement for the OpenClaw gateway daemon.

Modules:
  config          — load/validate nova_gateway.json settings
  context_builder — assemble Nova's system prompt from workspace .md files
  session_store   — JSONL v4 session writer, reader, compaction
  tool_executor   — exec / read / message tool dispatch
  agent_loop      — Ollama inference + tool call loop
  discord_client  — discord.py bot (trigger + reply)
  scheduler       — APScheduler cron jobs
  gateway         — FastAPI entry point (port 18790)

Usage:
  python -m nova_gateway.gateway        # start everything
  python -m nova_gateway.gateway --dry  # verify config only, no connections
"""

__version__ = "0.1.0"
