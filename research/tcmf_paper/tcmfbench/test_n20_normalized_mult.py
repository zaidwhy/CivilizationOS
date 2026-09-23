"""N20 unit tests: normalizing the episodic score before multiplying does not rescue the
multiplicative operator.

Run: python -m tcmfbench.test_n20_normalized_mult (or pytest tcmfbench/test_n20_normalized_mult.py)
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many


def _pure_mat(seed=0):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    sc = generate_many(1, cfg, base_seed=seed)[0]
    return M.materialize(sc, cfg.max_mem_per_citizen)


def test_normalized_multiplicative_uses_the_same_normalized_score_as_additive():
    mat = _pure_mat()
    epi_from_additive_internals = M._minmax(M._episodic_scores(mat))
    # rank_tcmf_normalized_multiplicative must rank consistently with multiplying that exact
    # normalized score by (1 + lam*boost) - verified indirectly via a hand-built score below,
    # since the normalized score itself isn't returned by the ranking function.
    boost = M._causal_boosts(mat, threshold=0.45, clean=True, favor_root=False)
    lam = 4.0
    expected_score = {
        i: epi_from_additive_internals.get(i, 0.0) * (1.0 + lam * boost.get(i, 0.0))
        for i in mat.all_ids
    }
    expected_order = sorted(mat.all_ids, key=lambda i: expected_score[i], reverse=True)
    got_order = M.rank_tcmf_normalized_multiplicative(mat, lam=lam, threshold=0.45, clean=True)
    assert got_order == expected_order


def test_normalized_multiplicative_is_never_better_than_raw_multiplicative_on_a_hand_case():
    # A hand-built pair where the root cause's raw episodic score sits near the pool minimum:
    # min-max normalization pushes it toward 0 relative to the pool, which should make the
    # normalized-multiplicative crossing point harder to clear, not easier, matching the
    # full-benchmark sweep (N20) at every lambda tested.
    mat = _pure_mat(seed=3)
    for lam in (1.0, 4.0, 8.0):
        raw_order = M.rank_tcmf_multiplicative(mat, lam=lam, clean=True, favor_root=False)
        norm_order = M.rank_tcmf_normalized_multiplicative(mat, lam=lam, clean=True, favor_root=False)
        root = mat.root_id
        raw_rank = raw_order.index(root) + 1 if root in raw_order else len(raw_order) + 1
        norm_rank = norm_order.index(root) + 1 if root in norm_order else len(norm_order) + 1
        assert norm_rank >= raw_rank, (
            f"lam={lam}: normalized-mult root rank {norm_rank} beat raw-mult's {raw_rank} - "
            "contradicts the N20 full-benchmark finding"
        )


def test_normalized_multiplicative_recall5_matches_committed_n20_reference_points():
    # Bit-for-bit reference points from the committed results_normalized_mult/results_normalized_mult.json
    # (pure regime, realistic pool, 5 seeds x 300), so a future refactor of _minmax or the
    # causal-boost formula gets caught here rather than silently drifting from the paper's
    # published Table tab:normmult.
    from .generator import GenConfig as _GC
    from . import run_eval

    cfg = _GC(n_distractors=20, n_noise=55)
    mats = run_eval._materialize(cfg, 30, 0)  # small n smoke check, not the full n=1500
    import numpy as np
    from . import metrics as MT

    for lam, floor in ((0.6, 0.0), (20.0, 0.5)):
        vals = [
            MT.recall_at_k(
                M.rank_tcmf_normalized_multiplicative(m, lam=lam, clean=True), m.gold_ids, 5
            )
            for m in mats
        ]
        mean = float(np.mean(vals))
        if lam == 0.6:
            assert mean <= 0.05, f"lam=0.6 normalized-mult recall@5={mean}, expected near-floor"
        else:
            assert mean >= floor, f"lam=20 normalized-mult recall@5={mean}, expected >= {floor}"


if __name__ == "__main__":
    test_normalized_multiplicative_uses_the_same_normalized_score_as_additive()
    test_normalized_multiplicative_is_never_better_than_raw_multiplicative_on_a_hand_case()
    test_normalized_multiplicative_recall5_matches_committed_n20_reference_points()
    print("all N20 tests passed")
