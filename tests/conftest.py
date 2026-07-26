"""Shared test helpers.

We can't run Brawl Stars inside a test, so we build FAKE game screens:
random-noise images with a unique little "landmark" pasted where a real
button would be. The bot can't tell the difference - and that's the point.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

SCREEN_W, SCREEN_H = 640, 360
LANDMARK_W, LANDMARK_H = 60, 40

# each fake landmark gets its own random seed = its own unique look
SEEDS = {
    "play_button.png": 1,
    "in_match.png": 2,
    "in_match_ready.png": 8,
    "match_end.png": 3,
    "rewards.png": 4,
    "spectate_exit.png": 5,
    "proceed.png": 6,
    "lets_go.png": 7,
}


def make_landmark(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (LANDMARK_H, LANDMARK_W, 3), dtype=np.uint8)


def make_screen(landmark: np.ndarray | None, pos: tuple[int, int] = (300, 150),
                bg_seed: int = 99) -> np.ndarray:
    rng = np.random.default_rng(bg_seed)
    screen = rng.integers(0, 255, (SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    if landmark is not None:
        x, y = pos
        screen[y:y + landmark.shape[0], x:x + landmark.shape[1]] = landmark
    return screen


@pytest.fixture(autouse=True)
def fresh_bot_memory():
    """Wipe the bot's short-term memory before every test.

    play.MEMORY belongs to the module, so without this, one test's
    match would leak into the next test's match - the same way a real
    match wipes it at step 0.
    """
    from yonchbot import play
    play.MEMORY.update({"loot_angle": None, "loot_steps": 0, "cubes": 0,
                        "focus": None, "focus_prev": None, "carry_steps": 0,
                        "carry_beats": 0, "strafe_flip": False,
                        "focus_time": None, "focus_prev_time": None,
                        "last_view": None, "walked": None,
                        "detour": None, "detour_steps": 0})
    yield


@pytest.fixture
def templates_dir(tmp_path):
    """A folder with all four landmark templates saved as PNGs."""
    d = tmp_path / "templates"
    d.mkdir()
    for name, seed in SEEDS.items():
        cv2.imwrite(str(d / name), make_landmark(seed))
    return d


@pytest.fixture
def fake_screens():
    """One fake screenshot per game screen, plus a blank 'mystery' screen."""
    return {
        "lobby": make_screen(make_landmark(SEEDS["play_button.png"])),
        "in_match": make_screen(make_landmark(SEEDS["in_match.png"])),
        # the attack button changes color with ammo: blue when empty
        # (in_match.png), yellow when loaded (in_match_ready.png).
        # BOTH must mean "we're in a match" - see the full-ammo bug!
        "in_match_ready": make_screen(make_landmark(SEEDS["in_match_ready.png"])),
        "match_end": make_screen(make_landmark(SEEDS["match_end.png"])),
        "rewards": make_screen(make_landmark(SEEDS["rewards.png"])),
        "mystery": make_screen(None, bg_seed=7),
    }


@pytest.fixture
def config(tmp_path, templates_dir):
    """A test copy of config.yaml pointing at temp folders."""
    return {
        "device": {"serial": ""},
        "vision": {"templates_dir": str(templates_dir), "match_threshold": 0.85},
        "match": {
            "joystick_anchor": [100, 300],
            "attack_button": [550, 310],
            "super_button": [500, 250],
            "pattern": "circle",
            "joystick_distance": 80,
            "joystick_hold_ms": 500,
            "attack_every_steps": 2,
        },
        "timing": {"seconds_between_looks": 0.0},
        "safety": {
            "max_games": 3,
            "give_up_after_unknowns": 3,
            "safe_tap_spot": [320, 340],
            "stuck_screenshots_dir": str(tmp_path / "stuck"),
        },
        "diary": {
            "csv_path": str(tmp_path / "games.csv"),
            "dashboard_path": str(tmp_path / "progress.html"),
        },
    }
