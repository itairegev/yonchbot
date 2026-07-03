# 🗺️ The Mentor Guide — YonchBot Summer Plan

For the uncle (and parents). Eight sessions, ~60–90 minutes each, one or
two per week. Every session ends with a **victory moment** — something
that visibly works. Never push past the victory moment; end on a high.

**The real goal** is not the bot. It's the moment Yonch realizes:
*"I set a goal, I broke it into steps, I got stuck, I got unstuck, and
now a thing I built is doing what I told it to."* The bot is the vehicle.

### Ground rules to establish in session 1, together
- The bot plays only on the **lab account** (a fresh account made for it).
  Botting is against Supercell's rules — using a lab account is how
  engineers experiment without hurting the real thing. If the lab
  account gets banned someday, that's part of the experiment.
- Yonch drives the keyboard whenever possible. You navigate, he types.
- Getting stuck is the curriculum, not a failure of it. When something
  breaks, say "great, a bug!" and mean it.

### What you need
- This Mac, this project folder.
- An Android phone (any cheap/old one works) **or** an Android emulator
  on the Mac (BlueStacks Air / MuMu Player — both run on Apple Silicon).
- Brawl Stars installed on it, logged into a **new** account.
- A USB cable (for a real phone).

---

## Session 1 — The Rules & The Lab 🧪

**Goal:** understand what we're building, set up the tools, make the
computer and the phone talk to each other.

1. **The pitch (10 min).** Ask Yonch: "If you had a robot that could see
   the screen and touch the screen, could it play Brawl Stars?" Let him
   design the robot out loud. He'll invent look-think-act on his own —
   then show him `README.md`: that's literally the plan.
2. **The rules talk (10 min).** Read Rule #1 together. Let *him* create
   the lab account and name it something fun.
