"""The big one: does the whole bot work, start to finish?

We use the ReplayDevice (a pretend phone) to feed the brain a story:
lobby -> match -> match -> match -> match over.
Then we check the bot did the right things at every step.
"""

from yonchbot.brain import Brain
from yonchbot.device import ReplayDevice
from yonchbot.progress import Diary
from yonchbot.screens import ScreenDetector


def quiet(*args, **kwargs):
    """A do-nothing `say` so tests don't print."""


def make_brain(frames, config, templates_dir):
    device = ReplayDevice(frames)
    detector = ScreenDetector(templates_dir)
    diary = Diary(config["diary"]["csv_path"])
    return Brain(device, detector, diary, config, say=quiet), device, diary


def test_plays_a_full_game(config, templates_dir, fake_screens):
    frames = [
        fake_screens["lobby"],
        fake_screens["in_match"],
        fake_screens["in_match"],
        fake_screens["in_match"],
        fake_screens["match_end"],
    ]
    brain, device, diary = make_brain(frames, config, templates_dir)

    games_done = brain.run(max_games=1)

    assert games_done == 1
    # it pressed PLAY in the lobby (landmark center is at 330, 170)
    assert ("tap", 330, 170) in device.actions
    # it moved the joystick during the match (swipes happened)
    swipes = [a for a in device.actions if a[0] == "swipe"]
    assert len(swipes) == 3
    # and the game went into the diary
    games = diary.read_games()
    assert len(games) == 1
    assert games[0]["finished"] == "yes"
    assert games[0]["steps_played"] == "3"


def test_gives_up_when_too_confused(config, templates_dir, fake_screens):
    frames = [fake_screens["mystery"]] * 20  # nothing but mystery screens
    brain, device, diary = make_brain(frames, config, templates_dir)

    games_done = brain.run(max_games=1)

    assert games_done == 0  # it stopped instead of looping forever
    # it saved "help me" screenshots for us to look at
    import os
    stuck_dir = config["safety"]["stuck_screenshots_dir"]
    assert len(os.listdir(stuck_dir)) == config["safety"]["give_up_after_unknowns"]


def test_taps_through_rewards_screen(config, templates_dir, fake_screens):
    frames = [
        fake_screens["rewards"],
        fake_screens["in_match"],    # play at least one step - end screens
        fake_screens["match_end"],   # only count for games we PLAYED
    ]
    brain, device, diary = make_brain(frames, config, templates_dir)

    games_done = brain.run(max_games=1)

    assert games_done == 1
    safe_spot = tuple(config["safety"]["safe_tap_spot"])
    assert ("tap", *safe_spot) in device.actions


def test_leftover_end_screen_does_not_count_as_a_game(config, templates_dir, fake_screens):
    """An end screen we never played for gets cleared, not celebrated."""
    frames = [
        fake_screens["match_end"],   # leftovers from before we started!
        fake_screens["lobby"],
        fake_screens["in_match"],
        fake_screens["in_match"],
        fake_screens["match_end"],   # this one WE earned
    ]
    brain, device, diary = make_brain(frames, config, templates_dir)

    games_done = brain.run(max_games=1)

    assert games_done == 1
    games = diary.read_games()
    assert len(games) == 1                    # exactly one real game logged
    assert games[0]["steps_played"] == "2"    # the one we actually played
