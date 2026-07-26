# Labeling Guide — teaching YonchBot to SEE

We're teaching the bot to recognize things on screen by SHOWING it examples.
This is how modern AI vision works: you draw boxes around things in a bunch of
pictures, tell it what each box is, and it learns the pattern. Then it can find
those things in pictures it's never seen.

The pictures to label are in **`data/to_label/`** (300 of them).

## What we're labeling (the "classes")

Draw a tight box around each of these when you see them in a frame:

| Class | What it is | How to spot it |
|-------|-----------|----------------|
| `enemy` | An opponent brawler | A character with a **health bar** above it that is NOT ours. In most modes the enemy bar is **red**; in some events it's a different colour - go by "it's another player we'd fight." |
| `ball` | The Brawl Ball | The soccer/beach ball on the field. Only in Brawl Ball matches. |
| `player` | US (the bot's own brawler) | Usually near the middle of the screen, often with a **green** health bar and our name. |
| `teammate` | A friendly player | Another brawler on OUR side (blue name tag / same team colour). Lets the bot learn to pass later. |

Skip a frame if it's clearly a menu (event cards, trophy screens) - a few of
those slipped into the folder. Just don't label those; we can delete them later.

## Tips for good boxes
- **Tight boxes:** wrap the box snugly around the brawler's body, not the empty
  space around it. Include the health bar with the body if they touch.
- **Every instance:** if there are 4 enemies on screen, draw 4 `enemy` boxes.
- **Partly off-screen is fine:** box the visible part.
- **When unsure, skip the frame** rather than guess - a wrong label teaches the
  wrong thing.

## How to do it (two easy options)

### Option A — Roboflow (web, recommended, free)
1. Make a free account at https://roboflow.com
2. Create a new project -> type: **Object Detection**.
3. Upload the images from `data/to_label/`.
4. Add the classes above (`enemy`, `ball`, `player`, `teammate`).
5. Draw boxes on each image. (Roboflow has a nice fast box tool.)
6. When done, **Generate** a dataset and **Export** in **YOLOv8** format.
   Save the export into `data/dataset/`.

### Option B — labelImg (offline app)
1. `pip install labelImg` then run `labelImg`.
2. Open Dir -> `data/to_label/`. Set save format to **YOLO**.
3. Draw boxes (shortcut `w`), pick the class, next image (`d`).
4. It writes a `.txt` next to each image with the boxes.

## How many to label?
- **A first useful model:** ~150-200 labeled frames is enough to see it working.
- **Good:** ~300 (all of them).
- The more variety (maps, skins, positions), the better it generalizes. That's
  why we spread the picks across sessions.

## What happens next (grown-up part)
Once labeled, we train a small YOLOv8 model on them, check its accuracy, and
plug it into the bot's eyes (`play.py` see()), replacing the old colour-matching
that kept failing. See docs/yolo-vision-plan.md.

## Quick sanity rule
If YOU can instantly tell "that's an enemy / that's the ball," the model can
learn it - as long as we give it enough clear examples. Label what's obvious,
skip what's ambiguous.
