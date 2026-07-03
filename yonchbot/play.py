"""How the bot plays a match. THIS is the fun file to tweak!

The strategy is simple on purpose:
  1. walk somewhere (following a movement pattern)
  2. attack every couple of seconds (auto-aim does the hard part)
  3. repeat until the match ends

The movement patterns live in PATTERNS. Each one is just a list of
compass angles (degrees) the bot walks in, one after another, in a loop.

Ideas to try:
  * add your own pattern (a square? a star? your initials?)
  * make attack_every_seconds smaller - does the bot do better?
  * make a "scaredy-cat" pattern that walks away from the middle
"""

from __future__ import annotations

import random

from . import controls

# name -> list of walking angles, done in order, repeating.
# 90 = up, 0 = right, 180 = left, 270 = down (see controls.py)
PATTERNS: dict[str, list[float]] = {
    # walk in a circle-ish octagon
    "circle": [0, 45, 90, 135, 180, 225, 270, 315],
    # sneak up the map in a zigzag
    "zigzag": [60, 120, 60, 120],
    # mostly sit still (in a bush, we hope), tiny shuffles
    "bush_camper": [90, 270],
    # totally random - chaos mode!
    "headless_chicken": [],
}


def next_angle(pattern_name: str, step: int) -> float:
    """Which direction to walk on step number `step`."""
    angles = PATTERNS.get(pattern_name, PATTERNS["circle"])
    if not angles:  # empty list = random chaos
        return random.uniform(0, 360)
    return angles[step % len(angles)]


def play_step(device, config: dict, step: int) -> None:
    """One heartbeat of in-match playing: walk a bit, maybe attack."""
    joystick = tuple(config["match"]["joystick_anchor"])
    attack_button = tuple(config["match"]["attack_button"])
    pattern = config["match"]["pattern"]

    angle = next_angle(pattern, step)
    controls.joystick_push(
        device,
        anchor=joystick,
        angle_degrees=angle,
        distance=config["match"]["joystick_distance"],
        hold_ms=config["match"]["joystick_hold_ms"],
    )

    # Attack every N steps (each step is roughly one joystick push long)
    if step % config["match"]["attack_every_steps"] == 0:
        controls.attack(device, attack_button)
