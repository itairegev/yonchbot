"""Turn a recorded human gameplay video into behavior-cloning demos.

For each ~1.3s window (4 frames at 3fps): read the world with the bot's
own vision, measure which way the HUMAN moved (camera motion), and label
the window with the tactic that best explains the movement. Only
confident windows become demo lines - ambiguous ones are skipped.
"""
import glob
import json
import math
import sys

import cv2
import numpy as np

sys.path.insert(0, "/Users/itairegev/projects/yonchbot")
import yaml
from yonchbot import play, rl, vision

FRAMES_DIR = sys.argv[1] if len(sys.argv) > 1 else (
    "/private/tmp/claude-501/-Users-itairegev-projects-yonchbot/"
    "c63a4f81-872d-4f39-8516-6f5f5a7ff8e5/scratchpad/demo_frames")
FRAMES = sorted(glob.glob(FRAMES_DIR + "/f_*.png"))
OUT = "/Users/itairegev/projects/yonchbot/data/rl/human_demos.jsonl"
config = yaml.safe_load(open("/Users/itairegev/projects/yonchbot/config.yaml"))
digits = {0: vision.load_template("/Users/itairegev/projects/yonchbot/assets/templates/score_0.png"),
          1: vision.load_template("/Users/itairegev/projects/yonchbot/assets/templates/score_1.png")}

WINDOW = 3          # frames per decision window (1s of video)
FPS = 3.0


def find_ball_video(img):
    """The ball finder, tuned for WhatsApp-squeezed colors: compression
    washes out the ball's orange, so we accept paler shades here than
    the live bot does on its raw screenshots."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, (8, 130, 80), (22, 255, 235))
    orange = cv2.morphologyEx(orange, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(orange, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        round_ish = 0.75 <= w / h <= 1.35 if h else False
        big_enough = 45 <= w <= 100 and 45 <= h <= 100
        solid = cv2.contourArea(contour) >= 0.5 * w * h
        if round_ish and big_enough and solid:
            return (x + w // 2, y + h // 2)
    return None

def compass_of_camera_motion(view_a, view_b):
    """Which compass way did the PLAYER walk between two views?
    The camera follows the player, so the scenery slides the OPPOSITE
    way: walking north (up) slides the world down (+y in image)."""
    (dx, dy), _ = cv2.phaseCorrelate(view_a, view_b)
    walk_x, walk_y = -dx, -dy          # player moves opposite the slide
    if math.hypot(dx, dy) < 2.0:
        return None, 0.0               # basically standing still
    # compass: 90=up. Image y counts down, so up = negative walk_y.
    return math.degrees(math.atan2(-walk_y, walk_x)) % 360, math.hypot(dx, dy)

def angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)

# ---- pass 1: read every frame once ----
facts = []
for f in FRAMES:
    img = cv2.imread(f)
    h, w = img.shape[:2]
    us = (w // 2, h // 2)
    in_match = vision.read_score(img, config["match"]["score_left_box"],
                                 digits) is not None
    ball = find_ball_video(img)
    # Brawl Ball has no loot boxes - every red bar IS an enemy, so the
    # (compression-fragile) name-tag check isn't needed here.
    enemies = vision.find_red_bars(img)
    facts.append({"view": vision.travel_view(img), "ball": ball,
                  "enemies": enemies, "us": us, "w": w, "h": h,
                  "in_match": in_match})

# ---- pass 2: label windows ----
demos, skipped, carrying_since = [], 0, None
for i in range(0, len(facts) - WINDOW, WINDOW):
    window = facts[i:i + WINDOW + 1]
    if not all(fr["in_match"] for fr in window):
        skipped += 1
        continue    # menus, goal cutscenes, spawn screens: not gameplay
    start = window[0]
    us, w, h = start["us"], start["w"], start["h"]

    # average the walk direction across the window
    angles, strength = [], 0.0
    for a, b in zip(window, window[1:]):
        ang, mag = compass_of_camera_motion(a["view"], b["view"])
        if ang is not None:
            angles.append(ang)
            strength += mag
    if not angles:
        skipped += 1
        continue    # stood still all window - no tactic to learn
    sx = sum(math.cos(math.radians(a)) for a in angles)
    sy = sum(math.sin(math.radians(a)) for a in angles)
    walk = math.degrees(math.atan2(sy, sx)) % 360

    # carrying proxy: the ball vanished right where we stood
    ball = start["ball"]
    if ball is not None:
        near = math.dist(ball, us) < 260
        carrying_since = i if near else None
        carrying = False
    else:
        carrying = carrying_since is not None and i - carrying_since <= WINDOW * 2
    enemies = start["enemies"]
    focus = min(enemies, key=lambda e: math.dist(e, us)) if enemies else None

    # ---- the labeling ladder: which tactic explains this movement? ----
    label = None
    if ball is not None and angle_gap(walk, play.angle_towards(us, ball)) < 50:
        label = "chase_ball"
    elif carrying and angle_gap(walk, 90) < 60:
        label = "push_north"
    elif focus is not None and angle_gap(walk, play.angle_towards(us, focus)) < 50 \
            and math.dist(focus, us) < 0.35 * w:
        label = "fight"
    elif angle_gap(walk, 270) < 60 and (enemies or
            (ball is not None and ball[1] > us[1])):
        label = "fall_back"
    if label is None:
        skipped += 1
        continue

    # features exactly like the live bot builds them
    ctx = {"screenshot": None, "us": us, "width": w, "height": h,
           "ball": ball, "carrying": carrying, "enemies": enemies,
           "focus": focus}
    play.MEMORY["last_shift"] = strength / max(1, len(angles))
    step = round((i / FPS) / 1.3)      # video seconds -> bot heartbeats
    x = rl.features_from_ctx(ctx, config, step)
    demos.append({"x": [round(float(v), 4) for v in x],
                  "action": play.TACTICS.index(label)})

with open(OUT, "a" if "--append" in sys.argv else "w") as f:
    for d in demos:
        f.write(json.dumps(d) + "\n")

from collections import Counter
print(f"windows labeled: {len(demos)}, skipped: {skipped}")
print("tactic mix:", dict(Counter(play.TACTICS[d['action']] for d in demos)))
