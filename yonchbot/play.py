"""How the bot plays a match. THIS is the fun file to tweak!

Every heartbeat has three parts, like a real player:

  SEE     - look at the screenshot once and understand everything:
            where's the ball? enemies? are we carrying? are we stuck?
  CHOOSE  - pick ONE tactic for this beat (the rule ladder below - or,
            in training mode, the learning pilot from rl.py picks!)
  ACT     - run the tactic: feet on the joystick, thumb on the trigger.

The five tactics (see docs/brawl-ball-tactics-research.md for why):

  chase_ball  - the ball is the objective. Go get it.
  push_north  - we HAVE the ball: advance it. Kick smart, never down.
  fight       - punch the nearest enemy (only in Edgar's short reach!).
  fall_back   - they're attacking our goal: get between ball and net.
  super_play  - unleash the Super to break through a crowd.

The movement patterns live in PATTERNS. Each one is just a list of
compass angles (degrees) the bot walks in, one after another, in a loop.

Ideas to try:
  * add your own pattern (a square? a star? your initials?)
  * tweak the rule ladder in choose_tactic - can you beat it?
  * make a "scaredy-cat" mode: when OUR health is low, run AWAY
    from the red bars instead of toward them
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np

from . import controls, vision

# name -> list of walking angles, done in order, repeating.
# 90 = up, 0 = right, 180 = left, 270 = down (see controls.py)
PATTERNS: dict[str, list[float]] = {
    # walk in a circle-ish octagon
    "circle": [0, 45, 90, 135, 180, 225, 270, 315],
    # sneak up the map in a zigzag
    "zigzag": [60, 120, 60, 120],
    # mostly sit still (in a bush, we hope), tiny shuffles
    "bush_camper": [90, 270],
    # totally random - chaos mode!
    "headless_chicken": [],
}

# The five football tactics, in one fixed order - the learning pilot
# (rl.py) refers to them by number, so the order must never change.
TACTICS = ["chase_ball", "push_north", "fight", "fall_back", "super_play"]


def next_angle(pattern_name: str, step: int) -> float:
    """Which direction to walk on step number `step`."""
    angles = PATTERNS.get(pattern_name, PATTERNS["circle"])
    if not angles:  # empty list = random chaos
        return random.uniform(0, 360)
    return angles[step % len(angles)]


def angle_towards(here: tuple[int, int], there: tuple[int, int]) -> float:
    """The compass angle to walk (or shoot) to get from `here` to `there`.

    Remember session 2: y counts DOWNWARD on screens. So we flip the
    up-down part before asking atan2 (the "which angle is this" function).
    """
    dx = there[0] - here[0]
    dy = here[1] - there[1]  # flipped on purpose!
    return math.degrees(math.atan2(dy, dx)) % 360


def gas_escape_angle(screenshot) -> float | None:
    """If the poison gas is closing in, which way is OUT?

    The gas is a huge pale-green cloud. We paint every pale-green pixel
    white on a mask, and if that's a lot of the screen (>5%), we find the
    CENTER of all that green (its "average spot") and run the exact
    opposite way. If there's barely any green, we're safe - return None.
    """
    hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
    gas = cv2.inRange(hsv, (40, 40, 150), (80, 180, 255))
    # Shrink the mask a little: a real cloud is HUGE and survives,
    # stray green pixels (grass, sparkles) vanish.
    gas = cv2.erode(gas, np.ones((5, 5), np.uint8))
    if cv2.countNonZero(gas) < 0.04 * gas.size:
        return None
    ys, xs = np.nonzero(gas)
    gas_center = (int(xs.mean()), int(ys.mean()))
    height, width = screenshot.shape[:2]
    us = (width // 2, height // 2)
    return (angle_towards(us, gas_center) + 180) % 360  # AWAY from it!


def bush_direction(screenshot) -> float | None:
    """Which way to the nearest bush worth hiding in? None if no bush.

    Bushes are the DARK rich green tufts (the poison gas is pale green -
    different color, different feeling!). We find every bushy patch big
    enough to hide a brawler and head for the closest one. A nice bonus:
    once we're IN the bush, "walk toward the bush" just makes us shuffle
    in place - hidden but never standing still.
    """
    hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
    bush = cv2.inRange(hsv, (50, 100, 40), (75, 255, 140))
    bush = cv2.erode(bush, np.ones((5, 5), np.uint8))
    height, width = screenshot.shape[:2]
    us = (width // 2, height // 2)
    best, best_d2 = None, None
    contours, _ = cv2.findContours(bush, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        if cv2.contourArea(contour) < 3000:   # too small to hide in
            continue
        x, y, w, h = cv2.boundingRect(contour)
        spot = (x + w // 2, y + h // 2)
        d2 = (spot[0] - us[0]) ** 2 + (spot[1] - us[1]) ** 2
        if best is None or d2 < best_d2:
            best, best_d2 = spot, d2
    if best is None:
        return None
    return angle_towards(us, best)


def predict_spot(spot, prev, dt, us, bullet_speed=2000, speed_cap=450):
    """Where will a runner BE when our bullet lands? Aim THERE.

    A shot isn't instant: it flies for (distance / bullet_speed) seconds.
    From two looks we know the runner's speed (pixels per real second -
    looks aren't evenly spaced, so we divide by actual time!). Multiply
    speed by the bullet's flight time = how far ahead to aim.

    spot = where they are NOW, prev = where they were dt seconds ago,
    us   = our own position (bullets start from us).
    """
    if prev is None or dt <= 0.05:
        return spot
    vx, vy = (spot[0] - prev[0]) / dt, (spot[1] - prev[1]) / dt
    speed = (vx * vx + vy * vy) ** 0.5
    if speed > 2 * speed_cap:
        return spot  # nobody runs THAT fast - it's a different enemy
    if speed > speed_cap:  # a wobbly reading - trust the cap, not the blur
        vx, vy = vx * speed_cap / speed, vy * speed_cap / speed
    flight = math.dist(us, spot) / bullet_speed
    return (spot[0] + round(vx * flight), spot[1] + round(vy * flight))


# The bot's tiny short-term memory: after a box breaks, keep walking to
# where it stood for a couple heartbeats to scoop up the power cubes -
# and count every pickup, because cubes = strength = permission to fight.
MEMORY = {"loot_angle": None, "loot_steps": 0, "cubes": 0,
          "focus": None, "focus_prev": None, "carry_steps": 0,
          "focus_time": None, "focus_prev_time": None,
          "last_view": None, "walked": None, "detour": None, "detour_steps": 0,
          "last_shift": 0.0,
          # the punch ledger: who we swung at, how much health they had,
          # and how many punches LANDED this match (the bar-width receipt)
          "swung_at": None, "swing_width": 0, "hits": 0}

# If the camera slid LESS than this (in postcard pixels) after a joystick
# push, we didn't really move - we're pressed against a wall or a crate.
# Measured from real games: standing still reads ~0-3, walking reads 10+.
STUCK_SHIFT = 3.0


def check_for_wall(screenshot) -> None:
    """Did our last step actually MOVE us? If not, plan a sidestep.

    Walls and crates don't show up on our radar - but physics does.
    We compare this look with the previous one: when we walk, the whole
    world slides past the camera (it follows us!). Pushed the joystick
    and the world stood still? We're walking into something. Sidestep
    left or right for two beats and try again.
    """
    view = vision.travel_view(screenshot)
    shift = vision.camera_shift(MEMORY["last_view"], view) \
        if MEMORY["last_view"] is not None else 0.0
    MEMORY["last_shift"] = shift  # the learning pilot likes to know this
    if MEMORY["walked"] is not None and MEMORY["last_view"] is not None and \
            shift < STUCK_SHIFT:
        MEMORY["detour"] = (MEMORY["walked"] + random.choice((-90, 90))) % 360
        MEMORY["detour_steps"] = 2
    MEMORY["last_view"] = view


def walk_or_detour(walk: float, urgent: bool = False) -> float:
    """The chosen direction - unless a wall sidestep is in progress.

    urgent=True (fleeing poison gas!) skips the sidestep: better to rub
    against a wall than to argue with poison.
    """
    if MEMORY["detour_steps"] > 0 and not urgent:
        MEMORY["detour_steps"] -= 1
        walk = MEMORY["detour"]
    MEMORY["walked"] = walk  # remember it, so check_for_wall can judge it
    return walk


# ---------------------------------------------------------------- SEE --

def see(screenshot, config: dict, step: int) -> dict:
    """LOOK at one screenshot and understand everything at once.

    Returns one dict of facts ("the world as we see it") that both the
    rule ladder and the learning pilot read. One look, many readers.
    """
    if step == 0:  # fresh match, fresh memory (BOTH pilots pass through here)
        MEMORY["loot_angle"], MEMORY["loot_steps"] = None, 0
        MEMORY["cubes"], MEMORY["focus"], MEMORY["focus_prev"] = 0, None, None
        MEMORY["carry_steps"], MEMORY["carry_beats"] = 0, 0
        MEMORY["focus_time"], MEMORY["focus_prev_time"] = None, None
        MEMORY["last_view"], MEMORY["walked"] = None, None
        MEMORY["detour"], MEMORY["detour_steps"] = None, 0
        MEMORY["last_shift"] = 0.0
        MEMORY["swung_at"], MEMORY["swing_width"], MEMORY["hits"] = None, 0, 0

    ctx = {"screenshot": screenshot, "us": None, "enemies": [], "boxes": [],
           "escape": None, "ball": None, "near_ball": False,
           "carrying": False, "crowd": [], "defenders": [], "focus": None,
           "width": 0, "height": 0, "reach": 0, "enemy_bars": [],
           "hit_confirmed": False}
    if screenshot is None:
        return ctx

    check_for_wall(screenshot)
    height, width = screenshot.shape[:2]
    us = (width // 2, height // 2)  # the camera follows us = we ARE the center
    ctx.update(width=width, height=height, us=us)

    ctx["enemy_bars"] = []   # (x, y, width) - width = health LEFT
    for bx, by, bw in vision.find_red_bars_wide(screenshot):
        if vision.has_name_tag(screenshot, (bx, by)):
            ctx["enemies"].append((bx, by))
            ctx["enemy_bars"].append((bx, by, bw))
        else:
            ctx["boxes"].append((bx, by))
    ctx["escape"] = gas_escape_angle(screenshot)

    # Did our last punch LAND? We wrote down who we swung at and how
    # wide their health bar was. If that enemy's bar is NARROWER now,
    # the punch connected - one confirmed hit in the ledger.
    ctx["hit_confirmed"] = False
    if MEMORY["swung_at"] is not None:
        sx, sy = MEMORY["swung_at"]
        for bx, by, bw in ctx["enemy_bars"]:
            if (bx - sx) ** 2 + (by - sy) ** 2 < 150 ** 2 and \
                    bw <= MEMORY["swing_width"] - 6:
                ctx["hit_confirmed"] = True
                MEMORY["hits"] += 1
                break
        MEMORY["swung_at"] = None

    # Pros only fire when most pellets will land - no cross-map hope-shots.
    ctx["reach"] = round(width * config["match"].get("shoot_range", 0.45))

    if config["match"].get("football", False):
        ball = vision.find_ball(screenshot)
        ctx["ball"] = ball
        kick_range = config["match"].get("kick_range", 220)
        ctx["near_ball"] = ball is not None and \
            (ball[0] - us[0]) ** 2 + (ball[1] - us[1]) ** 2 < kick_range ** 2
        if ctx["near_ball"]:
            MEMORY["carry_steps"] = 4
        elif ball is not None:   # ball visible but FAR = someone else's ball
            MEMORY["carry_steps"] = 0
            MEMORY["carry_beats"] = 0   # possession over - clock resets
        # The ball hides UNDER us while we hold it - so "ball vanished
        # right after we stood on it" means it's at our feet.
        ctx["carrying"] = ball is None and MEMORY["carry_steps"] > 0
        if ctx["carrying"]:
            MEMORY["carry_steps"] -= 1
        # A ball sitting at the exact middle = fresh kickoff after a goal.
        if ball is not None and abs(ball[0] - width // 2) < 70 \
                and abs(ball[1] - height // 2) < 70:
            MEMORY["carry_steps"] = 0

    # who's crowding us, and who stands between us and their goal?
    ctx["crowd"] = [e for e in ctx["enemies"]
                    if (e[0] - us[0]) ** 2 + (e[1] - us[1]) ** 2
                    < (2.5 * ctx["reach"]) ** 2]
    ctx["defenders"] = [e for e in ctx["enemies"] if e[1] < us[1] + 40]

    # FOCUS FIRE (coach's orders): once we're shooting somebody, keep
    # shooting THAT somebody until they're gone. Switching targets
    # mid-fight is how both of them get to live.
    if ctx["enemies"]:
        last = MEMORY["focus"]
        if last is not None:
            focus = min(ctx["enemies"], key=lambda b: (b[0] - last[0]) ** 2
                                                    + (b[1] - last[1]) ** 2)
        else:
            focus = min(ctx["enemies"], key=lambda b: (b[0] - us[0]) ** 2
                                                    + (b[1] - us[1]) ** 2)
        MEMORY["focus_prev"] = last
        MEMORY["focus_prev_time"] = MEMORY["focus_time"]
        MEMORY["focus"] = focus
        MEMORY["focus_time"] = time.monotonic()
        ctx["focus"] = focus
    else:
        MEMORY["focus"] = MEMORY["focus_prev"] = None
        MEMORY["focus_time"] = MEMORY["focus_prev_time"] = None
    return ctx


def body_of(ctx, bar):
    """A red bar floats ABOVE its owner's head - aim a bit BELOW it
    to hit the body. (We learned this after a human watched our
    shots sail over everyone's hair.)"""
    return (bar[0], bar[1] + round(ctx["height"] * 0.075))


def in_range(ctx, spot) -> bool:
    us = ctx["us"]
    return (spot[0] - us[0]) ** 2 + (spot[1] - us[1]) ** 2 < ctx["reach"] ** 2


def aim_ahead_of_focus(ctx, config):
    """The full aiming pipeline: body, then lead the runner (predict_spot)."""
    target = body_of(ctx, ctx["focus"])
    dt = (MEMORY["focus_time"] - MEMORY["focus_prev_time"]) \
        if MEMORY["focus_prev_time"] is not None else 0
    prev = MEMORY["focus_prev"]
    return predict_spot(target, body_of(ctx, prev) if prev else None, dt,
                        ctx["us"],
                        bullet_speed=config["match"].get("bullet_speed", 2000),
                        speed_cap=config["match"].get("enemy_speed_cap", 450))


# ------------------------------------------------------------- CHOOSE --

def choose_tactic(ctx, config) -> str:
    """The football rule ladder (rewritten 2026-07-25 to the owner's plan):

      1. Ball is our WHOLE job. Have it -> carry it north and score.
      2. Otherwise RUN FROM FIGHTS - a crowd of enemies means flee, not brawl.
      3. Ball is loose and safe-ish -> go get it.
      4. Only if an enemy is right on top of us AND there's no ball to
         chase do we shoot back (pure self-defence, never a hunt).
    """
    # 1. WE HAVE THE BALL - scoring beats everything, even a crowd.
    swarmed = len(ctx["crowd"]) >= 2
    if (ctx["near_ball"] or ctx["carrying"]) and swarmed and \
            vision.super_is_ready(ctx["screenshot"],
                                  tuple(config["match"]["super_button"])):
        return "super_play"   # blast the ball through the pack toward goal
    if ctx["near_ball"] or ctx["carrying"]:
        return "push_north"

    # 2. NO BALL + enemies crowding us -> RUN AWAY (don't stand and fight).
    if ctx["crowd"]:
        return "fall_back"

    # 3. Ball is loose somewhere -> chase it (the default footballer life).
    if ctx["ball"] is not None:
        return "chase_ball"

    # 4. No ball in sight and an enemy is literally on us -> shoot back
    #    only as self-defence, and only when they're in punch range.
    if ctx["focus"] is not None and in_range(ctx, body_of(ctx, ctx["focus"])):
        return "fight"
    return "chase_ball"


# ---------------------------------------------------------------- ACT --

def run_tactic(name: str, device, config: dict, ctx) -> None:
    """Execute one tactic for one heartbeat: trigger first, then feet."""
    joystick = tuple(config["match"]["joystick_anchor"])
    attack_button = tuple(config["match"]["attack_button"])
    super_button = tuple(config["match"].get("super_button", attack_button))
    us, ball = ctx["us"], ctx["ball"]

    walk = 90.0  # default: push toward their goal

    if name == "push_north":
        # Coach's rule first: winning late = keep the ball, kick NOTHING.
        if should_stall(ctx, config, ctx.get("step", 0)):
            # walk it to the nearest bottom corner and guard it there
            corner_x = ctx["width"] * (0.12 if us[0] < ctx["width"] / 2 else 0.88)
            walk = angle_towards(us, (round(corner_x), round(ctx["height"] * 0.8)))
            controls.joystick_push(device, anchor=joystick,
                                   angle_degrees=walk_or_detour(strafe(walk, ctx)),
                                   distance=config["match"]["joystick_distance"],
                                   hold_ms=config["match"].get("step_hold_ms", 700))
            return
        # -- WE have the ball. Attack = kick, so pick the kick well.
        if ctx["near_ball"] or ctx["carrying"]:
            MEMORY["carry_beats"] = MEMORY.get("carry_beats", 0) + 1
            if not ctx["enemies"]:
                # An empty screen = the enemies are dead or far: the
                # GOLDEN WINDOW. March the ball upfield first - free
                # ground now beats a hopeful long shot - THEN, after a
                # few beats of progress, auto-aim kicks it at their goal.
                if MEMORY["carry_beats"] >= 3:
                    controls.attack(device, attack_button)
            elif ctx["crowd"]:
                # Contested: a carrier is defenseless - pass UP immediately,
                # dribbling into a fight loses the ball every time. And
                # bend the pass AWAY from the defenders (clear_lane_up).
                controls.aim_and_shoot(device, attack_button,
                                       clear_lane_up(ctx))
            # else: enemies exist but far - DRIBBLE (kick nothing, keep
            # the ball at our feet and keep marching at their goal).
        walk = angle_towards(us, ball) if ball is not None else 90

    elif name == "super_play":
        if vision.super_is_ready(ctx["screenshot"], super_button):
            if ctx["near_ball"] or ctx["carrying"]:
                # Swarmed with the ball: BLAST it through the pack.
                controls.fire_super(device, super_button, 90)
            elif ctx["focus"] is not None:
                controls.fire_super(device, super_button, angle_towards(
                    us, aim_ahead_of_focus(ctx, config)))
            walk = 90 if ball is None else angle_towards(us, ball)
        else:  # no super after all - fight like a normal person
            run_tactic("fight", device, config, ctx)
            return

    elif name == "fall_back":
        # -- THEY have the ball on OUR half: don't chase it from
        # behind - park DEEP, like a keeper on the goal line. The
        # coach's rule: your body stops the ball; stand 70% of the
        # way home, not politely at midfield.
        own_goal = (ctx["width"] // 2, ctx["height"])
        if ball is not None:
            block = (round(ball[0] + 0.7 * (own_goal[0] - ball[0])),
                     round(ball[1] + 0.7 * (own_goal[1] - ball[1])))
            walk = angle_towards(us, block)
        else:
            walk = 270  # straight home
        if ctx["focus"] is not None and in_range(ctx, body_of(ctx, ctx["focus"])):
            # a carrier can't fight back - free punches!
            controls.aim_and_shoot(device, attack_button, angle_towards(
                us, aim_ahead_of_focus(ctx, config)))
            record_swing(ctx)

    elif name == "fight":
        # Self-defence only (owner's plan 2026-07-25): "run from enemy
        # battles". We NEVER charge an enemy. If one is close enough to
        # punch, we shoot back once - but our FEET always retreat AWAY
        # from them (toward their goal-side if we can, so backing off
        # still walks us up-field toward the ball/goal, not into our net).
        if ctx["focus"] is not None:
            if in_range(ctx, body_of(ctx, ctx["focus"])):
                controls.aim_and_shoot(device, attack_button, angle_towards(
                    us, aim_ahead_of_focus(ctx, config)))
                record_swing(ctx)
            # walk directly AWAY from the enemy (180 deg from facing them)
            away = (angle_towards(us, ctx["focus"]) + 180) % 360
            walk = away
        else:
            walk = 90

    else:  # chase_ball - the default life of a footballer
        if ball is not None:
            walk = angle_towards(us, ball)
        elif ctx["focus"] is not None:
            walk = angle_towards(us, ctx["focus"])   # hunt whoever has it
        else:
            walk = (90 + random.uniform(-45, 45)) % 360  # push up-field

    controls.joystick_push(device, anchor=joystick,
                           angle_degrees=walk_or_detour(strafe(walk, ctx)),
                           distance=config["match"]["joystick_distance"],
                           hold_ms=config["match"].get("step_hold_ms", 700))


def log_demo(config: dict, features, tactic: str) -> None:
    """Write down (what we saw, what the rulebook chose) - one line per
    beat. This diary is the learning pilot's homework: before its first
    real game it STUDIES these lines until it plays like the rulebook
    (that's "behavior cloning" - learning by copying the veteran)."""
    path = config.get("rl", {}).get("demos_path")
    if not path or not config.get("rl", {}).get("log_demos", False):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"x": [round(float(v), 4) for v in features],
                            "action": TACTICS.index(tactic)}) + "\n")


