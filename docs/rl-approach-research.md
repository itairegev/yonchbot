# RL Approach Research: What Can Actually Learn in 100–200 Matches

Context: YonchBot sees ~1 frame / 1.3 s, so a 2.5 min Brawl Ball match is only ~110–130
decision steps. 100–200 episodes ≈ 15k–25k decision steps TOTAL — that's less experience
than Atari agents burn in their first minute of training. Everything below follows from
that number.

## 1. What works at our sample budget (ranked)

**#1 — Evolution of the rule-bot's parameters (we already have this: `evolve.py`).**
Most reliable use of real matches. Optimizing 3–5 discrete "genes" with champion/challenger
is a (1+1)-ES, which is exactly what the noisy-optimization literature recommends at tiny
budgets. One fix needed: win/loss is a coin flip with teammates and matchmaking in the mix —
at 10 games/side you cannot statistically distinguish a 50% bot from a 65% bot. Use a
**denser fitness** instead of raw wins: goals scored − goals conceded + fraction of steps
near the ball. Same games, far more signal per game.

**#2 — Behavior cloning (BC) the rule bot into `TinyPolicy` — costs ZERO extra matches.**
Log `(features, rule_action)` pairs while the rule bot plays (or replay saved screenshots
offline through `play.py` logic). TinyPolicy has ~500 parameters (10×16 + 16×16); a few
thousand labeled pairs — i.e. **20–30 matches of logs, which you'd play anyway** — trains it
to >90% agreement with plain cross-entropy in seconds on a laptop. BC-pretrain-then-RL-finetune
is the standard recipe when environment samples are precious (PIRLNav, BC+RL integration papers).
This turns REINFORCE from "learn to play from scratch" into "learn to *deviate* from a decent
player," which is a vastly easier problem.

**#3 — Learned high-level tactic selection over rule-based execution (recommended design, §2).**
Don't make the net choose among 16 raw swipe/fire micro-actions every 1.3 s. Let it pick one of
~5 **tactics** that the existing rule code executes. Fewer, more meaningful decisions = credit
assignment over ~100 macro-choices per match instead of noisy micro-twitches. This is the
options/hierarchical pattern (HAVEN etc. on Google Research Football), and at the extreme it
degrades gracefully into a **contextual bandit** — the most sample-efficient learner that still
uses state.

