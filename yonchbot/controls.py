"""The bot's hands.

Brawl Stars is controlled with two thumbs:
  * LEFT thumb  = the movement joystick (drag it in a direction to walk)
  * RIGHT thumb = the attack button (tap it to auto-aim and shoot)

We copy that with taps and swipes. A "joystick push" is just a swipe that
starts where the joystick lives and ends a little bit away, in the
direction we want to walk.

Directions are angles in degrees, like a compass drawn on the screen:
      90 = up
       0 = right      180 = left
     270 = down
"""

from __future__ import annotations

import math


def tap(device, x: int, y: int) -> None:
    """Poke the screen at (x, y)."""
    device.tap(x, y)


def joystick_push(device, anchor: tuple[int, int], angle_degrees: float,
                  distance: int = 150, hold_ms: int = 900) -> None:
    """Push the movement joystick in a direction.

    anchor        = where the joystick sits on screen (from config.yaml)
    angle_degrees = which way to walk (see the compass above)
    distance      = how far to push (further = walk at full speed)
    hold_ms       = how long to hold the push (longer = walk longer)
    """
    ax, ay = anchor
    # Trigonometry! cos gives the left-right part of the direction,
    # sin gives the up-down part. Screens count y DOWNWARD, so we subtract.
    radians = math.radians(angle_degrees)
    # round() and not int(): cos(270°) comes out as -0.0000000000000002,
    # and int() would chop 99.999... down to 99. Computers, eh?
    end_x = round(ax + distance * math.cos(radians))
    end_y = round(ay - distance * math.sin(radians))
    device.swipe(ax, ay, end_x, end_y, ms=hold_ms)


def attack(device, button: tuple[int, int]) -> None:
    """Tap the attack button. Brawl Stars auto-aims at the closest enemy."""
    device.tap(*button)


def aim_and_shoot(device, button: tuple[int, int], angle_degrees: float,
                  distance: int = 280, hold_ms: int = 350) -> None:
    """Drag the attack button in a direction and let go = an AIMED shot.

    A tap (see `attack`) lets the game pick a target. But if you DRAG
    the attack button, YOU choose the direction - and the shot fires the
    moment you let go. Same trigonometry as walking, different thumb.
    """
    bx, by = button
    radians = math.radians(angle_degrees)
    end_x = round(bx + distance * math.cos(radians))
    end_y = round(by - distance * math.sin(radians))  # y counts downward!
    device.swipe(bx, by, end_x, end_y, ms=hold_ms)


def fire_super(device, super_button: tuple[int, int], angle_degrees: float,
               distance: int = 280, hold_ms: int = 350) -> None:
    """Unleash the SUPER in a chosen direction.

    Works exactly like an aimed shot, but dragged from the super button
    (the skull). Only makes sense when the button is glowing - check
    with vision.super_is_ready first!
    """
    aim_and_shoot(device, super_button, angle_degrees, distance, hold_ms)
