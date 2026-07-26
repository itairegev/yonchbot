"""The bot's LEARNING brain - the Karpathy method, phone-sized and honest.

This is "Pong from Pixels" (Andrej Karpathy's famous recipe), adapted to
a brutal reality: our phone plays ~20 games an hour, not the thousands an
emulator manages. Research (docs/rl-approach-research.md) says a learner
this small, fed one win/loss bit per game, flatlines. So we cheat smart,
three ways the pros use when experience is expensive:

  1. TACTICS, not twitches. The net doesn't steer every swipe - it picks
     one of play.py's five TACTICS every few heartbeats. ~40 meaningful
     decisions per match instead of hundreds of noisy micro-moves.
  2. STUDY before playing (behavior cloning). The rulebook bot writes
     down (what I saw, what I chose) as it plays. The net reads that
     diary until it copies the veteran ~90% of the time - THEN it starts
     learning from consequences. Deviating from good is easier than
     inventing good.
  3. GRADES every step (reward shaping). Not just "won/lost" at the end:
     getting closer to the ball, winning possession, and pushing it north
     earn small points; goals earn big ones. Small points are CAPPED so
     they can never outweigh a real goal - we grade homework, but the
     exam still decides the grade.

The learning rule is still REINFORCE, one line of idea:
    choices that led to good -> a bit more likely next time.
    choices that led to bad  -> a bit less likely.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import play, vision

N_FEATURES = 12
N_ACTIONS = len(play.TACTICS)   # the five tactics, by number


def features_from_ctx(ctx, config: dict, step: int) -> np.ndarray:
    """Boil one look at the world down to 12 honest numbers."""
    us, width, height = ctx["us"], max(ctx["width"], 1), max(ctx["height"], 1)

    def rel(spot):  # where is it, as a fraction of the screen from us?
        return ((spot[0] - us[0]) / width, (spot[1] - us[1]) / height)

    ball, focus = ctx["ball"], ctx["focus"]
    bx, by = rel(ball) if ball else (0.0, 0.0)
    ex, ey = rel(focus) if focus else (0.0, 0.0)
    super_ready = ctx["screenshot"] is not None and vision.super_is_ready(
        ctx["screenshot"], tuple(config["match"]["super_button"]))
    return np.array([
        1.0,                                  # a constant "gut feeling" input
        1.0 if ball else 0.0, bx, by,
        1.0 if ctx["carrying"] else 0.0,
        1.0 if focus else 0.0, ex, ey,
        min(1.0, len(ctx["enemies"]) / 3.0),  # how crowded is it here?
        1.0 if super_ready else 0.0,
        min(1.0, play.MEMORY["last_shift"] / 20.0),  # are we actually moving?
        min(1.0, step / 130.0),               # how late in the match is it?
    ], dtype=np.float64)


class TinyPolicy:
    """Two layers of numpy. Karpathy-sized: small enough to read whole."""

    def __init__(self, n_hidden: int = 16, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.W1 = rng.normal(0, 0.5, (n_hidden, N_FEATURES))
        self.W2 = rng.normal(0, 0.5, (N_ACTIONS, n_hidden))
        self.episode: list[tuple[np.ndarray, np.ndarray, int]] = []
        self.baseline = 0.0   # running "how well do we usually do?"
        self.episodes = 0     # how many whole games we've learned from

    def action_odds(self, x: np.ndarray):
        h = np.tanh(self.W1 @ x)
        logits = self.W2 @ h
        e = np.exp(logits - logits.max())
        return e / e.sum(), h

    def act(self, x: np.ndarray, rng: np.random.Generator) -> int:
        """Pick a tactic by rolling weighted dice - exploring, not perfect."""
        p, h = self.action_odds(x)
        action = int(rng.choice(N_ACTIONS, p=p))
        self.episode.append((x, h, action))
        return action

    def _nudge(self, x, h, dlogits, lr: float) -> None:
        """One gradient step: make dlogits' preferred choices more likely."""
        self.W2 += lr * np.outer(dlogits, h)
        dh = (self.W2.T @ dlogits) * (1 - h * h)
        self.W1 += lr * np.outer(dh, x)

    def study(self, demos: list, passes: int = 1, lr: float = 0.01) -> float:
        """Learn by COPYING the rulebook (behavior cloning).

        demos = [(features, rulebook_choice), ...]. For each remembered
        moment, nudge the net toward the choice the rulebook made.
        Returns the fraction it now gets right - report card included.
        """
        for _ in range(passes):
            for x, action in demos:
                p, h = self.action_odds(x)
                dlogits = -p
                dlogits[action] += 1.0   # cross-entropy: "should've picked THIS"
                self._nudge(x, h, dlogits, lr)
        right = sum(1 for x, a in demos
                    if int(np.argmax(self.action_odds(x)[0])) == a)
        return right / max(1, len(demos))

    def finish_episode(self, rewards: list[float], lr: float = 0.001,
                       gamma: float = 0.9, demos: list | None = None,
                       bc_weight: float = 0.1,
                       rng: np.random.Generator | None = None) -> None:
        """The Karpathy line, upgraded with per-step credit.

        Each decision is judged by the discounted RETURN that followed it
        (rewards soon after count fully, rewards long after count less) -
        so the choice that WON the ball gets the credit, not whatever the
        bot happened to do at the final whistle.
        """
        n = min(len(rewards), len(self.episode))
        if n == 0:
            self.episode.clear()
            return
        returns, g = [], 0.0
        for r in reversed(rewards[:n]):
            g = r + gamma * g
            returns.append(g)
        returns.reverse()
        returns = np.array(returns)
        # judge against how well we USUALLY do (the running baseline) -
        # "was this game's play surprisingly good, or surprisingly bad?"
        adv = returns - self.baseline
        self.baseline = 0.95 * self.baseline + 0.05 * float(returns.mean())
        if len(returns) > 1 and returns.std() > 1e-8:
            adv = adv / returns.std()   # keep big games from shouting
        for (x, h, action), a in zip(self.episode[:n], adv):
            p, _ = self.action_odds(x)
            h = np.tanh(self.W1 @ x)   # fresh h - the net changes as we go
            dlogits = -p
            dlogits[action] += 1.0
            self._nudge(x, h, dlogits * a, lr)
        self.episode.clear()
        # The safety line back to the rulebook: a small refresher of
        # cloning every game, so one weird match can't erase the studying.
        if demos and bc_weight > 0:
            rng = rng or np.random.default_rng()
            sample = [demos[i] for i in
                      rng.choice(len(demos), size=min(64, len(demos)),
                                 replace=False)]
            self.study(sample, passes=1, lr=lr * bc_weight * 10)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, W1=self.W1, W2=self.W2, baseline=self.baseline,
                 episodes=self.episodes)

    @classmethod
    def load(cls, path: str | Path) -> "TinyPolicy":
        data = np.load(path)
        policy = cls()
        if data["W1"].shape != policy.W1.shape or \
                data["W2"].shape != policy.W2.shape:
            return policy   # the brain grew since this save - start fresh
        policy.W1, policy.W2 = data["W1"], data["W2"]
        policy.baseline = float(data["baseline"])
        policy.episodes = int(data["episodes"])
        return policy


