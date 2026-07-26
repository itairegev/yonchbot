# Brawl Ball — mechanics & strategy research (2026-07-25)

Compiled from web research (Fandom wiki, NamuWiki, pro guides) to inform the
bot's decision logic. See also [[coach-knowledge]] and
[[vision-detection-findings]].

## THE KEY INSIGHT for bot logic: "Do I hold the ball?"

The whole state machine hinges on one question each tick:

- **Holding the ball →** the attack button becomes a **KICK**. You **cannot
  damage enemies**. Options: dribble toward goal, shoot at goal (ONLY if the
  lane is clear / goalie is dead), or pass to a better-positioned teammate.
  You can still be attacked; you **drop the ball** if knocked back, stunned,
  or killed.
- **Not holding the ball →** the attack button **damages enemies**. Options:
  go contest/pick up the ball, or shoot the nearest threat (a defender, a low
  enemy, or an enemy about to grab the ball).

So "shoot the goal" and "shoot an enemy" are the **same button** — which one
happens is decided entirely by ball possession.

## Rules
- 3v3 (5v5 variant exists). Ball spawns center at start.
- **First to 2 goals wins.** Timer 2:30 (150s). Tie → 60s overtime with all
  walls/bushes destroyed. Still tied → draw.
- After a goal: ball resets to center, players reset to start.
- **Respawn ~7s** (older sources say 5s). This is THE exploit window: kill the
  defender, then push and score in their absence.

## Controls (touchscreen)
- Left = movement joystick. Right = attack joystick: drag to aim, release to
  fire; **tap = quick-fire/auto-aim at nearest target.**
- Kick is aimed like an attack (straight line in aimed direction). Auto-aim
  tap works for kicks too.
- Ball is picked up by **walking into it** while no one else holds it.
- Super shot = kick with Super: much faster/farther. Great for scoring across
  distance before enemies respawn.

## SHOOTING PRIORITY — who/what to shoot (encode this order)
1. **Clear the defender guarding the goal first** (Super/CC ideal). Attacking
   into a defended goal loses possession.
2. Secure/maintain possession via positioning.
3. **Score only when the lane to goal is clear** OR the goalie is dead
   (respawn window).
4. **Pass instead of shooting if a defender is near the goal.**

Concrete rules:
- Shoot at goal when: path clear of defenders OR enemy goalie dead.
- Do NOT shoot at goal when a defender can block — pass/reposition.
- Shoot an ENEMY (not ball) when you DON'T hold the ball and an enemy is a
  blocking threat / low / about to grab the ball.

## Positioning & roles
- Kickoff: split into 3 lanes, contest center ball.
- Attacker (tank barges ball in AFTER threats cleared), Midfielder (holds
  center, pressure), Defender/goalie (near own goal, strips carrier with CC,
  transitions to counter).
- Keep the ball in the ENEMY half; keep it OUT of your own half. Control
  midfield to block the path to your goal.

## Top beginner mistakes (avoid these)
- Everyone chasing the ball / solo-scoring, no defender, no passing.
- Overcommitting to attack before clearing defenders → instant counter-goal.
  Correct: stop the enemy push FIRST, then attack together.
- Walking the ball into a charged enemy CC super.
- Shooting a defended goal instead of passing around the defender.

## Top winning habits
1. Defense-first tempo: neutralize enemy push, THEN attack. Keep one defender.
2. Exploit the ~7s respawn window after a kill.
3. Pass, don't solo-dribble (ball moves faster than a runner; bank shots work).
4. Control ball position/space — corner it in the enemy half.
5. Manage Supers/walls deliberately (CC to strip carrier / clear goalie).

## Gaps to verify in-game before hardcoding
- Exact respawn seconds (5 vs 7).
- Exact kick distance in tiles.

## Sources
- https://brawlstars.fandom.com/wiki/Brawl_Ball
- https://en.namu.wiki/w/브롤스타즈/게임%20모드/브롤%20볼
- https://brawlstars.fandom.com/wiki/Beginner%27s_Guide
- https://www.repeat.gg/content/brawl-stars-pro-tips-for-brawl-ball/
- https://theriagames.com/guide/brawl-stars-brawl-ball-guide/
- https://gamingonphone.com/guides/brawl-stars-brawl-ball-guide/
- https://brawltime.ninja/blog/guides/brawl-ball
