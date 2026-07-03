# How the pros run & automate Brawl Stars 🔬

Research notes (July 2026). We hit a wall — Brawl Stars crashes on Google's
stock emulator. Before working around it, we asked: how do the people who do
this *for a living* — game QA teams, security researchers, and the automation
community — actually do it? Here's what they do, and what it means for us.

## The core reason for our crash

Supercell games ship a **hardware-attestation / anti-tamper layer** that runs
before the game does. It inspects the device for tell-tale signs of an emulator,
a rooted phone, or a debugger, and if it finds them it kills the app on the
splash screen. That's exactly our `zkvvp.Y: 02` crash. It is *intended*
behavior, not a bug — the same family of protection Supercell has used to block
Hay Day and Clash of Clans on emulators for years.

So everyone who runs these games off a normal phone is, in some sense, working
around a check that's designed to stop them. The three professional worlds do it
in three different ways.

## 1. Game QA teams — they don't fight the check, they own the build

Professional mobile-game QA almost never botfights the shipping anti-cheat,
because **they test the game *before* it ships**, on builds the studio gives them:

- **Real device farms.** Racks of actual phones (self-hosted with tools like
  GADS/Appium-Device-Farm, or rented from AWS Device Farm / Firebase Test Lab).
  Real hardware sidesteps emulator detection entirely, and GPU rendering matches
  what players see. This is the single most common professional answer.
- **Instrumented builds.** Tools like **AltTester** compile a testing SDK *into*
  the game, so the automation queries Unity objects directly instead of guessing
  from pixels. Requires the source/build — only the studio can do this.
- **Vision-AI automation on release builds.** Tools like **Drizz** and classic
  **Appium image recognition** drive the *shipping* build by looking at the
  screen and tapping — "see the PLAY button, tap the PLAY button." No source
  needed.
- **The takeaway:** *no single tool tests everything.* Pros layer functional
  automation + performance profiling + native-screen control.

**What's striking for us:** the vision-AI approach the pros use on release builds
is *exactly what YonchBot does.* Screenshot → find the button → tap it. We
independently built the same architecture a QA studio would reach for. That's a
real validation of the design, and a great thing to tell Yonch.

## 2. Security researchers — they study the check itself

Pen-testers and mobile-security researchers treat emulator/root detection as the
*subject* of study, using instrumentation frameworks (Frida, Magisk, Xposed) to
hook the app at runtime and observe or neutralize the checks. This is legitimate,
skilled work — it's how you audit whether an app's protections actually hold.

**We are deliberately NOT going here.** It's advanced, it edges into ToS/DMCA
grey areas, and it teaches an 11-year-old the wrong first lesson. We note it so
Yonch knows this world *exists* (security research is a real, cool career) —
but our project's rule holds: no hooking, no root, no tamper. We work *with* the
platform's interface, not against its protections.

## 3. The automation / botting community — the practical middle path

The open-source Brawl Stars bots (Jooi025's BrawlStarsBot, Soodoboo's, and
others) all converge on the **same recipe**, and it matches what we found by
trial:

- **Emulator: BlueStacks (5 / Air), on Windows or Mac.** Gaming emulators like
  BlueStacks present themselves convincingly enough that the game runs. Google's
  stock AVD does not. (This is our exact finding.)
- **Vision: OpenCV template matching + sometimes a YOLOv8 object detector** to
  find bushes, enemies, power cubes. Our template-matching approach is the same
  first rung; a YOLO "find the enemies" model is literally graduation idea #3 in
  our mentor guide.
- **Control: two schools.**
  - *BlueStacks-native macro control* (what Jooi025 uses on Windows): drive the
    emulator window with simulated mouse/keyboard. No ADB.
  - *ADB control* (what **YonchBot** uses): the clean, documented Android
    interface — `screencap` + `input tap/swipe`. Works on real phones AND on
    BlueStacks once you `adb connect` to it.
- **Reality check they all print:** it violates Supercell's ToS and risks a ban.
  Which is why our Rule #1 (lab account only) is the *right* engineering answer,
  not a killjoy one.

## What this means for YonchBot (decisions)

1. **Keep the ADB design.** It's the professional, portable interface. BlueStacks
   speaks ADB too (`adb connect 127.0.0.1:PORT`), so one bot runs on a real
   phone, a device farm, or BlueStacks — no code change. Most hobby bots are
   locked to one emulator on one OS; ours isn't. Good lesson: *program to the
   interface, not the vendor.*
2. **Use BlueStacks Air as the game host** (see EMULATOR.md). Keep the stock AVD
   as a safe practice phone for the early sessions.
3. **Best of all: a real cheap Android phone beats every emulator.** No detection
   fight, real GPU, plug in USB, `adb devices`, done. If the family has an old
   Android phone in a drawer, that's the smoothest path and the closest to how a
   QA device farm actually works.
4. **We stay on the ethical side of the line the security world walks:** vision +
   the official input interface, lab account only. Same tools as the pros,
   without the tamper.

## Sources

- Drizz, *Best Mobile Game Testing Tools in 2026* — https://www.drizz.dev/post/best-mobile-game-testing-tools-in-2026-complete-comparison
- Drizz, *Mobile Game Testing in 2026: The Complete Guide* — https://www.drizz.dev/post/mobile-game-testing-in-2026-the-complete-guide
- Appium Device Farm — https://devicefarm.org/
- PerfectQA, *Appium Image Recognition for Mobile Game Testing* — https://www.perfectqaservices.com/blog/appium-image-recognition-for-mobile-game-testing
- Jooi025 / BrawlStarsBot (BlueStacks + OpenCV/YOLO, Windows) — https://github.com/Jooi025/BrawlStarsBot
- BlueStacks: enabling ADB — https://support.bluestacks.com/hc/en-us/articles/23925869130381-How-to-enable-Android-Debug-Bridge-on-BlueStacks-5
- Emulator/root detection & bypass research (Frida/Magisk) — https://github.com/okankurtuluss/FridaBypassKit
