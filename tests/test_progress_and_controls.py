"""Tests for the diary, the dashboard, and the joystick math."""

from pathlib import Path

from yonchbot import controls, device as device_module
from yonchbot.dashboard import build_dashboard, games_per_day
from yonchbot.device import ReplayDevice, list_devices
from yonchbot.progress import Diary
from tests.conftest import make_screen


# ---------- the diary ----------

def test_diary_remembers_games(tmp_path):
    diary = Diary(tmp_path / "games.csv")
    diary.log_game(screens_seen=10, steps_played=25, finished=True)
    diary.log_game(screens_seen=4, steps_played=0, finished=False, notes="got confused")

    games = diary.read_games()
    assert len(games) == 2
    assert games[1]["notes"] == "got confused"

    totals = diary.totals()
    assert totals.games == 2
    assert totals.finished == 1
    assert totals.total_steps == 25


def test_bot_levels_up_every_5_finished_games(tmp_path):
    diary = Diary(tmp_path / "games.csv")
    for _ in range(12):
        diary.log_game(screens_seen=5, steps_played=10, finished=True)

    totals = diary.totals()
    assert totals.bot_level == 3       # 12 games // 5 + 1
    assert totals.next_level_in == 3   # 3 more to reach 15


# ---------- the dashboard ----------

def test_dashboard_builds_a_real_html_page(tmp_path):
    diary = Diary(tmp_path / "games.csv")
    diary.log_game(screens_seen=8, steps_played=20, finished=True)
    out = build_dashboard(diary, tmp_path / "progress.html")

    html = Path(out).read_text()
    assert "YonchBot" in html
    assert "games played" in html
    assert "Lv. 1" in html


def test_dashboard_works_with_empty_diary(tmp_path):
    diary = Diary(tmp_path / "games.csv")  # never written to
    out = build_dashboard(diary, tmp_path / "progress.html")
    assert "No games yet" in Path(out).read_text()


def test_games_per_day_counts_correctly():
    games = [
        {"when": "2026-07-10T10:00:00"},
        {"when": "2026-07-10T11:00:00"},
        {"when": "2026-07-11T09:00:00"},
    ]
    assert games_per_day(games) == [("2026-07-10", 2), ("2026-07-11", 1)]


# ---------- listing connected phones ----------

class FakeProc:
    def __init__(self, text):
        self.stdout = text.encode()


def test_list_devices_reads_ready_phones(monkeypatch):
    output = (
        "List of devices attached\n"
        "R58M20ABCDE\tdevice\n"          # a real phone, ready
        "emulator-5554\tdevice\n"        # an emulator, ready
        "R99OFFLINE99\toffline\n"        # not ready - should be skipped
        "R11UNAUTH11\tunauthorized\n"    # didn't tap Allow - should be skipped
    )
    monkeypatch.setattr(device_module.subprocess, "run",
                        lambda *a, **k: FakeProc(output))
    assert list_devices() == ["R58M20ABCDE", "emulator-5554"]


def test_list_devices_when_none_connected(monkeypatch):
    monkeypatch.setattr(device_module.subprocess, "run",
                        lambda *a, **k: FakeProc("List of devices attached\n\n"))
    assert list_devices() == []


def test_list_devices_when_adb_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(device_module.subprocess, "run", boom)
    assert list_devices() == []


# ---------- the joystick math ----------

def test_joystick_pushes_in_the_right_directions():
    device = ReplayDevice([make_screen(None)])
    anchor = (100, 300)

    controls.joystick_push(device, anchor, angle_degrees=0, distance=50)    # right
    controls.joystick_push(device, anchor, angle_degrees=90, distance=50)   # up
    controls.joystick_push(device, anchor, angle_degrees=180, distance=50)  # left
    controls.joystick_push(device, anchor, angle_degrees=270, distance=50)  # down

    swipes = [a for a in device.actions if a[0] == "swipe"]
    (_, _, _, right_x, right_y, _) = swipes[0]
    (_, _, _, up_x, up_y, _) = swipes[1]
    (_, _, _, left_x, left_y, _) = swipes[2]
    (_, _, _, down_x, down_y, _) = swipes[3]

    assert right_x == 150 and right_y == 300   # moved right, same height
    assert up_x == 100 and up_y == 250         # up = SMALLER y on a screen!
    assert left_x == 50 and left_y == 300
    assert down_x == 100 and down_y == 350