3. **Install the tools (grown-up hands ok here):**
   ```bash
   brew install android-platform-tools
   cd ~/projects/yonchbot
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Wake up the phone.** Follow **`docs/PHONE-SETUP.md`** together — it's a
   6-step checklist with a "how you know it worked" check after each step
   (7-tap developer mode, USB debugging, the Allow popup, `adb devices`).
   Let Yonch do the taps.
5. **🏆 Victory moment:** the device appears in the list. The computer
   and the phone are talking. Run `python -m yonchbot check` for the
   full green-checkmark experience.

**What he learned:** what a terminal is, that programmers install tools,
that devices can talk to each other, and why labs exist.

---

## Session 2 — The Bot's Eyes 👀

**Goal:** take a screenshot from code and discover an image is numbers.

1. Yonch runs: `python -m yonchbot screenshot` — then opens the picture.
   The computer just *saw* the phone.
2. Open Python together and peek inside the image:
   ```python
   from yonchbot.device import AdbDevice
   image = AdbDevice().screenshot()
   print(image.shape)        # (height, width, 3) — it's a grid!
   print(image[500][800])    # one pixel = 3 numbers (blue, green, red)
   ```
3. Play "pixel detective": pick a spot on the screen, guess its three
   numbers, print them, see who was closest.
4. **🏆 Victory moment:** "a photo is just a spreadsheet of numbers" —
   watch his face when this lands.

**What he learned:** images are data, coordinates (x, y), and that y
counts *downward* on screens (this will matter in session 7!).

---

## Session 3 — The Bot's Hands 👉

**Goal:** make the phone do something from code. Biggest wow of the project.

1. Take a screenshot, open it, and find something tappable. Measure its
   position (Preview shows pixel coordinates when you select).
2. Yonch types: `python -m yonchbot tap 800 500` (his numbers).
   **The phone taps itself.**
3. Free play: navigate the game menus entirely by terminal commands.
   Make it a challenge: "get from the lobby to the shop using only taps."
4. Read `yonchbot/controls.py` together — it's short. Find where the tap
   actually happens.
5. **🏆 Victory moment:** controlling a phone without touching it. Magic
   that he understands is not magic.

**What he learned:** code has real-world effects; coordinates again;
reading someone else's code.

---

## Session 4 — Teach It To See 🎯

**Goal:** template matching — the bot finds the PLAY button by itself.

1. Read `assets/templates/README.md` and create `play_button.png`
   together (screenshot → crop in Preview → save).
2. Yonch runs: `python -m yonchbot find play_button` → `🎯 Found it! 97% sure.`
3. Experiment time (this is the science lesson):
   - Crop a *bad* template (half the button + background) — score drops.
   - In `config.yaml`, set `match_threshold: 0.99` — the bot gets picky.
   - Set it to `0.3` — the bot starts "finding" buttons that aren't there.
   Talk about it: robots aren't sure, they're *confident to a degree*.
4. Capture the other 3 templates (`in_match.png`, `match_end.png`,
   `rewards.png`) — the table in the templates README says what to crop.
5. **🏆 Victory moment:** the bot says where the button is, and it's right.

**What he learned:** how machines "see" (sliding comparison + score),
thresholds and false positives — genuinely the same tradeoff every AI
system deals with.

---

## Session 5 — Which Screen Are We On? 🗺️

**Goal:** screen detection; the idea of *state*.

1. Ask first: "You look at the game for half a second and know if you're
   in the lobby or in a match. HOW?" (He recognizes landmarks. So will
   the bot — that's what the templates were for.)
2. Yonch runs `python -m yonchbot where` on different screens: lobby,
   in a match, on the end screen. The bot names each one.
3. Read `yonchbot/screens.py` together. Draw the map on paper:
   LOBBY → LOADING → MATCH → END → REWARDS → back to LOBBY.
4. Run the test suite: `python -m pytest tests/ -q` — 17 green dots.
   Explain: these are little robots that check OUR robot. Break something
   on purpose (edit a number in `screens.py`), watch a test go red, fix it.
5. **🏆 Victory moment:** the bot correctly names every screen he shows it.

**What he learned:** states and state machines, landmarks-as-evidence,
and what tests are for.

---

## Session 6 — The Brain 🧠

**Goal:** the full loop runs; the bot starts a match BY ITSELF.

1. Read `yonchbot/brain.py` together — it's the whole bot in one page:
   *see the lobby → press play; see a match → play; see the end → log it.*
2. Before running it, ask him to predict out loud exactly what the bot
   will do, step by step. (Prediction → observation. Science.)
3. `python -m yonchbot play 1` — narrate what it's doing as it happens.
   It will press PLAY. It will flail around the match adorably. That's fine.
4. When it hits a screen it doesn't know, it saves a photo in
   `data/stuck/` and eventually stops politely. Look at those photos —
   "what confused the robot?" is a great debugging conversation.
5. **🏆 Victory moment:** the bot plays a match, start to finish, and
   writes it in its diary (`data/games.csv` — open it!).

**What he learned:** loops, if/else as decision-making, and that a dumb
loop of simple rules produces surprisingly alive behavior.

---

## Session 7 — Playing The Game ⚔️

**Goal:** make the bot play *better*. This is his session — you're just
the assistant now.

1. Open `yonchbot/play.py`. It's built to be tweaked:
   - Try each movement pattern (`config.yaml` → `pattern`):
     `circle`, `zigzag`, `bush_camper`, `headless_chicken`.
   - Change `attack_every_steps`. Faster attacks — better or worse?
   - **The big one:** he invents his own pattern and adds it to
     `PATTERNS` (a list of compass angles). His initials? A square?
2. Run 2–3 games per pattern (`python -m yonchbot play 2`), keep score
   on paper: which pattern survives longest?
3. Joystick math, gently: angles as compass directions, and remember
   session 2 — y counts downward, that's why the code *subtracts* sin.
4. **🏆 Victory moment:** "the bot is playing MY strategy."

**What he learned:** editing real code, experiment design (change ONE
thing at a time!), a taste of trigonometry that feels like a superpower.

---

## Session 8 — The Diary & The Dashboard 📊

**Goal:** see the whole summer's progress; set the next goal.

1. `python -m yonchbot dashboard` → open `data/progress.html`.
   Games played, moves made, **bot level** (levels up every 5 games),
   games-per-day chart. That's HIS summer, in data.
2. Read `yonchbot/progress.py` — the diary is a simple CSV. Open it in
   Numbers/Sheets too: same data, different views.
3. Set a summer goal together and write it down: e.g. "bot level 10 by
   September" or "a pattern that finishes 10 matches in a row."
4. **Graduation talk:** everything he touched — terminal, Python, images,
   coordinates, state machines, loops, tests, data — is what professional
   engineers use daily. Not kid versions. The real thing.
5. **🏆 Victory moment:** the dashboard, plus the sentence "I built this."

**What he learned:** data collection and visualization, goal-setting with
measurable numbers — and that he can, in fact, do anything.

---

## Graduation ideas (if the summer keeps going 🚀)

Ordered roughly by difficulty:

1. **Better brawler pick** — tap a specific brawler in the lobby first.
2. **Health awareness** — read the health bar's pixels; when it's low,
   switch to the `bush_camper` pattern (his first *adaptive* behavior!).
3. **Walk toward the action** — find enemies on screen (they have
   red health bars) and walk toward/away from them.
4. **Notifications** — the bot messages the family chat when it levels up.
5. **A "wins" column** — detect the victory vs. defeat screen as two
   different templates and log which one happened.
6. **Show a friend** — the best test of understanding is explaining it.

## When things break (they will)

- `adb devices` shows nothing → different cable/port; re-accept the
  "allow USB debugging?" popup on the phone.
- `find` can't see a button that's clearly there → re-crop tighter; check
  the game is in the same language/resolution as when you cropped.
- Bot taps the wrong place → your device's resolution differs from
  `config.yaml`'s positions; re-measure with a screenshot.
- Bot keeps saying UNKNOWN → look at `data/stuck/` photos; probably a
  popup you need a template for, or just tap it away and continue.
- Something else → `python -m yonchbot check` first, always.
