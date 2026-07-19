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

from . import play, vision
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

        # In football mode, keep a picture of the "BRAWL BALL" banner so
        # we can check we're queuing for the RIGHT game before pressing PLAY -
        # and one of the Brawl Ball CARD, to find it in the mode browser
        # (the cards move around as new events unlock, so we look, not guess).
        self._football_banner = None
        self._football_card = None
        self._victory = None
        if config["match"].get("football"):
            for name, attr in [("football_banner.png", "_football_banner"),
                               ("football_card.png", "_football_card"),
                               ("victory.png", "_victory")]:
                path = detector.templates_dir / name
                if path.exists():
                    setattr(self, attr, vision.load_template(path))

        # The optional LEARNING pilot (see rl.py - the Karpathy method).
        # When config match.pilot == "rl", a tiny neural net flies the
        # brawler and learns from every win and loss. No rules, no help.
        self.policy = None
        if config["match"].get("pilot") == "rl":
            import numpy as np
            from . import rl
            self._policy_path = Path(config["match"].get(
                "policy_path", "data/rl/policy.npz"))
            self.policy = rl.TinyPolicy.load(self._policy_path) \
                if self._policy_path.exists() else rl.TinyPolicy()
            self._rl_rng = np.random.default_rng()
            say(f"🧠 RL pilot aboard - {self.policy.episodes} games of experience.")

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
                self._play_one_step(screenshot)
            elif screen == Screen.SPECTATE:
                self._leave_spectate(screenshot)
            elif screen == Screen.MATCH_END:
                if self.steps_played > 0:
                    self._finish_match(screenshot)
                    games_done += 1
                else:
                    # An end screen we did NOT play for = leftovers from
                    # before we started. Clear it, but it's not our game.
                    self.say("🧹 Old end screen - clearing it, doesn't count.")
                    match = self.detector.find_landmark(screenshot, Screen.MATCH_END)
                    if match:
                        self.device.tap(*match.center)
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
        # Football-only rule: if the lobby banner is NOT showing Brawl Ball,
        # something switched the mode - switch it back before playing.
        if self._football_banner is not None and \
                vision.find(screenshot, self._football_banner, 0.8) is None:
            # Never loop forever: if switching keeps failing, football may
            # simply not be on today's menu - stop and ask the humans.
            self._mode_switch_fails = getattr(self, "_mode_switch_fails", 0) + 1
            if self._mode_switch_fails > 5:
                self.say("⚽ I can't find football in today's events. "
                         "Stopping so a human can pick a mode.")
                self.confused_count = self.config["safety"]["give_up_after_unknowns"]
                return
            self.say("⚽ Wrong game mode! Switching back to football.")
            self.device.tap(*self.config["match"]["event_banner_spot"])
            self.device.wait(3)
            # Now the mode browser is open - FIND the Brawl Ball card and
            # tap it (cards move as events unlock, so eyes beat guesses).
            browser = self.device.screenshot()
            card = None
            if self._football_card is not None:
                card = vision.find(browser, self._football_card, 0.8)
            if card:
                self.device.tap(*card.center)
            else:  # can't see the card - use the remembered spot and hope
                self.device.tap(*self.config["match"]["football_card_spot"])
            self.device.wait(2)
            return

        self._mode_switch_fails = 0   # banner is right - all forgiven
        match = self.detector.find_landmark(screenshot, Screen.LOBBY)
        if match:
            self.say(f"🎮 Lobby! Pressing PLAY ({match.confidence:.0%} sure).")
            self.device.tap(*match.center)

    def _play_one_step(self, screenshot) -> None:
        if self.steps_played == 0:
            self.say("⚔️  Match started! Time to play.")
        if self.policy is not None:
            from . import rl
            x = rl.features_from(screenshot, self.config, carrying=False)
            action = self.policy.act(x, self._rl_rng)
            rl.do_action(self.device, self.config, action, screenshot)
            self.steps_played += 1
            return
        # The screenshot rides along so play.py can hunt for red health bars.
        play.play_step(self.device, self.config, self.steps_played,
                       screenshot=screenshot)
        self.steps_played += 1

    def _finish_match(self, screenshot) -> None:
        # Did we WIN? The end screen says so - and the diary keeps score,
        # because "are we getting better?" deserves a real answer.
        notes = ""
        if self._victory is not None:
            # The VICTORY banner slides in with an animation - our first
            # glimpse of this screen is often too early. Wait a beat and
            # take a fresh, settled look before judging the game.
            self.device.wait(1.5)
            settled = self.device.screenshot()
            won = vision.find(settled, self._victory, 0.65) is not None
            notes = "WIN ⚽" if won else "loss"
            self.say(f"🏁 Match over ({notes}) after {self.steps_played} steps.")
        else:
            self.say(f"🏁 Match over after {self.steps_played} steps. Writing it in the diary.")
        self.diary.log_game(
            screens_seen=self.screens_seen,
            steps_played=self.steps_played,
            finished=True,
            notes=notes,
        )
        if self.policy is not None and notes:
            # The Karpathy moment: one number teaches the whole game.
            self.policy.finish_episode(1.0 if "WIN" in notes else -1.0)
            self.policy.episodes += 1
            self.policy.save(self._policy_path)
            self.say(f"🧠 Learned from game #{self.policy.episodes}.")
        match = self.detector.find_landmark(screenshot, Screen.MATCH_END)
        if match:
            self.device.tap(*match.center)
        self.steps_played = 0
        self.screens_seen = 0

    def _leave_spectate(self, screenshot) -> None:
        """We died and the game wants us to watch. No thanks - Exit."""
        self.say("👻 We're out - leaving spectator mode.")
        match = self.detector.find_landmark(screenshot, Screen.SPECTATE)
        if match:
            self.device.tap(*match.center)

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
        # Every 3rd confused look we instead try a place a known button
        # hides: the spectate Exit (gas clouds sometimes cover it), then
        # the home button (in case we wandered into some menu).
        safety = self.config["safety"]
        if self.confused_count % 3 == 1 and "spectate_exit_spot" in safety:
            self.device.tap(*safety["spectate_exit_spot"])
        elif self.confused_count % 3 == 0 and "home_button" in safety:
            self.device.tap(*safety["home_button"])
        else:
            self.device.tap(*safety["safe_tap_spot"])
