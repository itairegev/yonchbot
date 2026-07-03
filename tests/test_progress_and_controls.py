"""Tests for the diary, the dashboard, and the joystick math."""

from pathlib import Path

from yonchbot import controls
from yonchbot.dashboard import build_dashboard, games_per_day
from yonchbot.device import ReplayDevice
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
