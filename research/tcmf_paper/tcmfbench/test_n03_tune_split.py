"""N03 unit tests: the tune/test seed split contract and the tie-break rule for hyperparameter
selection, plus a small end-to-end smoke test of the sweep-then-test pipeline. Run directly:

    python -m tcmfbench.test_n03_tune_split

(from ``research/tcmf_paper``, with the project venv on PATH) or via pytest. No scipy; pure
numpy/stdlib only, per the standing rules in NIGHT_QUEUE.md.
"""
from __future__ import annotations

import asyncio

from . import _bootstrap  # noqa: F401
from .run_tuned import (
    GRIDS, SWEEP_BUDGET, TEST_SEEDS, TUNE_SEEDS, select_best, run_regime, _pool_mats, _sweep,
)
from .generator import GenConfig


def test_tune_test_split_is_disjoint_and_covers_the_n01_seed_set() -> None:
    tune, test = set(TUNE_SEEDS), set(TEST_SEEDS)
    assert tune & test == set(), "tune and test seeds must be disjoint"
    assert tune | test == {0, 1, 2, 3, 4}, "must cover exactly N01/N02's 5-seed protocol"
    # "40% tune / 60% test" per the queue spec.
    assert len(tune) / (len(tune) + len(test)) == 0.4
    assert len(test) / (len(tune) + len(test)) == 0.6


def test_every_operator_gets_an_equal_sweep_budget() -> None:
    assert len(GRIDS) == 5  # tcmf_add, tcmf_mult, rrf, causal_only, graph_ppr
    for grid in GRIDS.values():
        assert len(grid) == SWEEP_BUDGET == 5


def test_select_best_picks_the_argmax() -> None:
    assert select_best({0.5: 0.10, 1.0: 0.40, 2.0: 0.35}) == 1.0


def test_select_best_ties_break_toward_the_smallest_candidate() -> None:
    # 1.0 and 2.0 tie at the best score 0.90 -> must pick the smaller, 1.0, not whichever the
    # dict happens to iterate last. This is the exact case a naive `max(scores, key=scores.get)`
    # gets wrong (Python's max keeps the FIRST max on ties, which is insertion-order dependent,
    # not value-dependent) - insertion order here is deliberately the losing order (2.0 first).
    scores = {0.5: 0.80, 2.0: 0.90, 1.0: 0.90}
    assert select_best(scores) == 1.0


def test_select_best_single_candidate() -> None:
    assert select_best({4.0: 0.5}) == 4.0


def test_pool_mats_pure_and_mixed_respect_the_seed_stride() -> None:
    """Tune and test pools must not silently collide (same contract N01's stride test checks,
    re-verified here for the specific TUNE_SEEDS/TEST_SEEDS this script uses)."""
    cfg = GenConfig()
    tune_mats = _pool_mats("pure", cfg, 5, TUNE_SEEDS)
    test_mats = _pool_mats("pure", cfg, 5, TEST_SEEDS)
    tune_keys = {tuple(round(x, 6) for x in m.scenario.query_embedding[:4]) for m in tune_mats}
    test_keys = {tuple(round(x, 6) for x in m.scenario.query_embedding[:4]) for m in test_mats}
    assert tune_keys.isdisjoint(test_keys)
    assert len(tune_mats) == 5 * len(TUNE_SEEDS)
    assert len(test_mats) == 5 * len(TEST_SEEDS)


def test_sweep_selects_a_value_from_each_grid() -> None:
    """Small end-to-end smoke test (n=5/seed, so 10 tune scenarios): the sweep must run to
    completion, without touching the test split, and land on a value that is actually in the
    corresponding grid."""
    cfg = GenConfig()
    mats_tune = _pool_mats("pure", cfg, 5, TUNE_SEEDS)
    selected, tune_scores = asyncio.run(_sweep(mats_tune))
    assert set(selected) == set(GRIDS)
    for op_key, v in selected.items():
        assert v in GRIDS[op_key]
        assert len(tune_scores[op_key]) == SWEEP_BUDGET


class _Args:
    regime = "pure"
    n = 5
    out = None
    n_distractors = 20
    n_noise = 55


def test_run_regime_pure_end_to_end_smoke(tmp_path=None) -> None:
    """Full pipeline (sweep on tune, evaluate on test, write output) at tiny scale, pure
    regime. Asserts it completes and produces a non-empty results file - not a check on the
    numbers themselves (those come from the real overnight run at n=300)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        args = _Args()
        args.out = d
        asyncio.run(run_regime("pure", args))
        from pathlib import Path
        assert (Path(d) / "RESULTS_TUNED.md").exists()
        assert (Path(d) / "results_tuned.json").exists()
        import json
        data = json.loads((Path(d) / "results_tuned.json").read_text(encoding="utf-8"))
        assert set(data["selected"]) == set(GRIDS)
        assert "tcmf_add" in data["test_main"]


def _run_all() -> None:
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
