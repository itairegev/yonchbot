"""Tests for the learning pilot (the Karpathy method, phone-sized)."""

import numpy as np

from yonchbot import rl
from tests.conftest import make_screen


def test_features_are_ten_honest_numbers(config):
    x = rl.features_from(make_screen(None), config, carrying=False)
    assert x.shape == (rl.N_FEATURES,)
    assert x[0] == 1.0                    # the "gut feeling" bias is always on


def test_the_net_learns_which_action_pays():
    """A one-armed-bandit drill: only action 3 is ever rewarded.
    After a few hundred games, the net should strongly prefer it."""
    policy = rl.TinyPolicy(seed=3)
    rng = np.random.default_rng(3)
    x = np.zeros(rl.N_FEATURES); x[0] = 1.0
    before = policy.action_odds(x)[0][3]
    for _ in range(400):
        action = policy.act(x, rng)
        policy.finish_episode(1.0 if action == 3 else -1.0, lr=0.05)
    after = policy.action_odds(x)[0][3]
    assert after > before and after > 0.5     # it FOUND the paying lever

def test_saved_brain_wakes_up_identical(tmp_path):
    policy = rl.TinyPolicy(seed=5)
    policy.episodes = 42
    policy.save(tmp_path / "policy.npz")
    twin = rl.TinyPolicy.load(tmp_path / "policy.npz")
    assert twin.episodes == 42
    assert np.allclose(policy.W1, twin.W1) and np.allclose(policy.W2, twin.W2)
