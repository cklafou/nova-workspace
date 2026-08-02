# Last updated: 2026-08-02 11:08:29
"""Tests for voice_preview."""
CASES = [
    {"name": "clean reply passes", "args": {"text": "He's right to correct himself, and that's how I want him to work with me. The rest of his update is about the shadow import and a tidy I don't have a receipt for, so I'll go check where things landed instead of narrating his update as my own conclusion."}, "expect_startswith": "clean"},
    {"name": "Great question flags", "args": {"text": "Great question. The answer is forty-six, from the manifest."}, "expect_contains": "performed enthusiasm"},
    {"name": "Certainly flags", "args": {"text": "Certainly! Let me look that up for you."}, "expect_contains": "performed eagerness"},
    {"name": "genuine agreement does NOT flag", "args": {"text": "You caught it faster than I did, which is why you're better at this. And yeah, the number was wrong and the receipt says so."}, "expect_absent": "flag"},
    {"name": "unearned gratitude flags", "args": {"text": "Thank you for pointing that out, it really helped me understand."}, "expect_contains": "unearned gratitude"},
]
