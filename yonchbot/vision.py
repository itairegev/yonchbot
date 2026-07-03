"""The bot's eyes.

A screenshot is just a huge grid of numbers (each pixel = 3 numbers for
blue, green, red). To "see" a button, we slide a small picture of that
button (a "template") across the big screenshot and ask at every spot:
"how similar does this look, from 0 to 1?"

The spot with the highest score is where the button probably is.
If even the best score is low, the button isn't on screen at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Match:
    """Where we found something, and how sure we are."""

    x: int          # left edge of the found box
    y: int          # top edge of the found box
    width: int
    height: int
    confidence: float  # 0.0 = "no idea", 1.0 = "absolutely certain"

    @property
    def center(self) -> tuple[int, int]:
        """The middle of the box - the best place to tap!"""
        return (self.x + self.width // 2, self.y + self.height // 2)


def load_template(path: str | Path) -> np.ndarray:
    """Load a small picture (like a cropped PLAY button) from a file."""
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(
            f"Couldn't load the template image: {path}\n"
            "Did you crop and save it? Check assets/templates/README.md"
        )
    return image


def find(screen: np.ndarray, template: np.ndarray, threshold: float = 0.85) -> Match | None:
    """Look for `template` inside `screen`.

    Returns a Match if we're at least `threshold` sure, otherwise None.

    Try changing the threshold and see what happens:
      * too high (0.99) -> the bot becomes too picky and misses buttons
      * too low  (0.50) -> the bot "sees" buttons that aren't there!
    """
    if (template.shape[0] > screen.shape[0]) or (template.shape[1] > screen.shape[1]):
        return None  # the template is bigger than the screen - can't match

    scores = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, best_score, _, best_spot = cv2.minMaxLoc(scores)

    if best_score < threshold:
        return None

    h, w = template.shape[:2]
    return Match(x=best_spot[0], y=best_spot[1], width=w, height=h,
                 confidence=float(best_score))
