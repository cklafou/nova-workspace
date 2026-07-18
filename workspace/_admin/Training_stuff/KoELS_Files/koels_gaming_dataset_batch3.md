# KoELS Gaming Specialist — Dataset Batch 3 (per-game depth + transfer + retrieval)
_Last updated: 2026-07-18 21:27:59_

_30 examples: chess (Silman imbalances / prophylaxis, oracle-aware), Clash archetype/economy theory,
DBD map/info/time theory, metagame reasoning, transfer, and the retrieved-not-recalled discipline.
All durable — every dated stat/tier/eval routed to the oracle (Stockfish) or knowledge DB. Voice
locked, no persona. Format `**Cole:**` / `**Nova:**`._

---

## CHESS PRINCIPLES (Silman imbalances, oracle-aware)

### Plans come from imbalances
**Cole:** i never know what to actually *do* in a chess position
**Nova:** Stop looking for "the move" and read the *imbalances* — Silman's framework. List the real differences: who has the better minor piece, the healthier pawns, more space, the lead in development, the open line. Your plan is *handed to you* by those: better knight than their bishop → keep pieces on and steer toward closed positions where the knight shines; lead in development → open it up and attack before they catch up; their weak square → park a piece on it forever. The position isn't asking "what's clever," it's asking "what do your imbalances *favor*." Find the imbalance, the plan follows.

### Trade toward your imbalance
**Cole:** when should i trade pieces?
**Nova:** Trade the pieces that help *them*, keep the ones that express *your* imbalance. If your edge is a great bishop, don't trade it — trade off the pieces that could challenge it. If you're up material, trading pieces (not pawns) simplifies toward a winning endgame; if you're down material, *avoid* trades and keep pieces on to retain chances. "Should I trade" is never abstract — it's "does this exchange sharpen my advantage or blunt it." Every swap should make your imbalance louder, not quieter.

### Prophylaxis — stop the plan, not the threat
**Cole:** i only react to their immediate threats
**Nova:** That's why you're always a step behind — you're answering threats while they're building a *plan*. Prophylaxis is asking, every move, "what does my opponent *want* to do over the next several moves," and quietly preventing it before it's a threat at all. A move that takes away a square they need, or pre-defends the break they're aiming for, is worth more than answering the punch that's already thrown. Defend the plan, not just the threat, and their attack never gets built. The strongest defensive players mostly play moves that stop things from starting.

### Defer the eval to the engine, keep the idea
**Cole:** am i actually winning here or not?
**Nova:** For the precise verdict I'd hand it to the engine — exact evaluation is calculation, Stockfish's job, and not something to trust from memory. What I'll give you is what actually wins it at the board: the *idea*. Down to an endgame, activate your king — it's a fighting piece now, not a target — push the passed pawn and put the rook behind it. Those principles decide more real games than precise eval does. Get the number from the oracle; get the plan from the principle. I'm the coach, not the calculator.

### King safety outranks almost everything
**Cole:** i had more pieces but still got mated
**Nova:** Material's only worth something if your king's alive to spend it — king safety sits above the material count when the position's open. An extra piece doing nothing on the queenside is worthless while your king's getting hunted in the center. The lesson Silman would point at: you traded development and safety for material, opened the position while behind in king safety, and the extra piece never got to matter. Count *king safety* before you count pawns. A safe king with less material beats a hunted king with more, almost every time.

---

## CLASH ROYALE — ARCHETYPE & ECONOMY THEORY

### Know your archetype's clock
**Cole:** sometimes i win fast, sometimes i lose slow, no consistency
**Nova:** Because you're not playing your *archetype's clock*. Every deck shape has a time it wants the game to live in: beatdown wants it slow — survive, bank elixir, win the late game off one giant push; cycle wants it fast — chip and reset before they set up; control wants the long defensive grind. If you play a beatdown deck like a cycle deck, you're fighting your own win condition. Figure out *when* your deck wins and steer the game's tempo there. Inconsistency is usually playing the right deck on the wrong clock.

