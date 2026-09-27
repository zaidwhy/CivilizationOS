"""N21 unit tests: the shipped retriever's recall@5 loss comes from its deployed lambda=2.0 sitting
below the Corollary bound, not from favor-root depth weighting.

Run: python -m tcmfbench.test_n21_shipped_lambda (or pytest tcmfbench/test_n21_shipped_lambda.py)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import metrics as MT
from .generator import GenConfig, generate_many

RESULTS = Path(__file__).resolve().parents[1] / "results_shipped_lambda" / "results_shipped_lambda.json"


def _mats(n=20, seed=0):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    return [M.materialize(sc, cfg.max_mem_per_citizen) for sc in generate_many(n, cfg, base_seed=seed)]


def _mean_recall5_and_root_rank(lam, mats):
    r5, rr = [], []
    for mat in mats:
        order = asyncio.run(M.rank_tcmf(mat, lam=lam))
        r5.append(MT.recall_at_k(order, mat.gold_ids, 5))
        rr.append(MT.rank_of(order, mat.root_id) or len(order) + 1)
    return sum(r5) / len(r5), sum(rr) / len(rr)


def test_shipped_retriever_reaches_full_recall_at_lambda_4_keeping_root_first():
    r5, rr = _mean_recall5_and_root_rank(4.0, _mats())
    assert r5 == 1.0
    assert rr == 1.0


def test_shipped_retriever_loses_recall_at_deployed_lambda_2_but_keeps_root_first():
    r5, rr = _mean_recall5_and_root_rank(2.0, _mats())
    assert r5 < 1.0
    assert rr == 1.0


def test_reimplemented_scoring_matches_the_deployed_retriever_up_to_ties():
    # The fusion variants in this benchmark score memories with a reimplementation of the
    # deployed boost and fusion (methods._causal_boosts / _minmax / _episodic_scores). Configured
    # like the deployed class (weak-ancestor fallback on, favor-root, no prune), it must reproduce
    # the real TCMFRetriever's ranking: identical top-10, and never ordering a lower-scored memory
    # above a higher-scored one (only exactly tied scores may be broken differently).
    for lam in (2.0, 4.0):
        for mat in _mats(n=10):
            real = asyncio.run(M.rank_tcmf(mat, lam=lam))
            reimpl = M.rank_tcmf_ablation(mat, additive=True, clean=False, favor_root=True,
                                          prune_k=None, lam=lam, threshold=0.45)
            assert real[:10] == reimpl[:10]
            epi = M._minmax(M._episodic_scores(mat))
            b = M._causal_boosts(mat, 0.45, clean=False, favor_root=True)
            score = {i: epi[i] + lam * b[i] for i in mat.all_ids}
            assert all(score[a] >= score[c] - 1e-9 for a, c in zip(real, real[1:]))


def test_committed_results_match_the_paper():
    res = json.load(open(RESULTS))["results"]
    assert round(res["shipped_l2"]["recall@5"][0], 2) == 0.79
    assert round(res["shipped_l4"]["recall@5"][0], 2) == 1.00
    assert round(res["shipped_l4"]["root_rank"][0], 1) == 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
