"""Tests for the fusion-operator propositions in ``theory.py``.

Two halves, and the second is the one that matters:

  1. Hand-computed cases pinning each formula to an answer worked out on paper.
  2. Checks against the SHIPPED rankers on real generated scenarios - the propositions are
     only worth stating if the code they describe actually behaves that way.

Run: python -m tcmfbench.test_theory (or pytest tcmfbench/test_theory.py)
"""
from __future__ import annotations

import math

from . import _bootstrap  # noqa: F401
from . import methods as M
from . import theory as T
from .mixed import MixedConfig, generate_mixed

# Boost flags held identical for both operators wherever they are compared, so the operator
# is the only moving part - the same fixed-inputs design the benchmark itself uses.
BOOST_KW = dict(threshold=0.45, clean=True, favor_root=False)


def _real_scenario(seed: int = 7):
    """A realistic-pool mixed scenario (the N01 pool size), materialized."""
    cfg = MixedConfig(n_distractors=20, n_noise=55)
    return M.materialize(generate_mixed(f"theory-{seed}", cfg, seed=seed))


def _inputs(mat):
    """The exact episodic scores and causal boosts both operators consume."""
    e = M._episodic_scores(mat)
    b = M._causal_boosts(mat, **BOOST_KW)
    return e, b


# ------------------------------------------------------------------ hand-computed cases

def test_mult_unpromotable_hand_case():
    """e_r=0.5 b_r=1.0 vs e_d=2.0 b_d=0.4.
    intercept = 0.5 - 2.0 = -1.5 (< 0); slope = 0.5*1.0 - 2.0*0.4 = 0.5 - 0.8 = -0.3 (< 0).
    Both non-positive, so the margin only ever decreases from an already-losing start."""
    assert T.mult_winning_interval(0.5, 1.0, 2.0, 0.4) is None
    assert not T.mult_promotable(0.5, 1.0, 2.0, 0.4)
    assert T.mult_crossover_lambda(0.5, 1.0, 2.0, 0.4) is None
    # and directly: no lam anywhere on a wide grid makes the margin positive
    for lam in [0.0, 0.5, 1, 2, 4, 8, 16, 64, 256, 1e3, 1e6, 1e12]:
        assert T.mult_margin(0.5, 1.0, 2.0, 0.4, lam) < 0


def test_mult_promotable_hand_case_crossover_is_exact():
    """e_r=0.5 b_r=1.0 vs e_d=2.0 b_d=0.2.
    intercept = -1.5; slope = 0.5 - 0.4 = 0.1 (> 0) -> crossover at 1.5 / 0.1 = 15."""
    assert T.mult_promotable(0.5, 1.0, 2.0, 0.2)
    lam_star = T.mult_crossover_lambda(0.5, 1.0, 2.0, 0.2)
    # isclose, not ==: the slope 0.5*1.0 - 2.0*0.2 is 0.09999999999999998 in binary floating
    # point, so the exact quotient lands at 15.000000000000004.
    assert math.isclose(lam_star, 15.0)
    assert T.mult_winning_interval(0.5, 1.0, 2.0, 0.2)[1] == math.inf
    assert math.isclose(T.mult_margin(0.5, 1.0, 2.0, 0.2, lam_star), 0.0, abs_tol=1e-9)
    assert T.mult_margin(0.5, 1.0, 2.0, 0.2, lam_star - 0.1) < 0
    assert T.mult_margin(0.5, 1.0, 2.0, 0.2, lam_star + 0.1) > 0


def test_mult_winning_interval_is_bounded_when_slope_is_negative():
    """Leading at lam=0 but with a negative slope: a larger lam actively HURTS.
    e_i=2.0 b_i=0.1 vs e_j=1.0 b_j=0.5. intercept = 1.0; slope = 0.2 - 0.5 = -0.3.
    i wins for lam < 1.0/0.3 = 3.333..."""
    iv = T.mult_winning_interval(2.0, 0.1, 1.0, 0.5)
    assert iv is not None
    lo, hi = iv
    assert lo == 0.0
    assert math.isclose(hi, 1.0 / 0.3)
    assert T.mult_margin(2.0, 0.1, 1.0, 0.5, hi - 0.01) > 0
    assert T.mult_margin(2.0, 0.1, 1.0, 0.5, hi + 0.01) < 0
    # "crossover" is meaningless here - raising lam is the wrong direction
    assert T.mult_crossover_lambda(2.0, 0.1, 1.0, 0.5) is None


def test_mult_zero_slope_makes_lambda_irrelevant():
    """e_i*b_i == e_j*b_j: the margin is constant, so the sweep does literally nothing."""
    assert T.mult_winning_interval(1.0, 0.4, 2.0, 0.2) is None       # intercept -1 <= 0
    assert T.mult_winning_interval(2.0, 0.2, 1.0, 0.4) == (0.0, math.inf)  # intercept +1