def record_swing(ctx) -> None:
    """Write down who we swung at and their health-bar width.

    Next beat, see() checks the receipt: if that enemy's bar shrank,
    the punch landed. That count - hits WE generated - is the fairest
    grade for our own play: wins are a team grade, punches are ours."""
    focus = ctx["focus"]
    for bx, by, bw in ctx["enemy_bars"]:
        if (bx - focus[0]) ** 2 + (by - focus[1]) ** 2 < 40 ** 2:
            MEMORY["swung_at"], MEMORY["swing_width"] = (bx, by), bw
            return


def clear_lane_up(ctx) -> float:
    """Pick an UP-ish kick direction that avoids the defenders.

    "Never pass to the opponents" - the #1 sin in every guide we've
    studied. A blind kick straight north hands the ball to whoever is
    standing north. So we check where the enemies ahead are bunched and
    bend the kick to the OTHER side - still firmly upfield (65-115°),
    because the other law still rules: never, ever kick toward our goal."""
    us = ctx["us"]
    ahead = [e for e in ctx["enemies"] if e[1] < us[1] + 40]
    if not ahead:
        return 90
    mean_x = sum(e[0] for e in ahead) / len(ahead)
    # defenders bunched to our RIGHT -> kick up-LEFT (115°), and vice versa
    return 115 if mean_x > us[0] else 65


