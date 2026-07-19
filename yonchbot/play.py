"""How the bot plays a match. THIS is the fun file to tweak!

Every heartbeat the bot answers TWO questions separately, like a real
player: where do my FEET go, and where does my TRIGGER point?

FEET (the most urgent rule wins):
  1. Poison gas creeping in?  RUN the other way. Never argue with poison.
  2. Enemy on screen?         Are we STRONG (3+ power cubes collected)
                              and are they CLOSE? Then finish them -
                              that's how our human coach won: only take
                              fights you've already won. Otherwise walk
                              AWAY ("kiting"). Charging while weak is
                              how we got rank 9 once. Never again.
  3. Loot box on screen?      Walk to it. Power cubes make us stronger.
  4. Box just broke?          Keep walking there 2 more heartbeats to
                              scoop up the cubes that popped out.
  5. Nothing around?          Walk the movement pattern - keep moving,
                              a standing target is a dead target.

TRIGGER (checked BEFORE the feet - fresh eyes make straight shots!):
  * Enemy in range?  Shoot AT them - at the BODY, below the health bar.
  * Box in range?    Crack it open.
  * Out of range?    Hold fire. Pros only shoot when the pellets will
                     land - and a stray shot tells everyone where we are.

The movement patterns live in PATTERNS. Each one is just a list of
compass angles (degrees) the bot walks in, one after another, in a loop.

Ideas to try:
  * add your own pattern (a square? a star? your initials?)
  * make attack_every_steps smaller - does the bot do better?
  * make a "scaredy-cat" mode: when OUR health is low, run AWAY
    from the red bars instead of toward them
"""

from __future__ import annotations

import math
import random

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


# The bot's tiny short-term memory: after a box breaks, keep walking to
# where it stood for a couple heartbeats to scoop up the power cubes -
# and count every pickup, because cubes = strength = permission to fight.
MEMORY = {"loot_angle": None, "loot_steps": 0, "cubes": 0,
          "focus": None, "focus_prev": None, "carry_steps": 0}


