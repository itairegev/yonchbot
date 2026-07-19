"""Does the bot know which game screen it's looking at?"""

from yonchbot.screens import Screen, ScreenDetector


def test_recognizes_every_screen(templates_dir, fake_screens):
    detector = ScreenDetector(templates_dir)

    assert detector.which_screen(fake_screens["lobby"]) == Screen.LOBBY
    assert detector.which_screen(fake_screens["in_match"]) == Screen.IN_MATCH
    assert detector.which_screen(fake_screens["match_end"]) == Screen.MATCH_END
    assert detector.which_screen(fake_screens["rewards"]) == Screen.REWARDS


def test_mystery_screen_is_unknown(templates_dir, fake_screens):
    detector = ScreenDetector(templates_dir)
    assert detector.which_screen(fake_screens["mystery"]) == Screen.UNKNOWN


def test_reports_missing_templates(tmp_path):
    empty_dir = tmp_path / "no_templates_here"
    empty_dir.mkdir()
    detector = ScreenDetector(empty_dir)
    assert len(detector.missing_templates) == 7


def test_finds_where_the_play_button_is(templates_dir, fake_screens):
    detector = ScreenDetector(templates_dir)
    match = detector.find_landmark(fake_screens["lobby"], Screen.LOBBY)
    assert match is not None
    assert match.center == (330, 170)  # pasted at (300,150), size 60x40
