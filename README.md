# 🤖 YonchBot

A robot that plays Brawl Stars — built by Yonatan and his uncle, one summer,
to learn how real software gets made.

The bot is not magic. It does three things, over and over:

1. **👀 LOOKS** — takes a screenshot of the phone
2. **🧠 THINKS** — figures out which screen it's on and what to do
3. **👉 ACTS** — taps and swipes, like a robot finger

That's it. That's also how self-driving cars, warehouse robots and Mars
rovers work: look → think → act → repeat. Same idea, just for Brawl Stars.

---

## 👨‍👦 For the grown-ups: what this project actually is

This is a **teaching project**. The bot is the vehicle; the cargo is
everything a working engineer does daily, in kid-sized portions:

- **Computer vision** — the bot finds buttons, enemies, the ball and the
  poison gas by color and shape (OpenCV, no AI models).
- **State machines** — "which screen am I on, and what's the one right
  thing to do here?"
- **Debugging as a way of life** — every time the bot got confused it
  saved a photo of what it saw (`data/stuck/`). Every one of those photos
  became a fix. That folder is a museum of solved mysteries.
- **The scientific method** — change ONE thing, measure, keep the winner.
  The bot now literally runs this loop on itself (see below).
- **Honest data** — every game is logged to a diary (`data/games.csv`)
  with a WIN/loss label the bot reads off its own screen.

**What it achieved in its first two days** (all fully autonomous):
took a fresh account from 0 to **650+ trophies**, won a Solo Showdown
outright (Rank 1 of 10), then switched to Brawl Ball (football) and won
roughly two-thirds of ~60 matches, carrying one brawler to **Silver rank**.

**Running costs: zero.** The bot is plain Python + OpenCV + adb. No AI,
no cloud, no tokens, no subscriptions. An AI assistant helped *write* it;
none is involved in *running* it.

## ⚠️ Rule #1 — the Lab Account

Automating a game is **against Supercell's terms of service**, and
accounts that do it can get banned. So this project has one law:

> **The bot only ever plays on a brand-new "lab account" made just for
> it. NEVER on anyone's real account.**

If the lab account is ever banned — that's part of the experiment, and
a fine lesson in why rules and test environments exist. Real engineers
work exactly this way: never experiment on the real thing.

## What's in the box

```
yonchbot/            the bot itself
  device.py            talking to the phone (or a pretend phone for tests)
  vision.py            the eyes  — buttons, health bars, the ball, gas, bushes
  controls.py          the hands — taps, swipes, joystick math, aimed shots
  screens.py           "which screen is this?" (lobby, match, victory...)
  brain.py             the think-loop (the heart of the bot)
  play.py              HOW it plays — strategy rules, the fun file to tweak 🎮
  evolve.py            the science lab — the bot experiments on ITSELF 🧬
  rl.py                a tiny learning brain (the "Karpathy method") 🧠
  progress.py          the diary — every game gets written down
  dashboard.py         builds the progress web page
  cli.py               the commands you type
assets/templates/    small pictures of buttons the bot learned to recognize
tests/               40 tests — proof the bot works, no phone needed
config.yaml          the control panel — positions, timing, strategy knobs
MENTOR_GUIDE.md      the step-by-step summer teaching plan 👈 START HERE
docs/                phone setup, emulator options, research notes
```

## Quick start

```bash
# 1. tools (on a Mac)
brew install android-platform-tools        # adb, for talking to the phone
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. phone: enable Developer Options → USB debugging, plug in via USB
#    Full kid-friendly checklist: docs/PHONE-SETUP.md
adb devices                                # should list the device

# 3. checkup
python -m yonchbot check

# 4. GO
python -m yonchbot play 3
python -m yonchbot dashboard
```

Keep the phone plugged in and its screen timeout long — the one thing
the bot cannot do is enter the PIN if the lock screen re-arms.

## The commands

| Command | What it does |
|---|---|
| `python -m yonchbot check` | is everything connected and ready? |
| `python -m yonchbot screenshot` | save a picture of the phone screen |
| `python -m yonchbot tap 500 300` | tap the screen at x=500, y=300 |
| `python -m yonchbot find play_button` | can the bot see this button right now? |
| `python -m yonchbot where` | which game screen are we on? |
| `python -m yonchbot play 10` | play up to 10 games by itself |
| `python -m yonchbot evolve 6 4` | 🧬 self-improve: 6 experiments, 4 games per side |
| `python -m yonchbot train 20` | 🧠 let the learning brain play & learn 20 games |
| `python -m yonchbot dashboard` | build the progress page (`data/progress.html`) |

`Ctrl-C` **always** stops the bot. Humans are the boss, not the robot.

## How it plays (the strategy, in one breath)

Flee the poison gas above all → in football, chase the ball and kick it
toward the enemy goal → shoot enemies with *led* shots (aim where they're
GOING) → fire the super the moment it glows → farm power cubes → hide in
bushes when there's nothing better to do — and never, ever stand still.

Almost every rule traces back to a human lesson: things Yonatan's family
said out loud ("run from the green clouds!", "keep shooting the same
enemy!") and one filmed round of a human winning, studied frame by frame.

## How it improves itself (no AI involved)

Two ways, both plain Python:

1. **Evolution** (`evolve`) — champion settings vs. challenger settings,
   one knob changed at a time, real games played, wins counted, the
   winner keeps the crown. Every experiment is logged to
   `data/evolution.csv`. This is the scientific method with a scoreboard.

2. **A learning brain** (`train`) — a tiny two-layer neural network
   (~120 lines of numpy, in the spirit of Andrej Karpathy's famous
   "Pong from Pixels") that starts knowing NOTHING and learns from pure
   consequence: win → repeat those moves more; lose → less. It saves its
   brain after every game and remembers forever. It starts hilariously
   bad. Watching its win-rate crawl upward over hundreds of games is the
   whole point.

## Running the tests

```bash
python -m pytest tests/
```

40 tests, no phone needed — they run the bot against a *pretend* phone
showing fake game screens: fake lobbies, fake enemies, a fake ball, even
fake poison gas. If they're all green, the bot's brain works.

## The story so far (for the campfire)

- The bot's very first template was cropped while a popup dimmed the
  screen — so it hunted a *grey* PLAY button that never exists. Lesson:
  robots see exactly what you show them.
- It once stood still because it couldn't recognize the match — and the
  game kicked it for being AFK. Lesson: bugs have consequences.
- It charged enemies bravely once, and finished rank 9 of 10. The diary
  remembers. Lesson: measure before you believe.
- It hid in a bush while its football team scored around it — recorded
  0 damage in a *victory*. Lesson: being present isn't participating.
- And then it won. Lesson: iteration works.

Every stuck screenshot, every diary row, and every test in this repo is
a chapter of that story. It was built in conversation with an AI coding
assistant — but what runs on the phone is 100% understandable, hackable,
kid-readable Python. Open `play.py` and change something. That's the way.
