"""Tests for the bot's science lab."""

import random

from yonchbot.evolve import GENES, Evolution, mutate, pick_winner


def test_mutation_changes_exactly_one_gene():
    rng = random.Random(7)
    champion = {g: GENES[g][0] for g in GENES}
    for _ in range(20):
        challenger = mutate(champion, rng)
        changed = [g for g in GENES if champion[g] != challenger[g]]
        assert len(changed) == 1                      # one change at a time!
        assert challenger[changed[0]] in GENES[changed[0]]


def test_better_challenger_takes_the_crown():
    a, b = {"kick_range": 220}, {"kick_range": 140}
    assert pick_winner(a, 1, b, 3) is b


def test_ties_go_to_the_champion():
    a, b = {"kick_range": 220}, {"kick_range": 140}
    assert pick_winner(a, 2, b, 2) is a


def test_evolution_runs_experiments_and_keeps_the_log(tmp_path):
    rng = random.Random(1)
    lab = Evolution(tmp_path / "evolution.csv", rng=rng)
    champion = {g: GENES[g][0] for g in GENES}

    # a pretend arena: settings with a bigger kick_range win more games
    def fake_play(settings, n):
        return 3 if settings["kick_range"] > 140 else 1

    final = lab.run(champion, rounds=6, games_per_side=3,
                    play_games=fake_play, say=lambda *a: None)

    assert final["kick_range"] > 140          # the lab FOUND the better gene
    lines = (tmp_path / "evolution.csv").read_text().strip().splitlines()
    assert len(lines) == 1 + 6 * 2            # header + 2 rows per round
