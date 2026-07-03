# 🤖 YonchBot

A robot that plays Brawl Stars — built by Yonch and his uncle, one summer.

The bot is not magic. It does three things, over and over:

1. **👀 LOOKS** — takes a screenshot of the phone
2. **🧠 THINKS** — figures out which screen it's on and what to do
3. **👉 ACTS** — taps and swipes, like a robot finger

That's it. That's also how self-driving cars, warehouse robots and Mars
rovers work: look → think → act → repeat. You're building the same thing,
just for Brawl Stars.

## ⚠️ Rule #1 — the Lab Account

Automating a game is **against Supercell's rules**, and accounts that do
it get banned. So this project has one law:

> **The bot only ever plays on a brand-new "lab account" we made just
> for it. NEVER on your real account.**

Real engineers work like this too: you never experiment on the real thing.
Labs exist so you can break stuff safely.

## What's in the box

```
yonchbot/            the bot itself
  device.py            talking to the phone (or a pretend phone for tests)
  vision.py            the eyes  — finding buttons in screenshots
  controls.py          the hands — taps, swipes, joystick math
  screens.py           "which screen is this?"
  brain.py             the think-loop (the heart of the bot)
  play.py              HOW it plays — the fun file to tweak! 🎮
  progress.py          the diary — every game gets written down
  dashboard.py         builds the progress web page
  cli.py               the commands you type
assets/templates/    small pictures of buttons (you create these — see its README)
tests/               proof the bot works, no phone needed
config.yaml          the control panel — positions, timing, personality
MENTOR_GUIDE.md      the step-by-step summer plan 👈 START HERE
```

## Quick start (grown-up version)

```bash
# 1. tools
brew install android-platform-tools        # adb, for talking to the phone
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. phone: enable Developer Options → USB debugging, plug in via USB
#    (or use an Android emulator like BlueStacks/MuMu with adb enabled)
adb devices                                # should list your device

# 3. checkup
python -m yonchbot check

# 4. teach it to see (capture templates — assets/templates/README.md)
python -m yonchbot screenshot
python -m yonchbot find play_button

# 5. GO
python -m yonchbot play 1
python -m yonchbot dashboard
```

## The commands

| Command | What it does |
|---|---|
| `python -m yonchbot check` | is everything connected and ready? |
| `python -m yonchbot screenshot` | save a picture of the phone screen |
| `python -m yonchbot tap 500 300` | tap the screen at x=500, y=300 |
| `python -m yonchbot find play_button` | can the bot see this button right now? |
| `python -m yonchbot where` | which game screen are we on? |
| `python -m yonchbot play 3` | play up to 3 games |
| `python -m yonchbot dashboard` | build the progress page |

`Ctrl-C` **always** stops the bot. You are the boss, not the robot.

## Running the tests

```bash
python -m pytest tests/
```

17 tests, no phone needed — they run the bot against a *pretend* phone
showing fake game screens. If they're all green, the bot's brain works.
