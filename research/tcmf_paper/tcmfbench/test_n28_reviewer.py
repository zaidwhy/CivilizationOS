"""N28 tests: operator isolation under leakage, tuned-PPR scaling, tuned-weight domain check.

Run: python -m tcmfbench.test_n28_reviewer (or pytest tcmfbench/test_n28_reviewer.py)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import _bootstrap  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def _r():
    return json.load(open(ROOT / "results_reviewer_n28" / "results_reviewer_n28.json"))


def test_operator_gap_survives_with_normalization_held_fixed():
    a = _r()["A_leakage_isolation"]
    leaky = [k for k in a if not k.startswith(("spurious_p0.0", "realtext_tau0.6"))]
    assert len(leaky) == 12
    for k in leaky:
        v = a[k]
        best_mult = max(v["best_mult_norm"]["recall@5"], v["mult_norm_limit"],
                        v["best_mult_raw"]["recall@5"], v["mult_raw_limit"])
        assert v["add_norm_l4"] > best_mult, k


def test_no_gap_on_clean_signal():
    a = _r()["A_leakage_isolation"]
    for k in ("spurious_p0.0_prox", "spurious_p0.0_root"):
        v = a[k]
        assert abs(v["add_norm_l4"] - v["best_mult_raw"]["recall@5"]) < 0.005
        assert abs(v["add_norm_l4"] - v["best_mult_norm"]["recall@5"]) < 0.005


def test_scaling_margin_against_tuned_ppr():
    for pool, row in _r()["B_scale_tuned_ppr"].items():
        assert abs(row["graph_ppr_a0.95"] - 2 / 3) < 1e-9
        assert row["tcmf_add"] >= 0.98


def test_tuned_multiplication_ties_additive_in_all_eight_domains():
    c = _r()["C_domains_tuned_mult"]
    assert len(c) == 8
    for d, row in c.items():
        assert row["mult_l16"] >= row["add_l4"] - 1e-9, d
        assert row["mult_l0.6"] < 0.5, d


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
