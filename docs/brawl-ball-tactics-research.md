# Brawl Ball Tactics Research (for the Edgar vision bot)

Research for turning Brawl Ball tactics into simple IF-THEN rules the bot can run
with its existing vision signals. Sources at the bottom.

## Key facts

**Mode rules**
- 3v3. First team to score 2 goals wins; if the timer runs out, the team with more goals wins. ([Brawl Stars Wiki](https://brawlstars.fandom.com/wiki/Brawl_Ball))
- Tie at timer end → 1 minute of overtime and **all walls/obstacles on the map are destroyed**. Still tied → draw. ([Brawl Stars Wiki](https://brawlstars.fandom.com/wiki/Brawl_Ball))
- After a goal, play pauses briefly, everyone respawns at their spawn side, and the ball resets to the center of the map. ([Brawl Stars Wiki](https://brawlstars.fandom.com/wiki/Brawl_Ball))
- **You cannot attack while carrying the ball** — pressing attack *kicks* the ball instead. Gadgets can't be activated while holding it. ([Brawl Stars Wiki](https://brawlstars.fandom.com/wiki/Brawl_Ball))
- Kicking with your **Super sends the ball much further and faster but consumes the Super**. Auto-aim kicks the ball toward the center of the enemy goal line. ([Brawl Stars Wiki](https://brawlstars.fandom.com/wiki/Brawl_Ball))
- Dying while carrying drops the ball where you died. The ball banks off walls, so wall/bank shots and passes around defenders work. ([Repeat.gg pro tips](https://www.repeat.gg/content/brawl-stars-pro-tips-for-brawl-ball/))

**Tactics consensus (wikis/guides)**
- Don't shoot at goal with a defender in the way; **clear defenders first or pass around them**. ([Gamezebo](https://www.gamezebo.com/walkthroughs/brawl-stars-guide-brawl-ball-tips-cheats-and-strategies/), [Theria Games](https://theriagames.com/guide/brawl-stars-brawl-ball-guide/))
- Balanced play: **stop the enemy push first, then attack as a team**; keep someone near your own goal when the enemy has the ball. ([Theria Games](https://theriagames.com/guide/brawl-stars-brawl-ball-guide/))
- **Passing/kicking forward beats dribbling** into contested space; a carrier is defenseless. ([Theria Games](https://theriagames.com/guide/brawl-stars-brawl-ball-guide/))
- Keeping the ball near a corner/wall limits enemy steal angles. ([Repeat.gg](https://www.repeat.gg/content/brawl-stars-pro-tips-for-brawl-ball/))
- Common beginner mistakes: chasing kills far from the ball, kicking without a clear lane, overcommitting to offense with no defender, wasting Super kicks, breaking your own protective walls. ([Theria Games](https://theriagames.com/guide/brawl-stars-brawl-ball-guide/), [Repeat.gg](https://www.repeat.gg/content/brawl-stars-pro-tips-for-brawl-ball/))

**Edgar**
- Melee assassin; **shortest attack range in the game** (~2.3 tiles), fast movement, low-ish HP. ([Edgar wiki](https://brawlstars.fandom.com/wiki/Edgar), [noff.gg](https://www.noff.gg/brawl-stars/brawler/edgar))
- **Lifesteal trait: heals ~35% of damage dealt** by his punches (more with Fisticuffs star power), so he sustains only while actively punching. ([noff.gg guide](https://www.noff.gg/brawl-stars/build/5558/actual-edgar-guide-(in-depth)), [ExitLag](https://www.exitlag.com/blog/edgar-brawl-stars/))
- **Super (Vault) charges passively over time** (unique trait) and also from dealing damage; the jump is ~0.9s airborne, clears walls, and gives a ~2.5s speed boost on landing. ([Edgar wiki](https://brawlstars.fandom.com/wiki/Edgar))
- Weak to ranged poke and knockback; he must close distance or he does nothing. ([1v9.gg](https://1v9.gg/blog/edgar-brawl-stars-guide))
- Known Edgar Brawl Ball combo: **kick the ball toward the goal, Super-jump after it, land, and kick it in** — the jump skips defenders. ([theriagames Edgar guide](https://theriagames.com/guide/brawl-stars-edgar-guide/))

**AFK / inactivity**
- Community-reported numbers: idle warning after ~12 s of no input, removal/bot-takeover at ~15 s; a kicked player is locked out of that mode for ~5 min. **Weak sourcing (fan wiki/Quora — no official Supercell number found)**, so treat "any input at least every ~10 s" as the safety budget. Movement joystick input counts as activity. ([Quora](https://www.quora.com/How-much-time-does-it-take-to-be-inactive-to-get-inactive-rewards-in-Brawl-Stars), [fan wiki](https://brawlstarsconception.fandom.com/wiki/Idling))

**Existing bot heuristics (prior art)**
- [Jooi025/BrawlStarsBot](https://github.com/Jooi025/BrawlStarsBot) (YOLOv8 showdown bot): move to nearest bush, attack only when enemy within range, gadget when enemy is close, auto-requeue after defeat. No Brawl Ball logic exists in public bots — mode logic is ours to write.
- [workofart/brawlstars-ai](https://github.com/workofart/brawlstars-ai) and [eforce67/BrawlStars-ComputerVision](https://github.com/eforce67/BrawlStars-ComputerVision) use RL/NEAT from pixels — confirms rule-based + object detection is the practical path for a simple bot.

## Tactics ranked by impact for a bot

Signals available: `ball_pos`, `self_pos` (screen center), `enemy_pos[]` (red bars),
own goal = screen **bottom**, enemy goal = screen **top**, `dist()`, `super_ready`,
`wall_stuck`. "NEW" marks rules needing a signal the bot doesn't have.

### Tier 1 — never lose the game for free
1. **Never kick toward own goal.** IF carrying/near ball AND about to kick THEN only kick with an upward (toward-top) component; clamp kick direction to the top half-plane. *Signals: ball_pos, self_pos.* Needs NEW: `carrying_ball` flag (detect: ball sprite overlaps self / ball icon over head) — can approximate with `dist(ball, self) < small`.
2. **The ball is the objective — don't chase kills.** IF not carrying AND ball is free THEN move toward `ball_pos`, ignoring enemies more than ~1.5 screen-heights from the ball. *Signals: ball_pos, self_pos, enemy_pos, dist.*
3. **Stay alive as carrier.** IF carrying AND ≥2 enemies within medium range ahead THEN kick the ball forward (up) immediately rather than dribble — a carrier can't attack. *Signals: carrying flag (see rule 1), enemy_pos, dist.*
4. **Anti-AFK / anti-stuck.** IF no meaningful action for ~8 s OR `wall_stuck` fires THEN issue a movement input (jitter toward ball). Keeps under the ~12–15 s idle kick. *Signals: wall_stuck, internal timer.*

### Tier 2 — win conditions
5. **Score when the lane is clear.** IF carrying AND `self_pos` is in top third AND no enemy between self and top-center goal THEN kick at goal (auto-aim kicks toward goal center). *Signals: carrying, self_pos, enemy_pos.* Better with NEW: goal-post detector for exact goal x-range; top-center heuristic works meanwhile.
6. **Super = goal or escape, not a kill button.** IF carrying near enemy goal AND defender blocks lane AND `super_ready` THEN Super-kick (flies past defenders) OR: kick ball toward goal then Super-jump to it and tap-kick in (Edgar combo). *Signals: super_ready, carrying, ball_pos, enemy_pos.*
7. **Defend when the enemy has the ball on your half.** IF ball is in bottom third AND an enemy is within close range of the ball THEN move to a point *between* ball and bottom-center (own goal), then attack the carrier (a carrier can't fight back — free punches for Edgar). *Signals: ball_pos, enemy_pos, self_pos.*
8. **After-goal reset detection.** IF ball suddenly reappears at screen-center and all enemies vanish/reset THEN clear all state and go to rule 2. *Signals: ball_pos discontinuity.* Optional NEW: score-UI reader to know match score / 2-goal status.

### Tier 3 — Edgar-specific polish
9. **Only fight in punch range.** IF engaging THEN keep pressing attack only when nearest enemy dist < melee threshold (~2.3 tiles); otherwise don't fire (attacking while near ball would kick it). *Signals: enemy_pos, dist.*
10. **Punch to live.** IF own HP low AND enemy adjacent THEN keep attacking (lifesteal ~35%) instead of running in the open. *Signals: enemy_pos.* Needs NEW: own-HP reader (green bar above self) — without it, default to "always punch when adjacent."
11. **Retreat from ranged poke.** IF ≥2 enemies at medium-long range AND no ball nearby AND `super_ready` is false THEN back off toward bottom (walls/cover) — Edgar loses every poke war. *Signals: enemy_pos, dist, super_ready.*
12. **Overtime awareness (optional).** In overtime all walls are gone — `wall_stuck` should stop firing; pure straight-line pathing to ball/goal becomes optimal. *Signals: none needed; optional NEW: timer/OT banner reader.*

**Suggested priority order per frame:** 4 (anti-stuck) → 8 (reset) → 1/3 (carrier safety) → 5/6 (score) → 2 (get ball) → 7 (defend) → 9–11 (combat).

## Edgar notes

- Edgar is a poor "brawl-ball meta" pick but a fine bot brawler: fast, simple kit,
  Super charges by itself, and auto-aim punches work at melee range.
- Best bot role: **ball chaser / counter-attacker**. Grab loose balls, run them up,
  kick early when contested. Avoid long dribbles into 2+ enemies.
- Save Super for: (a) jumping the last wall/defender line to score, (b) escaping
  when surrounded, (c) reaching a loose ball on the enemy half fast. Never Super
  onto 2+ healthy enemies just for a fight.
- His whole defense is offense: when forced to fight, commit to punching
  (lifesteal); half-hearted trades at range are always lost.

## Sources

- Brawl Ball rules: https://brawlstars.fandom.com/wiki/Brawl_Ball
- Brawl Ball guide (tactics, mistakes): https://theriagames.com/guide/brawl-stars-brawl-ball-guide/
- Brawl Ball pro tips (corners, defender role, bank shots): https://www.repeat.gg/content/brawl-stars-pro-tips-for-brawl-ball/
- Brawl Ball beginner guide: https://www.gamezebo.com/walkthroughs/brawl-stars-guide-brawl-ball-tips-cheats-and-strategies/
- Edgar wiki (stats, trait): https://brawlstars.fandom.com/wiki/Edgar
- Edgar stats: https://www.noff.gg/brawl-stars/brawler/edgar
- Edgar in-depth guide (Brawl Ball super combo): https://www.noff.gg/brawl-stars/build/5558/actual-edgar-guide-(in-depth)
- Edgar guide: https://theriagames.com/guide/brawl-stars-edgar-guide/
- Edgar guide (weaknesses): https://1v9.gg/blog/edgar-brawl-stars-guide
- Edgar build guide: https://www.exitlag.com/blog/edgar-brawl-stars/
- AFK timing (unofficial): https://www.quora.com/How-much-time-does-it-take-to-be-inactive-to-get-inactive-rewards-in-Brawl-Stars , https://brawlstarsconception.fandom.com/wiki/Idling
- Prior-art bots: https://github.com/Jooi025/BrawlStarsBot , https://github.com/workofart/brawlstars-ai , https://github.com/eforce67/BrawlStars-ComputerVision
