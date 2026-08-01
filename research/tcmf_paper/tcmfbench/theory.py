"""Formal analysis of the fusion operator.

The benchmark's empirical result is that additive fusion recovers the causal signal and
multiplicative fusion does not. This module proves *why*, and exposes the proof's predicates
as ordinary functions so that every claim in the paper's theory section is checkable against
the shipped ranking code rather than asserted. ``test_theory.py`` runs those checks, both on
hand-computed cases and on real generated scenarios.

Notation, matching ``methods.py``:

    e(i) > 0    raw episodic score (relevance + recency + importance). Strictly positive:
                relevance is clamped to >= 0 and recency is exp(-decay * age) > 0, so no
                memory ever scores exactly zero (see ``api/memory/stream.py`` retrieve()).
    ehat(i)     min-max normalised episodic score, in [0, 1] (``methods._minmax``).
    b(i)        causal boost, in [0, 1]; exactly 0 for any memory with no ancestor above
                the similarity threshold (``methods._causal_boosts``).

    s_mult(i; lam) = e(i) * (1 + lam * b(i))        -> ``rank_tcmf_multiplicative``
    s_add(i; lam)  = ehat(i) + lam * b(i)           -> ``rank_tcmf_additive``

The regime the paper is about: the root cause r is semantically *dissimilar* to the crisis
(e(r) small) while distractors d are semantically *similar* to it (e(d) large), and r is a
causal ancestor of the crisis while d is not (b(r) > b(d) = 0).
"""
from __future__ import annotations

import math

# --------------------------------------------------------------------------------------
# Proposition 1 - multiplicative fusion
#
#   s_mult(i) - s_mult(j) = e(i)(1 + lam b(i)) - e(j)(1 + lam b(j))
#                         = [e(i) - e(j)] + lam [e(i)b(i) - e(j)b(j)]
#
# The pairwise margin is AFFINE in lam, with intercept e(i) - e(j) and slope
# e(i)b(i) - e(j)b(j). Two consequences, and they are the whole proposition:
#
#   (a) The required lam is set by the EPISODIC scores, not by the causal evidence alone.
#       The crossing point is
#
#           lam* = [e(j) - e(i)] / [e(i)b(i) - e(j)b(j)]
#
#       whose denominator involves e. It therefore admits no bound in terms of the causal
#       margin b(i) - b(j): as e(i)b(i) approaches e(j)b(j) from above, lam* diverges. So a
#       single global lam cannot be correct across scenarios - each scenario's episodic
#       landscape moves the requirement.
#   (b) When e(i)b(i) <= e(j)b(j) the slope is non-positive and lam* is +infinity: no lam
#       promotes i over j at all. Promotion requires b(i)/b(j) > e(j)/e(i), and since b is
#       bounded by 1 this is unsatisfiable once the episodic ratio is large enough.
#
# NOTE (measured, not assumed): on this benchmark the (b) case is RARE - it occurs for about
# 1 of 200 root-cause/distractor pairs. The operative failure is (a), the unbounded and
# scenario-dependent requirement, not outright impossibility. The paper's claim is stated
# accordingly. See ``test_theory.py`` and THEORY.md for the measured spread.
# --------------------------------------------------------------------------------------


def mult_margin(e_i: float, b_i: float, e_j: float, b_j: float, lam: float) -> float:
    """s_mult(i) - s_mult(j) at a given lam. Positive means i outranks j."""
    return (e_i - e_j) + lam * (e_i * b_i - e_j * b_j)


