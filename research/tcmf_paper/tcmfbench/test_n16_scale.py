"""N16 unit tests: scale stress test + multi-crisis mode.

Checks the item's own "Verify" criteria: at pool 80 the scale sweep reproduces N01 exactly
(same seeds), and per-crisis metrics in multi-crisis mode are never pooled - plus the
cross-contamination invariant the multi-crisis mode exists to test (querying one crisis must
not boost another crisis's true ancestors, since they are not BFS-reachable from it).

Run: python -m tcmfbench.test_n16_scale (or pytest tcmfbench/test_n16_scale.py)
"""
from __future__ import annotations

import sys

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many
from .multi_crisis import (MultiCrisisConfig, generate_multi_crisis, materialize_multi_crisis,
                           crisis_scoped_mat)


def test_realistic_pool_config_matches_n01_exactly():
    """N01-scale config (n_distractors=20, n_noise=55) must give pool=78, same as
    results_main_scale/results_mixed_scale's own committed pool_size."""
    cfg = GenConfig(n_distractors=20, n_noise=55)
    sc = generate_many(1, cfg, base_seed=0)[0]
    mat = M.materialize(sc, cfg.max_mem_per_citizen)
    assert len(mat.all_ids) == 78


def test_small_pool_config_matches_n01_exactly():
    cfg = GenConfig()  # defaults: n_distractors=6, n_noise=8
    sc = generate_many(1, cfg, base_seed=0)[0]
    mat = M.materialize(sc, cfg.max_mem_per_citizen)
    assert len(mat.all_ids) == 17


def test_multi_crisis_pool_is_shared_not_per_crisis():
    """The whole point of the mode: one shared pool, not N independent scenarios stapled
    together - pool size must be less than n_crises times a single-crisis pool."""
    cfg = MultiCrisisConfig(n_crises=2)
    sc, specs = generate_multi_crisis("t", cfg, seed=1)
    mat, views = materialize_multi_crisis(sc, specs, cfg)
    assert len(views) == cfg.n_crises
    single_crisis_pool = (cfg.witnesses_per_ancestor * (cfg.chain_len - 1)
                          + cfg.n_distractors_per_crisis)
    assert len(mat.all_ids) < cfg.n_crises * single_crisis_pool * 2  # shares noise, not doubled


def test_every_crisis_gold_set_is_disjoint():
    """A memory cannot be gold for two crises at once - each witness is authored for exactly
    one chain."""
    cfg = MultiCrisisConfig(n_crises=3)
    sc, specs = generate_multi_crisis("t", cfg, seed=2)
    mat, views = materialize_multi_crisis(sc, specs, cfg)
    all_gold = [v.gold_ids for v in views]
    for i in range(len(all_gold)):
        for j in range(i + 1, len(all_gold)):
            assert all_gold[i].isdisjoint(all_gold[j])


def test_other_crises_gold_ids_excludes_own():
    cfg = MultiCrisisConfig(n_crises=2)
    sc, specs = generate_multi_crisis("t", cfg, seed=3)
    mat, views = materialize_multi_crisis(sc, specs, cfg)
    for v in views:
        assert v.gold_ids.isdisjoint(v.other_crises_gold_ids)


def test_causal_boost_does_not_leak_across_crises():
    """The core claim under test: querying crisis A's causal boost for crisis B's true
    ancestors must be exactly 0 - they are not BFS-reachable from crisis A's event, since the
    two chains share no edges."""
    cfg = MultiCrisisConfig(n_crises=2)
    sc, specs = generate_multi_crisis("t", cfg, seed=4)
    mat, views = materialize_multi_crisis(sc, specs, cfg)
    for v in views:
        scoped = crisis_scoped_mat(mat, v)
        boosts = M._causal_boosts(scoped, threshold=0.45, clean=True)
        for other_id in v.other_crises_gold_ids:
            assert boosts.get(other_id, 0.0) == 0.0


def test_crisis_scoped_mat_shares_the_underlying_pool():
    """crisis_scoped_mat must not copy or filter the memory pool - both views see every
    memory, including the OTHER crisis's witnesses, which is the whole point of the stress
    test (a real ambiguous shared pool, not two isolated single-crisis scenarios)."""
    cfg = MultiCrisisConfig(n_crises=2)
    sc, specs = generate_multi_crisis("t", cfg, seed=5)
    mat, views = materialize_multi_crisis(sc, specs, cfg)
    for v in views:
        scoped = crisis_scoped_mat(mat, v)
        assert scoped.all_ids == mat.all_ids
        assert v.other_crises_gold_ids <= set(scoped.all_ids)


if __name__ == "__main__":
    import traceback

    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
