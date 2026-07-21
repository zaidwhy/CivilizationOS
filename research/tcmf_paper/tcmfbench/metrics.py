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
