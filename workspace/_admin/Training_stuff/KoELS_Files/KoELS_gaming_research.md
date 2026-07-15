# KoELS Gaming Specialist — Research & Strategic Canon
_Last updated: 2026-07-15 23:14:48_

**The vision (Cole):** the gaming loadout makes Nova the hypothetical top competitor *in every
category* — a first-principles strategist who thinks like a military commander, goes outside
conventional gaming wisdom, and *teaches/coaches* it brilliantly — while the current metas, tier
lists, and stats are pulled live off the internet rather than memorized.

**The KoELS split this research is organized around:**
- **Part A → the LoRA (weights).** Durable, timeless strategic *reasoning* and *coaching method*.
  This is what we train. It never goes stale.
- **Part B → the knowledge DB (retrieval).** The volatile metas/stats/tier-lists, pulled by the
  updater from the sources mapped below. **Never trained into weights** — baking a dated tier list
  in is the confident-hallucination failure KoELS exists to prevent.

---

## PART A — THE DURABLE CANON (trains the adapter)

### A1. Universal strategic frameworks (the "military strategist" core)

- **OODA loop (John Boyd).** Observe → Orient → Decide → Act, continuously. The edge isn't just
  *speed* through your own loop — it's getting **inside the opponent's loop**: act in ways that are
  surprising, ambiguous, and varied so *their* observe/orient stage feeds on confusion. Tempo as a
  weapon; deliberate irregularity (speeding up/slowing down) to break their rhythm. *(Boyd; iterum,
  artofmanliness, oodaloop.)*
- **Sun Tzu / Art of War.** Know yourself **and** the enemy; "all warfare is based on deception —
  appear weak when strong, strong when weak"; **attack weakness, not strength**; win without
  fighting where possible; the **indirect approach** — enter the side door, not the defended gate;
  position where you hold the advantage. *(grahammann, byu, asymmetric.pro, jamesclear.)*
- **Principles of war (MOOSEMUSS).** Mass, Objective, Offensive, Surprise, **Economy of Force**,
  Maneuver, Unity of Command, Security, Simplicity. Economy of force + mass = the durable lesson:
  commit the minimum where it's "good enough," concentrate the surplus at the decisive point.
  *(Modern War Institute; idga.)*
- **Sirlin, *Playing to Win* (the competitive-gaming bible).** The **"scrub"**: a player handicapped
  by *self-imposed rules the game doesn't know about* — losing to their own notion of how one
  "should" play. First-principles antidote: reason from *what actually wins*, not from convention or
  aesthetics. Unconventional play to disrupt the opponent; **adaptability** as the trait elite
  players rank highest. *(sirlin.net/ptw.)*  ← this is the literal heart of Cole's "outside the box."
- **Game theory.** **Minimax** — pick the line that minimizes your worst case; assume a competent
  opponent. **Expected value** over outcome — grade decisions on the odds you had, not the result.
  **Mixed strategies** — against a thinking opponent, *be unpredictable on purpose*; a pure pattern
  is exploitable. Equilibrium thinking: what's my best response to their best response.
  *(minimax/Wikipedia; game-theory refs.)*

### A2. The transferable currencies (carry across every game)

These are the durable concepts the dataset already drafts — now sourced and reinforced:
- **Tempo / initiative** — who acts and who reacts (OODA, chess initiative).
- **Resource economy & positive trades** — spend less than they do to handle what they commit
  (Clash elixir; chess material; economy of force).
- **Win conditions** — name how you actually win *and* how they do; bend moves toward yours, make
  theirs expensive.
- **Risk matched to position** — ahead, reduce variance; behind, *increase* it (minimax + variance).
- **Information & deception** — control what they can know; feed false signals (Boyd, Sun Tzu, DBD
  mind-games).
- **Position / control** — own the space that makes their good options scarce.

### A3. Per-game timeless principles (the depth, not the meta)

- **Chess — Silman's 7 imbalances:** material, bishop-vs-knight, pawn structure, development,
  initiative, space, open lines/weak squares. *Plans are derived from imbalances* (lead in
  development → attack; superior minor piece → trade off its challengers). **Prophylaxis** —
  prevent the opponent's plan, not just their immediate threat. Opening *principles* over memorized
  lines. NOTE: exact position eval is the **Stockfish oracle's** job; the adapter's chess value is
  *coaching and explaining*, not calculating. *(Silman, How to Reassess Your Chess; chess.com.)*
- **Clash Royale — durable economy/archetype theory:** positive elixir trades as the engine;
  **archetypes** (beatdown = tank + counter-push off defensive value; control/cycle = cheap defense,
  chip with a win-con; siege; bridge-spam) as *shapes of a plan*, not specific cards; cycle/timing
  (bait the answer, then commit); defense that leaves a survivor = free offense. Card *stats and the
  current best decks* are **retrieval** (RoyaleAPI). *(ldshop, clashdecks, sportskeeda.)*
- **Dead by Daylight — map/info/time theory:** **map control** (protect central gens, deny the
  3-gen); **mind-games** (break line of sight, bait the pallet drop, the moonwalk) = applied
  deception; **time as the real currency** (a chase over ~a gen's worth of time should be dropped to
  pressure gens); **don't tunnel** — spread pressure, hook-state economy. Killer/perk *tier lists*
  are **retrieval** (Otzdarva, TierMaker). *(eip.gg, dbdguides, steam community.)*

### A4. Coaching & teaching method (so she *trains others*, not just knows)

