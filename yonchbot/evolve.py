"""The bot's science lab - where it improves ITSELF.

No AI, no magic: this is the same method scientists (and gamers!) use:

  1. Take the CHAMPION settings (the best strategy we know so far).
  2. Make a CHALLENGER: copy the champion, change exactly ONE thing.
  3. Let each play the same number of games. Count the wins.
  4. Whoever wins more becomes (or stays) the champion.
  5. Go to step 2. Forever. The bot gets better while you sleep.

Changing only ONE thing at a time is the golden rule of experiments -
change two and you can't tell which one mattered. (Session 7 rule!)

Every experiment is written to data/evolution.csv, so you can chart
the bot's strategy getting better over time - science with receipts.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime
from pathlib import Path

# The knobs the bot is allowed to experiment with, and the values it
# may try. Small menus on purpose: fewer choices = faster learning.
GENES: dict[str, list] = {
    "kick_range": [140, 220, 320],     # kick early, or dribble in close?
    "shoot_range": [0.30, 0.45, 0.60], # picky sniper, or spray-happy?
    "step_hold_ms": [220, 300, 420],   # twitchy little steps, or strides?
}


def mutate(champion: dict, rng: random.Random) -> dict:
    """Copy the champion, then change exactly ONE gene to a NEW value."""
    challenger = dict(champion)
    gene = rng.choice(sorted(GENES))
    options = [v for v in GENES[gene] if v != champion[gene]]
    challenger[gene] = rng.choice(options)
    return challenger


def pick_winner(champion: dict, champ_wins: int,
                challenger: dict, chall_wins: int) -> dict:
    """More wins takes the crown. Ties go to the champion - a challenger
    must PROVE it's better, not just equal."""
    return challenger if chall_wins > champ_wins else champion


class Evolution:
    """Runs champion-vs-challenger experiments and keeps the log."""

    def __init__(self, log_path: str | Path, rng: random.Random | None = None):
        self.log_path = Path(log_path)
        self.rng = rng or random.Random()

    def _log(self, round_no: int, role: str, settings: dict, wins: int,
             games: int, crowned: bool) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.log_path.exists()
        with open(self.log_path, "a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["when", "round", "role", *sorted(GENES),
                                 "wins", "games", "champion_after"])
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"), round_no, role,
                *[settings[g] for g in sorted(GENES)], wins, games,
                "yes" if crowned else "no",
            ])

    def run(self, champion: dict, rounds: int, games_per_side: int,
            play_games, say=print) -> dict:
        """The experiment loop. `play_games(settings, n)` must play n games
        with those settings and return how many were WON."""
        for round_no in range(1, rounds + 1):
            challenger = mutate(champion, self.rng)
            changed = [g for g in GENES if champion[g] != challenger[g]][0]
            say(f"🧪 Round {round_no}: challenger changes {changed}: "
                f"{champion[changed]} -> {challenger[changed]}")

            champ_wins = play_games(champion, games_per_side)
            say(f"   champion won {champ_wins}/{games_per_side}")
            chall_wins = play_games(challenger, games_per_side)
            say(f"   challenger won {chall_wins}/{games_per_side}")

            winner = pick_winner(champion, champ_wins, challenger, chall_wins)
            self._log(round_no, "champion", champion, champ_wins,
                      games_per_side, winner is champion)
            self._log(round_no, "challenger", challenger, chall_wins,
                      games_per_side, winner is challenger)
            if winner is challenger:
                say(f"👑 New champion! {changed} is now {challenger[changed]}")
            else:
                say("👑 Champion defends the crown.")
            champion = winner
        return champion
