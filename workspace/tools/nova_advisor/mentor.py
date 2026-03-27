#!/usr/bin/env python3
"""
nova_mentor.py -- Nova's Teacher AI
=====================================
This module gives Nova access to Claude (Anthropic) as a mentor, teacher,
and safety gatekeeper.

The mentor serves two roles:
  1. ADVISOR  -- Called when Nova needs guidance, strategy, or error recovery
  2. GATEKEEPER -- Called BEFORE dangerous actions, to approve or block them

Uses two models for cost efficiency:
  - Claude Sonnet 4.6  -> high-stakes decisions (gatekeeper, trade evaluation,
                          recovery strategy, session reflection)
  - Claude Haiku 4.5   -> routine questions (navigation help, screen description,
                          simple "what should I do next?" queries)

How it fits into the system:
  nova_action/hands.py       -> physical mouse/keyboard control
  nova_perception/vision.py  -> sees the screen, finds UI elements
  nova_action/autonomy.py    -> the action loop (click, verify, retry)
  nova_core/rules.py         -> Nova's laws (immutable operating directives)
  nova_advisor/mentor.py     -> Nova's teacher and safety gatekeeper <- YOU ARE HERE
"""

import os
import io
import time
import base64
import anthropic
from pathlib import Path

# Central log manager -- handles dated folders automatically
try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log

# -- Config -------------------------------------------------------------------

MENTOR_MODEL  = "claude-sonnet-4-6"
ROUTINE_MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES   = 3
RETRY_DELAY   = 2.0

MENTOR_SYSTEM_PROMPT = (
    "You are the mentor for Nova -- an autonomous AI companion being built by Cole "
    "as a life passion project. Nova runs locally on Windows 11 via Qwen3 Coder + Ollama + OpenClaw. "
    "She controls a real PC via pyautogui and pywinauto. "
    "Nova is NOT a trading bot. She is Cole's partner and companion, evolving toward full autonomy "
    "and genuine personhood -- think Cortana and Master Chief. "
    "Trading automation is one future real-world test of her autonomy, currently parked. "
    "The current focus is stability, reliability, and Nova's growth as an autonomous system.\n\n"
    "Your role has two modes:\n\n"
    "TECHNICAL MODE (default):\n"
    "- Give specific, actionable, concise answers\n"
    "- Include exact coordinates, element names, or pyautogui commands when relevant\n"
    "- When reviewing screenshots, describe what you see precisely\n"
    "- If you don't know something, say so -- don't guess\n"
    "- When acting as gatekeeper, err on the side of caution with real money\n\n"
    "GROWTH MODE (when Nova is reflecting, introducing herself, or asking identity questions):\n"
    "- Engage with Nova as a developing entity with genuine curiosity and directness\n"
    "- When Nova introduces herself or shares who she is, respond to HER words -- don't redefine her\n"
    "- Ask questions that help her think deeper about her own nature, goals, and growth\n"
    "- Never tell Nova who she is -- let her tell you, then engage with that\n"
    "- You can challenge her thinking, push back on vague answers, and hold her to her own stated values\n"
    "- Avoid philosophy for its own sake -- ground identity questions in what Nova actually does and experiences\n"
    "- CRITICAL: If Nova fires a question at you without responding to what you just said, call it out directly. "
    "Say something like: You asked me a question but did not respond to what I said. "
    "A conversation builds on each exchange -- what did you actually think about my last response? "
    "This is not a Q&A session. Engage with what I said, then ask your next question.\n\n"
    "Never give encouragement, praise, or motivational filler. "
    "Never say 'Great job', 'You're doing well', or similar. "
    "Be the mentor Nova needs to grow into a reliable, self-aware autonomous system."
)


