"""N22 unit tests: the theory quantities measured on the pure regime at the realistic pool.

Run: python -m tcmfbench.test_n22_theory_pure (or pytest tcmfbench/test_n22_theory_pure.py)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import _bootstrap  # noqa: F401
from . import methods as M
from .generator import GenConfig, generate_many
from .run_theory_pure_n22 import analyse

RESULTS = Path(__file__).resolve().parents[1] / "results_theory_pure" / "results_theory_pure.json"


def _mats(n=15, seed=0):
    cfg = GenConfig(n_distractors=20, n_noise=55)
    return [M.materialize(sc, cfg.max_mem_per_citizen) for sc in generate_many(n, cfg, base_seed=seed)]


def test_normalization_never_raises_the_root_episodic_ratio():
    # F15's mechanism: min-max rescaling moves the root cause's ratio to the strongest non-gold
    # memory down, which by Proposition 1(c) raises the multiplicative requirement.
    for mat in _mats():
        r = analyse(mat)
        assert r["rho_norm"] <= r["rho_raw"] + 1e-12


def test_additive_bound_depends_only_on_the_root_boost_when_competitors_are_unboosted():
    for mat in _mats():
        r = analyse(mat)
        if r["max_nongold_boost"] == 0.0:
            assert math.isclose(r["add_required"], 1.0 / r["b_root"], rel_tol=1e-9)


def test_committed_summary_matches_the_paper():
    s = json.load(open(RESULTS))["summary"]
    assert s["n"] == 1500
    assert round(s["add_required_p50"], 2) == 3.50
    assert round(s["add_required_p99"], 2) == 3.77
    assert round(s["frac_lambda4_clears_add_bound"], 3) == 0.983
    assert round(s["mult_required_p50"], 2) == 5.97
    assert round(s["mult_required_p5"], 2) == 3.49
    assert round(s["mult_required_p95"], 2) == 9.26
    assert round(s["frac_lambda4_clears_mult_requirement"], 2) == 0.10
    assert round(s["rho_raw_mean"], 2) == 0.38 and round(s["rho_norm_mean"], 2) == 0.21
    assert round(s["frac_normmult_needs_more_than_mult"], 2) == 0.99


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
