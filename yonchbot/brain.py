"""The bot's brain: look, think, act, repeat.

This is a "state machine" - a fancy name for a simple idea:
figure out which situation (state) you're in, then do the one
right thing for that situation.

  See the lobby?        -> press PLAY
  See a match?          -> play! (walk + attack)
  See the end screen?   -> press EXIT, write the game in the diary
  See the rewards?      -> tap to continue
  See something weird?  -> stay calm, save a photo of it, try a safe tap

The whole bot is this loop. Everything else is helpers.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2

from . import play
from .progress import Diary
from .screens import Screen, ScreenDetector


class Brain:
    def __init__(self, device, detector: ScreenDetector, diary: Diary,
                 config: dict, say=print):
        self.device = device
        self.detector = detector
        self.diary = diary
        self.config = config
        self.say = say  # how the bot talks to us (print, or quiet in tests)

        # memories about the current game
        self.steps_played = 0
        self.screens_seen = 0
        self.confused_count = 0  # how many UNKNOWNs in a row

    def run(self, max_games: int = 1) -> int:
        """The main loop. Returns how many games were finished."""
        games_done = 0
        give_up_after = self.config["safety"]["give_up_after_unknowns"]

        while games_done < max_games:
            screenshot = self.device.screenshot()
            screen = self.detector.which_screen(screenshot)
            self.screens_seen += 1

            if screen != Screen.UNKNOWN:
                self.confused_count = 0

            if screen == Screen.LOBBY:
                self._press_play(screenshot)
            elif screen == Screen.IN_MATCH:
                self._play_one_step()
            elif screen == Screen.MATCH_END:
                self._finish_match(screenshot)
                games_done += 1
            elif screen == Screen.REWARDS:
                self._collect_rewards()
            else:
                self._handle_confusion(screenshot)
                if self.confused_count >= give_up_after:
                    self.say("🛑 I'm too confused. Stopping so we can look together.")
                    break

            self.device.wait(self.config["timing"]["seconds_between_looks"])

        return games_done

    # ---- one small method per situation, so each is easy to read ----

    def _press_play(self, screenshot) -> None:
        match = self.detector.find_landmark(screenshot, Screen.LOBBY)
        if match:
            self.say(f"🎮 Lobby! Pressing PLAY ({match.confidence:.0%} sure).")
            self.device.tap(*match.center)

    def _play_one_step(self) -> None:
        if self.steps_played == 0:
            self.say("⚔️  Match started! Time to play.")
        play.play_step(self.device, self.config, self.steps_played)
        self.steps_played += 1

    def _finish_match(self, screenshot) -> None:
        self.say(f"🏁 Match over after {self.steps_played} steps. Writing it in the diary.")
        self.diary.log_game(
            screens_seen=self.screens_seen,
            steps_played=self.steps_played,
            finished=True,
        )
        match = self.detector.find_landmark(screenshot, Screen.MATCH_END)
        if match:
            self.device.tap(*match.center)
        self.steps_played = 0
        self.screens_seen = 0

    def _collect_rewards(self) -> None:
        self.say("🎁 Rewards! Tapping to continue.")
        self.device.tap(*self.config["safety"]["safe_tap_spot"])

    def _handle_confusion(self, screenshot) -> None:
        self.confused_count += 1
        self.say(f"🤔 I don't recognize this screen ({self.confused_count} in a row).")
        stuck_dir = Path(self.config["safety"]["stuck_screenshots_dir"])
        stuck_dir.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("stuck_%Y%m%d_%H%M%S") + f"_{self.confused_count}.png"
        cv2.imwrite(str(stuck_dir / name), screenshot)
        # A tap in a safe spot dismisses most popups without buying anything.
        self.device.tap(*self.config["safety"]["safe_tap_spot"])