def test_additive_sufficient_lambda_hand_case():
    """Worst case: root cause bottom of the episodic scale, distractor top.
    ehat_r=0.0 b_r=0.8 vs ehat_d=1.0 b_d=0.0 -> lam > 1.0 / 0.8 = 1.25."""
    lam_star = T.additive_sufficient_lambda(0.0, 0.8, 1.0, 0.0)
    assert lam_star == 1.25
    assert T.add_margin(0.0, 0.8, 1.0, 0.0, lam_star) == 0.0
    assert T.add_margin(0.0, 0.8, 1.0, 0.0, lam_star + 0.01) > 0
    assert T.add_margin(0.0, 0.8, 1.0, 0.0, lam_star - 0.01) < 0


def test_additive_needs_no_lambda_when_already_leading():
    """Causal advantage AND episodic advantage: any lam >= 0 works."""
    assert T.additive_sufficient_lambda(0.9, 0.8, 0.1, 0.0) == 0.0


def test_additive_declines_to_promote_without_causal_advantage():
    assert T.additive_sufficient_lambda(0.0, 0.3, 1.0, 0.3) is None   # equal boosts
    assert T.additive_sufficient_lambda(0.0, 0.1, 1.0, 0.9) is None   # worse boost
    assert T.additive_uniform_lambda(0.3, 0.3) is None


def test_uniform_lambda_dominates_every_episodic_configuration():
    """Corollary 2.1: the uniform bound must be >= the per-instance bound for every
    admissible pair of normalised episodic scores, since ehat is confined to [0, 1]."""
    b_i, b_j = 0.7, 0.2
    uniform = T.additive_uniform_lambda(b_i, b_j)
    assert math.isclose(uniform, 2.0)     # 0.7 - 0.2 is 0.49999999999999994 in binary float
    for ehat_i in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for ehat_j in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert T.additive_sufficient_lambda(ehat_i, b_i, ehat_j, b_j) <= uniform


def test_sweep_reaches_causal_ordering_only_when_episodic_is_flat():
    """Proposition 3's degenerate escape hatch: e must factor out of e*b."""
    ids = ["a", "b", "c"]
    b = {"a": 0.1, "b": 0.9, "c": 0.5}
    flat = {i: 1.0 for i in ids}
    assert T.sweep_reaches_causal_ordering(flat, b, ids)
    varied = {"a": 5.0, "b": 0.2, "c": 1.0}
    assert not T.sweep_reaches_causal_ordering(varied, b, ids)


# ------------------------------------------------- checks against the shipped rankers

def test_limit_ranking_matches_shipped_multiplicative_at_large_lambda():
    """Corollary 1.1 against the real code: the predicted lam -> infinity ordering must be
    exactly what ``rank_tcmf_multiplicative`` produces once lam is large."""
    mat = _real_scenario()
    e, b = _inputs(mat)
    predicted = T.mult_limit_ranking(e, b, mat.all_ids)
    actual = M.rank_tcmf_multiplicative(mat, lam=1e12, **BOOST_KW)
    assert predicted == actual


def test_lambda_zero_ranking_is_the_episodic_ordering():
    """The other endpoint of Proposition 3's interpolation."""
    mat = _real_scenario()
    e, _ = _inputs(mat)
    episodic_order = sorted(mat.all_ids, key=lambda i: e.get(i, 0.0), reverse=True)
    assert M.rank_tcmf_multiplicative(mat, lam=0.0, **BOOST_KW) == episodic_order


def test_unpromotable_predictions_hold_across_a_full_lambda_sweep():
    """Proposition 1(b) is a claim about EVERY lam, so sweep and check it.

    Seed 7 is the one seed in 1-10 that actually contains a permanently-ahead distractor (it
    out-boosts the root cause), which makes it the case worth pinning. For that distractor,
    the shipped multiplicative ranker must never once place the root cause above it.
    """
    mat = _real_scenario(7)
    e, b = _inputs(mat)
    root = mat.root_id
    assert root is not None
    stuck = T.unpromotable_pairs(e, b, root, M.distractor_ids(mat))
    assert stuck, "seed 7 is expected to contain the unpromotable case"

    for lam in [0.0, 0.1, 0.6, 1, 2, 4, 8, 16, 32, 64, 128, 1e3, 1e5, 1e9]:
        order = M.rank_tcmf_multiplicative(mat, lam=lam, **BOOST_KW)
        pos = {mid: r for r, mid in enumerate(order)}
        for d in stuck:
            assert pos[d] < pos[root], f"lam={lam} promoted the root cause above {d}"


def test_unpromotable_case_is_rare_and_is_a_boost_defect_not_a_fusion_defect():
    """Scope limit, measured rather than assumed. Outright impossibility is rare, and where
    it happens the distractor has out-boosted the root cause - a failure of the boost
    function (threshold and depth weighting), which no choice of fusion operator can fix.
    """
    total = stuck_total = 0
    for seed in range(1, 11):
        mat = _real_scenario(seed)
        e, b = _inputs(mat)
        root = mat.root_id
        dis = M.distractor_ids(mat)
        stuck = T.unpromotable_pairs(e, b, root, dis)
        total += len(dis)
        stuck_total += len(stuck)
        for d in stuck:
            assert b[d] >= b[root], "unpromotable without out-boosting: unexplained"
    assert total == 200
    assert stuck_total <= 2, f"impossibility got common ({stuck_total}/200) - reframe needed"


