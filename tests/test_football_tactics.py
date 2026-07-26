"""The Brawl Ball rulebook, in tests - one per coaching rule.

Sources and reasoning live in docs/brawl-ball-tactics-research.md.
Screen geometry reminder: 640x360 fake screens, we are at (320, 180),
our goal is the BOTTOM edge, theirs is the TOP.
"""

from yonchbot import play
from yonchbot.device import ReplayDevice
from tests.conftest import make_screen


def football(config):
    config["match"]["football"] = True
    config["match"]["shoot_range"] = 0.12   # Edgar's short arms
    config["match"]["kick_range"] = 100     # 220 real px, scaled to the
    return config                           # little 640px test screens


def add_enemy(screen, x, y):
    screen[y:y + 12, x - 50:x + 50] = (40, 20, 230)      # red bar
    screen[y - 30:y - 15, x - 60:x + 60] = (255, 255, 255)  # name tag


def carry_the_ball():
    """The ball hides under our feet while we carry it."""
    play.MEMORY["carry_steps"] = 3


def test_carrier_marches_the_golden_window_then_shoots(config):
    """Nobody on screen = the golden respawn window: march the ball up
    for a few beats FIRST (free ground!), then auto-aim it at the goal."""
    frame = make_screen(None)
    device = ReplayDevice([frame] * 3)
    carry_the_ball()
    attack_spot = tuple(config["match"]["attack_button"])

    play.play_step(device, football(config), step=1, screenshot=frame)
    play.play_step(device, football(config), step=2, screenshot=frame)
    assert ("tap", *attack_spot) not in device.actions   # still marching

    play.play_step(device, football(config), step=3, screenshot=frame)
    assert ("tap", *attack_spot) in device.actions       # NOW shoot


def test_never_chases_a_guarded_ball(config):
    """'Control first, ball second': a loose ball with two guards on it
    is bait - the bot must hold its shape, not sprint in and feed."""
    screenshot = make_screen(None)
    paint_ball(screenshot, 320, 60)    # ball far upfield, out of reach...
    add_enemy(screenshot, 200, 120)    # ...with two enemies guarding it
    add_enemy(screenshot, 450, 110)    # (placed clear of the ball's pixels)
    device = ReplayDevice([screenshot])

    play.play_step(device, football(config), step=1, screenshot=screenshot)

    jx, jy = config["match"]["joystick_anchor"]
    walk = next(a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (jx, jy))
    _, _, y1, _, y2, _ = walk
    assert y2 > y1   # feet go DOWN into defensive shape, not up into the trap


def test_contested_carrier_kicks_up_never_down(config):
    """Crowded carrier = pass UP immediately (a carrier can't punch)."""
    screenshot = make_screen(None)
    add_enemy(screenshot, 360, 150)   # an enemy right next to us
    device = ReplayDevice([screenshot])
    carry_the_ball()
    play.play_step(device, football(config), step=1, screenshot=screenshot)

    bx, by = config["match"]["attack_button"]
    kicks = [a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (bx, by)]
    assert len(kicks) == 1
    _, _, y1, _, y2, _ = kicks[0]
    assert y2 < y1   # the kick flies UP - never toward our own goal


def test_contested_kick_bends_away_from_defenders(config):
    """'Never pass to the opponents': with a defender ahead-RIGHT, the
    escape kick must fly up-LEFT - upfield, but not into their hands."""
    screenshot = make_screen(None)
    add_enemy(screenshot, 400, 130)    # defender ahead of us, to the right
    device = ReplayDevice([screenshot])
    carry_the_ball()
    play.play_step(device, football(config), step=1, screenshot=screenshot)

    bx, by = config["match"]["attack_button"]
    kick = next(a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (bx, by))
    _, x1, y1, x2, y2, _ = kick
    assert y2 < y1        # upfield, always
    assert x2 < x1        # and bent LEFT, away from the defender


