"""N01: guard the two things a larger candidate pool could silently break.

1. The per-citizen materialize() split (`max_mem_per_citizen`) must not re-cap the
   enlarged pool - `n_citizens` scales with pool size, and every downstream retrieve()
   call passes a `k` far above any realistic pool, so no memory should be dropped before
   scoring. If this regresses, every recall number in the paper becomes an artifact of
   silent truncation rather than of the method.
2. The random-baseline recall@k should match the closed-form hypergeometric expectation
   k/pool, not just "look low" - this is the harness sanity check N01 asks for.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tcmfbench.generator import GenConfig, generate_many
from tcmfbench import methods as M
from tcmfbench.run_eval import _analytic_random_recall


def test_materialize_does_not_truncate_large_pool():
    cfg = GenConfig(n_distractors=20, n_noise=55)
    for sc in generate_many(10, cfg, base_seed=0):
        mat = M.materialize(sc, cfg.max_mem_per_citizen)
        pool = len(mat.all_ids)
        assert pool == cfg.n_distractors + cfg.n_noise + (cfg.chain_len - 1)
        epi = M._episodic_scores(mat)
        assert len(epi) == pool, (
            f"episodic scores truncated: {len(epi)} of {pool} memories scored"
        )


def test_materialize_does_not_truncate_small_pool():
    """Same invariant at the OLD default pool (~17), so a regression that only shows up
    at one scale cannot hide."""
    cfg = GenConfig()
    for sc in generate_many(10, cfg, base_seed=0):
        mat = M.materialize(sc, cfg.max_mem_per_citizen)
        pool = len(mat.all_ids)
        epi = M._episodic_scores(mat)
        assert len(epi) == pool


def test_analytic_random_recall_matches_known_hypergeometric_case():
    # 3 gold in a pool of 10: E[recall@1] = 1/10, E[recall@5] = 5/10, E[recall@10] = 1.0 (capped)
    out = _analytic_random_recall(gold_count=3, pool_size=10, ks=(1, 5, 10))
    assert abs(out["recall@1"] - 0.1) < 1e-9
    assert abs(out["recall@5"] - 0.5) < 1e-9
    assert abs(out["recall@10"] - 1.0) < 1e-9


def test_analytic_random_recall_matches_empirical_at_large_pool():
    """The measured `random` baseline over many scenarios should land close to the
    analytic k/pool expectation - this is the concrete number N01 asks the harness to
    reproduce (~0.12 at k=10, pool~80), not just 'looks about right'."""
    cfg = GenConfig(n_distractors=20, n_noise=55)
    scs = generate_many(200, cfg, base_seed=0)
    pool = (cfg.chain_len - 1) + cfg.n_distractors + cfg.n_noise
    gold = cfg.chain_len - 1
    analytic = _analytic_random_recall(gold, pool, (1, 5, 10))

    hits = {1: 0, 5: 0, 10: 0}
    for sc in scs:
        mat = M.materialize(sc, cfg.max_mem_per_citizen)
        ranked = M.rank_random(mat, seed=1234)
        for k in (1, 5, 10):
            hits[k] += sum(1 for i in ranked[:k] if i in mat.gold_ids)
    measured = {k: hits[k] / (len(scs) * gold) for k in (1, 5, 10)}

    for k in (1, 5, 10):
        assert abs(measured[k] - analytic[f"recall@{k}"]) < 0.03, (
            f"k={k}: measured {measured[k]:.3f} vs analytic {analytic[f'recall@{k}']:.3f}"
        )
