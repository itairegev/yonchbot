# Running Brawl Stars on the Mac (no phone needed) 🖥️

You don't need an Android phone — the Mac can *pretend* to be one.
That pretend phone is called an **emulator**. The bot can't tell the
difference (remember the costume idea from `device.py`? Same trick,
one level deeper).

## One-time setup (grown-up hands)

```bash
# 1. the tools (adb + Android SDK manager)
brew install android-platform-tools android-commandlinetools

# 2. the Android system itself (~2 GB download, be patient)
yes | sdkmanager --licenses
sdkmanager --install "platform-tools" "emulator" "platforms;android-35" \
  "system-images;android-35;google_apis_playstore;arm64-v8a"

# 3. create the virtual phone (we call it "yonchphone")
avdmanager create avd --name yonchphone --package \
  "system-images;android-35;google_apis_playstore;arm64-v8a" --device "pixel_7"

# 4. three settings avdmanager gets wrong for our use:
#    let the Mac keyboard type into the phone, use the real GPU
#    (without it, games run in slow-motion software rendering),
#    and give the phone enough storage for a big game
sed -i '' \
  -e 's/hw.keyboard=no/hw.keyboard=yes/' \
  -e 's/hw.gpu.enabled=no/hw.gpu.enabled=yes/' \
  -e 's/hw.gpu.mode=auto/hw.gpu.mode=host/' \
  -e 's/disk.dataPartition.size=6G/disk.dataPartition.size=16G/' \
  ~/.android/avd/yonchphone.avd/config.ini
```

## Starting the virtual phone (every session)

```bash
emulator -avd yonchphone &
```

A phone window appears on the Mac. Wait until it fully boots, then check:

```bash
adb devices          # should show:  emulator-5554   device
python -m yonchbot check
```

## Installing Brawl Stars (once)

1. On the virtual phone, open the **Play Store** app.
2. Sign in with a Google account — use a family/spare account,
   not a main one (lab-account thinking, all the way down).
3. Search for **Brawl Stars**, install, open, and create the
   **lab account** (Rule #1!).
4. Play one match by hand (well — by mouse) to get past the tutorial.

## Good to know

- The mouse is your finger. Click-drag = swipe.
- If the game feels slow or choppy, that's normal for the official
  emulator — the bot doesn't mind, it's not in a hurry. If it bothers
  the humans, gaming emulators (BlueStacks Air, MuMu Player) are
  smoother, but getting adb working on them is fiddlier.
- Everything else in the project works exactly the same as with a real
  phone: screenshots, taps, templates, `play`, the dashboard.
- To wipe the virtual phone and start fresh:
  `avdmanager delete avd --name yonchphone` and re-create it.
