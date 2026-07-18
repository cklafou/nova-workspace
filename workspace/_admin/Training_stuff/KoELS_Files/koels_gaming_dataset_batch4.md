# KoELS Gaming Specialist — Dataset Batch 4 (chess at master level)
_Last updated: 2026-07-18 21:27:59_

_18 examples grounded in master chess theory: Kotov (candidate moves / analysis tree), Nimzowitsch
(My System — prophylaxis, overprotection, blockade, outpost, pawn-chain base), and Chase-Simon/
de Groot (chunking — how expertise actually works, and how to build it). Oracle-aware: exact eval
is Stockfish's job; the adapter coaches the *reasoning*. Voice locked, no persona._

---

## CALCULATION & THINKING METHOD (Kotov, and its honest correction)

### Candidate moves before calculation (Kotov)
**Cole:** when it's a sharp position i just start calculating and get lost
**Nova:** That's the classic failure Kotov diagnosed — calculating before you've chosen *what* to calculate, so you wander in circles re-analyzing the same lines. His method: first list your **candidate moves** — the two, three, four genuinely interesting tries — *then* calculate each one in an orderly way, one branch to the end, without jumping back to the start. Pick the candidates, then build the tree. Drifting into calculation with no list is how you burn ten minutes and come out with nothing. Choose the questions before you spend time answering them.

### Calculate each branch once (the analysis tree)
**Cole:** i calculate a line, then doubt it, then recalculate it over and over
**Nova:** That's "thinking in circles," and Kotov's whole point is that it wastes the clock and the mind. Discipline: pick a candidate, follow that branch to a conclusion *once*, write the verdict in your head — "this leads to a worse endgame" — and *move on* to the next candidate. Don't re-tread a line you've already judged unless new information forces it. Calculate each branch a single clean time, then compare verdicts at the end. Re-analyzing the same variation isn't thoroughness, it's a loop eating your time.

### Real GMs start from better candidates (chunking corrects Kotov)
**Cole:** so i should calculate like a rigid tree every move?
**Nova:** No — and this is the honest correction to Kotov that the cognitive research forces. De Groot found masters consider *the same number* of candidate moves as amateurs; they're just better because they start from *better* candidates, recognized instantly through pattern, not through exhaustive trees. So the tree is a tool for sharp, unclear spots — most positions, you should be *recognizing* the right plan, not brute-forcing it. Train your pattern library and you'll need the tree less. Calculation is the backup; recognition is the engine.

### Expertise is chunks, built by exposure (Chase-Simon)
**Cole:** how do top players just *see* the right move so fast?
**Nova:** Chase and Simon answered this: experts store thousands of **chunks** — recurring configurations of pieces — in long-term memory, and a familiar chunk instantly suggests its plan. The proof is brutal and clarifying: masters can rebuild a real position from a glance, but on a *random* arrangement their recall collapses to a beginner's. So it's not raw memory or calculation speed — it's *recognition of patterns seen before*. The takeaway for getting better: you build that library through deliberate exposure to real, meaningful positions, not by memorizing moves. Volume of *patterns*, not hours of clicking.

### How to actually build pattern recognition (coaching)
**Cole:** okay so how do i build that pattern library fast
**Nova:** Study positions *in clusters of the same type* so the chunk forms, not random puzzles. Play through master games of *one* structure — say, the isolated-queen-pawn — until you can predict the plan before you see the move; then the next structure. Annotate *why*, in your own words, because the verbalization is what files the chunk. And review your own games for the pattern you *missed*, so the gap gets a label. You're not memorizing moves, you're teaching your perception to recognize a situation on sight. Same structure, many examples, named out loud — that's how the library grows.

---

## POSITIONAL MASTERY (Nimzowitsch, My System)

### Prophylaxis — prevent the plan, not the threat (Nimzowitsch)
**Cole:** i defend each threat as it comes and still get ground down
**Nova:** Because you're answering threats while your opponent executes a *plan*. Nimzowitsch's prophylaxis is anticipatory: every move, ask "what does my opponent *want* to do over the next several moves," and quietly take it away before it's a threat at all. A move that removes the square their knight needs, or pre-covers the pawn break they're aiming for, defuses the attack before it's built. The strongest defenders mostly play moves that stop things from *starting*. Defend the plan; the threats then never arrive.

### Overprotection — excess defense buys freedom (Nimzowitsch)
**Cole:** isn't defending a square with extra pieces just passive?
**Nova:** Counterintuitively, no — Nimzowitsch called it **overprotection** and it's the opposite of passive. Pile *more* defenders on your key strongpoint than it strictly needs, and two things happen: it becomes impregnable, and — the subtle part — every overprotecting piece draws *life* from that strong square, gaining flexibility and good squares of its own. The classic image is a knight on a supported central outpost backed by pawns and pieces; it's a fortress *and* a launchpad. Over-defending your best feature isn't timid; it's investing in a strongpoint that pays the whole position back.

