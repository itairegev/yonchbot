# Vision detection findings — why the bot shoots at nothing (2026-07-25)

Investigation triggered by live play: the bot lost every game 0-1 with ~0 hits,
and the human watching said **"you keep shooting at the borders, not on enemies."**

## The core bug: detection returns 0 targets

Testing `yonchbot/vision.py` against **real match frames** captured from the phone
(2340×1080), on the current season's maps:

- `find_red_bars_wide(frame)` → **0 red bars found**
- `find_ball(frame)` → **None**
- Therefore `see()` returns `enemies=[]`, `focus=None`, `ball=None`.

With no enemies and no ball detected, the tactics fall through to `chase_ball`
with `ball=None`, and any attack fires at a default/wrong heading — i.e. "at the
borders." The bot is effectively blind.

## Why detection fails

1. **Health bars are not the expected RED.** `find_red_bars_wide` only matches
   strict red (HSV hue 0-10 or 170-180, sat>150, val>150). In the current
   game — especially the Daily Contest "Score High" variant and the new
   season's neon maps — brawler health bars render **green / orange / teal**,
   not red. So the red filter matches nothing.
   - Frame evidence: `scratchpad/inmatch.png` (Score-High variant) shows
     health bars in green (israel 6000) and orange (7170), on a pink/cyan map.

2. **Map/skin visual noise.** The new maps are highly saturated (pink spiky
   walls, cyan floors, neon). Even where red-ish pixels exist, they're map
   decoration, not bars — and the "solid red + name tag above" heuristic
   can latch onto the wrong thing or nothing.

3. **Ball skin mismatch.** `find_ball` expects a "dark-orange round sphere."
   The current ball is a **beach ball** (multicolor) in some events and a
   different skin in others — the orange-sphere heuristic misses it.
   - Frame evidence: `scratchpad/inmatch2.png` (normal jungle Brawl Ball) —
     ball is a red/white beach ball top-right; `find_ball` returned None.

## What this means

The strategy/tactics layer (choose_tactic, flee-vs-score, aiming, prediction)
is **downstream of vision** and can't work while vision is blind. The real
fix order is:

1. **Fix target detection first** — make enemy detection robust to health-bar
   color (detect the bar *shape* + name tag regardless of red/green/orange),
   and make ball detection match the current ball skin(s).
2. Only then re-tune tactics and aiming.

## Frames on hand for tuning (scratchpad/)
- `inmatch.png` — Daily Contest "Score High" variant (green/orange bars, pink map)
- `inmatch2.png` — normal 3v3 Brawl Ball, jungle pitch, beach ball
- `frameA.png`, `frameB.png`, `peek.png`, `play_now.png` — assorted in/near match

## Next step
Capture a fresh set of clean in-match frames, sample the ACTUAL health-bar and
ball pixel colors, and rewrite `find_red_bars_wide` / `find_ball` to match what
the game really renders this season. See [[yonchbot-training-workflow]].
