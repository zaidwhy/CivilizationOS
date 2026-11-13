"""Paired statistics. numpy only, seeded, so every interval in the report is reproducible."""
from __future__ import annotations

import math

import numpy as np

BOOTSTRAP_RESAMPLES = 5000
PERMUTATIONS = 10000


def mean_ci(values: np.ndarray, seed: int = 0) -> tuple[float, float, float]:
    """Mean with a percentile bootstrap 95% interval."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values)))
    means = values[idx].mean(axis=1)
    return float(values.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_diff(a: np.ndarray, b: np.ndarray, seed: int = 0) -> dict[str, float]:
    """Mean of a - b on paired scenarios: bootstrap interval and a sign-flip permutation p."""
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    mean, lo, hi = mean_ci(diff, seed)
    rng = np.random.default_rng(seed + 1)
    signs = rng.choice((-1.0, 1.0), size=(PERMUTATIONS, len(diff)))
    null = np.abs((signs * diff).mean(axis=1))
    p = float((np.sum(null >= abs(mean) - 1e-12) + 1) / (PERMUTATIONS + 1))
    return {"diff": mean, "lo": lo, "hi": hi, "p": p, "n": float(len(diff))}


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sided exact McNemar p for paired binary outcomes."""
    a, b = np.asarray(a).astype(bool), np.asarray(b).astype(bool)
    only_a, only_b = int(np.sum(a & ~b)), int(np.sum(~a & b))
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values, keyed like the input."""
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    adjusted, running = {}, 0.0
    for rank, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p))
        adjusted[key] = running
    return adjusted