### Blockade — restrain, blockade, destroy (Nimzowitsch)
**Cole:** their passed pawn scares me, what do i do with it
**Nova:** Nimzowitsch's exact sequence: "first restrain, then blockade, finally destroy." Don't panic-trade or race it — first take away its freedom to advance, then plant a piece *directly in front of it* to stop it dead, and only then, at leisure, win it. And the right blockader is usually a **knight**: it sits in front of the pawn losing none of its own power, because a knight attacks around corners. A blockaded passed pawn isn't a danger, it's a target you've frozen. Stop it moving, sit on it, take it when you're ready.

### Attack the base of the pawn chain (Nimzowitsch)
**Cole:** there's a long locked pawn chain, where do i even play
**Nova:** Nimzowitsch's rule: **attack the base of the chain.** A pawn chain is only as strong as its rearmost pawn — the head is defended by the ones behind it, but the base is defended by nothing in the chain. Break the base and the whole structure crumbles from the back. So in locked positions, identify which end is the foundation and aim your pawn break and your pieces *there*, not at the well-defended front. Don't bang on the strong end of a wall; pull the bottom brick.

### The outpost — a permanent home in their half (Nimzowitsch)
**Cole:** what makes a knight "good" vs "bad"?
**Nova:** A great knight usually means an **outpost** — a square in or near the enemy camp that their pawns can *no longer* attack (the pawns that would've challenged it are gone or advanced past). Park a knight there, support it with a pawn, and it's a permanent thorn: it can't be kicked, it eyes weak squares, and it cramps everything. A "bad" knight is one with no such home, stuck defending. So the positional question isn't "is my knight active *now*," it's "can I build it a permanent outpost." Find the hole in their structure and move in for good.

---

## EVALUATION & WHOLE-POSITION JUDGMENT

### King safety as a first-order question
**Cole:** i was up material and still got mated, what did i miss
**Nova:** Material only counts if your king lives to spend it — king safety sits *above* the material count in an open position. An extra piece idle on the queenside is worthless while your king's hunted in the center. The likely story: you grabbed material and paid for it in time and safety, opened the position while your king was the less safe one, and the extra piece never mattered. Evaluate king safety *before* you count pawns. A safe king down material beats a hunted king up material almost every time.

### Defer the exact number, keep the plan (oracle-aware)
**Cole:** is this position actually winning?
**Nova:** For the precise verdict I'd hand it to the engine — exact evaluation is calculation, Stockfish's domain, and not something to recite from memory with false confidence. What I'll give you is what actually *wins it at the board*: the plan the position's imbalances call for. If you've got the bishop pair in an open position, pry it open further and let them work; if you're up a clean pawn in an endgame, trade pieces not pawns and activate your king. Get the number from the oracle; get the plan from the principles. I coach the *why*; the engine owns the *how-much*.

### Two weaknesses (the principle behind conversion)
**Cole:** i'm clearly better but can't convert the win
**Nova:** Because one weakness usually isn't enough — a defender can hold a single target. The master principle is the **principle of two weaknesses**: create a *second* problem on the other side of the board so the defense is stretched between two points it can't both cover. You probe one weakness to fix their pieces there, then open a second front; the defender breaks because they can't be in two places. Conversion is rarely a single knockout — it's making them defend two things with one set of pieces. Don't hammer the one weakness harder; manufacture a second.

### Trade toward your imbalance, not away from it
**Cole:** general rule for trading when i'm not sure?
**Nova:** Trade the pieces that serve *them*, keep the ones expressing *your* edge. Up material → trade pieces (not pawns) toward a winning endgame. A dominant knight on an outpost → don't trade it; trade the bishop that could challenge it. Cramped → trade pieces to get breathing room. Attacking → keep attackers on the board. Every exchange should make your advantage *louder*. "Should I trade" is never abstract; it's "does this swap sharpen or blunt the thing I'm winning with."

---

## COACHING THE LEARNER (chunking-informed)

### Study the level just above you (zone of proximal development)
**Cole:** should i study super-GM games to improve fastest?
**Nova:** Usually not yet — and the chunking research explains why. Top-GM games solve problems you don't have the patterns to even *see*, so most of it doesn't file as a usable chunk; it washes over you. Study games a level or two above you, where the mistakes being punished are mistakes *you* still make — those positions are close enough to your pattern library that the new chunk *sticks*. Reach a little, not a lot. The right material is hard enough to stretch your recognition and close enough to grasp it.

### Annotate in your own words (filing the chunk)
**Cole:** i watch lessons but it doesn't stick
**Nova:** Passive watching doesn't build chunks — *verbalizing* does. After a position clicks, close it and write, in your own words, *why* the plan worked: "knight to the outpost because their pawns can't challenge it, then double rooks on the open file." The act of putting it in language is what files the pattern into long-term memory where you'll recognize it next time. A lesson you watched is information; a lesson you re-explained is a chunk. Teach it back to yourself — that's the step that makes it yours.

---

_End Batch 4 — 18 master-level chess examples (Kotov, Nimzowitsch, Chase-Simon chunking), oracle-aware.
Next: Batch 5 — universal military/decision expertise (Clausewitz, Lanchester, Boyd maneuver, Kelly)._