def test_edgar_holds_his_punches_at_long_range(config):
    """An enemy across the field is out of punch reach - no wild swings."""
    screenshot = make_screen(None)
    add_enemy(screenshot, 600, 60)    # far away, up-right
    device = ReplayDevice([screenshot])
    play.play_step(device, football(config), step=1, screenshot=screenshot)

    bx, by = config["match"]["attack_button"]
    swings = [a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (bx, by)]
    assert swings == []


def paint_ball(screen, x, y):
    """Draw a ball the way vision.find_ball hunts for it: a solid disc
    of the ball's exact dark-orange (given in HSV, the detector's language)."""
    import cv2
    import numpy as np
    hsv_ball = np.full((64, 64, 3), (15, 220, 160), dtype=np.uint8)
    screen[y - 32:y + 32, x - 32:x + 32] = cv2.cvtColor(hsv_ball, cv2.COLOR_HSV2BGR)


def test_stalls_to_protect_a_late_lead(config):
    """Coach's rule: up 1-0 late in the game with the ball at our feet,
    the smartest kick is NO kick. Walk it to a corner and keep it."""
    frame = make_screen(None)
    device = ReplayDevice([frame])
    carry_the_ball()

    play.play_step(device, football(config), step=95, screenshot=frame,
                   scores=(1, 0))

    bx, by = config["match"]["attack_button"]
    kicks = [a for a in device.actions if (a[1], a[2]) == (bx, by)]
    assert kicks == []             # no kick, no tap - possession is the win
    walks = [a for a in device.actions if a[0] == "swipe"]
    assert len(walks) == 1         # but the feet keep moving (no AFK kick!)


def test_never_walks_in_a_straight_line_under_fire(config):
    """Coach's rule: micro-strafe. Two steps toward the same enemy must
    NOT trace the same line - the zigzag is what makes skillshots miss."""
    screenshot = make_screen(None)
    add_enemy(screenshot, 380, 150)    # a close enemy - we're in a fight
    device = ReplayDevice([screenshot, screenshot])

    play.play_step(device, football(config), step=1, screenshot=screenshot)
    play.play_step(device, football(config), step=2, screenshot=screenshot)

    jx, jy = config["match"]["joystick_anchor"]
    walks = [a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (jx, jy)]
    assert len(walks) == 2
    assert (walks[0][3], walks[0][4]) != (walks[1][3], walks[1][4])


def test_counts_a_landed_punch_by_the_shrinking_health_bar(config):
    """Punch an enemy, and next look their red bar is NARROWER: that's
    a receipt. The hits ledger must count exactly one hit."""
    before = make_screen(None)
    before[144:156, 330:430] = (40, 20, 230)       # enemy close, full 100px bar
    before[114:129, 320:440] = (255, 255, 255)     # name tag

    after = make_screen(None)
    after[144:156, 330:400] = (40, 20, 230)        # same enemy, bar now 70px
    after[114:129, 320:440] = (255, 255, 255)

    device = ReplayDevice([before, after])
    cfg = football(config)
    play.play_step(device, cfg, step=1, screenshot=before)   # swings (in range)
    assert play.MEMORY["swung_at"] is not None
    play.play_step(device, cfg, step=2, screenshot=after)    # sees the receipt
    assert play.MEMORY["hits"] == 1

    # a THIRD look with no new swing must not double-count
    play.play_step(device, cfg, step=3, screenshot=after)
    assert play.MEMORY["hits"] == 1


def test_defends_own_goal_when_enemy_has_the_ball(config):
    """Ball deep in our half with an enemy on it: run DOWN to block,
    don't chase from behind."""
    screenshot = make_screen(None)
    paint_ball(screenshot, 320, 300)   # ball low, on OUR half
    add_enemy(screenshot, 380, 290)    # with an enemy right on it
    assert play.vision.find_ball(screenshot) is not None, "test needs a visible ball"
    device = ReplayDevice([screenshot])

    play.play_step(device, football(config), step=1, screenshot=screenshot)

    jx, jy = config["match"]["joystick_anchor"]
    walk = next(a for a in device.actions if a[0] == "swipe" and (a[1], a[2]) == (jx, jy))
    _, _, y1, _, y2, _ = walk
    assert y2 > y1   # feet head DOWN, between the ball and our goal
