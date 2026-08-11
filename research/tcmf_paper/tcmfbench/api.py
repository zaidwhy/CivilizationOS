"""TCMFBench public API (N17).

Everything else in this package is reachable only by editing a ``run_*.py`` script's own
hard-coded method dict. This module is the one stable surface: register a retriever as a plain
function and get the paper's own standard metric table back, on the paper's own tiers, with no
edits to any internal module.

Minimal usage:

    from tcmfbench.api import evaluate

    def my_retriever(mat):
        return sorted(mat.all_ids, key=lambda i: mat.mem[i]["importance"], reverse=True)

    table = evaluate(my_retriever, tier="pure", n=300)
    print(table["recall@5"])  # (mean, ci_lo, ci_hi)

See ``README.md``'s "Adding a method" section for the full walkthrough, including the mixed
and real-text tiers.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Union

from .generator import GenConfig
from .mixed import MixedConfig
from . import methods as M
from . import metrics as MT
from .stats import bootstrap_ci
from . import run_eval as _RE
from . import run_mixed as _RM

Materialized = M.Materialized
RetrieverFn = Callable[[Materialized], Union[list[str], Awaitable[list[str]]]]

TIERS = ("pure", "mixed")


async def _order(fn: RetrieverFn, mat: Materialized) -> list[str]:
    r = fn(mat)
    return await r if hasattr(r, "__await__") else r


def _score_pure(ranked: list[str], mat: Materialized) -> dict[str, float]:
    out = {f"recall@{k}": MT.recall_at_k(ranked, mat.gold_ids, k) for k in (1, 3, 5, 10)}
    out["root_mrr"] = MT.reciprocal_rank(ranked, mat.root_id)
    out["root_rank"] = MT.rank_of(ranked, mat.root_id) or (len(ranked) + 1)
    out["ndcg@10"] = MT.ndcg_at_k(ranked, mat.gold_ids, mat.root_id, 10)
    return out


def _score_mixed(ranked: list[str], mat: Materialized) -> dict[str, float]:
    out = _score_pure(ranked, mat)
    out["causal@5"] = MT.recall_at_k(ranked, mat.gold_causal, 5)
    out["semantic@5"] = MT.recall_at_k(ranked, mat.gold_semantic, 5)
    return out


def _agg(rows: list[dict[str, float]], seed: int = 0) -> dict[str, tuple[float, float, float]]:
    import numpy as np
    out = {}
    for k in rows[0]:
        vals = np.array([r[k] for r in rows], dtype=float)
        vals = vals[~np.isnan(vals)]
        out[k] = bootstrap_ci(vals, seed=seed) if len(vals) else (float("nan"),) * 3
    return out


async def _evaluate_async(retriever: RetrieverFn, tier: str, n: int, seed: int,
                          n_distractors: int | None, n_noise: int) -> dict:
    overrides = {"n_noise": n_noise}
    if n_distractors is not None:
        overrides["n_distractors"] = n_distractors

    if tier == "pure":
        mats = _RE._materialize(GenConfig(**overrides), n, seed)
        score_fn = _score_pure
    elif tier == "mixed":
        mats = _RM._mats(MixedConfig(**overrides), n, seed)
        score_fn = _score_mixed
    else:
        raise ValueError(f"unknown tier {tier!r}; choose from {TIERS}")

    rows = [score_fn(await _order(retriever, mat), mat) for mat in mats]
    return _agg(rows)


def evaluate(retriever: RetrieverFn, *, tier: str = "pure", n: int = 300, seed: int = 0,
            n_distractors: int | None = None, n_noise: int = 8) -> dict[str, tuple[float, float, float]]:
    """Run ``retriever`` on ``tier``'s standard protocol and return
    ``{metric: (mean, ci_lo, ci_hi)}`` - the exact shape every method's row takes in the paper's
    own tables (95% percentile bootstrap, seed 0 - N02).

    ``retriever`` takes one ``Materialized`` scenario (``mat.all_ids``, ``mat.mem[id]`` for
    per-memory fields, ``mat.scenario`` for the query, ``mat.graph`` for the causal graph if
    your method wants it - see any function in ``methods.py`` for the full attribute surface)
    and returns a ranked list of ids, or an awaitable of one. Sync and async retrievers both
    work.

    ``tier``: "pure" (single causal-gold regime, the paper's main comparison) or "mixed" (both
    causal- and semantic-gold, reports causal@5/semantic@5 too). Defaults match the paper's own
    Table tab:main / tab:mixed protocol exactly.
    """
    import asyncio
    return asyncio.run(_evaluate_async(retriever, tier, n, seed, n_distractors, n_noise))
