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
        self._football_card2 = None
        self._victory = None
        if config["match"].get("football"):
            # (two card pictures: the events page shows Brawl Ball as a
            # TALL card some days and a WIDE card on others - same game,
            # different outfit. We know both faces.)
            for name, attr in [("football_banner.png", "_football_banner"),
                               ("football_card.png", "_football_card"),
                               ("football_card2.png", "_football_card2"),
                               ("victory.png", "_victory")]:
                path = detector.templates_dir / name
                if path.exists():
                    setattr(self, attr, vision.load_template(path))

        # The score reader: two little digit pictures (0 and 1) and the
        # boxes where each team's score lives. Brawl Ball ends at 2, and
        # the victory banner covers that - so 0/1 is all we need to read.
        self._digits = {}
        for digit in (0, 1):
            path = detector.templates_dir / f"score_{digit}.png"
            if path.exists():
                self._digits[digit] = vision.load_template(path)

        # The optional LEARNING pilot (see rl.py - the Karpathy method,
        # upgraded): when config match.pilot == "rl", a tiny neural net
        # picks among the five play.py tactics and learns from shaped
        # rewards - goals, possession, progress - not just win/loss.
        self.pilot = None
        if config["match"].get("pilot") == "rl":
            from . import rl
            policy_path = Path(config.get("rl", {}).get(
                "policy_path", "data/rl/policy.npz"))
            policy = rl.TinyPolicy.load(policy_path) \
                if policy_path.exists() else rl.TinyPolicy()
            self.pilot = rl.Pilot(policy, config, say=say)
            say(f"🧠 RL pilot aboard - {policy.episodes} games of experience.")

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

            # The give-up check lives OUTSIDE the branches: any situation
            # may raise the confusion count (even the lobby, when the game
            # mode can't be fixed) - and "I give up" must actually stop us.
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
            card = self._find_football_card()
            if card is None and "trophies_tab_spot" in self.config["match"]:
                # New seasons open the browser on their own special page -
                # the normal events hide under the TROPHIES tab. Go there.
                self.device.tap(*self.config["match"]["trophies_tab_spot"])
                self.device.wait(2)
                card = self._find_football_card()
            if card:
                self.device.tap(*card.center)
            else:
                # Still nothing? A fresh season covers every event with a
                # "NEW!" card. Tap the remembered spot TWICE: the first
                # tap peels the cover, the second picks the event.
                self.device.tap(*self.config["match"]["football_card_spot"])
                self.device.wait(2)
                self.device.tap(*self.config["match"]["football_card_spot"])
            self.device.wait(2)
            return

        self._mode_switch_fails = 0   # banner is right - all forgiven
        match = self.detector.find_landmark(screenshot, Screen.LOBBY)
        if match:
            self.say(f"🎮 Lobby! Pressing PLAY ({match.confidence:.0%} sure).")
            self.device.tap(*match.center)

    def _find_football_card(self):
        """Take a fresh look at the mode browser - is Brawl Ball visible?
        Checks both of the card's outfits (tall and wide)."""
        browser = self.device.screenshot()
        for card in (self._football_card, self._football_card2):
            if card is None:
                continue
            match = vision.find(browser, card, 0.8)
            if match is not None:
                return match
        return None

    def _read_scores(self, screenshot):
        """Read the match score off the top bars: (ours, theirs) or None."""
        if not self._digits or "score_left_box" not in self.config["match"]:
            return None
        ours = vision.read_score(screenshot,
                                 self.config["match"]["score_left_box"],
                                 self._digits)
        theirs = vision.read_score(screenshot,
                                   self.config["match"]["score_right_box"],
                                   self._digits)
        if ours is None or theirs is None:
            return None
        return (ours, theirs)

    def _play_one_step(self, screenshot) -> None:
        if self.steps_played == 0:
            self.say("⚔️  Match started! Time to play.")
        scores = self._read_scores(screenshot)
        if scores is not None:
            self._last_scores = scores   # remembered for the diary
        if self.pilot is not None:
            ctx = play.see(screenshot, self.config, self.steps_played)
            ctx["scores"], ctx["step"] = scores, self.steps_played
            self.pilot.step(self.device, ctx, self.steps_played, scores)
            self.steps_played += 1
            return
        # The screenshot rides along so play.py can hunt for red health
        # bars - and the score rides along so it knows when to stall.
        play.play_step(self.device, self.config, self.steps_played,
                       screenshot=screenshot, scores=scores)
        self.steps_played += 1

    def _finish_match(self, screenshot) -> None:
        # Did we WIN? Two witnesses get asked, in order of reliability:
        #   1. The SCOREBOARD we read all game (whoever led, won) -
        #      but a tie at our last look means we missed the decider.
        #   2. The VICTORY banner. Careful: the first end screen is a
        #      "GAME HIGHLIGHT" replay - the banner only appears AFTER
        #      we tap onward. (We logged wins as losses for half a day
        #      before catching that. Screenshots don't lie; assumptions do.)
        won = None
        scores = getattr(self, "_last_scores", None)
        if scores is not None and scores[0] != scores[1]:
            won = scores[0] > scores[1]

        match = self.detector.find_landmark(screenshot, Screen.MATCH_END)
        if match:
            self.device.tap(*match.center)   # onward, past the highlight
        if won is None and self._victory is not None:
            self.device.wait(2.0)            # let the banner slide in
            settled = self.device.screenshot()
            won = vision.find(settled, self._victory, 0.65) is not None

        notes = ""
        if won is not None or self._victory is not None:
            notes = "WIN ⚽" if won else "loss"
            if scores is not None:
                # the diary keeps the score - the evolution lab judges
                # champions by goals, not by coin-flip wins
                notes += " {}-{}".format(*scores)
            # ...and the punch count: hits WE landed are the one stat
            # that grades OUR play alone, whatever the teammates did
            notes += f" hits:{play.MEMORY['hits']}"
            self.say(f"🏁 Match over ({notes}) after {self.steps_played} steps.")
        else:
            self.say(f"🏁 Match over after {self.steps_played} steps. Writing it in the diary.")
        self.diary.log_game(
            screens_seen=self.screens_seen,
            steps_played=self.steps_played,
            finished=True,
            notes=notes,
        )
        if self.pilot is not None:
            # The learning moment: grade the whole game and update the net.
            self.pilot.finish(won)
        self._last_scores = None
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
