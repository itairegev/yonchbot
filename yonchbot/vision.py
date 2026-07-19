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


def find_red_bars(screen: np.ndarray) -> list[tuple[int, int]]:
    """Find the red health bars floating over enemies and loot boxes.

    Anything worth shooting in a match wears a little red bar above it.
    So instead of teaching the bot what every brawler looks like, we
    just look for "wide, short, VERY red rectangles". That's it!

    Returns a list of (x, y) centers of the bars we found.
    """
    # HSV is a way of describing color by "which color" (hue) instead of
    # mixing blue+green+red - much easier to say "find RED" in.
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    # Red sits at BOTH ends of the hue circle, so we need two ranges.
    strong_red = cv2.inRange(hsv, (0, 150, 150), (10, 255, 255)) | \
                 cv2.inRange(hsv, (170, 150, 150), (180, 255, 255))
    # Clean-up, in two moves (order matters!):
    #   1. OPEN  = erase lone red specks (a bar survives, dust doesn't)
    #   2. CLOSE = bridge tiny gaps so a bar counts as ONE shape
    # (We keep the un-smoothed mask too - see the solid-red check below.)
    smoothed = cv2.morphologyEx(strong_red, cv2.MORPH_OPEN,
                                np.ones((3, 3), np.uint8))
    smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE,
                                np.ones((3, 9), np.uint8))

    bars = []
    contours, _ = cv2.findContours(smoothed, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # A health bar is wide and short. These numbers filter out
        # red decorations (too small) and the attack button (too tall).
        if not (w >= 3 * h and 40 <= w <= 220 and 5 <= h <= 18):
            continue
        # And a real bar is SOLID red - random red speckles that the
        # smoothing glued together are not. So we check the ORIGINAL
        # mask (before smoothing): at least 60% must be truly red.
        box = strong_red[y:y + h, x:x + w]
        if cv2.countNonZero(box) >= 0.6 * w * h:
            bars.append((x + w // 2, y + h // 2))
    return bars


def has_name_tag(screen: np.ndarray, bar_center: tuple[int, int]) -> bool:
    """Is there a player NAME written above this red bar?

    This is how we tell an enemy from a loot box: enemies walk around
    with their name in bright letters over their head - boxes are shy
    and don't introduce themselves. So we peek at the strip just above
    the bar and count bright, white-ish "letter" pixels.
    """
    x, y = bar_center
    strip = screen[max(0, y - 38):max(0, y - 8), max(0, x - 90):x + 90]
    if strip.size == 0:
        return False
    white = cv2.inRange(strip, (240, 240, 240), (255, 255, 255))
    return cv2.countNonZero(white) > 100  # a name has LOTS of white pixels


def find_ball(screen: np.ndarray) -> tuple[int, int] | None:
    """Find the Brawl Ball ball - the whole point of football!

    The ball is a dark-orange sphere. Tricky part: crates and barrels
    are orange too! But they're BRIGHT and boxy, while the ball is
    darker and round. So: orange + not-too-bright + round-ish + solid.
    """
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, (10, 180, 90), (20, 255, 220))
    orange = cv2.morphologyEx(orange, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(orange, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        round_ish = 0.8 <= w / h <= 1.25 if h else False
        big_enough = 50 <= w <= 90 and 50 <= h <= 90
        solid = cv2.contourArea(contour) >= 0.55 * w * h  # a disc, not an edge
        if round_ish and big_enough and solid:
            return (x + w // 2, y + h // 2)
    return None


def super_is_ready(screen: np.ndarray, button_center: tuple[int, int]) -> bool:
    """Is the SUPER button glowing yellow (fully charged)?

    The skull button is dark blue while the super charges, and turns
    bright YELLOW when it's ready. We watched a human win with a
    perfectly-timed super - so the bot learned to check for the glow.
    """
    x, y = button_center
    region = screen[max(0, y - 55):y + 55, max(0, x - 55):x + 55]
    if region.size == 0:
        return False
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (18, 150, 180), (35, 255, 255))
    # Threshold is deliberately forgiving: the ready glow looks different
    # per brawler (Shelly floods the button, Nita just wears the ring).
    # Trying to fire an uncharged super costs nothing - missing a charged
    # one costs the match.
    return cv2.countNonZero(yellow) > 0.08 * region.shape[0] * region.shape[1]


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
