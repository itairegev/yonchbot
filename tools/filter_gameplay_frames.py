"""Sift the huge data/stuck/ pile into a clean set of IN-MATCH gameplay frames.

The bot saves a screenshot every time it's "confused" (data/stuck/). Most of
those are menus and matchmaking screens, but a big chunk are real in-match
Brawl Ball frames the bot couldn't read - and THOSE are the gold we want to
label and train a YOLO detector on (see docs/yolo-vision-plan.md).

This tool copies the likely-gameplay frames into data/gameplay/ so they're
ready to label. It's a HEURISTIC, not perfect - it errs toward keeping frames;
you'll still eyeball them before labeling.

How it tells gameplay from menus (no ML needed):
  * In-match frames have the SCORE BAR in the top corners (two small, brightly
    coloured boxes at top-left and top-right).
  * They have the CONTROL UI (attack/super buttons) - a saturated blob in the
    bottom-right.
  * The playfield fills the frame edge to edge (menus have flat panels / black
    letterbox bands).
A frame that shows BOTH the top score bar and the bottom controls is almost
certainly gameplay.

Usage:
    python -m tools.filter_gameplay_frames                 # dry run: just count
    python -m tools.filter_gameplay_frames --copy          # copy into data/gameplay/
    python -m tools.filter_gameplay_frames --copy --limit 400
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "data" / "stuck"
DST = PROJECT_ROOT / "data" / "gameplay"


def match_signature(img) -> tuple[float, float, float]:
    """Return (bottom-right control saturation, top score-bar saturation,
    edge fill). Higher = more like in-match gameplay."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # bottom-right control buttons: bright + saturated blob
    br = hsv[int(h * 0.70):int(h * 0.95), int(w * 0.82):w]
    br_sat = float(((br[:, :, 1] > 90) & (br[:, :, 2] > 90)).mean())

    # top score bar in BOTH corners (menus rarely have both)
    tl = hsv[0:70, 0:260]
    tr = hsv[0:70, w - 260:w]
    top_sat = float(((tl[:, :, 1] > 90).mean() + (tr[:, :, 1] > 90).mean()) / 2)

    # edge fill: gameplay fills to the frame edges; menus have flat/dark bands.
    # measure saturation along the left+right edge columns.
    edges = hsv[:, list(range(0, 30)) + list(range(w - 30, w))]
    edge_fill = float((edges[:, :, 1] > 60).mean())

    return br_sat, top_sat, edge_fill


def is_gameplay(img) -> bool:
    br_sat, top_sat, edge_fill = match_signature(img)
    # Require the control UI AND the score bar - the pair is the strong signal.
    # edge_fill is a tie-breaker that rejects letterboxed menu popups.
    return br_sat > 0.15 and top_sat > 0.10 and edge_fill > 0.25


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", action="store_true",
                    help="copy matching frames into data/gameplay/ (else dry run)")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after copying this many (0 = no limit)")
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--dst", default=str(DST))
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    files = sorted(src.glob("*.png"))
    print(f"Scanning {len(files)} frames in {src} ...")

    if args.copy:
        dst.mkdir(parents=True, exist_ok=True)

    kept = 0
    scanned = 0
    corrupt = 0
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            corrupt += 1
            continue
        scanned += 1
        if is_gameplay(img):
            kept += 1
            if args.copy:
                shutil.copy(f, dst / f.name)
            if args.limit and kept >= args.limit:
                break
        if scanned % 500 == 0:
            print(f"  ...{scanned} scanned, {kept} gameplay so far")

    pct = (100 * kept / scanned) if scanned else 0
    print(f"\nScanned {scanned} readable frames ({corrupt} corrupt/skipped).")
    print(f"Gameplay frames: {kept}  ({pct:.0f}%)")
    if args.copy:
        print(f"Copied to {dst}")
    else:
        print("(dry run - pass --copy to actually copy them)")


if __name__ == "__main__":
    main()
