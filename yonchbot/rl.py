"""The bot's LEARNING brain - the Karpathy method, phone-sized.

This is "Pong from Pixels" (Andrej Karpathy's famous recipe), adapted:

  * A TINY neural network - two layers of plain numpy, no frameworks.
  * It looks at FEATURES (where's the ball? the enemy? are we carrying?)
    instead of raw pixels, because our phone plays ~25 games an hour,
    not the thousands an emulator manages. Small brain, small appetite.
  * POLICY GRADIENT learning (REINFORCE), the one-line idea:
        won the game?  -> make every move you made a bit MORE likely.
        lost the game? -> make every move a bit LESS likely.
    That's it. No teacher, no rules. Just consequences, repeated.

The rulebook bot (play.py) is the wise veteran; this one is a baby
that learns from scratch. Watching its win-rate crawl up over hundreds
of games IS the lesson: learning is compound interest on experience.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import controls, vision

# 8 compass directions x (hold fire / fire) = 16 possible moves per beat
DIRECTIONS = [0, 45, 90, 135, 180, 225, 270, 315]
N_ACTIONS = len(DIRECTIONS) * 2
N_FEATURES = 10


def features_from(screenshot, config, carrying: bool) -> np.ndarray:
    """Boil the whole screen down to 10 honest numbers the brain can eat."""
    height, width = screenshot.shape[:2]
    us = (width // 2, height // 2)

    ball = vision.find_ball(screenshot) if config["match"].get("football") else None
    enemies = [b for b in vision.find_red_bars(screenshot)
               if vision.has_name_tag(screenshot, b)]
    enemy = min(enemies, key=lambda b: (b[0] - us[0]) ** 2 + (b[1] - us[1]) ** 2) \
        if enemies else None

    def rel(spot):  # where is it, as a fraction of the screen from us?
        return ((spot[0] - us[0]) / width, (spot[1] - us[1]) / height)

    bx, by = rel(ball) if ball else (0.0, 0.0)
    ex, ey = rel(enemy) if enemy else (0.0, 0.0)
    return np.array([
        1.0,                              # a constant, so the net has a "gut feeling"
        1.0 if ball else 0.0, bx, by,
        1.0 if enemy else 0.0, ex, ey,
        1.0 if carrying else 0.0,
        1.0 if vision.super_is_ready(
            screenshot, tuple(config["match"]["super_button"])) else 0.0,
        min(1.0, len(enemies) / 3.0),     # how crowded is it here?
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
        """Pick a move by rolling weighted dice - exploring, not perfect."""
        p, h = self.action_odds(x)
        action = int(rng.choice(N_ACTIONS, p=p))
        self.episode.append((x, h, action))
        return action

    def finish_episode(self, reward: float, lr: float = 0.01) -> None:
        """The Karpathy line: nudge every move of the game toward (or away
        from) being repeated, in proportion to how surprising the result was."""
        advantage = reward - self.baseline
        self.baseline = 0.95 * self.baseline + 0.05 * reward
        for x, h, action in self.episode:
            p, _ = self.action_odds(x)
            # gradient of log-probability of the chosen action (softmax rule)
            dlogits = -p
            dlogits[action] += 1.0
            self.W2 += lr * advantage * np.outer(dlogits, h)
            dh = (self.W2.T @ dlogits) * (1 - h * h)
            self.W1 += lr * advantage * np.outer(dh, x)
        self.episode.clear()

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, W1=self.W1, W2=self.W2, baseline=self.baseline,
                 episodes=self.episodes)

    @classmethod
    def load(cls, path: str | Path) -> "TinyPolicy":
        data = np.load(path)
        policy = cls()
        policy.W1, policy.W2 = data["W1"], data["W2"]
        policy.baseline = float(data["baseline"])
        policy.episodes = int(data["episodes"])
        return policy


def do_action(device, config: dict, action: int, screenshot) -> None:
    """Turn the brain's chosen number into real thumbs on real glass."""
    angle = DIRECTIONS[action % len(DIRECTIONS)]
    fire = action >= len(DIRECTIONS)
    controls.joystick_push(
        device, anchor=tuple(config["match"]["joystick_anchor"]),
        angle_degrees=angle,
        distance=config["match"]["joystick_distance"], hold_ms=300)
    if fire:
        controls.aim_and_shoot(
            device, tuple(config["match"]["attack_button"]), angle)
