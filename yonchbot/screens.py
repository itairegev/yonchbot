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
    MATCH_END = "match_end"    # victory/defeat screen, EXIT/CONTINUE visible
    REWARDS = "rewards"        # tokens/boxes screen, tap to continue
    UNKNOWN = "unknown"        # no landmark found - a popup? an ad? who knows


# Each screen -> the template file that proves we're on it.
# Order matters: we check top to bottom and take the first hit.
LANDMARKS = [
    (Screen.MATCH_END, "match_end.png"),
    (Screen.REWARDS, "rewards.png"),
    (Screen.IN_MATCH, "in_match.png"),
    (Screen.LOBBY, "play_button.png"),
]


class ScreenDetector:
    """Loads the landmark templates once, then answers "which screen?" fast."""

    def __init__(self, templates_dir: str | Path, threshold: float = 0.85):
        self.templates_dir = Path(templates_dir)
        self.threshold = threshold
        self._templates: dict[Screen, np.ndarray] = {}
        for screen, filename in LANDMARKS:
            path = self.templates_dir / filename
            if path.exists():
                self._templates[screen] = vision.load_template(path)

    @property
    def missing_templates(self) -> list[str]:
        """Which landmark pictures haven't been captured yet?"""
        have = set(self._templates)
        return [f for s, f in LANDMARKS if s not in have]

    def which_screen(self, screenshot: np.ndarray) -> Screen:
        """Look at a screenshot and say which screen it is."""
        for screen, _filename in LANDMARKS:
            template = self._templates.get(screen)
            if template is None:
                continue
            if vision.find(screenshot, template, self.threshold) is not None:
                return screen
        return Screen.UNKNOWN

    def find_landmark(self, screenshot: np.ndarray, screen: Screen):
        """Find WHERE a screen's landmark is (so we can tap it)."""
        template = self._templates.get(screen)
        if template is None:
            return None
        return vision.find(screenshot, template, self.threshold)
