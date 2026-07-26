"""Tests for the learning pilot (the Karpathy method, phone-sized)."""

import numpy as np

from yonchbot import play, rl
from tests.conftest import make_screen


def test_features_are_twelve_honest_numbers(config):
    config["match"]["football"] = True
    ctx = play.see(make_screen(None), config, step=5)
    x = rl.features_from_ctx(ctx, config, step=5)
    assert x.shape == (rl.N_FEATURES,)
    assert x[0] == 1.0                    # the "gut feeling" bias is always on
    assert 0.0 <= x[-1] <= 1.0            # the match clock stays a fraction


def test_the_net_learns_which_action_pays():
    """A one-armed-bandit drill: only action 3 is ever rewarded.
    After a few hundred games, the net should strongly prefer it."""
    policy = rl.TinyPolicy(seed=3)
    rng = np.random.default_rng(3)
    x = np.zeros(rl.N_FEATURES); x[0] = 1.0
    before = policy.action_odds(x)[0][3]
    for _ in range(400):
        action = policy.act(x, rng)
        policy.finish_episode([1.0 if action == 3 else -1.0], lr=0.05)
    after = policy.action_odds(x)[0][3]
    assert after > before and after > 0.5     # it FOUND the paying lever


def test_saved_brain_wakes_up_identical(tmp_path):
    policy = rl.TinyPolicy(seed=5)
    policy.episodes = 42
    policy.save(tmp_path / "policy.npz")
    twin = rl.TinyPolicy.load(tmp_path / "policy.npz")
    assert twin.episodes == 42
    assert np.allclose(policy.W1, twin.W1) and np.allclose(policy.W2, twin.W2)


def test_studying_copies_the_rulebook():
    """Behavior cloning: given a diary where the choice clearly depends
    on what was seen, the net should learn to copy it almost perfectly."""
    rng = np.random.default_rng(7)
    demos = []
    for _ in range(300):
        x = np.zeros(rl.N_FEATURES)
        x[0] = 1.0
        x[1] = float(rng.integers(0, 2))      # "ball visible?"
        demos.append((x, 0 if x[1] > 0 else 2))  # see ball -> chase; else fight
    policy = rl.TinyPolicy(seed=1)
    accuracy = policy.study(demos, passes=15)
    assert accuracy > 0.9


def test_pilot_hands_out_goal_rewards(config):
    """Score goes 0-0 -> 1-0: +goal reward. Then 1-0 -> 1-1: -goal."""
    config["rl"] = {"macro_beats": 3, "reward_goal": 2.0}
    pilot = rl.Pilot(rl.TinyPolicy(seed=2), config, say=lambda *a: None)
    ctx = {"ball": None, "us": (320, 180), "width": 640, "height": 360,
           "carrying": False, "enemies": [], "focus": None, "screenshot": None}

    pilot.prev_scores = (0, 0)
    assert pilot._grade(ctx, (1, 0)) >= 2.0        # we scored!
    assert pilot._grade(ctx, (1, 1)) <= -2.0       # they answered.


def test_pilot_pays_for_landed_punches(config):
    """The coach's grading: a punch WE landed is worth a full point -
    it's the one stat on screen that is entirely our own doing."""
    config["rl"] = {"macro_beats": 3, "reward_hit": 1.0}
    pilot = rl.Pilot(rl.TinyPolicy(seed=2), config, say=lambda *a: None)
    ctx = {"ball": None, "us": (320, 180), "width": 640, "height": 360,
           "carrying": False, "enemies": [(400, 150)], "focus": (400, 150),
           "screenshot": None, "hit_confirmed": True}

    assert pilot._grade(ctx, None) >= 1.0


def test_win_bonus_is_off_by_default(config):
    """Wins are a team grade - the coach zeroed the win bonus. The
    rewards handed to the learner must arrive WITHOUT a victory bump."""
    config["rl"] = {"macro_beats": 3}

    class SpyPolicy(rl.TinyPolicy):
        def finish_episode(self, rewards, **kwargs):
            self.seen = list(rewards)

    policy = SpyPolicy(seed=2)
    pilot = rl.Pilot(policy, config, say=lambda *a: None)
    pilot.rewards = [0.5]
    pilot.finish(won=True)
    assert policy.seen == [0.5]   # no +10 slipped in with the whistle


def test_pilot_homework_points_are_capped(config):
    """Shaped rewards must never outweigh a goal: capped at ±3/game."""
    config["rl"] = {"macro_beats": 3}
    pilot = rl.Pilot(rl.TinyPolicy(seed=2), config, say=lambda *a: None)
    ctx = {"ball": None, "us": (320, 180), "width": 640, "height": 360,
           "carrying": True, "enemies": [], "focus": None, "screenshot": None}
    total = 0.0
    for _ in range(300):   # 300 possession bonuses would be 90 points...
        pilot.prev_carrying = False   # pretend we JUST got the ball each time
        total += pilot._grade(ctx, None)
    assert total <= 3.0    # ...but the cap holds the line


def test_rule_bot_writes_its_diary(config, tmp_path):
    """During rule play, every beat becomes one (saw, chose) diary line."""
    demos_path = tmp_path / "demos.jsonl"
    config["match"]["football"] = True
    config["rl"] = {"demos_path": str(demos_path), "log_demos": True}
    from yonchbot.device import ReplayDevice
    device = ReplayDevice([make_screen(None)])

    play.play_step(device, config, step=1, screenshot=make_screen(None))

    demos = rl.load_demos(demos_path)
    assert len(demos) == 1
    x, action = demos[0]
    assert x.shape == (rl.N_FEATURES,)
    assert 0 <= action < rl.N_ACTIONS
