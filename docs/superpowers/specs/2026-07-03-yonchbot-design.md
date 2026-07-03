# YonchBot — Design Document

**Date:** 2026-07-03
**Goal:** Build a Brawl Stars bot as a summer-break teaching project for an 11-year-old
("Yonch"), mentored by his uncle. The bot's purpose is educational: show that goals +
logic + hard work = a real, working thing. It does NOT need to reach top ranks — it
needs to show visible, measurable progress.

## Ground rules (non-negotiable)

1. **Lab account only.** Automating gameplay violates Supercell's Terms of Service and
   can get an account banned. The bot is only ever used on a brand-new throwaway
   account created for this project. Yonch's real account is never touched.
   This is itself lesson #1: engineers respect rules and think about consequences.
2. **No game modification.** The bot works like a robot player: it *looks* at the
   screen (screenshots) and *touches* the screen (taps/swipes). No memory editing,
   no APK patching, no packet interception. This keeps the project ethical,
   simple, and maximally educational (computer vision + control logic).
3. **Kid-readable code.** Small files, plain names, comments that explain *why*.
   Every module should be explainable to an 11-year-old in one sitting.

## Approaches considered

| Approach | Verdict |
|---|---|
| **A. Android device/emulator + ADB + Python/OpenCV** | ✅ Chosen. Pure Python, works over USB with any Android phone or with an emulator on the Mac, screenshots + taps are two shell commands, OpenCV template matching is visual and intuitive for a kid ("teach the bot to see the PLAY button"). |
| B. iOS automation | ❌ Requires WebDriverAgent/jailbreak-grade tooling; fragile and not kid-feasible. |
| C. API / memory hacking | ❌ Against the rules we set, and teaches the wrong lessons. |

## Architecture

```
Mac (Python)                        Android phone / emulator
┌─────────────────────────┐   USB   ┌──────────────────┐
│ yonchbot                │◄───────►│  Brawl Stars     │
│  eyes:  vision.py       │  adb    │  (lab account)   │
│  hands: controls.py     │         └──────────────────┘
│  brain: brain.py        │
│  diary: progress.py     │
└─────────────────────────┘
```

The bot is a **sense → think → act loop**, framed for Yonch as:
**eyes** (screenshot + find pictures), **brain** (which screen am I on? what do I do?),
**hands** (tap, swipe, move the joystick), **diary** (write down every game we played).

### Modules (package `yonchbot/`)

- `device.py` — `Device` interface with two implementations:
  - `AdbDevice` — real device: `adb exec-out screencap -p` for eyes, `adb shell input` for hands.
  - `ReplayDevice` — plays back a folder of recorded screenshots and records taps;
    lets us build & test everything without the game, and lets Yonch "unit test" the bot.
- `vision.py` — `find(screen, template) -> Match | None` using OpenCV
  `matchTemplate` with a confidence threshold. `Match` has `center`, `confidence`, `box`.
- `controls.py` — `tap(device, x, y)`, `swipe(...)`, `hold_joystick(direction, seconds)`.
  Joystick = long swipe from the joystick anchor point; attack = tap the attack button.
- `screens.py` — screen recognition: given a screenshot, return which game screen we're
  on (`LOBBY`, `LOADING`, `IN_MATCH`, `MATCH_END`, `REWARDS`, `UNKNOWN`) by looking for
  template images in `assets/templates/`.
- `brain.py` — the state machine: for each recognized screen, do the right thing
  (lobby → tap PLAY; in match → run `play_match`; match end → tap continue; etc.).
  Includes a max-games limit and a panic key (Ctrl-C always safe).
- `play.py` — in-match behavior, deliberately simple and tunable:
  move in a pattern (config-chosen: `circle`, `zigzag`, `bush_camper`), attack every
  N seconds (auto-aim tap). This is the file Yonch will tweak the most.
- `progress.py` — appends one row per game to `data/games.csv`
  (timestamp, brawler, result, duration, notes) and computes streaks/totals.
- `dashboard.py` — renders `data/progress.html`: games played, results over time,
  a "bot level" that grows with total games — visible progress, the whole point.
- `cli.py` (+ `__main__.py`) — kid-friendly commands:
  `screenshot`, `tap X Y`, `find <template>`, `where` (which screen), `play [n]`,
  `dashboard`. Each prints friendly, emoji-flavored output.
- `config.yaml` — all coordinates, timings, thresholds, and "personality" knobs in one
  editable file. No magic numbers in code.
- `assets/templates/` — cropped PNGs of buttons. Ships with a README explaining how
  Yonch captures his own (screenshot → crop the PLAY button → save). Template capture
  is a curriculum session, not something we pre-bake (device resolutions differ).

### Data flow

`Device.screenshot()` → numpy image → `screens.which_screen()` → `brain.step()` decides
→ `controls.*` → `Device.tap/swipe` → repeat. Every finished match → `progress.log_game()`.

### Error handling

- Unknown screen for > N seconds → take a "help me" screenshot into `data/stuck/`,
  tap the safe corner (configurable), and continue; after M consecutive unknowns, stop
  cleanly with a friendly message. Never loops blindly.
- ADB disconnect → clear error telling you to check the cable/emulator.
- All waits are config-driven with generous defaults; the bot is slow on purpose
  (watchability > efficiency — Yonch should be able to narrate what it's doing).

### Testing

- `pytest` suite that runs with **no device and no game**:
  - `vision` tested with synthetic images (draw a shape, crop it, find it).
  - `screens`/`brain` tested with the `ReplayDevice` and generated fixture images.
  - `progress` tested against a temp CSV.
- Live testing happens in the curriculum sessions with the real device.

## Curriculum (`MENTOR_GUIDE.md`)

Eight ~90-minute sessions, each with: goal, what the mentor preps, what Yonch does
hands-on, the "victory moment", and what he learned. Sessions:

1. **The Rules & The Lab** — why a lab account, install tools, connect phone, first `adb devices`.
2. **The Bot's Eyes** — take a screenshot from Python; open it; it's just numbers!
3. **The Bot's Hands** — first tap from code; make the phone do something. (Huge wow moment.)
4. **Teach It To See** — crop the PLAY button, template matching, confidence scores.
5. **Which Screen Are We On?** — screen detection; the idea of *state*.
6. **The Brain** — the loop: if lobby → press play; watch it start a match alone.
7. **Playing The Game** — joystick math, movement patterns, attack timing; tweak `play.py`.
8. **The Diary & The Dashboard** — progress chart, bot levels, set a summer goal (e.g., "100 games logged").
Plus a **graduation ideas** list (smarter aiming, avoid walls, Discord notifications).

## Success criteria

- `pytest` green with zero devices attached.
- `python -m yonchbot play` runs the full loop against `ReplayDevice` fixtures.
- Curriculum is complete enough that a mentor can run session 1 without reading the code.
- Progress is visible: dashboard renders from logged games.