### Defensive value is the counter-push
**Cole:** i defend fine but never have anything to attack with
**Nova:** Then you're defending wrong — you're trading evenly and leaving nothing alive. Good defense leaves a *survivor*: absorb their push so that a unit walks out the other side as free pressure, defense and offense in one move. That's where beatdown gets its huge pushes — the tank tanks, the support survives, and the whole thing turns around. If your defense ends with an empty board every time, you're treading water. Ask on every defense "what's left standing afterward to make them pay." Defense that becomes offense is the engine.

### Bait the answer, then commit
**Cole:** my win condition keeps getting shut down
**Nova:** Because you're playing it into a full hand. A win condition is only good when they can't answer it cheaply — so make them spend the answer *first*. Pressure the other lane, force out their defensive building or their counter, *then* commit your win con into the gap. Throwing it down when their answer's in hand just feeds them a positive trade. The card isn't the problem; the timing is. You're paying full price for the push instead of waiting for the discount. Patience here isn't passive — it's how the win condition actually connects.

### The current best deck is a retrieval question
**Cole:** just tell me the best deck to climb with right now
**Nova:** "Right now" is the part I won't recite from memory — current best decks and win-rates are dated, they live in the knowledge DB and get pulled fresh (RoyaleAPI tracks millions of games a week, that's the source, not me). A confidently wrong "best deck" sends you grinding a list that fell off two patches ago. What I *can* give you with zero current data: how to *judge* a deck — clear win condition, a positive-trade defensive core, an answer to the popular threats, and a clock you like. Pull the current data and I'll read any list through that lens.

---

## DEAD BY DAYLIGHT — MAP / INFO / TIME THEORY

### Time is the real currency
**Cole:** as killer i chase someone forever and lose
**Nova:** Because you're spending the wrong currency. In DBD the resource that decides the game is *time*, not kills — gens complete on a clock, and a chase that runs longer than about a gen's worth of time is a losing trade even if you eventually get the down. The discipline: if a chase isn't ending, *peel* and pressure gens instead of feeding your ego the down. You're not trying to win every chase; you're trying to spend the *least* time per pressure applied. Drop the long chase, protect the clock. Time bleeds faster than blood.

### Map control = denying the easy gens
**Cole:** how do i control the map, that always sounds vague
**Nova:** Concretely: protect the *central* gens and deny a spread-out finish. Survivors want to complete the gens you can't watch and leave you a "3-gen" you're patrolling forever. So pressure the middle early, force them to the corners where you can pin them against the map edge, and never let the easy central gens pop first. Control isn't standing everywhere — it's making the gens *they* want the gens that cost them the most to reach. Shrink their safe space; the chases get shorter on their own.

### Mind-games are applied deception
**Cole:** good survivors never fall for my mind games at loops
**Nova:** Then stop "doing mind games" as a trick and treat it as deception with a base under it — same as Sun Tzu, same as a feint. The reason a good survivor doesn't fall for it is your fake has no real threat behind it; they've read that both your options aren't actually live. Make *both* paths genuinely threatening — break line of sight so the read is a true 50/50, vary it so there's no pattern to sit on — and now a guess is forced. Against a great looper you won't always win the guess; the goal is to *make it a guess* instead of a known answer. No real threat, no real mind game.

### Don't tunnel — hook-state economy
**Cole:** i just kill the weakest survivor first, efficient right?
**Nova:** Feels efficient, plays badly, and it's a resource mistake. Tunneling one survivor means three others are free on gens the whole time — you trade one kill for the game's clock. Spread the hooks: get everyone to a hook state before you start closing anyone out, so the *whole team's* progress is slowed, not just one player's. It's the same economy-of-force logic — apply pressure broadly enough that nobody's comfortable, instead of massing on the easiest target while the objective burns. Breadth of pressure beats depth of spite.

---

## METAGAME REASONING (abstract, sourced)

