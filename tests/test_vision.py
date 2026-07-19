"""Can the bot's eyes actually see?"""

import numpy as np

from yonchbot import vision
from tests.conftest import make_landmark, make_screen


def test_finds_landmark_where_we_put_it():
    landmark = make_landmark(seed=42)
    screen = make_screen(landmark, pos=(200, 100))

    match = vision.find(screen, landmark)

    assert match is not None
    assert match.confidence > 0.99  # exact copy = nearly perfect score
    # the center should be in the middle of where we pasted it
    assert match.center == (200 + 30, 100 + 20)


def test_does_not_see_things_that_are_not_there():
    screen = make_screen(None)  # just noise, no landmark
    landmark = make_landmark(seed=42)

    assert vision.find(screen, landmark) is None


def test_template_bigger_than_screen_is_never_found():
    screen = make_landmark(seed=1)   # tiny image
    template = make_screen(None)     # big image

    assert vision.find(screen, template) is None


def test_low_threshold_makes_the_bot_gullible():
    """With threshold 0, the bot 'finds' the button in pure noise. A lesson!"""
    screen = make_screen(None)
    landmark = make_landmark(seed=42)

    assert vision.find(screen, landmark, threshold=0.0) is not None


def test_sees_red_health_bars():
    """Enemies and loot boxes wear wide short red bars - find them!"""
    screen = make_screen(None)
    screen[100:112, 200:300] = (40, 20, 230)  # a 100x12 bright red bar (BGR!)

    bars = vision.find_red_bars(screen)

    assert len(bars) == 1
    x, y = bars[0]
    assert abs(x - 250) <= 2 and abs(y - 106) <= 2  # middle of our bar


def test_ignores_red_things_that_are_not_bars():
    """The attack button is red too - but it's round-ish, not bar-shaped."""
    screen = make_screen(None)
    screen[100:160, 200:260] = (40, 20, 230)  # a 60x60 red BLOB, not a bar

    assert vision.find_red_bars(screen) == []