def load_all_demos(config: dict) -> list:
    """Everything there is to study: the rulebook's diary, plus any HUMAN
    gameplay we converted from recordings - counted 3x, because a human
    demonstration is worth more than a rulebook rerun."""
    rl_cfg = config.get("rl", {})
    demos = load_demos(rl_cfg["demos_path"]) if rl_cfg.get("demos_path") else []
    human = load_demos(rl_cfg["human_demos_path"]) \
        if rl_cfg.get("human_demos_path") else []
    return demos + 3 * human


def load_demos(path: str | Path) -> list:
    """Read the rulebook's diary back in: [(features, choice), ...]."""
    demos = []
    path = Path(path)
    if not path.exists():
        return demos
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
                demos.append((np.array(row["x"], dtype=np.float64),
                              int(row["action"])))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue   # a torn line (bot was killed mid-write) - skip it
    return [d for d in demos if d[0].shape == (N_FEATURES,)]


class Pilot:
    """The learning pilot: flies whole matches, grades its own play.

    Every `macro_beats` heartbeats it looks at the world, picks ONE of
    the five tactics, and sticks with it - like a coach calling plays,
    not a puppeteer pulling strings. Between picks it tallies the grade
    (the shaped rewards) for the pick that's currently running.
    """

    def __init__(self, policy: TinyPolicy, config: dict, say=print):
        self.policy = policy
        self.config = config
        self.say = say
        self.rng = np.random.default_rng()
        rl_cfg = config.get("rl", {})
        self.macro_beats = rl_cfg.get("macro_beats", 3)
        self.gamma = rl_cfg.get("gamma", 0.9)
        self.lr = rl_cfg.get("learn_rate", 0.001)
        self.bc_weight = rl_cfg.get("bc_weight", 0.1)
        # What counts as "good"? The coach decided (2026-07-22): wins are
        # a TEAM grade - random teammates share the credit and the blame.
        # Punches we personally land are OUR grade. So hits lead the
        # reward, goals stay as context, and the win bonus sits at zero.
        self.reward_hit = rl_cfg.get("reward_hit", 1.0)
        self.reward_goal = rl_cfg.get("reward_goal", 2.0)
        self.reward_win = rl_cfg.get("reward_win", 0.0)
        self.demos = load_all_demos(config)
        self.policy_path = Path(rl_cfg.get(
            "policy_path", "data/rl/policy.npz"))
        self.reset()

    def reset(self) -> None:
        self.tactic = "chase_ball"
        self.beats_left = 0
        self.rewards: list[float] = []
        self.shaped_total = 0.0
        self.prev_ball_gap = None
        self.prev_carrying = False
        self.prev_scores = None

    def step(self, device, ctx, step: int, scores) -> None:
        """One heartbeat: grade the running tactic, maybe pick a new one."""
        reward = self._grade(ctx, scores)
        if self.beats_left <= 0:   # time to call the next play
            x = features_from_ctx(ctx, self.config, step)
            action = self.policy.act(x, self.rng)
            self.tactic = play.TACTICS[action]
            self.beats_left = self.macro_beats
            self.rewards.append(0.0)
        if self.rewards:
            self.rewards[-1] += reward
        self.beats_left -= 1
        play.run_tactic(self.tactic, device, self.config, ctx)

    def _grade(self, ctx, scores) -> float:
        """The report card for the last beat. Small points are CAPPED at
        ±3 per game; goals (±5) and the final whistle (±10) are not -
        homework helps, but the exam decides."""
        shaped = 0.0
        # getting closer to the ball earns (a little), drifting away costs nothing
        if ctx["ball"] is not None and ctx["us"] is not None:
            gap = math.dist(ctx["us"], ctx["ball"]) / max(ctx["width"], 1)
            if self.prev_ball_gap is not None:
                shaped += min(0.02, max(0.0, self.prev_ball_gap - gap))
            self.prev_ball_gap = gap
        else:
            self.prev_ball_gap = None
        # winning possession is a real achievement - one-time bonus
        if ctx["carrying"] and not self.prev_carrying:
            shaped += 0.3
        self.prev_carrying = ctx["carrying"]
        # carrying AND actually moving = marching the ball somewhere
        if ctx["carrying"] and play.MEMORY["last_shift"] > play.STUCK_SHIFT:
            shaped += 0.05
        # the cap: homework points stop counting after ±3
        room = 3.0 - abs(self.shaped_total)
        shaped = max(-room, min(room, shaped)) if room > 0 else 0.0
        self.shaped_total += shaped

        reward = shaped
        # HITS - the star of the report card. A landed punch is the one
        # thing on this screen that is 100% OUR doing. Uncapped.
        if ctx.get("hit_confirmed"):
            reward += self.reward_hit
        # GOALS - smaller, uncapped context (needs the score reader)
        if scores is not None and self.prev_scores is not None:
            ours_now, theirs_now = scores
            ours_before, theirs_before = self.prev_scores
            if ours_now > ours_before:
                reward += self.reward_goal
                self.say(f"🥅 GOAL for us! (+{self.reward_goal:g})")
            if theirs_now > theirs_before:
                reward -= self.reward_goal
                self.say(f"😖 They scored. (-{self.reward_goal:g})")
        if scores is not None:
            self.prev_scores = scores
        return reward

    def finish(self, won: bool | None) -> None:
        """Match over: the final whistle reward, then one learning pass."""
        if self.rewards and won is not None and self.reward_win:
            self.rewards[-1] += self.reward_win if won else -self.reward_win
        self.policy.finish_episode(self.rewards, lr=self.lr, gamma=self.gamma,
                                   demos=self.demos, bc_weight=self.bc_weight,
                                   rng=self.rng)
        self.policy.episodes += 1
        self.policy.save(self.policy_path)
        self.say(f"🧠 Learned from game #{self.policy.episodes} "
                 f"({len(self.rewards)} decisions).")
        self.reset()