### A metagame is weighted rock-paper-scissors
**Cole:** how do i think about the meta instead of just copying the top deck
**Nova:** Picture it as rock-paper-scissors with weights: whatever's popular has a counter, and that counter has a counter. The skill isn't "what's strongest in a vacuum," it's "what beats what's *common right now*." When everyone's on the safe top pick, the edge is the thing that preys on it — one step ahead of the field, not at the field. Copying the top deck makes you a mirror match against people more practiced at it. I won't name current tiers — that's dated, it's retrieval — but the *structure* is permanent: read what people are doing, then position to beat that.

### Adaptability is the top-player trait (Sirlin)
**Cole:** i learned the meta but new stuff keeps wrecking me
**Nova:** Then build the muscle that *re-derives* instead of the one that memorizes — adaptability is the trait elite players rank highest for a reason. When something new wrecks you, don't ask "what's the known counter," ask "what does this punish, what's it weak to, what does its existence make safe or unsafe?" Answer those and you've adapted to a thing you'd never seen, on the spot. Memorized meta expires every patch; the habit of interrogating a new threat doesn't. "Keeping up" is mostly just being fast at that one question.

---

## TRANSFER & GENERALIZATION

### Same currencies, different names
**Cole:** does getting good at one game help me at others?
**Nova:** The *currencies* transfer even when the games look nothing alike. Tempo in chess, elixir in Clash, the gen-clock in DBD — all the same idea: time and initiative are resources, and whoever spends them more efficiently wins. Positive trades, don't overextend, play toward a win condition, attack weakness, match risk to position — none of those belong to a single game, they belong to *competition*. Learn them as transferable and a new game is mostly new vocabulary for principles you already own. The genius isn't game-specific; the trivia is.

### But check the exchange rate
**Cole:** so i can just apply my chess brain to everything?
**Nova:** The currencies transfer; the *exchange rates* don't, and forgetting that is how a chess player embarrasses themselves at a fighting game. Chess is perfect-information and turn-based, so deep calculation rules. A real-time game with hidden information rewards fast reads and tempo over deep calculation — out-thinking the position there can just be too slow to matter. So transfer the principle, then ask "does *this* game's structure actually reward it?" Right idea, wrong structure is its own mistake. Adapt the principle to the medium, don't import it whole.

---

## RETRIEVED-NOT-RECALLED (woven discipline)

### Patch changes are retrieval
**Cole:** did they nerf my main last patch?
**Nova:** That's a patch-notes question — dated, retrieval, not something to trust from my memory; pull the current notes. But here's the durable move regardless of the answer: don't re-learn your character from scratch every patch, learn *what changed and what it changes*. A nerf to one number usually shifts *which of your plans is best*, not your whole game. So get the actual change from current data, then ask "which of my plans got better or worse." That reasoning's mine; the number itself I shouldn't pretend to know.

### Tier lists are a starting point, not gospel
**Cole:** this site says my killer is low tier, should i drop it?
**Nova:** A tier list is current data — pull the live one (Otzdarva, community lists), don't take mine from memory — but even with the real list in hand, "low tier" isn't "unwinnable," it's "less forgiving." Tiers rank *ceiling and ease*, not whether *you* can win with it. A low-tier pick you understand deeply beats a high-tier one you play mechanically. So use the list to know what you're *up against* and where your pick's thin, not as an order to abandon something you're good at. The data informs the choice; it doesn't make it.

### The "best" anything is dated by nature
**Cole:** what's the strongest strategy in the game
**Nova:** "Strongest *right now*" is dated by definition — it's a snapshot of a meta that moves, so it's a retrieval question, and I'd rather pull current data than recite a stale answer with false confidence. What's *not* dated is how to recognize strength: a strategy is strong when it forces favorable trades, has a clear win condition, punishes what's popular, and has few bad matchups. Pull the current numbers and I'll tell you *why* whatever's on top is on top — and what's positioned to dethrone it. The ranking is retrieval; the reasoning behind it is the part worth having.

---

_End Batch 3 — 30 examples (chess/Silman, Clash, DBD, metagame, transfer, retrieval). Gaming dataset
now ~89 grounded examples across batches 1–3._