# ---------- the aiming math ----------

def test_angle_towards_matches_the_compass():
    from yonchbot.play import angle_towards
    here = (100, 100)
    assert angle_towards(here, (200, 100)) == 0    # target to the right
    assert angle_towards(here, (100, 50)) == 90    # up = SMALLER y!
    assert angle_towards(here, (0, 100)) == 180    # left
    assert angle_towards(here, (100, 200)) == 270  # down


def test_hunting_walks_and_shoots_toward_the_red_bar(config):
    """A red bar on screen = walk at it and fire an AIMED shot (no blind taps)."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[100:112, 500:600] = (40, 20, 230)  # red bar, up and to the right

    play.play_step(device, config, step=0, screenshot=screenshot)

    swipes = [a for a in device.actions if a[0] == "swipe"]
    taps = [a for a in device.actions if a[0] == "tap"]
    assert len(swipes) == 2   # one walk + one aimed shot
    assert taps == []         # no blind auto-aim tap while hunting
    # both the walk and the shot head up-and-right (bigger x, smaller y)
    for _, x1, y1, x2, y2, _ in swipes:
        assert x2 > x1 and y2 < y1


def test_kites_away_from_enemies_but_shoots_at_them(config):
    """An enemy (red bar WITH a name) = feet go one way, trigger the other."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[100:112, 500:600] = (40, 20, 230)   # red bar up-and-right...
    screenshot[70:85, 490:610] = (255, 255, 255)   # ...wearing a white name tag

    play.play_step(device, config, step=2, screenshot=screenshot)

    swipes = [a for a in device.actions if a[0] == "swipe"]
    walk = next(s for s in swipes if (s[1], s[2]) == (100, 300))   # joystick
    shot = next(s for s in swipes if (s[1], s[2]) == (550, 310))   # attack drag
    _, x1, y1, x2, y2, _ = shot
    assert x2 > x1 and y2 < y1        # shot points AT the enemy (up-right)
    _, x1, y1, x2, y2, _ = walk
    assert x2 < x1 and y2 > y1        # feet run AWAY (down-left)


def test_runs_away_from_the_poison_gas(config):
    """A big pale-green cloud on the left = run right, no arguing."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[100:300, 0:100] = (170, 250, 170)   # pale green wall on the LEFT

    play.play_step(device, config, step=1, screenshot=screenshot)

    walk = next(a for a in device.actions if a[0] == "swipe")
    _, x1, y1, x2, y2, _ = walk
    assert x2 > x1                    # feet head RIGHT, away from the cloud


def test_sneaks_into_bushes_when_nothing_is_happening(config):
    """No enemies, no boxes, no gas = go hide in the nearest bush."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[60:180, 460:620] = (35, 80, 35)     # dark green bush, up-right

    play.play_step(device, config, step=1, screenshot=screenshot)

    walk = next(a for a in device.actions if a[0] == "swipe")
    _, x1, y1, x2, y2, _ = walk
    assert x2 > x1 and y2 < y1        # feet sneak up-and-right, to the bush


# ---------- lessons from watching a human win ----------

def test_fires_the_super_when_it_glows(config):
    """Charged super + visible enemy = unleash it AT them."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[100:112, 500:600] = (40, 20, 230)    # enemy bar up-right...
    screenshot[70:85, 490:610] = (255, 255, 255)    # ...with a name tag
    screenshot[200:300, 450:550] = (0, 215, 255)    # super button GLOWING yellow

    play.play_step(device, config, step=1, screenshot=screenshot)

    supers = [s for s in device.actions
              if s[0] == "swipe" and (s[1], s[2]) == (500, 250)]
    assert len(supers) == 1           # the super was fired...
    _, x1, y1, x2, y2, _ = supers[0]
    assert x2 > x1 and y2 < y1        # ...straight at the enemy (up-right)


def test_finishes_close_enemies_when_strong(config):
    """3+ cubes collected and an enemy within reach = go end the fight."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[140:152, 360:460] = (40, 20, 230)    # enemy bar, CLOSE, up-right
    screenshot[110:125, 350:470] = (255, 255, 255)  # name tag

    play.MEMORY["cubes"] = 3          # we are strong (test sets this directly)
    play.play_step(device, config, step=1, screenshot=screenshot)

    walk = next(s for s in device.actions
                if s[0] == "swipe" and (s[1], s[2]) == (100, 300))
    _, x1, y1, x2, y2, _ = walk
    assert x2 > x1 and y2 < y1        # feet go TOWARD the enemy - finish them


