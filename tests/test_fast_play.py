"""Tests for the "play faster, play smarter" upgrade of 2026-07-22.

The coach's feedback: the bot stood still, walked into walls, and shot
where enemies USED to be. Every test here pins down one of the fixes.
"""

import numpy as np
import pytest

from yonchbot import device as device_module, play, vision
from yonchbot.device import AdbDevice, ReplayDevice
from yonchbot.screens import Screen, ScreenDetector
from tests.conftest import SEEDS, make_landmark, make_screen


# ---------- eyes: did the world slide past the camera? ----------

def test_camera_shift_sees_the_world_slide():
    before = make_screen(None, bg_seed=5)
    after = np.roll(before, 40, axis=1)  # the whole world slides 40px right

    view_a = vision.travel_view(before)
    view_b = vision.travel_view(after)

    assert vision.camera_shift(view_a, view_a) < 1     # same look = no move
    assert vision.camera_shift(view_a, view_b) > 3     # slid = we walked!


# ---------- feet: walking into a wall triggers a sidestep ----------

def test_walking_into_a_wall_triggers_a_detour(config):
    """If we pushed the joystick but the scenery never moved, we're
    stuck on an obstacle - the bot must pick a detour direction."""
    frame = make_screen(None, bg_seed=3)
    dev = ReplayDevice([frame, frame, frame])

    play.play_step(dev, config, step=0, screenshot=frame)   # walks somewhere
    assert play.MEMORY["detour_steps"] == 0                 # no verdict yet
    play.play_step(dev, config, step=1, screenshot=frame)   # world didn't move!
    assert play.MEMORY["detour_steps"] > 0                  # sidestep planned


def test_moving_normally_needs_no_detour(config):
    frame_a = make_screen(None, bg_seed=3)
    frame_b = np.roll(frame_a, 60, axis=1)  # world slid = we really moved
    dev = ReplayDevice([frame_a, frame_b])

    play.play_step(dev, config, step=0, screenshot=frame_a)
    play.play_step(dev, config, step=1, screenshot=frame_b)
    assert play.MEMORY["detour_steps"] == 0


# ---------- trigger: aim where the runner WILL be ----------

def test_prediction_leads_a_running_enemy():
    """Enemy ran 60px right in 0.15s; the bullet needs ~0.12s to reach
    them - so the aim point must sit AHEAD of them, to the right."""
    us = (320, 180)
    aim = play.predict_spot(spot=(560, 133), prev=(500, 133), dt=0.15, us=us)
    assert aim[1] == 133          # still the same height...
    assert 595 <= aim[0] <= 625   # ...but ~50px ahead of where they ARE


def test_prediction_leaves_standing_enemies_alone():
    aim = play.predict_spot(spot=(560, 133), prev=(560, 133), dt=0.15,
                            us=(320, 180))
    assert aim == (560, 133)


def test_prediction_ignores_impossible_jumps():
    """A 'runner' that crossed half the screen in a blink is really a
    DIFFERENT enemy - aim at where we see them, don't extrapolate."""
    aim = play.predict_spot(spot=(1500, 133), prev=(200, 133), dt=0.15,
                            us=(320, 180))
    assert aim == (1500, 133)


# ---------- hands: walking must not block thinking ----------

class FakeGesture:
    """Pretends to be a still-running `adb shell input swipe` process."""

    def __init__(self):
        self.waited = False

    def wait(self, timeout=None):
        self.waited = True


def test_walk_swipe_can_run_in_the_background(monkeypatch):
    launched = []

    def fake_popen(cmd, **kwargs):
        launched.append(cmd)
        return FakeGesture()

    monkeypatch.setattr(device_module.subprocess, "Popen", fake_popen)
    dev = AdbDevice()

    dev.swipe(0, 0, 100, 100, ms=800, wait=False)  # walk, don't wait
    assert len(launched) == 1                       # gesture launched...
    assert dev._walking is not None                 # ...and still running

    # The NEXT gesture must politely wait for the walking finger to lift
    # (two fingers fighting over the same screen = chaos).
    monkeypatch.setattr(dev, "_adb", lambda *a: b"")
    walking = dev._walking
    dev.tap(5, 5)
    assert walking.waited
    assert dev._walking is None


# ---------- eyes: raw screenshots (no slow PNG squeezing) ----------

def test_screenshot_decodes_raw_pixels(monkeypatch):
    w, h = 4, 2
    header = np.array([w, h, 1], dtype="<u4").tobytes()  # width, height, RGBA
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 200  # red channel (raw screencap speaks RGBA)
    rgba[..., 3] = 255

    dev = AdbDevice()
    monkeypatch.setattr(dev, "_adb", lambda *args: header + rgba.tobytes())

    img = dev.screenshot()
    assert img.shape == (h, w, 3)
    assert img[0, 0, 2] == 200  # ...but our images speak BGR: red is LAST


# ---------- eyes: reading the score off the top bars ----------

def test_reads_the_score_digits():
    rng = np.random.default_rng(11)
    digits = {0: rng.integers(0, 80, (40, 30, 3), dtype=np.uint8),
              1: rng.integers(175, 255, (40, 30, 3), dtype=np.uint8)}
    screen = make_screen(None)
    screen[20:60, 100:130] = digits[1]           # "1" pasted in the score box

    assert vision.read_score(screen, [80, 10, 100, 60], digits) == 1
    # a box with no digit in it reads as None - not a wild guess
    assert vision.read_score(screen, [400, 200, 100, 60], digits) is None


# ---------- memory: landmarks are found FAST the second time ----------

def test_detector_remembers_where_landmarks_live(templates_dir, fake_screens):
    detector = ScreenDetector(templates_dir)

    assert detector.which_screen(fake_screens["lobby"]) == Screen.LOBBY
    # Second look should use the remembered spot - and still be right.
    assert detector.which_screen(fake_screens["lobby"]) == Screen.LOBBY
    # A remembered spot must never make the bot hallucinate...
    assert detector.which_screen(fake_screens["mystery"]) == Screen.UNKNOWN
    # ...and if the button MOVED, the full search must still find it.
    moved = make_screen(make_landmark(SEEDS["play_button.png"]), pos=(50, 40))
    assert detector.which_screen(moved) == Screen.LOBBY