def strafe(walk: float, ctx) -> float:
    """Coach's rule: NEVER walk in a straight line. A tiny zigzag - one
    step bent left, the next bent right - makes every skillshot in the
    game miss, and costs almost no forward speed. (±14° keeps ~97% of
    the walking speed toward where we actually want to go. Trigonometry
    pays rent again!)"""
    if not ctx["enemies"]:
        return walk   # nobody aiming at us - walk straight, arrive sooner
    MEMORY["strafe_flip"] = not MEMORY.get("strafe_flip", False)
    return (walk + (14 if MEMORY["strafe_flip"] else -14)) % 360


def should_stall(ctx, config: dict, step: int) -> bool:
    """Coach's rule: winning late = STOP scoring, START stalling.

    Up a goal with the clock running out, the smartest kick is no kick:
    keep the ball at our feet in a safe corner and trade time for
    nothing. Possession is a win condition."""
    scores = ctx.get("scores")
    return (scores is not None and scores[0] > scores[1]
            and step >= config["match"].get("stall_after_step", 80)
            and (ctx["carrying"] or ctx["near_ball"]))


def play_step(device, config: dict, step: int, screenshot=None,
              scores=None) -> None:
    """One heartbeat of in-match playing: see, choose, act."""
    ctx = see(screenshot, config, step)
    ctx["scores"] = scores
    ctx["step"] = step

    # ---- FOOTBALL: pick one of the five tactics and run it ----
    if config["match"].get("football", False) and ctx["us"] is not None:
        tactic = choose_tactic(ctx, config)
        from . import rl  # imported here so numpy stays optional elsewhere
        log_demo(config, rl.features_from_ctx(ctx, config, step), tactic)
        run_tactic(tactic, device, config, ctx)
        return

    # ---- Everything below is the NON-football rulebook (Showdown) ----
    joystick = tuple(config["match"]["joystick_anchor"])
    attack_button = tuple(config["match"]["attack_button"])
    super_button = tuple(config["match"].get("super_button", attack_button))
    pattern = config["match"]["pattern"]
    us, focus, escape, boxes = ctx["us"], ctx["focus"], ctx["escape"], ctx["boxes"]
    screenshot = ctx["screenshot"]

    def nearest(spots):
        return min(spots, key=lambda s: (s[0] - us[0]) ** 2 + (s[1] - us[1]) ** 2)

    # ---- TRIGGER FIRST: aim from the freshest possible look ----
    # (walking takes most of a second - shooting after it means aiming
    #  at where everyone USED to be. That's the "timing" bug our coach saw.)
    if focus is not None:
        # Range is judged on where they ARE; the aim is bent to where
        # they're GOING. Mixing those up made us hold fire on runners.
        if vision.super_is_ready(screenshot, super_button) and \
                in_range(ctx, body_of(ctx, focus)):
            # The finishing move: a charged super, straight at our mark -
            # but only in range. Don't waste it on hope.
            controls.fire_super(device, super_button, angle_towards(
                us, aim_ahead_of_focus(ctx, config)))
        elif in_range(ctx, body_of(ctx, focus)):
            # Every heartbeat, not every other - a wounded enemy who gets
            # a breather is an enemy who comes back healed.
            controls.aim_and_shoot(device, attack_button, angle_towards(
                us, aim_ahead_of_focus(ctx, config)))
            record_swing(ctx)
    elif boxes and in_range(ctx, body_of(ctx, nearest(boxes))) and step % 2 == 0:
        controls.aim_and_shoot(device, attack_button,
                               angle_towards(us, body_of(ctx, nearest(boxes))))

    # ---- FEET: one walking direction, most urgent rule wins ----
    if escape is not None:
        walk = escape                                             # 1. flee the gas
    elif focus is not None:
        enemy = focus     # feet and trigger agree on who the fight is with
        d2 = (enemy[0] - us[0]) ** 2 + (enemy[1] - us[1]) ** 2
        strong = MEMORY["cubes"] >= 3
        close = d2 < (screenshot.shape[1] // 4) ** 2
        if strong and close:
            walk = angle_towards(us, enemy)                       # 2. finish them!
        else:
            walk = (angle_towards(us, enemy) + 180) % 360         #    ...or kite away
    elif boxes:
        walk = angle_towards(us, nearest(boxes))                  # 3. go crack it
        MEMORY["loot_angle"], MEMORY["loot_steps"] = walk, 2
    elif MEMORY["loot_steps"] > 0:
        MEMORY["loot_steps"] -= 1
        if MEMORY["loot_steps"] == 0:
            MEMORY["cubes"] += 1        # walked all the way there = cubes collected
        walk = MEMORY["loot_angle"]                               # 4. grab the cubes
    else:
        hideout = bush_direction(screenshot) if screenshot is not None else None
        if hideout is not None:
            walk = hideout                                        # 5. sneak to a bush
        else:
            walk = next_angle(pattern, step)                      # 6. keep moving

    # In a fight, take SHORT steps: a long walk-push blocks the loop, and
    # stale eyes are why shots miss. Out of combat, stride normally.
    controls.joystick_push(
        device,
        anchor=joystick,
        angle_degrees=walk_or_detour(walk, urgent=escape is not None),
        distance=config["match"]["joystick_distance"],
        hold_ms=config["match"].get("step_hold_ms", 700) if focus is not None
        else config["match"]["joystick_hold_ms"],
    )

    # (No blind shots anymore - a shot with no target just tells the
    #  whole map where we're hiding.)
