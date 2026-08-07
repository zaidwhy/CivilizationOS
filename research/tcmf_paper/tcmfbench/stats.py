"""Pure-numpy statistics: bootstrap confidence intervals and paired significance tests.

No scipy - not installed, and keeping the benchmark dependency-free is deliberate (see
NIGHT_QUEUE.md, N02). Every function here has a unit test against a hand-computed known
answer in ``test_stats.py``.
"""
from __future__ import annotations

import math

import numpy as np


def bootstrap_ci(values, statistic=np.mean, n_boot: int = 10000, alpha: float = 0.05,
                  seed: int = 0):
    """Percentile bootstrap CI for ``statistic`` over ``values`` (scenario-level resampling
    with replacement). Returns ``(point_estimate, lo, hi)``.

    ``statistic`` must accept an ``axis`` keyword (as ``np.mean`` does) so it can be applied
    to the whole (n_boot, n) resample matrix at once.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    point = float(statistic(values))
    if n == 1:
        return point, point, point
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_stats = statistic(values[idx], axis=1)
    lo = float(np.percentile(boot_stats, 100 * alpha / 2))
    hi = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    return point, lo, hi


_Z975 = 1.959963984540054  # standard normal 97.5th percentile - a fixed constant, not a
# scipy call: the two-sided 95% Wilson interval only ever needs this one z-value.


def wilson_ci(k: int, n: int, z: float = _Z975) -> tuple[float, float, float]:
    """Wilson score interval (Wilson, 1927) for a binomial proportion ``k`` successes out of
    ``n`` trials. Closed-form, no resampling needed - used where only the aggregate count is
    available (no per-trial array to bootstrap over), e.g. N11's Fig 6 reconstructs it from an
    already-committed ``mean`` and ``n``. Preferred over the naive Wald interval
    (``p +/- z*sqrt(p(1-p)/n)``) because Wald has poor coverage and can leave [0,1] entirely
    when ``p`` is near 0 or 1 - exactly the regime several decision_acc values sit in (e.g.
    0.97). Returns ``(p, lo, hi)``.
    """
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), ties get the mean of the ranks they would occupy - the same
    convention scipy.stats.rankdata uses and the one the Wilcoxon test requires."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=float)
    sorted_x = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    return ranks


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _exact_wilcoxon_counts(n: int) -> np.ndarray:
    """counts[w] = number of the 2**n equally-likely sign assignments over ranks {1..n} whose
    positive-signed ranks sum to w. Built by the standard subset-sum generating function
    product_{i=1}^{n} (1 + x**i), computed via DP (no scipy/no polynomial library needed)."""
    max_w = n * (n + 1) // 2
    counts = np.zeros(max_w + 1, dtype=np.float64)
    counts[0] = 1.0
    for i in range(1, n + 1):
        shifted = np.zeros_like(counts)
        shifted[i:] = counts[:max_w + 1 - i]
        counts = counts + shifted
    return counts


def wilcoxon_signed_rank(a, b) -> float:
    """Two-sided paired Wilcoxon signed-rank test p-value. Exact enumeration for small,
    tie-free samples (n <= 25); normal approximation with continuity correction and a
    tie-variance correction otherwise. Zero differences are dropped before ranking (the
    standard Wilcoxon treatment); if every difference is zero, returns 1.0 (no evidence of a
    difference is expressible)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    d = d[d != 0]
    n = len(d)
    if n == 0:
        return 1.0

    abs_d = np.abs(d)
    ranks = _rankdata(abs_d)
    signs = np.sign(d)
    w_pos = float(np.sum(ranks[signs > 0]))

    has_ties = len(np.unique(abs_d)) != n
    if n <= 25 and not has_ties:
        w_int = int(round(w_pos))
        counts = _exact_wilcoxon_counts(n)
        total = counts.sum()
        p_upper = counts[w_int:].sum() / total
        p_lower = counts[:w_int + 1].sum() / total
        p = 2 * min(p_upper, p_lower)
        return min(p, 1.0)

    mean_w = n * (n + 1) / 4.0
    _, tie_counts = np.unique(abs_d, return_counts=True)
    tie_correction = np.sum(tie_counts ** 3 - tie_counts) / 48.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0 - tie_correction
    if var_w <= 0:
        return 1.0
    if w_pos > mean_w:
        z = (w_pos - mean_w - 0.5) / math.sqrt(var_w)
    elif w_pos < mean_w:
        z = (w_pos - mean_w + 0.5) / math.sqrt(var_w)
    else:
        z = 0.0
    p = 2 * (1 - _norm_cdf(abs(z)))
    return min(p, 1.0)


def holm_bonferroni(pvalues) -> list[float]:
    """Holm step-down adjusted p-values (family-wise, less conservative than plain
    Bonferroni). Returns adjusted p-values in the same order as the input; a contrast is
    significant at level alpha iff its adjusted p-value is <= alpha."""
    pvalues = np.asarray(pvalues, dtype=float)
    n = len(pvalues)
    if n == 0:
        return []
    order = np.argsort(pvalues, kind="mergesort")
    adjusted = np.empty(n, dtype=float)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = min((n - rank) * pvalues[idx], 1.0)
        running_max = max(running_max, adj)
        adjusted[idx] = running_max
    return adjusted.tolist()
