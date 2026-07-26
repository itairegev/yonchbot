# Frida vs. YOLO vision — research & decision (2026-07-26)

Triggered by: screen-scraping vision fails this season (0 enemies/ball detected;
bot "shoots at the borders"). Question raised: use **Frida** (memory reading) to
sidestep vision? See also [[vision-detection-findings]],
[[yonchbot-vision-and-brawlball-research]].

## DECISION: Do NOT use Frida. Train a YOLO object detector instead.

## Why Frida is the wrong tool here
- **Needs root or a repackaged APK.** The phone (stock Samsung Galaxy A16,
  SM-A165F) is non-rooted. Rooting **permanently trips Knox (eFuse), wipes the
  device, voids warranty, breaks banking/secure apps.** The non-root path
  (repackage APK + frida-gadget) requires **re-signing**, which Brawl Stars'
  signature/integrity check rejects.
- **Brawl Stars is hardened with Promon SHIELD** (commercial RASP). It
  specifically: scans for Frida (`libFridaGadget.so`, ports 27042/27043),
  verifies APK signing cert, detects root, and **terminates the app on any
  tampering.**
- **Ban risk is high & permanent.** Client-side detection fires on *attaching
  at all* — read-only vs write makes no difference. Supercell ToS is
  zero-tolerance on bots/automation ("permanent ban"). Server-side anti-bot
  detection is rolling out in 2026.
- Net: Frida here = a device-wrecking arms race, not a stable foundation.

## Why YOLO object detection is the right path
The bot's real need is reliable game-state (enemy / ball / player / wall
positions). The failure is that **color/template matching is brittle** — breaks
on skins, maps, lighting. A **learned object detector (YOLOv8)** solves exactly
this:
- Handles new skins/maps/lighting that break template matching.
- **Zero device modification** — keeps the existing `adb screencap` + adb-tap
  pipeline; only the detector inside `vision.py` changes.
- No Frida ban tripwire. (The bot's own automation still carries ToS risk →
  **lab account only**, per the project's existing rule. [[yonchbot-purpose]])
- Great teaching arc for the kid: capture frames → label → train → measure
  accuracy (mAP/precision-recall) → close the loop. Real, modern, transferable
  ML.
- Head start: public **Roboflow Brawl Stars datasets** (player/enemy/wall/bush
  already labeled) and open-source YOLOv8 Brawl Stars bots exist.

## Caveats (state plainly)
- Better vision does NOT remove the ToS/automation ban risk. Keep everything on
  the throwaway **lab account**.
- If the "read game memory" experience is wanted for its own sake, do it on an
  open-source / self-made game we own — never a hardened commercial title.

## Sources
- Frida Android docs: https://frida.re/docs/android/
- OWASP MASTG (non-root gadget limits): https://mas.owasp.org/MASTG/techniques/android/MASTG-TECH-0026/
- Promon SHIELD reversal: https://github.com/KiFilterFiberContext/promon-reversal
- Supercell ToS: https://supercell.com/en/terms-of-service/
- Brawl Stars 2026 anti-cheat: https://www.sportsdunia.com/gaming/brawl-stars-anti-cheat-system-update-leaks-may-2026
- Roboflow BS dataset: https://universe.roboflow.com/ai-training-wheiu/brawl-stars-bot-bnvxv
- YOLOv8 BS bot (NeuroNeon): https://github.com/eforce67/NeuroNeon
