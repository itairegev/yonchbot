# YOLO vision plan — replace brittle detection with a trained detector

Goal: fix the real blocker (the bot can't see enemies/ball/players this season)
by swapping color/template matching for a **learned YOLOv8 object detector**,
while keeping the existing `adb screencap` + adb-tap pipeline unchanged.
Decision rationale: [[frida-vs-yolo-research-2026-07-26]].

## Why this is a surgical change

The ENTIRE game-state detection funnels through two calls in `play.py:see()`:
- enemies: `vision.find_red_bars_wide()` + `vision.has_name_tag()` (lines ~237-240)
- ball:    `vision.find_ball()` (line ~263)

Everything else in `vision.py` is MENU/UI detection that already works and
STAYS: `find()` (template match for banners/cards), `read_score()`,
`super_is_ready()`, `travel_view()`/`camera_shift()`, `load_template()`.

So the plan replaces the *implementation* of enemy + ball detection with YOLO,
keeping the SAME return types so the tactics layer is untouched:
- enemies → list of `(x, y)` centers (+ optional bar width for hit-detection)
- ball    → `(x, y)` or `None`
- (bonus YOLO can also give) player-self, teammates, walls, bushes

## Classes to detect (label schema)

Start minimal, matched to what the bot uses today, then extend:
1. `enemy`      (required — replaces red-bar + name-tag)
2. `ball`       (required — replaces find_ball)
3. `player`     (self — lets us stop assuming "us = screen center", which
                 breaks on death/respawn)
4. `teammate`   (enables real passing later — currently impossible)
5. `wall` / `bush` (later — pathing/cover)

## Phased plan

### Phase 0 — decide dataset source (fast)
- **Option A (fast start):** reuse a public Roboflow "Brawl Stars" dataset
  (has player/enemy/wall/bush). Pro: labeled already. Con: may not match this
  season's skins / our phone's resolution (2340x1080).
- **Option B (best fit, more work):** capture OUR frames from the phone and
  label them. Pro: exact match to our maps/skins/resolution. Con: labeling
  effort (great kid task).
- Likely: **A to bootstrap + prove the pipeline, then fine-tune on B.**

### Phase 1 — data collection — LARGELY DONE (2026-07-26)
- The bot already saved **5,961 frames** in `data/stuck/` (6.8 GB, Jul 18-25)
  from every "confused" moment - many are real in-match gameplay.
- `tools/filter_gameplay_frames.py` sifts those into likely-gameplay frames.
  Ran it 2026-07-26: **3,495 gameplay candidates** copied to `data/gameplay/`
  (4.8 GB). ~98 frames were corrupt (CRC) and skipped.
- NOTE: the heuristic is imperfect (~60% hit rate; some event-menu cards slip
  through as false positives; includes Showdown AND Brawl Ball frames). A human
  still eyeballs before labeling. Good enough to skip fresh capture for now.
- Frames span multiple maps/skins/seasons + BOTH red health bars (Showdown) and
  green/teal bars (neon Brawl Ball) - good for a model that generalizes.
- Still useful later: a `tools/capture_frames.py` for fresh targeted capture.

### Phase 2 — labeling
- Use Roboflow (free tier) or `labelImg` locally. Draw boxes for each class.
- Export in YOLO format. (Kid learns: what a bounding box / class is.)

### Phase 3 — train
- `ultralytics` YOLOv8n (nano = fast, CPU-friendly). Fine-tune from a
  pretrained checkpoint on our dataset.
- Success metric: mAP@0.5 on a held-out set; eyeball detections on real frames.
- Output: a `best.pt` weights file committed to `assets/models/` (or a small
  ONNX export for portability).

### Phase 4 — integrate (the surgical swap)
- New module `yonchbot/detector.py`: loads the model once, exposes
  `detect(frame) -> {"enemies":[(x,y)...], "ball":(x,y)|None,
   "player":(x,y)|None, "teammates":[...]}`.
- In `play.py:see()`, replace the red-bar/name-tag block and `find_ball` call
  with `detector.detect(screenshot)` results. Keep return shapes identical so
  choose_tactic/run_tactic need no changes.
- Config flag `vision.detector: "yolo" | "classic"` so we can A/B and fall back.
- Hit-detection (`MEMORY["hits"]` via shrinking bar width) currently relies on
  bar width — either keep the classic bar-width read for that one signal, or
  switch to "enemy box got smaller / disappeared." Decide during integration.

### Phase 5 — close the loop
- Run games, capture misses, add hard frames to the dataset, retrain.
- This is the RL/feedback loop the project already envisions
  ([[yonchbot-training-workflow]], docs/rl-approach-research.md).

## Dependencies
- `ultralytics` (YOLOv8), `torch` (CPU build is fine for nano). Add to
  requirements.txt. Note: heavier than current deps — keep model = nano.

## Risks / open questions
- Inference speed on the dev machine per frame (nano should be tens of ms on
  CPU; verify it keeps up with the bot's heartbeat).
- Resolution: train/infer at the phone's 2340x1080 or downscale consistently.
- ToS/ban risk is UNCHANGED — still automation. **Lab account only.**

## First concrete step (when ready)
Build `tools/capture_frames.py` + get one real Brawl Ball match's worth of
frames, OR pull a Roboflow dataset to prove the training pipeline end-to-end on
a handful of our frames before investing in labeling.