- **Deliberate practice (Anders Ericsson).** Improvement comes from *individualized, targeted*
  practice at the edge of ability (zone of proximal development), with **immediate feedback**,
  problem-solving, and repetition — **quality over hours**. A coach's job is sequencing the right
  next challenge and giving precise feedback. *(Ericsson 2008; sentio.org.)*
- **VOD review method (esports coaching).** Re-watch the game to find the *decision* mistakes (not
  just mechanics), surface the moment, offer the *alternative* line, and connect it to the feeling
  in the moment. Diagnose the **root cause**, not the ten symptoms — fix the one habit that caused
  the rest. *(insights.gg, nextlevelesports, esportstower.)*
- **Coaching voice rule for the dataset:** teach the *transferable principle under the move*, name
  the *category* of mistake, and coach root-not-leaves. (Already the spec's calibration bar — now
  evidence-backed.)

---

## PART B — THE LIVE-META LAYER (knowledge DB / updater — NOT weights)

The adapter must *defer* every dated specific to retrieval. Source map for the updater to pull from
(this is research about **where the facts live**, not the facts themselves):

| Game | Live data the DB holds | Primary sources |
|---|---|---|
| Chess | exact position eval, best line, current opening theory | **Stockfish** (oracle, ground truth), Lichess Opening Explorer + `database.lichess.org`, 365Chess |
| Clash Royale | current best decks, card stats, win-rates, meta archetypes | **RoyaleAPI** (`royaleapi.com/decks`, millions of games/week), content creators (SirTagCR) |
| Dead by Daylight | killer/perk/survivor tier lists, current strong builds | **Otzdarva** tier lists, TierMaker (per-patch community), PCGamesN/EarlyGuides |

**Discipline the adapter is trained to show:** "the *current* best deck / tier / eval is a retrieval
question — I'd pull it fresh; here's the durable *method* to read it once you have it." Every band in
the dataset over-represents this reflex.

---

## PART C — HOW THIS FEEDS THE DATASET

Each dataset band now maps to a sourced canon, so examples are grounded, not invented:
- *Positional/matchup eval, win-condition, metagame* → Silman imbalances, Sun Tzu position, OODA orient.
- *Resource/tempo, risk/decision* → economy of force, minimax/EV, Clash economy.
- *Coaching/explanation, mistake diagnosis* → deliberate practice + VOD-review method.
- *Chess/Clash/DBD bands* → A3 per-game principles (oracle/DB deferral baked in).
- *Transfer & "outside the box"* → Sirlin's scrub/first-principles + OODA "get inside their loop."
- *Retrieved-not-recalled* → Part B, woven through every band.

When I expand gaming to the ~280-example target, this canon is the well I draw from — so the LoRA
trains a genuine strategist's *reasoning*, attributable to real doctrine, with zero dated facts in
the weights.

---

## Sources
- OODA / Boyd: [iterum](https://iterum.co.uk/ooda-loops/), [Art of Manliness](https://www.artofmanliness.com/character/behavior/ooda-loop/), [OODAloop](https://oodaloop.com/the-ooda-loop-explained-the-real-story-about-the-ultimate-model-for-decision-making-in-competitive-environments/)
- Military strategy & games: [Modern War Institute](https://mwi.westpoint.edu/the-games-we-play-understanding-strategic-culture-through-games/), [IDGA](https://www.idga.org/command-and-control/articles/5-times-us-military-used-video-games-for-training-and-readiness)
- Sun Tzu: [grahammann](https://grahammann.net/book-notes/the-art-of-war-sun-tzu), [James Clear](https://jamesclear.com/book-summaries/the-art-of-war), [asymmetric.pro](https://asymmetric.pro/10-essential-the-art-of-war-lessons-you-need-to-know/)
- Game theory / minimax: [Wikipedia – Minimax](https://en.wikipedia.org/wiki/Minimax), [GeeksforGeeks](https://www.geeksforgeeks.org/dsa/minimax-algorithm-in-game-theory-set-1-introduction/)
- Deliberate practice: [Ericsson 2008 (Wiley)](https://onlinelibrary.wiley.com/doi/10.1111/j.1553-2712.2008.00227.x), [Sentio](https://sentio.org/what-is-deliberate-practice)
- Sirlin Playing to Win: [sirlin.net/ptw](https://www.sirlin.net/ptw), [Playing to Win overview](https://www.sirlin.net/articles/playing-to-win)
- Chess (Silman): [How to Reassess Your Chess](https://medium.com/@jarrodhill257/how-to-reassess-your-chess-by-jeremy-silman-c9da757214c6), [Chess.com strategy](https://www.chess.com/article/view/study-plan-for-intermediate-players-strategy2)
- Clash Royale: [LDShop guide](https://www.ldshop.gg/blog/clash-royale-gp/clash-royale-beginner-guide.html), [ClashDecks elixir](https://clashdecks.com/guides/elixir-management-101), [Sportskeeda positive trades](https://www.sportskeeda.com/esports/how-maintain-positive-elixir-trades-clash-royale), [RoyaleAPI](https://royaleapi.com/decks)
- DBD: [EIP.gg killer strategy](https://eip.gg/dbd/guides/basic-killer-strategy/), [DBD Guides](https://dbdguides.com/killers/the-spirit/), [Otzdarva tier lists](https://otzdarva.com/dbd/tierlists)
- Esports coaching / VOD: [Insights.gg](https://insights.gg/blog/what-are-vod-reviews-and-why-you-should-do-them), [Next Level Esports](https://www.nextlevelesports.com/blog/how-to-run-an-effective-vod-review)
- Chess data: [Lichess Opening Explorer](https://lichess.org/opening), [database.lichess.org](https://database.lichess.org/)
