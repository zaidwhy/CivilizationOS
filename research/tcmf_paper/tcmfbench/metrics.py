"""Ranking metrics for causal-ancestor retrieval."""
from __future__ import annotations

import math


def recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return float("nan")
    hit = sum(1 for i in ranked[:k] if i in gold)
    return hit / len(gold)


def rank_of(ranked: list[str], target: str | None) -> int | None:
    if target is None:
        return None
    for idx, i in enumerate(ranked):
        if i == target:
            return idx + 1
    return None


def reciprocal_rank(ranked: list[str], target: str | None) -> float:
    r = rank_of(ranked, target)
    return 1.0 / r if r else 0.0


def ndcg_at_k(ranked: list[str], gold: set[str], root: str | None, k: int) -> float:
    """Graded relevance: root cause = 2, other gold = 1, else 0."""
    def rel(i: str) -> int:
        if i == root:
            return 2
        return 1 if i in gold else 0

    dcg = sum(rel(i) / math.log2(idx + 2) for idx, i in enumerate(ranked[:k]))
    ideal = sorted((rel(i) for i in ranked), reverse=True)[:k]
    idcg = sum(r / math.log2(idx + 2) for idx, r in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def any_in_top_k(ranked: list[str], targets: set[str], k: int) -> float:
    """1.0 if ANY id in `targets` appears in the top-k of `ranked`, else 0.0; NaN if `targets`
    is empty (undefined, not zero - keeps it out of any mean via the same NaN-drop convention
    `recall_at_k` uses). Used for precision-side damage (N04): how often does a spurious causal
    edge promote a distractor into the top-k an agent would actually read?"""
    if not targets:
        return float("nan")
    return 1.0 if any(i in targets for i in ranked[:k]) else 0.0


def analytic_random_recall_at_k(pool_size: int, k: int) -> float:
    """Closed-form expected recall@k of a uniform-random ranking, independent of gold count.

    A uniform random permutation of ``pool_size`` items puts each item in the top-k with
    probability k/pool_size (for k <= pool_size). Gold hits in the top-k follow a
    Hypergeometric(pool_size, gold_size, k) distribution, whose mean is k*gold_size/pool_size,
    so E[recall@k] = E[hits]/gold_size = k/pool_size regardless of gold_size. This is the
    sanity check N01 uses to confirm the harness's `random` baseline is not silently capped
    to a smaller effective pool (e.g. by a per-citizen prune).
    """
    if pool_size <= 0:
        return float("nan")
    return min(1.0, k / pool_size)