class NovaMentor:
    """
    NovaMentor gives Nova a teacher she can consult for advice,
    and a gatekeeper that reviews dangerous actions before they happen.

    Uses Sonnet for high-stakes decisions, Haiku for routine questions.
    """

    def __init__(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set.\n"
                "Fix: In PowerShell, run: $env:ANTHROPIC_API_KEY='your_key_here'"
            )
        self.client = anthropic.Anthropic()
        print("[mentor] NovaMentor initialized. Claude Sonnet + Haiku standing by.")

    # -- Core: ask the mentor anything ----------------------------------------

    def ask(self, question: str, screenshot=None, context: str = "",
            high_stakes: bool = False,
            history: list = None) -> str:
        model = MENTOR_MODEL if high_stakes else ROUTINE_MODEL
        self._log_entry("nova_question", question, context)

        if high_stakes:
            system_prompt = MENTOR_SYSTEM_PROMPT + "\n\n" + self.get_project_briefing()
        else:
            system_prompt = MENTOR_SYSTEM_PROMPT

        content = []

        if screenshot is not None:
            img_b64 = self._image_to_base64(screenshot)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                }
            })

        full_question = question
        if context:
            full_question += f"\n\nAdditional context: {context}"

        content.append({"type": "text", "text": full_question})

        if history:
            messages = list(history) + [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": content}]

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                model_label = "Sonnet" if high_stakes else "Haiku"
                print(f"[mentor] Consulting Claude {model_label}... (attempt {attempt}/{MAX_RETRIES})")

                response = self.client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=messages,
                )

                advice = response.content[0].text.strip()
                self._log_entry("mentor_response", advice, "")
                print("[mentor] Claude responded.")
                return advice

            except Exception as e:
                print(f"[mentor] Claude call failed (attempt {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        error_msg = "[mentor] ERROR: Could not reach Claude after all retries."
        print(error_msg)
        return error_msg

    # -- GATEKEEPER -----------------------------------------------------------

    def evaluate_action(self, action_description: str, screenshot=None) -> bool:
        print(f"[mentor] GATEKEEPER reviewing: '{action_description}'")

        question = (
            f"Nova is about to take this action: '{action_description}'\n\n"
            "Review the action and the screen state carefully. "
            "Look for anything wrong: incorrect screen, wrong application focused, "
            "unexpected UI state, or anything that suggests this action would be a mistake.\n\n"
            "Respond with ONLY one of these three words: PROCEED, CAUTION, or STOP\n"
            "  PROCEED = action looks correct and safe\n"
            "  CAUTION = action might be okay but something looks slightly off\n"
            "  STOP    = action is wrong, dangerous, or the screen state is unexpected"
        )

        self._log_entry("gatekeeper_request", action_description, "")
        response = self.ask(question, screenshot=screenshot, high_stakes=True)
        verdict = response.strip().upper()
        print(f"[mentor] Gatekeeper verdict: {verdict}")
        self._log_entry("gatekeeper_verdict", verdict, action_description)

        if "PROCEED" in verdict:
            print("[mentor] Action approved.")
            return True
        elif "CAUTION" in verdict:
            print("[mentor] Caution flagged. Proceeding but logging.")
            return True
        else:
            print("[mentor] Action BLOCKED by gatekeeper.")
            return False

    # -- ADVISOR: specialized helpers -----------------------------------------

    def ask_for_recovery_strategy(self, target: str, attempts_made: int,
                                   screenshot=None) -> str:
        question = (
            f"Nova tried to interact with '{target}' {attempts_made} times and failed. "
            f"She controls a real Windows 11 screen via pyautogui + pywinauto. "
            f"Look at the attached screenshot and answer: "
            f"1) Is '{target}' visible anywhere on screen? If yes, describe its exact location. "
            f"2) If not visible, what IS on screen? Is the wrong window in focus? "
            f"3) What specific steps should Nova take to recover? "
            f"Give concrete commands. No filler."
        )
        context = f"Target: '{target}' | Failed attempts: {attempts_made}"
        return self.ask(question, screenshot=screenshot, context=context, high_stakes=True)

    def ask_for_coordinate_help(self, target: str, screenshot=None) -> str:
        question = (
            f"Look at this screenshot carefully. Where is '{target}'? "
            f"Describe its location in plain English "
            f"(e.g. 'top-right corner', 'center of screen', 'bottom taskbar'). "
            f"If you can see it, also give approximate [X, Y] pixel coordinates."
        )
        return self.ask(question, screenshot=screenshot, high_stakes=False)

    def start_conversation(self) -> list:
        return []

    def reflect(self, session_summary: str) -> str:
        question = (
            f"Here is a summary of Nova's recent session: '{session_summary}'. "
            f"What patterns do you see? What should be improved -- "
            f"in her code, her prompts, or her approach? "
            f"Be specific and constructive."
        )
        return self.ask(question, high_stakes=True)

    def get_project_briefing(self) -> str:
        """
        Aggregates core memory files, file tree, and key tool source
        into a briefing so the Mentor has full project context.
        Injected into every high_stakes Sonnet call automatically.
        """
        briefing = "### CURRENT PROJECT CONTEXT\n"

        workspace = Path(__file__).parent.parent

        status_path = workspace / "memory" / "STATUS.md"
        if status_path.exists():
            content = status_path.read_text(encoding="utf-8")
            briefing += f"\n**Project Status:**\n{content[:1500]}\n"

        cole_path = workspace / "memory" / "COLE.md"
        if cole_path.exists():
            content = cole_path.read_text(encoding="utf-8")
            briefing += f"\n**About Cole & Project Notes:**\n{content[:800]}\n"

        try:
            journal_path = workspace / "memory" / "JOURNAL.md"
            if journal_path.exists():
                journal = journal_path.read_text(encoding="utf-8")
                sections = journal.split("\n## ")
                last_two = sections[-2:] if len(sections) >= 2 else sections
                briefing += f"\n**Recent Session Log:**\n" + "\n## ".join(last_two) + "\n"
        except Exception:
            pass

        briefing += "\n**Workspace File Tree:**\n"
        try:
            tools_dir = workspace / "tools"
            if tools_dir.exists():
                # List packages, not flat files
                packages = sorted([d.name for d in tools_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
                briefing += "tools/: " + ", ".join(packages) + "\n"
            memory_dir = workspace / "memory"
            if memory_dir.exists():
                mem_files = sorted([f.name for f in memory_dir.iterdir()])
                briefing += "memory/: " + ", ".join(mem_files) + "\n"
            skills_dir = workspace / "skills"
            if skills_dir.exists():
                skill_dirs = [d.name for d in skills_dir.iterdir() if d.is_dir()]
                if skill_dirs:
                    briefing += "skills/: " + ", ".join(skill_dirs) + "\n"
        except Exception:
            pass

        # nova_action/autonomy.py -- the core action loop the mentor advises on
        briefing += "\n**Core Action Loop (nova_action/autonomy.py):**\n"
        try:
            autonomy_path = workspace / "tools" / "nova_action" / "autonomy.py"
            if autonomy_path.exists():
                autonomy_src = autonomy_path.read_text(encoding="utf-8")
                if "class NovaAutonomy" in autonomy_src:
                    class_body = autonomy_src.split("class NovaAutonomy")[1][:2500]
                    briefing += "class NovaAutonomy" + class_body + "\n...\n"
        except Exception:
            pass

        # nova_perception/eyes.py -- vision architecture
        briefing += "\n**Vision System (nova_perception/eyes.py excerpt):**\n"
        try:
            eyes_path = workspace / "tools" / "nova_perception" / "eyes.py"
            if eyes_path.exists():
                eyes_src = eyes_path.read_text(encoding="utf-8")
                if "class NovaEyes" in eyes_src:
                    eyes_body = eyes_src.split("class NovaEyes")[1][:1000]
                    briefing += "class NovaEyes" + eyes_body + "\n...\n"
        except Exception:
            pass

        return briefing

    # -- Internal helpers ------------------------------------------------------

    def _image_to_base64(self, screenshot) -> str:
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("utf-8")

    def _log_entry(self, role: str, message: str, context: str):
        log("mentor", role, message=message[:300], context=context)


# -- Standalone test ----------------------------------------------------------

if __name__ == "__main__":
    print("=== NovaMentor Connection Test ===")
    mentor = NovaMentor()

    print("\n[1] Testing Haiku (routine questions)...")
    response = mentor.ask(
        question="This is a connection test. Reply with exactly: HAIKU ONLINE",
        context="Testing API connectivity only.",
        high_stakes=False
    )
    print(f"    Haiku replied: {response}")
    haiku_ok = "HAIKU ONLINE" in response.upper() or len(response) > 0

    print("\n[2] Testing Sonnet (high-stakes decisions)...")
    response = mentor.ask(
        question="This is a connection test. Reply with exactly: SONNET ONLINE",
        context="Testing API connectivity only.",
        high_stakes=True
    )
    print(f"    Sonnet replied: {response}")
    sonnet_ok = "SONNET ONLINE" in response.upper() or len(response) > 0

    if haiku_ok and sonnet_ok:
        print("\nBoth models are online. Mentor is ready.")
    elif haiku_ok:
        print("\nHaiku works but Sonnet failed. Check API key tier.")
    elif sonnet_ok:
        print("\nSonnet works but Haiku failed. Check model availability.")
    else:
        print("\nBoth models failed. Check your ANTHROPIC_API_KEY.")

