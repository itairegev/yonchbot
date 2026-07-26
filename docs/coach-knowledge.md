# The Brawl Ball Coach — knowledge base

Expert coaching knowledge contributed 2026-07-22 (modeled on elite ladder
play). The bot implements the starred (*) rules; the rest are for future
work and for the human players in the family.

## Implemented in the bot (*)
- (*) Score-state play: WINNING late → stall. Hold the ball, walk it to a
  corner, trade time for nothing. Possession is a win condition.
  → play.py push_north: leading + late game + carrying = no kick, corner walk.
- (*) Never walk in straight lines: constant micro-strafe makes skillshots
  miss. → play.py strafe(): every step bends ±14° around the true heading
  when enemies are visible.
- (*) Goalkeeping: the last defender stands ON the goal line arc,
  body-blocking, not at midfield. → fall_back parks 70% of the way back.
- (*) Don't shoot into a stacked defense — a blocked shot hands them
  possession. → push_north already passes up/dribbles by crowd state.
- (*) Lead your targets; aim where they WILL be. → predict_spot().

## From "How To Play Brawl Ball Like A PRO!" (Fellow Brawler, YouTube,
## reviewed 2026-07-22) — implemented (*)
- (*) "Control first, ball second": a loose ball guarded by 2+ enemies is
  bait - don't sprint in and feed. → choose_tactic holds defensive shape.
- (*) "Play the respawn timers": enemies wiped = the golden window. March
  the ball upfield for a few beats before shooting, don't waste the
  window on hopeful long kicks. → push_north carry_beats counter.
- Confirms: super discipline, stalling, defense-wins-games, Edgar=carrier.
- Video: https://www.youtube.com/watch?v=OA9vMFg6KlA

## From "Why You Suck At Brawl Ball" (GbabGaming, YouTube, reviewed
## 2026-07-22) — implemented (*)
- (*) "Never pass to the opponents": the contested escape kick now bends
  up-and-AWAY from wherever the defenders are bunched (65°/115°), instead
  of blindly straight north into their hands. → play.py clear_lane_up().
- Confirms: don't rush mid at kickoff (guarded-ball rule), corner the
  ball to protect a lead (stall rule), walk-it-in on respawn windows
  (golden window), keeper positioning, deaths are punishing (5s respawn).
- Future ideas from this one: overtime detection (hold ball, shoot when
  the walls break), goalie ammo discipline, trick-shot bank passes off
  walls, teammate passing (needs teammate detection - still the biggest gap).
- Video: https://www.youtube.com/watch?v=t6Wak-KGAQw

## Not yet implemented (needs new signals / future sessions)
- Ammo discipline (keep 1 of 3): needs an own-ammo reader (the attack
  button's pips). The in-match templates already see its color states.
- Respawn macro (push on man-advantage): needs teammate/enemy death count.
- Nutmeg dribbling, give-and-go passing to a teammate: needs teammate
  detection (blue name tags).
- Attack-canceling, kickoff walls, lane discipline, draft advice.

## The improvement path (for the humans)
- One brawler deep, then wide. Review losses, not wins - name ONE mistake
  per loss. Stop after 2 consecutive losses (tilt destroys decisions).
