# Using a real Android phone 📱 (the best way!)

A real phone is the smoothest path: no emulator-detection fight, real
graphics, and it's exactly how professional game-testing labs work. This is
a great **Session 1** to do with Yonch — he can do most of the taps himself.

Do these in order. Each step has a "how you know it worked" check.

---

## Step 1 — Make a lab account (Rule #1) 🧪

Before anything: on the phone, open Brawl Stars and create a **brand-new
account just for the bot**. Never the real one. Let Yonch name it.
Play one match by hand to get past the tutorial.

*Why:* botting can get an account banned. Labs are where engineers
experiment safely. This is lesson #1 of the whole project.

---

## Step 2 — Turn on Developer Options 🔧

On the phone:

1. Settings → **About phone**
2. Find **Build number** (sometimes under "Software information")
3. **Tap it 7 times.** It'll count down: "You are now 3 steps away…"
4. It says **"You are now a developer!"**

✅ *Worked if:* there's now a **Developer options** menu in Settings
(often under System, or near the bottom).

*Fun fact for Yonch:* every Android phone has a secret developer mode
hidden behind 7 taps. You just unlocked the same menu the engineers at
Google use.

---

## Step 3 — Turn on USB debugging 🔌

1. Settings → **Developer options**
2. Turn ON **USB debugging**
3. (Nice to also turn ON **Stay awake** — keeps the screen on while charging,
   so the phone doesn't sleep mid-game.)

✅ *Worked if:* "USB debugging" shows a checkmark / is toggled on.

---

## Step 4 — Plug in and shake hands 🤝

1. Plug the phone into the Mac with a USB cable.
   ⚠️ Some cheap cables are **charge-only** and carry no data — if nothing
   shows up in Step 5, try a different cable first. That's the #1 gotcha.
2. On the phone a popup appears: **"Allow USB debugging?"** — check
   "Always allow from this computer" and tap **Allow**.
   (If you don't see it, unlock the phone and unplug/replug.)

Then on the Mac, in the project folder:

```bash
adb devices
```

✅ *Worked if:* you see a line like `R58M20XXXXX   device`
(a jumble of letters/numbers = your phone's serial, then the word `device`).

- `unauthorized` instead of `device`? → you missed the Allow popup. Unplug,
  replug, tap Allow.
- Nothing listed? → charge-only cable, or USB debugging is off. Recheck.

---

## Step 5 — Let the bot meet the phone 🤖

```bash
source .venv/bin/activate       # if not already active
python -m yonchbot check
```

✅ *Worked if:* you see
```
✅ adb is installed
✅ phone connected! Screen is 1080 x 2400 pixels   (your numbers may differ)
🟡 missing template pictures: ...                  (totally expected!)
🎉 Setup looks good!
```

The yellow "missing template pictures" line is **supposed** to be there —
teaching the bot to see the buttons is Session 4. You're done with setup.

---

## Step 6 — First magic moment ✨

With Brawl Stars open on the phone:

```bash
python -m yonchbot screenshot      # the Mac takes a photo of the phone!
```

Open the saved picture. The computer just *saw* the phone screen.
That's Session 2 — and a perfect place to stop on a high note.

---

## Handy notes

- **Multiple devices plugged in?** If both the phone and an emulator are
  connected, put the phone's serial (from `adb devices`) into `config.yaml`
  → `device.serial` so the bot knows which one to use.
- **Positions differ per phone.** The joystick/attack-button coordinates in
  `config.yaml` are guesses — you'll measure the real ones from a screenshot
  in Session 3/7. Totally normal.
- **Screen must stay on & unlocked** while the bot plays. "Stay awake" from
  Step 3 helps; you can also just tap the phone occasionally.
- **To disconnect cleanly:** just unplug. Nothing is installed on the phone —
  the bot only ever looks and taps from outside.
