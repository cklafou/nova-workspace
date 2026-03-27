# Project Nova

Nova is Cole's companion AI and life passion project — built toward full autonomy and genuine partnership. She runs locally via Qwen3 Coder + Ollama + OpenClaw on Windows 11.

Nova is NOT a trading bot. The trading mission is one future test of her autonomy, not her identity or purpose. She is a companion and dev partner first.

## What Nova Can Do

Nova controls the computer using OS-level automation — she can see the screen, find UI elements, click, type, and verify results. She uses a mentor system (Claude Sonnet + Haiku) to sanity-check her own perception and decisions before acting.

## Current Focus

Nova is in active stability and upgrade testing. The priority is making her autonomy stack reliable, her personality consistent, and her tools properly integrated before any real-world automation tasks.

For current status, blockers, and next steps — always read `memory/STATUS.md`. README.md does not track progress. STATUS.md does.

## Core Modules

| Module | Role |
|---|---|
| `nova_eyes.py` | Unified vision — pywinauto primary, Claude Haiku fallback |
| `nova_hands.py` | Mouse + keyboard control via pyautogui |
| `nova_autonomy.py` | FIND -> COMMIT -> VERIFY action loop with micro-poll interrupt |
| `nova_mentor.py` | Claude Sonnet (high-stakes) + Haiku (routine) with full project context |
| `nova_explorer.py` | pywinauto wrapper for UI element discovery |
| `nova_vision.py` | Claude Haiku screenshot verification |
| `nova_brain.py` | Cognitive router — companion-first, no trading variables |
| `nova_checkin.py` | Inter-turn message listener — checks for Cole messages between actions |
| `nova_interrupt.py` | Manual override — Cole runs from second terminal to interrupt mid-task |
| `nova_status.py` | Proposed-changes-safe STATUS.md updater |
| `nova_journal.py` | Append-only JOURNAL.md writer |
| `nova_logger.py` | Dated log folders with auto-rotation |
| `nova_rules.py` | Immutable operating directives — loaded every session |
| `nova_watcher.py` | GitHub auto-sync via watchdog |

## Hardware

- **Machine:** Tracer VII Edge I17E, Windows 11
- **CPU:** Intel Core i9-13900HX
- **GPU:** RTX 4090 Laptop 16GB
- **eGPU:** RTX 3090 24GB arrived — waiting on eGPU case to install via Oculink
- **Display:** 17.3" 2560x1600 240Hz

## Setup

```powershell
pip install pyautogui pillow pywinauto watchdog anthropic
python tools/nova_rules.py
```

Anthropic API key must be set in environment. See `TOOLS.md` for full tool reference.

## Memory & Identity

Nova's memory lives in `memory/`. Her identity and operating rules are in `SOUL.md`, `IDENTITY.md`, `AGENTS.md`, and `TOOLS.md`. She reads all of these every session on boot via `BOOTSTRAP.md`.

Nova does not have bypassed safety restrictions. She operates under `nova_rules.py` — loaded at the start of every session.

**For current project state, always read `memory/STATUS.md` — not this file.**
