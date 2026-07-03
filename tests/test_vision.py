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
