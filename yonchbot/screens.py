"""Which screen is the game showing right now?

Brawl Stars (like most games) is a bunch of screens:
the lobby, the loading screen, the match itself, the victory screen...

The bot recognizes each screen by looking for a "landmark" - a small
picture that ONLY appears on that screen. The PLAY button means we're
in the lobby. The EXIT button after a match means the match ended.

You create the landmark pictures yourself: take a screenshot, crop the
landmark, save it in assets/templates/ with the right name.
See assets/templates/README.md for the full list.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import numpy as np

from . import vision


class Screen(Enum):
    LOBBY = "lobby"            # main menu, PLAY button visible
    IN_MATCH = "in_match"      # we're playing! joystick visible
    SPECTATE = "spectate"      # we died; watching someone else, small Exit button
    MATCH_END = "match_end"    # victory/defeat screen, EXIT/CONTINUE visible
    REWARDS = "rewards"        # tokens/boxes screen, tap to continue
    UNKNOWN = "unknown"        # no landmark found - a popup? an ad? who knows


# Each screen -> the template file that proves we're on it.
# Order matters: we check top to bottom and take the first hit.
# A screen may have SEVERAL proofs: match_end is the EXIT button in
# Showdown, but the PROCEED button in Brawl Ball - same meaning, tap it.
LANDMARKS = [
    (Screen.MATCH_END, "match_end.png"),
    (Screen.MATCH_END, "proceed.png"),
    (Screen.MATCH_END, "lets_go.png"),
    (Screen.SPECTATE, "spectate_exit.png"),
    (Screen.REWARDS, "rewards.png"),
    # The attack button is our "we're in a match" landmark - but it
    # changes color! Yellow when loaded, blue when out of ammo. We need
    # BOTH pictures: with only the blue one, a bot that hadn't shot yet
    # was never "in a match"... so it never shot. Frozen all game!
    (Screen.IN_MATCH, "in_match_ready.png"),
    (Screen.IN_MATCH, "in_match.png"),
    (Screen.LOBBY, "play_button.png"),
]


class ScreenDetector:
    """Loads the landmark templates once, then answers "which screen?" fast."""

    def __init__(self, templates_dir: str | Path, threshold: float = 0.85):
        self.templates_dir = Path(templates_dir)
        self.threshold = threshold
        # A list of (screen, template) pairs - a screen can have several.
        self._entries: list[tuple[Screen, np.ndarray]] = []
        self._loaded_files: set[str] = set()
        # Buttons never move - so once we find one, we write down WHERE.
        # Next time we peek at that little spot first instead of combing
        # the whole screen. Same answers, ~50x less work per look.
        self._known_spots: dict[int, tuple[int, int]] = {}
        for screen, filename in LANDMARKS:
            path = self.templates_dir / filename
            if path.exists():
                self._entries.append((screen, vision.load_template(path)))
                self._loaded_files.add(filename)

    @property
    def missing_templates(self) -> list[str]:
        """Which landmark pictures haven't been captured yet?"""
        return [f for _s, f in LANDMARKS if f not in self._loaded_files]

    def which_screen(self, screenshot: np.ndarray) -> Screen:
        """Look at a screenshot and say which screen it is."""
        # FAST look first: check each landmark's remembered spot.
        for i, (screen, template) in enumerate(self._entries):
            spot = self._known_spots.get(i)
            if spot is not None and self._found_near(screenshot, template, spot):
                return screen
        # SLOW look: comb the whole screen - and remember what we find.
        for i, (screen, template) in enumerate(self._entries):
            match = vision.find(screenshot, template, self.threshold)
            if match is not None:
                self._known_spots[i] = (match.x, match.y)
                return screen
        return Screen.UNKNOWN

    def _found_near(self, screenshot: np.ndarray, template: np.ndarray,
                    spot: tuple[int, int], wiggle: int = 60) -> bool:
        """Is the template still at (or near) where we last saw it?"""
        x, y = spot
        h, w = template.shape[:2]
        window = screenshot[max(0, y - wiggle):y + h + wiggle,
                            max(0, x - wiggle):x + w + wiggle]
        return vision.find(window, template, self.threshold) is not None

    def find_landmark(self, screenshot: np.ndarray, screen: Screen):
        """Find WHERE a screen's landmark is (so we can tap it)."""
        for entry_screen, template in self._entries:
            if entry_screen != screen:
                continue
            match = vision.find(screenshot, template, self.threshold)
            if match is not None:
                return match
        return None
