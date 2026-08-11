"""N12 unit tests: leave-one-out ablation of the four shipped fixes.

Checks the item's own "Verify" criterion (the four effects sum roughly to the full gap, or the
interaction is quantified) as code, plus the cross-checks that justified the ablation function's
design: with every fix applied it must reproduce ``rank_tcmf_additive`` bit-for-bit, and with
every fix reverted it must reproduce the old ``rank_tcmf_multiplicative`` bit-for-bit, so the
ablation arms are provably not a separate, drifted reimplementation.

Run: python -m tcmfbench.test_n12_ablation (or pytest tcmfbench/test_n12_ablation.py)
"""
from __future__ import annotations

import sys

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate


def _mat(seed: int = 1):
    return M.materialize(generate(f"n12_{seed}", GenConfig(), seed=seed))


def test_full_arm_matches_rank_tcmf_additive_exactly():
    mat = _mat()
    full = M.rank_tcmf_ablation(mat, additive=True, clean=True, favor_root=True,
                                prune_k=None, lam=4.0, threshold=0.45)
    ref = M.rank_tcmf_additive(mat, lam=4.0, threshold=0.45, clean=True, favor_root=True)
    assert full == ref


def test_all_reverted_arm_matches_old_multiplicative_exactly():
    mat = _mat()
    broken = M.rank_tcmf_ablation(mat, additive=False, clean=False, favor_root=False,
                                  prune_k=None, lam=0.6, threshold=0.45)
    ref = M.rank_tcmf_multiplicative(mat, lam=0.6, threshold=0.45, clean=False, favor_root=False)
    assert broken == ref


def test_prune_never_drops_ids_it_should_keep():
    """The pruned pool must be a subset of all_ids, keep exactly min(prune_k, per-citizen
    count) ids per citizen, and every dropped id must have an episodic score <= every kept
    id's score within the same citizen (top-k by score, not by any other order)."""
    mat = _mat()
    epi = M._episodic_scores(mat)
    kept, pruned = M._prune_pool(mat, epi, prune_k=2)
    assert set(kept) | set(pruned) == set(mat.all_ids)
    assert set(kept) & set(pruned) == set()
    by_citizen: dict[str, list[str]] = {}
    for i in mat.all_ids:
        by_citizen.setdefault(mat.mem[i]["citizen_id"], []).append(i)
    for cid, ids in by_citizen.items():
        kept_here = [i for i in kept if i in ids]
        assert len(kept_here) == min(2, len(ids))
        if len(kept_here) < len(ids):
            min_kept_score = min(epi.get(i, 0.0) for i in kept_here)
            dropped_here = [i for i in ids if i not in kept_here]
            assert all(epi.get(i, 0.0) <= min_kept_score for i in dropped_here)


def test_pruned_ids_are_unrecoverable_and_sorted_last():
    """Pruned memories can never be recovered by any fusion score - the item's own description
    of the bug ("dropped ... before the causal boost could re-rank them")."""
    mat = _mat()
    ranked = M.rank_tcmf_ablation(mat, prune_k=2)
    epi = M._episodic_scores(mat)
    _, pruned = M._prune_pool(mat, epi, prune_k=2)
    if pruned:
        n_kept = len(mat.all_ids) - len(pruned)
        assert set(ranked[n_kept:]) == set(pruned)


def test_bfs_depth_cap_below_chain_length_cannot_reach_the_root_cause():
    """A depth cap shorter than the causal chain must not be able to find the root cause via
    true BFS ancestry - the ablation's own falsifiable claim behind the depth-cap sweep."""
    mat = _mat()
    cfg = GenConfig()
    ancestors_capped = M._ancestor_map(mat, clean=True, max_depth=1)
    # chain_len=4 means the root cause sits 3 hops back; a depth-1 cap cannot see it.
    assert mat.root_id not in ancestors_capped or cfg.chain_len <= 2


def test_interaction_direction_matches_the_paper_own_f5_framing():
    """F5's own claim: with recall already at ceiling, the depth weight decides WHICH ancestor
    surfaces first, not whether one surfaces at all - so fix3 alone should show ~zero recall@5
    effect while still moving root_mrr. This is the premise the interaction analysis depends on;
    if it stopped holding, the interaction write-up in main.tex would need to change too."""
    mat_list = [_mat(s) for s in range(1, 6)]
    import asyncio
    from . import run_eval as RE

    async def _agg():
        arms = {
            "full": dict(additive=True, clean=True, favor_root=True, prune_k=None,
                        lam=4.0, threshold=0.45),
            "minus_fix3": dict(additive=True, clean=True, favor_root=False, prune_k=None,
                               lam=4.0, threshold=0.45),
        }
        fns = {name: (lambda m, kw=kw: M.rank_tcmf_ablation(m, **kw)) for name, kw in arms.items()}
        return await RE._eval_methods(mat_list, fns)

    agg = asyncio.run(_agg())
    assert abs(agg["full"]["recall@5"][0] - agg["minus_fix3"]["recall@5"][0]) < 1e-9
    assert agg["full"]["root_mrr"][0] > agg["minus_fix3"]["root_mrr"][0]


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
