"""
Determines who should respond to each message based on @ mentions.
"""
import re

PARTICIPANTS = ["Claude", "Gemini", "Nova"]

def parse_directed(content: str) -> list:
    """
    Returns list of AI names that were @mentioned.
    Empty list means all should respond.
    """
    mentioned = []
    for name in PARTICIPANTS:
        if re.search(rf"@{name}\b", content, re.IGNORECASE):
            mentioned.append(name)
    return mentioned

def should_respond(ai_name: str, directed_at: list) -> bool:
    """Returns True if this AI should respond to this message."""
    if not directed_at:
        return True  # All respond by default
    return ai_name in directed_at