def play_step(device, config: dict, step: int, screenshot=None) -> None:
    """One heartbeat of in-match playing: move the feet, aim the trigger."""
    joystick = tuple(config["match"]["joystick_anchor"])
    attack_button = tuple(config["match"]["attack_button"])
    super_button = tuple(config["match"].get("super_button", attack_button))
    pattern = config["match"]["pattern"]

    if step == 0:  # fresh match, fresh memory
        MEMORY["loot_angle"], MEMORY["loot_steps"] = None, 0
        MEMORY["cubes"], MEMORY["focus"], MEMORY["focus_prev"] = 0, None, None
        MEMORY["carry_steps"] = 0

    # ---- LOOK: sort everything on screen into enemies and boxes ----
    enemies, boxes, escape, us, ball = [], [], None, None, None
    if screenshot is not None:
        height, width = screenshot.shape[:2]
        us = (width // 2, height // 2)  # the camera follows us = we ARE the center
        for bar in vision.find_red_bars(screenshot):
            if vision.has_name_tag(screenshot, bar):
                enemies.append(bar)
            else:
                boxes.append(bar)
        escape = gas_escape_angle(screenshot)
        if config["match"].get("football", False):
            ball = vision.find_ball(screenshot)


    def nearest(spots):
        return min(spots, key=lambda s: (s[0] - us[0]) ** 2 + (s[1] - us[1]) ** 2)

    def body_of(bar):
        """A red bar floats ABOVE its owner's head - aim a bit BELOW it
        to hit the body. (We learned this after a human watched our
        shots sail over everyone's hair.)"""
        return (bar[0], bar[1] + round(screenshot.shape[0] * 0.075))

    # Pros only fire when most pellets will land - no cross-map hope-shots.
    reach = round(screenshot.shape[1] * config["match"].get("shoot_range", 0.45))
    in_range = lambda spot: ((spot[0] - us[0]) ** 2 + (spot[1] - us[1]) ** 2
                             < reach ** 2)

    # FOCUS FIRE (coach's orders): once we're shooting somebody, keep
    # shooting THAT somebody until they're gone. Switching targets
    # mid-fight is how both of them get to live.
    if enemies:
        last = MEMORY["focus"]
        if last is not None:
            focus = min(enemies, key=lambda b: (b[0] - last[0]) ** 2
                                             + (b[1] - last[1]) ** 2)
        else:
            focus = nearest(enemies)
        MEMORY["focus_prev"] = last
        MEMORY["focus"] = focus
    else:
        focus = None
        MEMORY["focus"] = MEMORY["focus_prev"] = None

    def lead_the_target(spot):
        """Aim where they're GOING, not where they are.

        Every human learns this: by the time your shot arrives, a moving
        target has moved. We compare where our mark is NOW to where they
        were one look ago - that's their speed - and aim that much
        (times 1.5, for the shot's travel time) ahead of them.
        """
        prev = MEMORY["focus_prev"]
        if prev is None:
            return spot
        dx, dy = spot[0] - prev[0], spot[1] - prev[1]
        if dx * dx + dy * dy > 400 ** 2:
            return spot  # too big a jump = a DIFFERENT enemy, not speed
        dx = max(-160, min(160, dx))
        dy = max(-160, min(160, dy))
        return (spot[0] + round(dx * 1.5), spot[1] + round(dy * 1.5))

    # ---- FOOTBALL: a team sport with respawns! Dying is cheap and
    # hiding is useless - so football rules are BRAVE rules: always
    # moving, always shooting, always after the ball. Our goal is at
    # the bottom, theirs is UP - so everything gets pushed north.
    if config["match"].get("football", False) and us is not None:
        kicked = False
        if ball is not None:
            d2_ball = (ball[0] - us[0]) ** 2 + (ball[1] - us[1]) ** 2
            if d2_ball < config["match"].get("kick_range", 220) ** 2:
                MEMORY["carry_steps"] = 4      # on the ball (or holding it)
                controls.aim_and_shoot(device, attack_button, 90)  # KICK north!
                kicked = True
        elif MEMORY["carry_steps"] > 0:
            MEMORY["carry_steps"] -= 1         # ball under us = we're carrying
            controls.aim_and_shoot(device, attack_button, 90)      # kick ahead
            kicked = True
        # Shoot on the run: any enemy in range eats a leading shot.
        if not kicked and focus is not None and in_range(body_of(focus)):
            aim = angle_towards(us, body_of(lead_the_target(focus)))
            if vision.super_is_ready(screenshot, super_button):
                controls.fire_super(device, super_button, aim)
            else:
                controls.aim_and_shoot(device, attack_button, aim)
        # Feet: the ball first, then the fight, then push up-field.
        if ball is not None:
            walk = angle_towards(us, ball)
        elif MEMORY["carry_steps"] > 0:
            walk = 90
        elif focus is not None:
            walk = angle_towards(us, focus)    # hunt whoever has the ball
        else:
            walk = (90 + random.uniform(-45, 45)) % 360  # press toward their goal
        controls.joystick_push(device, anchor=joystick, angle_degrees=walk,
                               distance=config["match"]["joystick_distance"],
                               hold_ms=config["match"].get("step_hold_ms", 300))
        return

    # ---- TRIGGER FIRST: aim from the freshest possible look ----
    # (walking takes most of a second - shooting after it means aiming
    #  at where everyone USED to be. That's the "timing" bug our coach saw.)
    if focus is not None:
        # Range is judged on where they ARE; the aim is bent to where
        # they're GOING. Mixing those up made us hold fire on runners.
        target = body_of(lead_the_target(focus))
        if vision.super_is_ready(screenshot, super_button) and in_range(body_of(focus)):
            # The finishing move: a charged super, straight at our mark -
            # but only in range. Don't waste it on hope.
            controls.fire_super(device, super_button, angle_towards(us, target))
        elif in_range(body_of(focus)):
            # Every heartbeat, not every other - a wounded enemy who gets
            # a breather is an enemy who comes back healed.
            controls.aim_and_shoot(device, attack_button, angle_towards(us, target))
    elif boxes and in_range(body_of(nearest(boxes))) and step % 2 == 0:
        controls.aim_and_shoot(device, attack_button,
                               angle_towards(us, body_of(nearest(boxes))))

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
        angle_degrees=walk,
        distance=config["match"]["joystick_distance"],
        hold_ms=300 if focus is not None else config["match"]["joystick_hold_ms"],
    )

    # (No blind shots anymore - a shot with no target just tells the
    #  whole map where we're hiding.)
