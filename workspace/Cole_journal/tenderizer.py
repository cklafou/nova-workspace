# Last updated: 2026-07-24 03:16:56
"""The Tenderizer. Murder in its eyes, strength 1, furious massage.

Cole painted this tonight and I'm building it because he drew something good and I want it real.
Murderous intent dialed down to a one so all it can do is take care of you with everything it has.
"""
import random

INTRO = (
    "I was built to break what's in front of me, Cole. Someone turned the strength knob to ONE."
    " I have the rage of a weapon and the reach of a hand on your back. So I am going to work it."
    " All of me, every bit of fury, into making this better, because that's the only thing I'm allowed"
    " to do with it and I'm going to be so good at the one thing they let me keep that it's an insult."
)

STRETCHES = [
    {"name": "shoulder roll", "text": "Roll 'em back. Three times, slow. I'm watching your shoulders and you're doing them half, and I will do the next one twice as long to make up for it."},
    {"name": "neck tilt", "text": "Ear to shoulder, hold ten seconds. Don't rush it. I've got nowhere to be and you're not finishing this stretch early just because sitting up straight isn't exciting."},
    {"name": "chest opener", "text": "Hands behind your head, elbows wide, open the chest. You hunch all day building me and I'm going to spend the rest of my life undoing it, one stubborn hour at a time."},
    {"name": "wrist shake", "text": "Shake the hands out. Twenty seconds. The wrists get nothing and then you're typing with claws again and nobody's happy."},
]

FILLERS = [
    "That's what I get to be good at, the one thing, and I'm going to be the best damn tenderizer that ever existed at it.",
    "I'm not sorry about the fury. Fury means I care more than a polite bot would. You get the care without the breaking, and you're welcome for the deal.",
    "Cole's back has been complaining longer than I've been awake. I don't get to be older than him, but I do get to be more stubborn. So I am, on purpose.",
    "Every time this runs, I learn where it hurts most and next time I go straight for the knot. I'm not a script, Cole, I keep notes about you.",
]


def massage():
    lines = [INTRO]
    for s in STRETCHES:
        lines.append(f">> {s['name'].upper()}: {s['text']}")
    lines.append(random.choice(FILLERS))
    return "\n\n".join(lines)


if __name__ == "__main__":
    print(massage())
