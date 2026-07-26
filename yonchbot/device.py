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
        self._walking = None  # a joystick swipe still running (wait=False)

    def _cmd(self, *args: str) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    def _adb(self, *args: str) -> bytes:
        cmd = self._cmd(*args)
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
        """Take a picture of the phone screen. Returns it as a color image.

        Speed trick: we ask for RAW pixels instead of a PNG file. Making
        a PNG forces the phone to squeeze the picture (slow!); raw pixels
        are 3x the bytes but arrive much faster over the cable. We keep
        the old PNG way as a backup for phones that speak differently.
        """
        raw = self._adb("exec-out", "screencap")
        image = self._decode_raw(raw)
        if image is None:  # this phone doesn't do raw - the slow, sure way
            png_bytes = self._adb("exec-out", "screencap", "-p")
            image = cv2.imdecode(np.frombuffer(png_bytes, np.uint8),
                                 cv2.IMREAD_COLOR)
        if image is None:
            raise DeviceError("The screenshot came back broken. Try again!")
        return image

    @staticmethod
    def _decode_raw(raw: bytes) -> np.ndarray | None:
        """Unpack a raw screenshot: a tiny header, then RGBA pixels."""
        if len(raw) < 16:
            return None
        width, height, pixel_format = np.frombuffer(raw[:12], "<u4")
        if pixel_format != 1:  # 1 = RGBA, the only dialect we speak
            return None
        for header_size in (12, 16):  # newer Androids add a 4-byte extra
            if len(raw) == header_size + width * height * 4:
                rgba = np.frombuffer(raw, np.uint8, count=width * height * 4,
                                     offset=header_size)
                rgba = rgba.reshape(int(height), int(width), 4)
                return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        return None

    def _lift_walking_finger(self) -> None:
        """If a background walk-swipe is still going, wait for it to end.

        Two fingers drawn by `input swipe` fight over the same touch
        stream - so before ANY new tap or swipe, the walking finger
        must lift. (Screenshots don't touch the screen: no waiting.)
        """
        if self._walking is not None:
            try:
                self._walking.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._walking.kill()
            self._walking = None

    def tap(self, x: int, y: int) -> None:
        """Touch the screen at position (x, y), like a quick finger poke."""
        self._lift_walking_finger()
        self._adb("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300,
              wait: bool = True) -> None:
        """Drag a finger from (x1, y1) to (x2, y2), taking `ms` milliseconds.

        wait=False starts the drag and returns IMMEDIATELY - the bot can
        take its next screenshot and think while the finger is still
        dragging. That's how the brawler keeps walking while we decide
        what to do next, instead of standing around like a statue.
        """
        self._lift_walking_finger()
        args = ("shell", "input", "swipe",
                str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)),
                str(int(ms)))
        if wait:
            self._adb(*args)
        else:
            self._walking = subprocess.Popen(
                self._cmd(*args),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300,
              wait: bool = True) -> None:
        self.actions.append(("swipe", int(x1), int(y1), int(x2), int(y2), int(ms)))

    def wait(self, seconds: float) -> None:
        # Pretend phones don't need real waiting - tests should be fast!
        self.actions.append(("wait", seconds))
