"""The bot's diary.

Every game the bot plays gets one line in data/games.csv.
This is how we SEE progress: numbers going up, day after day.

A CSV file is just a table saved as text - you can open it in
Excel/Numbers/Google Sheets too!
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

COLUMNS = ["when", "screens_seen", "steps_played", "finished", "notes"]


@dataclass
class Totals:
    games: int
    finished: int
    total_steps: int

    @property
    def bot_level(self) -> int:
        """The bot levels up every 5 finished games. Everyone loves levels."""
        return 1 + self.finished // 5

    @property
    def next_level_in(self) -> int:
        """How many more finished games until the next level?"""
        return 5 - (self.finished % 5)


class Diary:
    def __init__(self, csv_path: str | Path):
        self.path = Path(csv_path)

    def log_game(self, screens_seen: int, steps_played: int,
                 finished: bool, notes: str = "") -> None:
        """Write one game into the diary."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        with open(self.path, "a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(COLUMNS)
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                screens_seen,
                steps_played,
                "yes" if finished else "no",
                notes,
            ])

    def read_games(self) -> list[dict]:
        """Read every game back out of the diary."""
        if not self.path.exists():
            return []
        with open(self.path, newline="") as f:
            return list(csv.DictReader(f))

    def totals(self) -> Totals:
        games = self.read_games()
        return Totals(
            games=len(games),
            finished=sum(1 for g in games if g["finished"] == "yes"),
            total_steps=sum(int(g["steps_played"] or 0) for g in games),
        )