**#4 — REINFORCE with terminal ±1 win/loss (current `rl.py` as-is): will not work here.**
200 episodes of one-bit reward is ~200 bits of learning signal, half of it noise from random
teammates. Direct evidence from the closest prior art: **workofart/brawlstars-ai** ran a DQN
on real Brawl Stars for **1000+ episodes** and still converged to "stand in the corner,
attack air" — with more data, a bigger net, and replay buffers than we have. Keep the
Karpathy scaffold (it's the teaching point!) but feed it shaped per-step rewards and a
BC warm start, or it will flatline and that's a discouraging lesson for a kid.

## 2. Recommended architecture for YonchBot

One design: **BC-pretrained tiny tactic-picker + rule-based execution + shaped rewards,
with `evolve.py` still tuning the rule parameters underneath.**

**State (12 features, all from existing vision):**
`[1 (bias), ball_visible, ball_dx, ball_dy, carrying, enemy_visible, enemy_dx, enemy_dy,
crowd (n_enemies/3), super_ready, |camera_shift| (am I actually moving / stuck on wall),
match_progress (step/130)]` — the current 10 in `features_from()` plus camera-shift and clock.

**Actions (5 discrete tactics, each executed by existing `play.py` code paths):**
1. `CHASE_BALL` — walk toward ball (current ball-first branch)
2. `PUSH_NORTH` — carry/kick toward enemy goal (kick-90° + walk-90° branch)
3. `FIGHT` — focus-fire nearest enemy with lead prediction (current combat branch)
4. `FALL_BACK` — walk 270° toward our goal (defensive; new but trivial: one angle)
5. `SUPER_PLAY` — fire super at focus/goal-ward if ready, else fallback to FIGHT
A tactic runs for 2–3 heartbeats (~3–4 s) before the next pick → ~40 decisions/match.

**Reward (HFO/GRF-style; per step unless noted):**
- `+0.02 × Δdist(us, ball)` reduction, normalized by screen width, clipped to [0, 0.02] — *ball proximity progress* (delta, never raw proximity — see pitfalls)
- `+0.3` on gaining possession (`carrying` 0→1), once per possession — HFO's "kickable" bonus
- `+0.05` per step while `carrying` AND camera-shift shows northward movement — *ball-to-goal progress proxy* (we lack field coordinates; camera motion while on the ball is the honest substitute for GRF's checkpoint regions)
- `+5` our goal / `−5` conceded — **requires a NEW vision signal**: Brawl Ball shows score pips at the top and a big center-screen banner + reset countdown after each goal; a template/color check on the score-pip row (or detecting the post-goal freeze via near-zero camera shift + ball respawn at center) is a small, well-scoped addition
- `+10` win / `−10` loss at match end (existing `victory.png` detection)
- **Cap total shaped (non-goal) reward at ±3 per episode** so goals and the win always dominate — same logic as GRF capping checkpoint reward at +1 (one goal's worth)

**Training loop:**
1. *Phase 0 (offline):* log features+rule-actions for 20–30 rule-bot matches (~3k pairs); train TinyPolicy by cross-entropy to ≥90% agreement.
2. *Phase 1 (online):* per-episode REINFORCE update (keep the Karpathy structure) but with **discounted per-step returns** (γ ≈ 0.9 over macro-steps) instead of one terminal scalar; keep the running baseline; small lr (1e-3); add a BC regularizer (mix 10% cross-entropy-to-rule-action into each update, or ε=0.1 forced rule actions) so the policy can't forget its warm start in a bad streak.
3. `evolve.py` keeps tuning `kick_range` / `shoot_range` / `step_hold_ms` in separate sessions, using the denser goals-based fitness.

## 3. Pitfalls (top 5 for this setup)

1. **Terminal-only reward at this budget is statistically dead.** ~150 one-bit noisy labels
   cannot train even 500 parameters. Every viable path adds signal per step (shaping, BC) or
   reduces parameters-per-decision (bandit over tactics, evolution over 3 genes).
2. **Reward hacking of proximity terms.** Raw "near the ball" reward teaches ball-orbiting
   without kicking (classic HFO failure; same species as OpenAI's CoastRunners boat looping
   for points). Use *progress deltas*, one-shot possession bonuses, and the ±3 episode cap.
3. **Shaped reward drowning the real objective.** If dribbling upfield can out-earn a goal,
   the bot optimizes dribbling. GRF's rule: total shaping ≤ one goal. Ours: cap at 3 < 5 (goal) < 10 (win).
4. **BC distribution shift (the DAgger problem).** The cloned/fine-tuned policy will wander
   into states the rule bot never produced and act garbage there. Mitigations: keep gas/wall
   escape as hard-coded reflexes *outside* the learned policy, and keep the BC regularizer on.
5. **Noise + nonstationarity.** Random teammates, matchmaking skill drift, and game-client
   updates (which killed workofart's project outright) make every evaluation noisy and every
   template fragile. Never crown an evolve.py champion on <15 games/side with win-based
   fitness; snapshot templates per game version; and remember the 1.3 s perception lag means
   rewards land 1–2 steps late — macro-actions (2–3 heartbeats) absorb most of that smear.

## 4. Sources

- Karpathy, "Deep RL: Pong from Pixels" — http://karpathy.github.io/2016/05/31/rl/
- Kurach et al., "Google Research Football" (checkpoint reward design) — https://arxiv.org/abs/1907.11180
- Felix Yu, GRF Kaggle agent write-up (practical GRF rewards/tactics) — https://flyyufelix.github.io/2020/12/02/google-football-rl.html
- Hausknecht & Stone, "Deep RL in Parameterized Action Space" (HFO shaped reward: ball-approach Δ + kick bonus + ball-to-goal Δ + goal bonus) — https://arxiv.org/abs/1511.04143
- Kalyanakrishnan et al., "Half Field Offense: an RL case study" (sparse-reward soccer difficulty) — https://www.cs.utexas.edu/~AustinVilla/sim/halffieldoffense/
- Ng, Harada & Russell, "Policy invariance under reward transformations" (potential-based shaping) — https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf
- OpenAI, "Faulty Reward Functions in the Wild" (CoastRunners reward hacking) — https://openai.com/index/faulty-reward-functions/
- workofart/brawlstars-ai (DQN on real Brawl Stars; 1000+ eps → degenerate policy; simulator-less training lessons) — https://github.com/workofart/brawlstars-ai
- eforce67/BrawlStars-ComputerVision (NEAT/neuroevolution + YOLOv8 on Brawl Stars) — https://github.com/eforce67/BrawlStars-ComputerVision
- Jooi025/BrawlStarsBot (rule-based CV bot, mastery farming) — https://github.com/Jooi025/BrawlStarsBot
- "Integrating Behavior Cloning and RL" (BC warm start + RL fine-tune) — https://dl.acm.org/doi/10.5555/3398761.3398819
- PIRLNav: BC-pretrain → RL-finetune recipe and its failure modes — https://arxiv.org/abs/2301.07302
- Yu et al., "Action Guidance: sparse + shaped rewards for RTS games" — https://arxiv.org/abs/2010.03956
- Ross, Gordon & Bagnell, DAgger (BC distribution shift) — https://arxiv.org/abs/1011.0686
- "Depth over Fidelity in Fixed-Budget Noisy Evolution Strategies" (noisy fitness, tiny budgets) — https://arxiv.org/abs/2606.06555
- david-cortes/contextualbandits (practical contextual-bandit toolkit) — https://github.com/david-cortes/contextualbandits