def test_additive_uniform_lambda_actually_promotes_the_root_cause():
    """Proposition 2 against the real code: the episodic-independent bound, computed only
    from causal margins, must genuinely lift the root cause above every zero-boost
    distractor in the shipped additive ranker."""
    mat = _real_scenario()
    e, b = _inputs(mat)
    root = mat.root_id
    zero_boost = {d for d in M.distractor_ids(mat) if b.get(d, 0.0) == 0.0}
    assert zero_boost, "no zero-boost distractor to test against"

    bounds = [T.additive_uniform_lambda(b[root], b[d]) for d in zero_boost]
    assert all(x is not None for x in bounds), "root cause earned no causal boost"
    lam = max(bounds) + 1e-6

    order = M.rank_tcmf_additive(mat, lam=lam, **BOOST_KW)
    pos = {mid: r for r, mid in enumerate(order)}
    for d in zero_boost:
        assert pos[root] < pos[d], f"lam={lam} left the root cause below {d}"


def test_multiplicative_requirement_is_unstable_across_scenarios():
    """The paper's core contrast, stated as a test. The lam multiplicative fusion needs
    swings widely from scenario to scenario (its crossing point depends on the episodic
    scores), while additive fusion's episodic-independent bound stays nearly constant. That
    spread is exactly why one global lam can serve additive fusion and cannot serve
    multiplicative fusion.
    """
    mult_needs, add_needs = [], []
    for seed in range(1, 11):
        mat = _real_scenario(seed)
        e, b = _inputs(mat)
        root = mat.root_id
        dis = M.distractor_ids(mat)
        mult_needs.append(T.mult_required_lambda(e, b, root, dis))
        add_needs.append(T.additive_required_lambda(b, root, dis))

    # Seed 7 is out of scope for BOTH operators: its out-boosting distractor is a boost-
    # function defect, so neither a multiplicative nor an additive lam can reach it. Drop it
    # from the comparison rather than counting it as evidence against multiplication.
    assert not math.isfinite(mult_needs[6]) and not math.isfinite(add_needs[6])
    finite_mult = [x for i, x in enumerate(mult_needs) if i != 6]
    finite_add = [x for i, x in enumerate(add_needs) if i != 6]
    assert all(math.isfinite(x) for x in finite_mult + finite_add)

    # The contrast, on the 9 scenarios where the fusion operator is the deciding factor.
    assert max(finite_mult) / min(finite_mult) > 2.5     # measured ~3x (3.11 to 9.26)
    assert max(finite_add) / min(finite_add) < 1.2       # measured ~10% (3.32 to 3.64)


def test_papers_lambda_of_4_exceeds_the_additive_sufficient_bound_on_every_seed():
    """The value the benchmark actually ships for ``tcmf_add`` is lam = 4. Proposition 2 says
    a lam above 1/(b(r) - b(d)) suffices; if the shipped value clears that bound on every
    seed then the tuned constant is explained by the theory rather than merely fitted, and
    the root cause provably outranks every distractor. Verified against the real ranker too.
    """
    for seed in range(1, 11):
        mat = _real_scenario(seed)
        e, b = _inputs(mat)
        root = mat.root_id
        dis = M.distractor_ids(mat)
        bound = T.additive_required_lambda(b, root, dis)
        if not math.isfinite(bound):
            continue                                     # seed 7: out-boosted, see above
        assert bound < 4.0, f"seed {seed}: bound {bound} not cleared by the shipped lam=4"

        order = M.rank_tcmf_additive(mat, lam=4.0, **BOOST_KW)
        pos = {mid: r for r, mid in enumerate(order)}
        for d in dis:
            assert pos[root] < pos[d], f"seed {seed}: lam=4 left the root below {d}"


def test_holds_across_several_seeds():
    """One scenario could be a fluke; the propositions are structural, so they must hold on
    every seed without exception."""
    for seed in [1, 2, 3, 4, 5]:
        mat = _real_scenario(seed)
        e, b = _inputs(mat)
        assert T.mult_limit_ranking(e, b, mat.all_ids) == \
            M.rank_tcmf_multiplicative(mat, lam=1e12, **BOOST_KW)
        root = mat.root_id
        for d in T.unpromotable_pairs(e, b, root, M.distractor_ids(mat)):
            for lam in [0.6, 4, 64, 1e6]:
                order = M.rank_tcmf_multiplicative(mat, lam=lam, **BOOST_KW)
                pos = {mid: r for r, mid in enumerate(order)}
                assert pos[d] < pos[root]


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [getattr(mod, n) for n in dir(mod) if n.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