def mult_winning_interval(e_i: float, b_i: float,
                          e_j: float, b_j: float) -> tuple[float, float] | None:
    """The set of lam >= 0 on which multiplicative fusion ranks i above j.

    Returns ``(lo, hi)`` bounding the open set ``{lam >= 0 : margin(lam) > 0}``, with ``hi``
    possibly ``math.inf``, or ``None`` when that set is empty. Because the margin is affine
    in lam this set is always a single interval - a lam sweep can flip any given pair at most
    once, which is Proposition 3 below.
    """
    intercept = e_i - e_j
    slope = e_i * b_i - e_j * b_j
    if slope > 0:
        # increasing margin: i wins from the crossing point onward
        lo = max(0.0, -intercept / slope) if intercept < 0 else 0.0
        return (lo, math.inf)
    if slope < 0:
        # decreasing margin: i can only win before the crossing point
        if intercept <= 0:
            return None
        return (0.0, -intercept / slope)
    # slope == 0: the margin is constant in lam, so lam is entirely irrelevant
    return (0.0, math.inf) if intercept > 0 else None


def mult_promotable(e_i: float, b_i: float, e_j: float, b_j: float) -> bool:
    """Proposition 1. Does ANY lam >= 0 rank i above j under multiplicative fusion?"""
    return mult_winning_interval(e_i, b_i, e_j, b_j) is not None


def mult_crossover_lambda(e_i: float, b_i: float, e_j: float, b_j: float) -> float | None:
    """The lam above which multiplicative fusion ranks i above j, or ``None`` if no such lam
    exists. At exactly this value the two scores tie; the inequality is strict above it.

    Only meaningful when i wins for arbitrarily large lam (a positive slope); returns
    ``None`` in the bounded-interval case, where a *larger* lam is the wrong direction.
    """
    iv = mult_winning_interval(e_i, b_i, e_j, b_j)
    if iv is None or iv[1] != math.inf:
        return None
    return iv[0]


def mult_limit_ranking(e: dict[str, float], b: dict[str, float],
                       ids: list[str]) -> list[str]:
    """Corollary 1.1 - the lam -> infinity ordering under multiplicative fusion.

    Sorting by the product e(i)*b(i), with e(i) breaking ties (memories that earn no causal
    boost all have product 0 and are ordered among themselves by episodic score alone, since
    their scores do not depend on lam at all). The episodic score is still present in the
    limit: that is precisely the failure, and it is why no lam recovers the causal ordering.

    Ties fall back to ``ids`` order, matching the stable ``sorted(..., reverse=True)`` that
    every ranker in ``methods.py`` uses.
    """
    return sorted(ids, key=lambda i: (e.get(i, 0.0) * b.get(i, 0.0), e.get(i, 0.0)),
                  reverse=True)


# --------------------------------------------------------------------------------------
# Proposition 2 - additive fusion
#
#   s_add(i) - s_add(j) = [ehat(i) - ehat(j)] + lam [b(i) - b(j)]
#
# Same affine form, but the slope is now the CAUSAL MARGIN ALONE. Whenever b(i) > b(j),
# every lam above (ehat(j) - ehat(i)) / (b(i) - b(j)) ranks i above j. And because ehat is
# min-max normalised into [0, 1], the numerator is at most 1, so
#
#       lam > 1 / (b(i) - b(j))
#
# suffices UNIFORMLY - independently of the episodic scores. That uniformity is the
# structural difference from Proposition 1, where the requirement scales with the episodic
# ratio and can therefore be unsatisfiable.
# --------------------------------------------------------------------------------------


def add_margin(ehat_i: float, b_i: float, ehat_j: float, b_j: float, lam: float) -> float:
    """s_add(i) - s_add(j) at a given lam. Positive means i outranks j."""
    return (ehat_i - ehat_j) + lam * (b_i - b_j)


def additive_sufficient_lambda(ehat_i: float, b_i: float,
                               ehat_j: float, b_j: float) -> float | None:
    """Proposition 2. The lam above which additive fusion ranks i above j, given these
    episodic scores. ``None`` when b(i) <= b(j): additive fusion will not promote a memory
    that has no causal advantage, which is the correct behaviour, not a limitation.
    """
    if b_i <= b_j:
        return None
    return max(0.0, (ehat_j - ehat_i) / (b_i - b_j))


