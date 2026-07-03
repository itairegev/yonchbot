"""The bot's connection to the phone.

A "Device" is anything the bot can take a screenshot of and tap on.
We have two kinds:

  * AdbDevice    - a REAL Android phone or emulator, connected with a USB
                   cable (or a running emulator). Uses the `adb` tool.
  * ReplayDevice - a PRETEND phone that shows recorded screenshots.
                   Great for testing the bot without the game.

Why do we do this? Because if the bot's brain doesn't care whether the
phone is real or pretend, we can test the brain anywhere, anytime.
Programmers call this an "interface". You can call it a costume:
both devices wear the same costume, so the brain can't tell them apart.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import cv2
import numpy as np


class DeviceError(Exception):
    """Something went wrong talking to the phone."""


def list_devices(adb_path: str = "adb") -> list[str]:
    """Return the serials of every connected, ready device.

    Handy when both a real phone and an emulator are plugged in and the
    bot needs to know there's a choice to make.
    """
    try:
        out = subprocess.run([adb_path, "devices"], capture_output=True,
                             timeout=15).stdout.decode(errors="replace")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    serials = []
    for line in out.splitlines()[1:]:          # skip the "List of devices" header
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":   # ready (not "offline"/"unauthorized")
            serials.append(parts[0])
    return serials


class AdbDevice:
    """A real Android phone or emulator, controlled through `adb`.

    adb ("Android Debug Bridge") is a little program that lets a computer
    talk to an Android device: take screenshots, tap the screen, and more.
    """

    def __init__(self, serial: str | None = None, adb_path: str = "adb"):
        self.adb_path = adb_path
        self.serial = serial  # which device, if several are plugged in

    def _adb(self, *args: str) -> bytes:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
        except FileNotFoundError:
            raise DeviceError(
                "I can't find the `adb` program! Install it with:\n"
                "    brew install android-platform-tools"
            )
        except subprocess.TimeoutExpired:
            raise DeviceError("The phone took too long to answer. Check the cable!")
        if result.returncode != 0:
            raise DeviceError(
                f"adb said no: {result.stderr.decode(errors='replace').strip()}\n"
                "Is the phone connected? Try running: adb devices"
            )
        return result.stdout

    def screenshot(self) -> np.ndarray:
        """Take a picture of the phone screen. Returns it as a color image."""
        png_bytes = self._adb("exec-out", "screencap", "-p")
        image = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise DeviceError("The screenshot came back broken. Try again!")
        return image

    def tap(self, x: int, y: int) -> None:
        """Touch the screen at position (x, y), like a quick finger poke."""
        self._adb("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        """Drag a finger from (x1, y1) to (x2, y2), taking `ms` milliseconds."""
        self._adb(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms)),
        )

    def wait(self, seconds: float) -> None:
        """Do nothing for a while. Even robots need patience."""
        time.sleep(seconds)


class ReplayDevice:
    """A pretend phone for testing.

    Give it a list of screenshot files (or images), and every time the bot
    asks for a screenshot it shows the next one. Every tap and swipe is
    written down in `self.actions` so tests can check what the bot did.
    """

    def __init__(self, frames: list):
        if not frames:
            raise DeviceError("ReplayDevice needs at least one frame!")
        self._frames = frames
        self._index = 0
        self.actions: list[tuple] = []

    def screenshot(self) -> np.ndarray:
        frame = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        if isinstance(frame, (str, Path)):
            image = cv2.imread(str(frame), cv2.IMREAD_COLOR)
            if image is None:
                raise DeviceError(f"Couldn't read the frame file: {frame}")
            return image
        return frame

    def tap(self, x: int, y: int) -> None:
        self.actions.append(("tap", int(x), int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        self.actions.append(("swipe", int(x1), int(y1), int(x2), int(y2), int(ms)))

    def wait(self, seconds: float) -> None:
        # Pretend phones don't need real waiting - tests should be fast!
        self.actions.append(("wait", seconds))
