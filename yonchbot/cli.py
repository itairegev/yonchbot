"""YonchBot's command line - how humans give the bot orders.

Try these (from the project folder, with the venv activated):

    python -m yonchbot check              is everything set up?
    python -m yonchbot screenshot         save a picture of the phone screen
    python -m yonchbot tap 500 300        tap the screen at x=500, y=300
    python -m yonchbot find play_button   look for a template on screen NOW
    python -m yonchbot where              which game screen are we on?
    python -m yonchbot play               play games (up to safety.max_games)
    python -m yonchbot dashboard          build the progress page
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import cv2
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(PROJECT_ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def make_device(config: dict):
    from .device import AdbDevice
    serial = config["device"]["serial"] or None
    return AdbDevice(serial=serial)


def make_detector(config: dict):
    from .screens import ScreenDetector
    return ScreenDetector(
        PROJECT_ROOT / config["vision"]["templates_dir"],
        threshold=config["vision"]["match_threshold"],
    )


def cmd_check(config: dict) -> None:
    """Friendly checkup: adb? device? templates?"""
    print("🔍 Checking the setup...")
    import shutil
    if shutil.which("adb"):
        print("  ✅ adb is installed")
    else:
        print("  ❌ adb is missing. Install it:  brew install android-platform-tools")
        return

    from .device import list_devices
    devices = list_devices()
    if not devices:
        print("  ❌ no phone found. Plug in via USB, turn on USB debugging,")
        print("     and tap 'Allow' on the phone. See docs/PHONE-SETUP.md")
        return
    if len(devices) > 1 and not config["device"]["serial"]:
        print(f"  🟡 {len(devices)} devices connected: {', '.join(devices)}")
        print("     Pick one: put its serial in config.yaml → device.serial")
        print("     (having both a phone AND the emulator plugged in does this)")

    try:
        device = make_device(config)
        image = device.screenshot()
        h, w = image.shape[:2]
        print(f"  ✅ phone connected! Screen is {w} x {h} pixels")
    except Exception as e:
        print(f"  ❌ can't reach the phone: {e}")
        return
    detector = make_detector(config)
    missing = detector.missing_templates
    if missing:
        print(f"  🟡 missing template pictures: {', '.join(missing)}")
        print("     (that's session 4 & 5 of the mentor guide - all good!)")
    else:
        print("  ✅ all template pictures are ready")
    print("🎉 Setup looks good!")


def cmd_screenshot(config: dict) -> None:
    device = make_device(config)
    image = device.screenshot()
    out_dir = PROJECT_ROOT / "data" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime("screen_%Y%m%d_%H%M%S.png")
    path = out_dir / name
    cv2.imwrite(str(path), image)
    print(f"📸 Saved! Open it:  open {path}")


def cmd_tap(config: dict, x: int, y: int) -> None:
    device = make_device(config)
    device.tap(x, y)
    print(f"👉 Tapped the screen at ({x}, {y})")


def cmd_find(config: dict, template_name: str) -> None:
    from . import vision
    device = make_device(config)
    template_path = PROJECT_ROOT / config["vision"]["templates_dir"] / f"{template_name}.png"
    template = vision.load_template(template_path)
    screen = device.screenshot()
    match = vision.find(screen, template, config["vision"]["match_threshold"])
    if match:
        print(f"🎯 Found it! Center at {match.center}, {match.confidence:.0%} sure.")
    else:
        print("🙈 Couldn't find it on the screen right now.")


def cmd_where(config: dict) -> None:
    device = make_device(config)
    detector = make_detector(config)
    screen = detector.which_screen(device.screenshot())
    print(f"🗺️  We are on the: {screen.value.upper()} screen")


def cmd_play(config: dict, games: int | None) -> None:
    from .brain import Brain
    from .progress import Diary
    max_games = min(games or config["safety"]["max_games"],
                    config["safety"]["max_games"])
    device = make_device(config)
    detector = make_detector(config)
    if detector.missing_templates:
        print("❌ Can't play yet - these template pictures are missing:")
        for t in detector.missing_templates:
            print(f"   • {t}")
        print("See assets/templates/README.md for how to make them.")
        return
    diary = Diary(PROJECT_ROOT / config["diary"]["csv_path"])
    brain = Brain(device, detector, diary, config)
    print(f"🤖 YonchBot is playing! (max {max_games} games, Ctrl-C to stop)")
    try:
        done = brain.run(max_games=max_games)
    except KeyboardInterrupt:
        print("\n🛑 Stopped by human. Good call, boss.")
        return
    print(f"🏆 Done! Finished {done} game(s). Run `dashboard` to see progress.")


def cmd_dashboard(config: dict) -> None:
    from .dashboard import build_dashboard
    from .progress import Diary
    diary = Diary(PROJECT_ROOT / config["diary"]["csv_path"])
    out = build_dashboard(diary, PROJECT_ROOT / config["diary"]["dashboard_path"])
    totals = diary.totals()
    print(f"📊 Dashboard ready: {totals.games} games, bot level {totals.bot_level}.")
    print(f"   Open it:  open {out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="yonchbot", description="A robot that plays Brawl Stars (on our lab account!)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check")
    sub.add_parser("screenshot")
    p_tap = sub.add_parser("tap")
    p_tap.add_argument("x", type=int)
    p_tap.add_argument("y", type=int)
    p_find = sub.add_parser("find")
    p_find.add_argument("template")
    sub.add_parser("where")
    p_play = sub.add_parser("play")
    p_play.add_argument("games", type=int, nargs="?", default=None)
    sub.add_parser("dashboard")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return
    config = load_config()
    try:
        if args.command == "check":
            cmd_check(config)
        elif args.command == "screenshot":
            cmd_screenshot(config)
        elif args.command == "tap":
            cmd_tap(config, args.x, args.y)
        elif args.command == "find":
            cmd_find(config, args.template)
        elif args.command == "where":
            cmd_where(config)
        elif args.command == "play":
            cmd_play(config, args.games)
        elif args.command == "dashboard":
            cmd_dashboard(config)
    except Exception as e:
        print(f"💥 Oops: {e}", file=sys.stderr)
        sys.exit(1)