def additive_uniform_lambda(b_i: float, b_j: float) -> float | None:
    """Corollary 2.1. A lam that ranks i above j for ANY episodic scores whatsoever, using
    only the causal margin. Valid because ehat lives in [0, 1], so the worst-case episodic
    deficit the causal term has to overcome is 1.

    This is the quantity with no multiplicative counterpart: Proposition 1 admits no
    episodic-independent bound, because there the required lam is unbounded as e(i)/e(j)
    goes to zero, and beyond a point no lam works at all.
    """
    if b_i <= b_j:
        return None
    return 1.0 / (b_i - b_j)


# --------------------------------------------------------------------------------------
# Proposition 3 - why a lam sweep cannot discover the fix
#
# Both margins are affine in lam, so each pair flips at most once and the ranking traced out
# as lam goes from 0 to infinity interpolates monotonically between two fixed endpoints:
#
#   multiplicative:  the e-ordering (lam = 0)  ->  the (e*b)-ordering (lam -> infinity)
#   additive:        the ehat-ordering (lam = 0) -> the b-ordering (lam -> infinity)
#
# The multiplicative sweep therefore CANNOT reach the causal ordering. Whatever the operator
# is going to do, it has already done by the time the crossover points are passed; if the
# root cause is unpromotable under Proposition 1, every lam in the sweep leaves it below the
# distractors. This is the formal content of the paper's observation that the low-lam
# ablation is flat, and it is what makes the operator choice a design failure rather than a
# tuning failure: a practitioner sweeping lam on the multiplicative form would never stumble
# onto the fix, because the fix is not in the sweep's range.
# --------------------------------------------------------------------------------------


def sweep_reaches_causal_ordering(e: dict[str, float], b: dict[str, float],
                                  ids: list[str]) -> bool:
    """Proposition 3, made checkable: does the multiplicative operator's lam -> infinity
    endpoint agree with the pure causal ordering? True only in the degenerate case where the
    episodic score is constant across candidates (then e factors out of e*b).
    """
    causal_order = sorted(ids, key=lambda i: b.get(i, 0.0), reverse=True)
    return mult_limit_ranking(e, b, ids) == causal_order


def mult_required_lambda(e: dict[str, float], b: dict[str, float],
                         target: str, competitors: set[str]) -> float:
    """The smallest lam that lifts ``target`` above EVERY competitor under multiplicative
    fusion; ``math.inf`` when even one competitor is unreachable. This is the quantity
    Proposition 1 says cannot be bounded by the causal margin.
    """
    worst = 0.0
    for j in competitors:
        if j == target:
            continue
        lam = mult_crossover_lambda(e.get(target, 0.0), b.get(target, 0.0),
                                    e.get(j, 0.0), b.get(j, 0.0))
        if lam is None:
            return math.inf
        worst = max(worst, lam)
    return worst


def additive_required_lambda(b: dict[str, float], target: str,
                             competitors: set[str]) -> float:
    """The uniform (episodic-independent) lam that lifts ``target`` above EVERY competitor
    under additive fusion; ``math.inf`` if some competitor's causal boost is at least the
    target's, which no fusion operator can repair because the defect is upstream in the
    boost function rather than in the fusion.

    Contrast with ``mult_required_lambda``: this value is a function of the causal boosts
    alone, so it is stable across scenarios whose episodic landscapes differ - which is what
    lets one global lam serve every scenario.
    """
    worst = 0.0
    for j in competitors:
        if j == target:
            continue
        lam = additive_uniform_lambda(b.get(target, 0.0), b.get(j, 0.0))
        if lam is None:
            return math.inf
        worst = max(worst, lam)
    return worst


def unpromotable_pairs(e: dict[str, float], b: dict[str, float],
                       target: str, competitors: set[str]) -> set[str]:
    """The competitors that multiplicative fusion can never rank below ``target``, for any
    lam >= 0. In the paper's regime, calling this with the root-cause memory and the
    distractor set returns the distractors that permanently outrank the root cause.
    """
    return {
        j for j in competitors
        if j != target and not mult_promotable(e.get(target, 0.0), b.get(target, 0.0),
                                               e.get(j, 0.0), b.get(j, 0.0))
    }