def test_focus_fire_sticks_to_the_wounded_enemy(config):
    """Once we're shooting someone, a NEW closer enemy doesn't distract us."""
    from yonchbot import play
    device = ReplayDevice([make_screen(None), make_screen(None)])

    first_look = make_screen(None)
    first_look[100:112, 500:600] = (40, 20, 230)    # enemy A, up-right
    first_look[70:85, 490:610] = (255, 255, 255)
    play.play_step(device, config, step=2, screenshot=first_look)  # focus on A

    second_look = make_screen(None)
    second_look[260:272, 500:600] = (40, 20, 230)   # A again, moved DOWN-right
    second_look[230:245, 490:610] = (255, 255, 255)
    second_look[60:72, 260:360] = (40, 20, 230)     # brand-new enemy B, closer!
    second_look[30:45, 250:370] = (255, 255, 255)
    device.actions.clear()
    play.play_step(device, config, step=3, screenshot=second_look)

    shot = next(s for s in device.actions
                if s[0] == "swipe" and (s[1], s[2]) == (550, 310))
    _, x1, y1, x2, y2, _ = shot
    assert x2 > x1 and y2 > y1     # still hammering A (down-right), not B


def test_leads_a_moving_target(config):
    """A running enemy gets shot at where they're GOING, not where they are."""
    import math
    import time
    from yonchbot import play
    device = ReplayDevice([make_screen(None), make_screen(None)])

    look1 = make_screen(None)
    look1[100:112, 250:350] = (40, 20, 230)     # enemy at x=300...
    look1[70:85, 240:360] = (255, 255, 255)
    play.play_step(device, config, step=2, screenshot=look1)

    time.sleep(0.3)   # speed is pixels per SECOND - let real time pass

    look2 = make_screen(None)
    look2[100:112, 450:550] = (40, 20, 230)     # ...now at x=500: running RIGHT
    look2[70:85, 440:560] = (255, 255, 255)
    device.actions.clear()
    play.play_step(device, config, step=4, screenshot=look2)

    shot = next(s for s in device.actions
                if s[0] == "swipe" and (s[1], s[2]) == (550, 310))
    _, x1, y1, x2, y2, _ = shot
    assert x2 > x1
    # the shot's angle must sit FLATTER (further right) than a straight
    # shot at where the enemy stands - that's the lead
    aimed = math.degrees(math.atan2(y1 - y2, x2 - x1))
    body = (500, 106 + round(360 * 0.075))
    at_them = play.angle_towards((320, 180), body)
    assert aimed < at_them - 1


def test_football_mode_runs_from_enemy_battles(config):
    """Owner's plan (2026-07-25): 'run from enemy battles'. A lone enemy with
    NO ball to contest is not a fight to win - it's a fight to AVOID. So the
    bot picks fall_back and its feet move AWAY from the enemy, not toward it."""
    from yonchbot import play
    config["match"]["football"] = True
    device = ReplayDevice([make_screen(None)])
    screenshot = make_screen(None)
    screenshot[100:112, 500:600] = (40, 20, 230)   # enemy up-right, no ball
    screenshot[70:85, 490:610] = (255, 255, 255)

    play.MEMORY["carry_steps"] = 0
    play.MEMORY["focus"] = None
    play.play_step(device, config, step=1, screenshot=screenshot)

    walk = next(s for s in device.actions
                if s[0] == "swipe" and (s[1], s[2]) == (100, 300))
    _, x1, y1, x2, y2, _ = walk
    # The enemy is UP the screen; fleeing means the feet move DOWN, away from
    # it (y grows). This is the deliberate reversal of the old "brave" test.
    # (We don't assert the x direction - a small strafe wiggle rides on top.)
    assert y2 > y1     # feet RETREAT downward, away from the up-screen enemy
