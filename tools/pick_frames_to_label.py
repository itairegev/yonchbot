"""Pick a small, DIVERSE subset of gameplay frames to hand-label for YOLO.

data/gameplay/ has ~3,500 frames, but many are near-duplicates (captured
seconds apart in the same match). Labeling 300 near-identical frames teaches the
model nothing. This tool spreads the picks EVENLY across each session (date), so
the subset covers many different maps, moments, and positions.

Usage:
    python -m tools.pick_frames_to_label --count 300         # copy 300 spread-out frames
    python -m tools.pick_frames_to_label --count 300 --copy  # (copy is the default action)

Output: data/to_label/ - the set to open in Roboflow / labelImg.
See docs/LABELING-GUIDE.md for how to label them.
"""
from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "data" / "gameplay"
DST = PROJECT_ROOT / "data" / "to_label"

DATE_RE = re.compile(r"stuck_(\d{8})_")


def session_of(name: str) -> str:
    m = DATE_RE.match(name)
    return m.group(1) if m else "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=300,
                    help="how many frames to pick in total")
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--dst", default=str(DST))
    ap.add_argument("--dry", action="store_true", help="just print the plan")
    args = ap.parse_args()

    src = Path(args.src)
    files = sorted(f.name for f in src.glob("*.png"))
    if not files:
        print(f"No frames in {src}. Run tools.filter_gameplay_frames --copy first.")
        return

    # group by session
    by_session: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_session[session_of(f)].append(f)

    # allocate the budget across sessions proportional to their size, then
    # pick EVENLY SPACED frames within each session (max spread = max variety).
    total = len(files)
    picks: list[str] = []
    for session, group in sorted(by_session.items()):
        group.sort()
        share = max(1, round(args.count * len(group) / total))
        step = max(1, len(group) // share)
        chosen = group[::step][:share]
        picks.extend(chosen)
        print(f"  session {session}: {len(group)} frames -> pick {len(chosen)} "
              f"(every {step}th)")

    picks = picks[:args.count]
    print(f"\nTotal picked: {len(picks)}")

    if args.dry:
        print("(dry run - pass no --dry to copy into data/to_label/)")
        return

    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    for f in picks:
        shutil.copy(src / f, dst / f)
    print(f"Copied {len(picks)} frames to {dst}")
    print("Next: open them in Roboflow or labelImg. See docs/LABELING-GUIDE.md")


if __name__ == "__main__":
    main()
